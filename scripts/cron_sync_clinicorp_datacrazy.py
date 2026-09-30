#!/usr/bin/env python3
"""Sincronizador Inteligente Clinicorp -> DataCrazy (Fases 1, 2 e 3).

Executado a cada 10 minutos via cron no servidor VPS Tecminas.

Regra de negócios: o sync MOVE o negócio existente do lead em cada funil. Só cria
quando o lead não tem nenhum negócio naquele funil. Se a leitura falhar, não escreve
nada e reprocessa no próximo ciclo (ver ADR 014).

Fase 1: Agendamento de Entrada / 1ª Consulta
  - Cria o lead se não existir com tags 'Clinicorp' e 'Paciente Ativo'.
  - Se 1ª consulta (FirstAppointment == 'X'), cria/move negócio no Funil Principal para 'Avaliação Agendada'.
  - No Funil Agendamentos, cria/move para 'Agendado' (ou 'Confirmado' se PatientConfirm == 'X').
  - Se retorno / 2ª consulta, move para 'Agendamento 2ª Consulta e Follow-up'.

Fase 2: Presença (Check-in) e No-Show (Faltas)
  - Se CheckinTime preenchido (compareceu):
      * Funil Principal -> 'Avaliação Realizada'
      * Funil Agendamentos -> 'Concluído'
  - Se horário passou sem CheckinTime (faltou):
      * Funil Principal -> 'Follow-Up Humanizado'
      * Funil Agendamentos -> 'Falta'

Fase 3: Orçamentos e Pagamentos (Fechamento e Pós-Venda)
  - Orçamentos (/estimates/list):
      * Funil Principal -> 'Orçamento (2ª Consulta)' e atualiza total do negócio (R$).
  - Pagamentos (/payment/list):
      * Funil Principal -> 'Ganho'
      * Funil Acompanhamento (Mesquita ou Ipatinga) -> Cria card em 'Avaliação de Atendimento' (NPS).
"""
import base64
import fcntl
import json
import logging
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Diretórios e Arquivos
RAIZ = Path(__file__).resolve().parent.parent
CACHE_FILE = RAIZ / "data" / "synced_lifecycle_cache.json"

# Pipelines e Etapas no DataCrazy
PIPE_FUNIL_PRINCIPAL = "7c922803-5c98-4733-9f72-55189ac97916"
STAGE_FP_NOVOS_LEADS = "ab4a1b39-acfc-4b0e-b2e4-ea9d27379b4f"
STAGE_FP_ATEND_HUMANIZADO = "39978ffb-bb1d-4f44-bfaf-ec5e37a8399e"
STAGE_FP_AVAL_AGENDADA = "e9839ca5-ee06-4e0f-870a-e68ffbe9dced"
STAGE_FP_FOLLOWUP = "a7a9d4ca-0dd3-4c4d-bc6e-4ca0dd48787d"
STAGE_FP_AVAL_REALIZADA = "217e02d4-f976-484f-ade1-dada7c691e07"
STAGE_FP_SEGUNDA_CONSULTA = "64e5e4ee-070e-4f9a-9cdb-d8ca140f74f4"
STAGE_FP_ORCAMENTO = "1c0188a1-5b6d-4073-a55f-9111549a8390"
STAGE_FP_GANHO = "8c2aab90-0181-46a0-a7da-76c461ab03bf"

PIPE_AGENDAMENTOS = "d0d8b215-5340-4d4e-a5e9-485d726a267f"
STAGE_AG_SOLICITADO = "0d571296-0109-4496-8e66-0baa6984587e"
STAGE_AG_AGENDADO = "c7bc5ab9-ba2a-42a5-87a2-00dd3142524c"
STAGE_AG_CONFIRMADO = "1feb298d-2ffe-47ba-ab51-7b689164f0a5"
STAGE_AG_CONCLUIDO = "ad95f43b-13eb-4e0c-8597-7ab59de67aa1"
STAGE_AG_FALTA = "b1a06f1e-b465-46be-ae5e-6dd7d2648821"

PIPE_ACOMP_MESQUITA = "b08016d6-61a1-4341-bb90-181a432423d9"
STAGE_ACOMP_MESQUITA_AVAL = "11b4aafe-0df6-4be7-874e-fd7c494b556f"

PIPE_ACOMP_IPATINGA = "8c829b9e-3b13-4af8-9187-0d7b9569d42e"
STAGE_ACOMP_IPATINGA_AVAL = "4291c947-597b-422c-97ed-5191d7b0ee39"

