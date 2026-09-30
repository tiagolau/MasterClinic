"""Configuração via variáveis de ambiente (com defaults de produção)."""
import os


def _int(nome: str, padrao: int) -> int:
    try:
        return int(os.environ.get(nome, "") or padrao)
    except ValueError:
        return padrao


# --- Banco ---
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://painel:painel@localhost:5432/painel"
)

# --- DataCrazy ---
DATACRAZY_TOKEN = os.environ.get("DATACRAZY_API_KEY_MASTERCLINIC") or os.environ.get(
    "DATACRAZY_TOKEN", ""
)
DATACRAZY_BASE = os.environ.get("DATACRAZY_BASE", "https://api.g1.datacrazy.io/api/v1")
DATACRAZY_TENANT = os.environ.get(
    "DATACRAZY_TENANT", "69937b06-43cd-40d2-bd39-d3d3c9223283"
)

# --- Meta ---
FB_ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN", "")
# contas separadas por vírgula; a primeira é a de tráfego de pacientes
META_AD_ACCOUNTS = [
    a.strip()
    for a in os.environ.get(
        "META_AD_ACCOUNTS", "act_146238145960571,act_256216457271970"
    ).split(",")
    if a.strip()
]
META_API_VERSION = os.environ.get("META_API_VERSION", "v25.0")

# --- Clinicorp ---
CLINICORP_USER = os.environ.get("CLINICORP_API_USER", "")
CLINICORP_TOKEN = os.environ.get("CLINICORP_API_TOKEN", "")
CLINICORP_SYNC_INTERVAL_MIN = _int("CLINICORP_SYNC_INTERVAL_MIN", 30)
CLINICORP_DIAS_PASSADO = _int("CLINICORP_DIAS_PASSADO", 7)
CLINICORP_DIAS_FUTURO = _int("CLINICORP_DIAS_FUTURO", 14)
# pagamentos: janela móvel re-sincronizada a cada ciclo (1 request cobre o range)
CLINICORP_PAGAMENTOS_DIAS = _int("CLINICORP_PAGAMENTOS_DIAS", 120)
# patient/get é 1 request por paciente — resolve em lotes, converge em alguns ciclos
CLINICORP_PACIENTES_POR_CICLO = _int("CLINICORP_PACIENTES_POR_CICLO", 120)

# --- IA (diagnóstico diário) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# anthropic | gemini | auto (usa anthropic se houver chave, senão gemini)
AI_PROVIDER = os.environ.get("AI_PROVIDER", "auto")
AI_MODEL_ANTHROPIC = os.environ.get("AI_MODEL_ANTHROPIC", "claude-sonnet-5")
# aceita lista separada por vírgula — tenta na ordem (fallback p/ 404/503 de preview)
AI_MODEL_GEMINI = os.environ.get(
    "AI_MODEL_GEMINI", "gemini-2.5-pro,gemini-3-pro-preview,gemini-3-flash-preview"
)

# --- uazapi (resumo diário no WhatsApp) ---
UAZAPI_URL = os.environ.get("UAZAPI_URL", "https://masterclinic.uazapi.com")
UAZAPI_TOKEN = os.environ.get("UAZAPI_TOKEN", "")  # token da instância que envia
# números destino separados por vírgula, formato 5531999999999
DIGEST_PHONES = [
    p.strip() for p in os.environ.get("DIGEST_PHONES", "").split(",") if p.strip()
]

# --- App / segurança ---
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")  # assina o cookie de sessão
INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "")  # protege POST /ingest/ctwa
TZ = os.environ.get("TZ", "America/Sao_Paulo")

# --- Agendamento ---
SYNC_INTERVAL_MIN = _int("SYNC_INTERVAL_MIN", 5)        # sync incremental DataCrazy
FULL_SYNC_INTERVAL_MIN = _int("FULL_SYNC_INTERVAL_MIN", 60)  # sweep completo
META_SYNC_INTERVAL_MIN = _int("META_SYNC_INTERVAL_MIN", 60)
META_SYNC_DIAS = _int("META_SYNC_DIAS", 3)              # rejanela de insights por sync
DIAGNOSTICO_HORA = _int("DIAGNOSTICO_HORA", 20)         # hora local do job diário
DIAGNOSTICO_MAX_CONVERSAS = _int("DIAGNOSTICO_MAX_CONVERSAS", 40)
DIAGNOSTICO_MAX_CHARS_CONVERSA = _int("DIAGNOSTICO_MAX_CHARS_CONVERSA", 3500)

# links para o painel do CRM (usados no dashboard e no digest)
CRM_URL = os.environ.get("CRM_URL", "https://crm.datacrazy.io")


def validar():
    """Falhas de configuração que impedem o boot em produção."""
    faltando = []
    if not DATACRAZY_TOKEN:
        faltando.append("DATACRAZY_API_KEY_MASTERCLINIC")
    if not DASHBOARD_PASSWORD:
        faltando.append("DASHBOARD_PASSWORD")
    if not SECRET_KEY:
        faltando.append("SECRET_KEY")
    return faltando
