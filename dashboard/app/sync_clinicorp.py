"""Sync de agendamentos do Clinicorp → clinicorp_agendamentos."""
import logging
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import clinicorp, config, db

log = logging.getLogger("painel.sync.clinicorp")


def _checkin_hhmm(v) -> str | None:
    """CheckinTime vem como epoch ms — converte para HH:MM local."""
    if not v:
        return None
    try:
        ts = float(v)
        dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, ZoneInfo(config.TZ))
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return str(v)[:8]


def _linha(a: dict) -> dict | None:
    ident = a.get("id") or a.get("AppointmentId")
    if not ident:
        return None
    fone = re.sub(r"\D", "", str(a.get("MobilePhone") or ""))
    return {
        "id": ident,
        "paciente": a.get("PatientName") or a.get("Name"),
        "paciente_id": a.get("Patient_PersonId"),
        "telefone": fone or None,
        "data": (a.get("date") or "")[:10] or None,
        "hora_ini": a.get("fromTime"),
        "hora_fim": a.get("toTime"),
        "procedimentos": a.get("Procedures"),
        "categoria": a.get("CategoryDescription"),
        "status_id": a.get("StatusId"),
        "checkin_em": _checkin_hhmm(a.get("CheckinTime")),
        "primeira_consulta": bool(a.get("FirstAppointment")),
        "clinica_id": a.get("Clinic_BusinessId"),
        "dentista_id": a.get("Dentist_PersonId"),
        "dados": {
            k: a.get(k)
            for k in ("Notes", "StatusColor", "CategoryColor", "Email", "CreateDate", "Deleted")
            if a.get(k) is not None
        },
    }


def _linha_pagamento(p: dict) -> dict | None:
    ident = p.get("id")
    if not ident:
        return None
    recebido_em = (p.get("ReceivedDate") or p.get("PaymentDate") or "")[:10] or None
    return {
        "id": ident,
        "paciente_id": p.get("PatientId"),
        "paciente": p.get("PatientName") or p.get("PayerName") or p.get("OwnerName"),
        "valor": p.get("Amount") or 0,
        "recebido_em": recebido_em,
        "pago_em": p.get("PaymentDate"),
        "forma": p.get("PaymentForm"),
        "tipo": p.get("Type"),
        "parcela": p.get("InstallmentNumber"),
        "parcelas": p.get("InstallmentsCount"),
        # 'X' = marcado; vazio/None = não
        "cancelado": bool(p.get("Canceled")),
        "recebido": p.get("PaymentReceived") == "X",
        "clinica_id": p.get("ReceiverBusinessId"),
        "dados": {
            k: p.get(k)
            for k in ("PaymentDescription", "CreditDebitCardFlag", "DueDate", "ExternalStatus")
            if p.get(k) is not None
        },
    }


def sync_pagamentos(dias: int | None = None):
    """Pagamentos recebidos na janela móvel (um único request cobre o range)."""
    if not (config.CLINICORP_USER and config.CLINICORP_TOKEN):
        return 0
    dias = dias or config.CLINICORP_PAGAMENTOS_DIAS
    ate = date.today()
    desde = ate - timedelta(days=dias)
    try:
        pags = clinicorp.pagamentos(desde.isoformat(), ate.isoformat())
    except Exception as e:
        log.warning("pagamentos %s→%s: %s", desde, ate, e)
        return 0
    linhas = [l for l in (_linha_pagamento(p) for p in pags) if l]
    db.upsert("clinicorp_pagamentos", linhas)
    log.info("clinicorp pagamentos: %d (%s → %s)", len(linhas), desde, ate)
    return len(linhas)


def sync_pacientes(limite: int | None = None):
    """Resolve o telefone dos pacientes que pagaram — é a chave que liga o
    faturamento à conversa do CRM (e daí ao anúncio de origem).

    Faz uma requisição por paciente, então roda em lotes: os pendentes de hoje
    entram no próximo ciclo. Aproveita o telefone já conhecido pela agenda.
    """
    if not (config.CLINICORP_USER and config.CLINICORP_TOKEN):
        return 0
    limite = limite or config.CLINICORP_PACIENTES_POR_CICLO

    # 1) de graça: pacientes que já aparecem na agenda com telefone
    db.ex(
        """INSERT INTO clinicorp_pacientes (id, nome, telefone)
           SELECT DISTINCT ON (a.paciente_id) a.paciente_id, a.paciente, a.telefone
           FROM clinicorp_agendamentos a
           WHERE a.paciente_id IS NOT NULL AND a.telefone IS NOT NULL
           ORDER BY a.paciente_id, a.data DESC
           ON CONFLICT (id) DO NOTHING"""
    )

    pendentes = db.q(
        """SELECT DISTINCT p.paciente_id
           FROM clinicorp_pagamentos p
           LEFT JOIN clinicorp_pacientes c ON c.id = p.paciente_id
           WHERE p.paciente_id IS NOT NULL AND c.id IS NULL
           LIMIT %s""",
        (limite,),
    )
    linhas = []
    for row in pendentes:
        try:
            pac = clinicorp.paciente(row["paciente_id"])
        except Exception as e:
            log.warning("paciente %s: %s", row["paciente_id"], e)
            continue
        if not pac:
            continue
        fone = re.sub(r"\D", "", str(pac.get("Phone") or pac.get("MobilePhone") or ""))
        linhas.append(
            {
                "id": pac.get("PatientId") or row["paciente_id"],
                "nome": pac.get("Name"),
                "telefone": fone or None,
                "email": pac.get("Email"),
                "nascimento": pac.get("BirthDate"),
                "dados": {k: pac.get(k) for k in ("Status", "OtherDocumentId") if pac.get(k)},
            }
        )
    if linhas:
        db.upsert("clinicorp_pacientes", linhas)
    log.info("clinicorp pacientes: +%d resolvidos (%d pendentes no lote)",
             len(linhas), len(pendentes))
    return len(linhas)


def sync_clinicorp():
    if not (config.CLINICORP_USER and config.CLINICORP_TOKEN):
        log.warning("credenciais Clinicorp ausentes — sync pulado")
        return
    hoje = date.today()
    total = 0
    for delta in range(-config.CLINICORP_DIAS_PASSADO, config.CLINICORP_DIAS_FUTURO + 1):
        dia = (hoje + timedelta(days=delta)).isoformat()
        try:
            ags = clinicorp.agendamentos(dia)
        except Exception as e:
            log.warning("agendamentos %s: %s", dia, e)
            continue
        linhas = [l for l in (_linha(a) for a in ags) if l]
        total += db.upsert("clinicorp_agendamentos", linhas)
    n_pag = sync_pagamentos()
    n_pac = sync_pacientes()
    db.estado_set(
        "ultimo_sync_clinicorp",
        {"em": hoje.isoformat(), "agendamentos": total, "pagamentos": n_pag, "pacientes": n_pac},
    )
    log.info("clinicorp: %d agendamentos (janela -%dd/+%dd)",
             total, config.CLINICORP_DIAS_PASSADO, config.CLINICORP_DIAS_FUTURO)