TAG_CLINICORP = "ffbd0c5a-f63b-4c66-855a-99181c529a5f"
TAG_PACIENTE_ATIVO = "db602517-ba04-49fc-be48-30b1100aa7ba"
TAGS = f"{TAG_CLINICORP},{TAG_PACIENTE_ATIVO}"

MCP_URL = "https://mcp.g1.datacrazy.io/api/mcp"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
TZ = ZoneInfo("America/Sao_Paulo")


def carregar_env():
    for env_path in [
        RAIZ / ".env",
        Path("/opt/painel-mc/.env"),
        Path.home() / ".claude" / ".env",
        Path.home() / ".Codex" / ".env",
    ]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("\"'")
                if k and k not in os.environ:
                    os.environ[k] = v

carregar_env()

DC_TOKEN = os.environ.get("DATACRAZY_API_KEY_MASTERCLINIC") or os.environ.get("DATACRAZY_TOKEN")
CC_USER = os.environ.get("CLINICORP_API_USER")
CC_TOKEN = os.environ.get("CLINICORP_API_TOKEN")

if not (DC_TOKEN and CC_USER and CC_TOKEN):
    print("ERRO: Credenciais ausentes no .env!", file=sys.stderr)
    sys.exit(1)

CC_AUTH = "Basic " + base64.b64encode(f"{CC_USER}:{CC_TOKEN}".encode()).decode()


def norm_phone(p):
    if not p: return ""
    d = re.sub(r"\D", "", str(p))
    if d.startswith("0") and len(d) == 12:
        d = "55" + d[1:]
    elif d.startswith("55") and len(d) in (12, 13):
        pass
    elif len(d) in (10, 11):
        d = "55" + d
    return d


def clinicorp_get(caminho: str, params: dict = None) -> list | dict:
    url_params = {"subscriber_id": CC_USER, **(params or {})}
    query = "&".join(f"{k}={v}" for k, v in url_params.items())
    url = f"https://api.clinicorp.com/rest/v1/{caminho.lstrip('/')}?{query}"
    req = urllib.request.Request(url, headers={"Authorization": CC_AUTH, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Erro Clinicorp GET {caminho}: {e}", file=sys.stderr)
        return []


def datacrazy_mcp(tool_name: str, args: dict, tentativas: int = 4) -> dict:
    """Chama uma tool do MCP. Falha sempre volta como {"error": ...} — o chamador decide.

    O MCP não devolve 429: o rate limit vem como 201 com result.isError e
    "Too many requests" no corpo. Isso é retentado com backoff. Criações não são
    retentadas em timeout/5xx (a requisição pode ter sido aplicada) — o próximo
    ciclo lista os negócios de novo e encontra o que foi criado.
    """
    idempotente = not tool_name.endswith("_create")
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1000000,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": args},
    }
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {DC_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": UA,
            "Accept": "application/json",
        },
    )
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                res = json.loads(r.read().decode())
            if "error" in res:
                return {"error": res["error"]}
            result = res.get("result", {})
            text = (result.get("content") or [{}])[0].get("text", "")
            try:
                dados = json.loads(text) if text else {}
            except json.JSONDecodeError:
                dados = {"error": text[:200]}
            if result.get("isError") or (isinstance(dados, dict) and "error" in dados):
                erro = str(dados.get("error") if isinstance(dados, dict) else text)
                if "too many requests" in erro.lower() and i < tentativas - 1:
                    time.sleep(20 * (i + 1))
                    continue
                print(f"Erro MCP em {tool_name}: {erro[:200]}", file=sys.stderr)
                return {"error": erro}
            return dados
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tentativas - 1:
                time.sleep(65)
                continue
            if idempotente and e.code in (502, 503, 504, 520) and i < tentativas - 1:
                time.sleep(3 * (i + 1))
                continue
            print(f"Erro HTTP {e.code} em {tool_name}", file=sys.stderr)
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            if idempotente and i < tentativas - 1:
                time.sleep(3 * (i + 1))
                continue
            print(f"Exceção em {tool_name}: {e}", file=sys.stderr)
            return {"error": str(e)}
    return {"error": "tentativas esgotadas"}


