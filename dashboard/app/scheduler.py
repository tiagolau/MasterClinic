"""Agendamento dos jobs (APScheduler) + bootstrap inicial."""
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import config, db, diagnostico, sync_clinicorp, sync_datacrazy, sync_meta

log = logging.getLogger("painel.scheduler")

scheduler = BackgroundScheduler(timezone=config.TZ)


def _protegido(fn, nome):
    def wrapper():
        try:
            fn()
        except Exception:
            log.exception("job %s falhou", nome)

    wrapper.__name__ = nome
    return wrapper


def _bootstrap():
    """Primeiro boot: carga completa se o banco estiver vazio."""
    try:
        sem_conversas = (db.q1("SELECT count(*) AS n FROM conversas") or {}).get("n", 0) == 0
        sem_pipelines = (db.q1("SELECT count(*) AS n FROM pipelines") or {}).get("n", 0) == 0
        if sem_conversas or sem_pipelines:
            log.info("carga inicial — rodando sync completo (pode demorar)")
            sync_datacrazy.sync_completo()
        meta_vazio = (db.q1("SELECT count(*) AS n FROM meta_insights") or {}).get("n", 0) == 0
        if meta_vazio and config.FB_ACCESS_TOKEN:
            log.info("backfill Meta 90 dias")
            sync_meta.sync_meta_historico(dias=90)
        cc_vazio = (db.q1("SELECT count(*) AS n FROM clinicorp_agendamentos") or {}).get("n", 0) == 0
        if cc_vazio and config.CLINICORP_USER and config.CLINICORP_TOKEN:
            log.info("carga inicial Clinicorp")
            sync_clinicorp.sync_clinicorp()
    except Exception:
        log.exception("bootstrap falhou")


def iniciar():
    scheduler.add_job(
        _protegido(sync_datacrazy.sync_incremental, "sync_incremental"),
        IntervalTrigger(minutes=config.SYNC_INTERVAL_MIN),
        id="sync_incremental",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _protegido(sync_datacrazy.sync_completo, "sync_completo"),
        IntervalTrigger(minutes=config.FULL_SYNC_INTERVAL_MIN),
        id="sync_completo",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _protegido(sync_meta.sync_meta, "sync_meta"),
        IntervalTrigger(minutes=config.META_SYNC_INTERVAL_MIN),
        id="sync_meta",
        max_instances=1,
        coalesce=True,
    )
    if config.CLINICORP_USER and config.CLINICORP_TOKEN:
        scheduler.add_job(
            _protegido(sync_clinicorp.sync_clinicorp, "sync_clinicorp"),
            IntervalTrigger(minutes=config.CLINICORP_SYNC_INTERVAL_MIN),
            id="sync_clinicorp",
            max_instances=1,
            coalesce=True,
        )
    scheduler.add_job(
        _protegido(diagnostico.rodar, "diagnostico"),
        CronTrigger(hour=config.DIAGNOSTICO_HORA, minute=30),
        id="diagnostico",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    threading.Thread(target=_bootstrap, daemon=True, name="bootstrap").start()
    log.info(
        "scheduler ativo: incremental %dmin, completo %dmin, meta %dmin, diagnóstico %02d:30",
        config.SYNC_INTERVAL_MIN,
        config.FULL_SYNC_INTERVAL_MIN,
        config.META_SYNC_INTERVAL_MIN,
        config.DIAGNOSTICO_HORA,
    )