def obter_ou_criar_lead(phone: str, name: str, pid: int = None) -> str | None:
    """Retorna o leadId existente ou cria um novo lead."""
    search_term = phone[-8:]
    res = datacrazy_mcp("lead_list", {"search": search_term})
    if "error" in res or "data" not in res:
        # Busca falhou: não dá para saber se o lead existe, então não cria.
        print(f"[PULADO] {name}: falha ao buscar lead — tenta no próximo ciclo", file=sys.stderr)
        return None
    leads = res["data"]
    for l in leads:
        lp = norm_phone(l.get("phone") or l.get("rawPhone"))
        if lp and (lp == phone or lp.endswith(search_term)):
            return l.get("id")

    # Não existe -> busca dados no Clinicorp e cria
    email = ""
    if pid:
        p_info = clinicorp_get("patient/get", {"PatientId": pid})
        if isinstance(p_info, list) and p_info: p_info = p_info[0]
        if isinstance(p_info, dict):
            em = (p_info.get("Email") or "").strip()
            if "@" in em and "." in em and not any(fake in em.lower() for fake in ["naotem", "teste@"]):
                email = em

    create_args = {
        "name": name or "Paciente Clinicorp",
        "phone": f"+{phone}",
        "tags": TAGS,
    }
    if email:
        create_args["email"] = email

    time.sleep(2.2)
    created = datacrazy_mcp("lead_create", create_args)
    lead_id = created.get("id")
    if lead_id:
        print(f"[NOVO LEAD] {name} (+{phone}) -> ID: {lead_id}")
    return lead_id


def obter_negocios_do_lead(lead_id: str) -> list[dict] | None:
    """Lista todos os negócios do lead. None = a listagem falhou (não é o mesmo que "sem negócios")."""
    res = datacrazy_mcp("lead_list_businesses", {"id": lead_id, "limit": 100})
    if "error" in res or "data" not in res:
        return None
    return res["data"]


def _pipeline_do_negocio(b: dict) -> str | None:
    # lead_list_businesses devolve pipelineId achatado; a REST aninha em stage.pipeline.
    st = b.get("stage") or {}
    return b.get("pipelineId") or st.get("pipelineId") or (st.get("pipeline") or {}).get("id")


def _etapa_do_negocio(b: dict) -> str | None:
    return b.get("stageId") or (b.get("stage") or {}).get("id")


def negocio_do_funil(negocios: list[dict], pipeline_id: str) -> tuple[bool, dict | None]:
    """(lead já tem negócio nesse funil?, negócio aberto a movimentar).

    Existindo qualquer negócio no funil, o sync nunca cria outro — só move o aberto.
    Com duplicados, escolhe o mais antigo (menor code) para convergir no card original.
    """
    do_funil = [b for b in negocios if _pipeline_do_negocio(b) == pipeline_id]
    abertos = sorted(
        (b for b in do_funil if b.get("status", "in_process") == "in_process"),
        key=lambda b: b.get("code") or 0,
    )
    return bool(do_funil), (abertos[0] if abertos else None)


def executar_sincronizacao():
    agora = datetime.now(TZ)
    hoje = agora.date()
    print(f"\n=======================================================")
    print(f"[{agora.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando Ciclo Completo (Fases 1, 2 e 3)...")
    print(f"=======================================================")

    # Carrega cache local
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    # ---------------------------------------------------------
    # 1. BUSCA DADOS NO CLINICORP (-3d a +7d)
    # ---------------------------------------------------------
    appts = []
    for delta in range(-3, 8):
        dia_str = (hoje + timedelta(days=delta)).isoformat()
        res = clinicorp_get("appointment/list", {"from": dia_str, "to": dia_str})
        if isinstance(res, list):
            appts.extend(res)

    print(f"Clinicorp: {len(appts)} agendamentos na janela (-3d a +7d)")

    # (lead_id, pipeline) criados neste ciclo — trava contra duplicar antes da listagem refletir
    criados_no_ciclo: set[tuple[str, str]] = set()

    # ---------------------------------------------------------
    # 2. PROCESSA FASES 1 & 2 (Agendamentos, Check-in, No-Show)
    # ---------------------------------------------------------
    for a in appts:
        pid = a.get("Patient_PersonId")
        phone = norm_phone(a.get("MobilePhone"))
        name = (a.get("PatientName") or a.get("Name") or "").strip().title()
        if not phone or len(phone) < 10 or not pid:
            continue

        appt_date_str = (a.get("date") or "")[:10]
        from_time = a.get("fromTime") or "00:00"
        to_time = a.get("toTime") or "23:59"
        is_first = bool(a.get("FirstAppointment"))
        is_confirmed = (a.get("PatientConfirm") == "X")
        has_checkin = (a.get("CheckinTime") is not None)

        # Checa se o horário já passou
        passou_horario = False
        try:
            fim_dt = datetime.strptime(f"{appt_date_str} {to_time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            passou_horario = (agora > (fim_dt + timedelta(minutes=45)))
        except Exception:
            passou_horario = (appt_date_str < hoje.isoformat())

        # Determina a etapa ideal no Funil Principal
        target_fp_stage = None
        if has_checkin:
            target_fp_stage = STAGE_FP_AVAL_REALIZADA
        elif passou_horario and not has_checkin:
            target_fp_stage = STAGE_FP_FOLLOWUP
        else: # Futuro ou em andamento
            target_fp_stage = STAGE_FP_AVAL_AGENDADA if is_first else STAGE_FP_SEGUNDA_CONSULTA

        # Determina a etapa ideal no Funil Agendamentos
        target_ag_stage = None
        if has_checkin:
            target_ag_stage = STAGE_AG_CONCLUIDO
        elif passou_horario and not has_checkin:
            target_ag_stage = STAGE_AG_FALTA
        elif is_confirmed:
            target_ag_stage = STAGE_AG_CONFIRMADO
        else:
            target_ag_stage = STAGE_AG_AGENDADO

        # Consulta chave de estado do agendamento no cache
        appt_key = f"{phone}_{appt_date_str}"
        estado_anterior = cache.get(appt_key, {})

        if (
            estado_anterior.get("fp_stage") == target_fp_stage
            and estado_anterior.get("ag_stage") == target_ag_stage
        ):
            continue  # Nada mudou neste agendamento

        # Resolve o lead no DataCrazy
        lead_id = estado_anterior.get("lead_id") or obter_ou_criar_lead(phone, name, pid)
        if not lead_id:
            continue

        time.sleep(1.0)
        negocios = obter_negocios_do_lead(lead_id)
        if negocios is None:
            print(f"[PULADO] {name}: falha ao listar negócios — nada criado, tenta no próximo ciclo", file=sys.stderr)
            continue

        ok = True
        for rotulo, pipe, alvo in (
            ("FP", PIPE_FUNIL_PRINCIPAL, target_fp_stage),
            ("AG", PIPE_AGENDAMENTOS, target_ag_stage),
        ):
            existe, biz = negocio_do_funil(negocios, pipe)
            if not existe and (lead_id, pipe) in criados_no_ciclo:
                # Outro agendamento do mesmo paciente acabou de criar e a listagem ainda
                # não refletiu. Não cria de novo; o próximo ciclo move para a etapa certa.
                ok = False
            elif not existe:
                # Lead sem nenhum negócio neste funil: único caso em que cria.
                time.sleep(2.0)
                res = datacrazy_mcp("business_create", {"leadId": lead_id, "stageId": alvo})
                ok = ok and "error" not in res
                if "error" not in res:
                    criados_no_ciclo.add((lead_id, pipe))
                print(f"[FASE 1 - {rotulo} CRIADO] {name} -> Etapa: {alvo}" + (" (FALHOU)" if "error" in res else ""))
            elif biz:
                atual = _etapa_do_negocio(biz)
                # Só move se a etapa mudar e o negócio não estiver já Ganho
                if atual != STAGE_FP_GANHO and atual != alvo:
                    time.sleep(2.0)
                    res = datacrazy_mcp("business_move_stage", {"id": biz["id"], "destinationStageId": alvo})
                    ok = ok and "error" not in res
                    print(f"[FASE 1/2 - {rotulo} MOVIDO] {name} (#{biz.get('code')}) -> De {atual} para {alvo}"
                          + (" (FALHOU)" if "error" in res else ""))
            # existe mas nenhum aberto (ganho/perdido): não reabre nem cria outro.

        if not ok:
            continue  # sem cache: o próximo ciclo reprocessa este agendamento

        # Atualiza cache
        cache[appt_key] = {
            "lead_id": lead_id,
            "fp_stage": target_fp_stage,
            "ag_stage": target_ag_stage,
            "updated_at": time.time(),
        }

    # ---------------------------------------------------------
    # 3. PROCESSA FASE 3 (Orçamentos & Pagamentos / Fechamento)
    # ---------------------------------------------------------
    sete_dias_atras = (hoje - timedelta(days=7)).isoformat()
    hoje_str = hoje.isoformat()

    # --- A. Orçamentos Emitidos ---
    estimates = clinicorp_get("estimates/list", {"from": sete_dias_atras, "to": hoje_str})
    if isinstance(estimates, list):
        for est in estimates:
            e_phone = norm_phone(est.get("PatientMobilePhone"))
            e_pid = est.get("PatientId")
            e_amount = float(est.get("Amount") or 0)
            e_name = (est.get("PatientName") or "").strip().title()
            if not e_phone or len(e_phone) < 10:
                continue

            est_key = f"est_{est.get('id')}"
            if cache.get(est_key):
                continue  # Orçamento já processado

            lead_id = obter_ou_criar_lead(e_phone, e_name, e_pid)
            if not lead_id:
                continue

            time.sleep(1.0)
            negocios = obter_negocios_do_lead(lead_id)
            if negocios is None:
                continue  # sem cache: tenta no próximo ciclo
            _, biz_fp = negocio_do_funil(negocios, PIPE_FUNIL_PRINCIPAL)
            if biz_fp:
                # Move para Orçamento (2ª Consulta) e atualiza valor
                time.sleep(2.0)
                datacrazy_mcp("business_move_stage", {"id": biz_fp["id"], "destinationStageId": STAGE_FP_ORCAMENTO})
                time.sleep(2.0)
                datacrazy_mcp("business_update_total", {"id": biz_fp["id"], "total": e_amount})
                print(f"[FASE 3 - ORÇAMENTO] {e_name} -> R$ {e_amount:.2f} movido para 'Orçamento (2ª Consulta)'")

            cache[est_key] = {"amount": e_amount, "time": time.time()}

    # --- B. Pagamentos Recebidos (Fechamento / Pós-Venda) ---
    payments = clinicorp_get("payment/list", {"from": sete_dias_atras, "to": hoje_str})
    if isinstance(payments, list):
        for pay in payments:
            if pay.get("PaymentReceived") != "X":
                continue  # Apenas pagamentos confirmados
            pay_id = pay.get("id")
            pay_key = f"pay_{pay_id}"
            if cache.get(pay_key):
                continue

            p_pid = pay.get("PatientId")
            p_name = (pay.get("PatientName") or pay.get("PayerName") or "").strip().title()
            p_amount = float(pay.get("Amount") or 0)
            if not p_pid:
                continue

            # Busca telefone do paciente na ficha
            p_info = clinicorp_get("patient/get", {"PatientId": p_pid})
            if isinstance(p_info, list) and p_info: p_info = p_info[0]
            p_phone = norm_phone(p_info.get("Phone") or p_info.get("MobilePhone")) if isinstance(p_info, dict) else ""
            if not p_phone or len(p_phone) < 10:
                continue

            lead_id = obter_ou_criar_lead(p_phone, p_name, p_pid)
            if not lead_id:
                continue

            time.sleep(1.0)
            negocios = obter_negocios_do_lead(lead_id)
            if negocios is None:
                continue  # sem cache: tenta no próximo ciclo

            # Pagamento NÃO marca ganho: a maioria é parcela de boleto de tratamento antigo
            # (ex.: 5/12) e marcaria como ganho o card atual do paciente. O gatilho de
            # ganho a definir é o orçamento com Status APPROVED (ver ADR 014).

            # Cria negócio no Funil de Acompanhamento (Pós-Venda)
            # Unidade: Mesquita se clinic_id/address indicar Mesquita, senão Ipatinga
            is_mesquita = "mesquita" in str(pay.get("PaymentDescription", "")).lower()
            pipe_acomp = PIPE_ACOMP_MESQUITA if is_mesquita else PIPE_ACOMP_IPATINGA
            stage_acomp = STAGE_ACOMP_MESQUITA_AVAL if is_mesquita else STAGE_ACOMP_IPATINGA_AVAL

            existe_acomp, _ = negocio_do_funil(negocios, pipe_acomp)
            if not existe_acomp and (lead_id, pipe_acomp) not in criados_no_ciclo:
                time.sleep(2.0)
                res = datacrazy_mcp("business_create", {"leadId": lead_id, "stageId": stage_acomp})
                if "error" in res:
                    continue  # sem cache: tenta no próximo ciclo
                criados_no_ciclo.add((lead_id, pipe_acomp))
                print(f"[FASE 3 - PÓS-VENDA] {p_name} -> Criado em 'Avaliação de Atendimento' no Acompanhamento!")

            cache[pay_key] = {"amount": p_amount, "time": time.time()}

    # Salva cache atualizado
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    print(f"[{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}] Ciclo Completo Concluído com Sucesso.")


if __name__ == "__main__":
    # Dois ciclos simultâneos (um atrasado por backoff + o próximo do cron) veriam
    # "sem negócio" ao mesmo tempo e criariam em dobro.
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    trava = open(CACHE_FILE.parent / "sync_clinicorp.lock", "w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"[{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}] Ciclo anterior ainda rodando — pulando.")
        sys.exit(0)
    executar_sincronizacao()
