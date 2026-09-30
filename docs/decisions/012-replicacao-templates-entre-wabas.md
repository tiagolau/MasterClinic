# 012 — Replicação de Templates entre as WABAs da BM Master Clinic

**Data:** 2026-08-10
**Status:** aceito

## Contexto

O acervo de templates aprovados da Master Clinic vivia numa única WABA
(`306417967823808`, canal "Oficial Master Clinic"). As demais WABAs da BM
`476121126154261` estavam vazias, o que impedia disparo ativo pelos outros
números (Financeiro, Recepção, Gerência) sem recriar tudo à mão no painel.

O pedido original citava a WABA `1350953883747065` como origem, mas o
levantamento mostrou que ela tinha **zero** templates — o acervo real era o da
`306417967823808`. Origem corrigida antes de executar.

Duas particularidades da Graph API tornaram a cópia não-trivial:

1. O `GET /message_templates` devolve, para headers de mídia, uma **URL
   `scontent.whatsapp.net`** — e não o `header_handle` que o `POST` exige. Copiar
   o payload cru falha.
2. O template `masterclinic_confirmar` estava cadastrado na origem com
   `language: en`, apesar do corpo em português (a cópia pré-existente na
   `105152822451126` já era `pt_BR`).

## Decisão

Script [`scripts/replicar_templates_waba.py`](../../scripts/replicar_templates_waba.py),
idempotente e com `--dry-run`, que:

- lista os templates `APPROVED` da origem;
- para cada header de mídia, **baixa** o arquivo da URL `scontent` e **re-sobe**
  uma única vez pela Resumable Upload API (`POST /{app_id}/uploads` → `POST
  /{session_id}` com `file_offset: 0`). O handle é *app-scoped*, então um upload
  serve para todas as WABAs de destino;
- normaliza o idioma de `masterclinic_confirmar` para `pt_BR` (mapa
  `CORRIGE_IDIOMA`), em vez de propagar o `en` errado;
- pula pares `(nome, idioma)` já existentes no destino;
- grava log em `logs/replicacao_TIMESTAMP.json`.

Execução em duas etapas: piloto numa WABA (6 submissões) para validar permissão
e handles, depois as quatro restantes.

## Alternativas Consideradas

- **Copiar o payload do GET direto no POST**: falha nos headers de mídia — a URL
  `scontent` não é aceita como `header_handle`.
- **Reaproveitar o `header_handle` original**: não é exposto pela API de leitura.
- **Refazer no painel do WhatsApp Manager**: 29 submissões manuais, sem log e
  com risco de divergência de texto entre WABAs.
- **Replicar `masterclinic_confirmar` como `en`**: fidelidade à origem
  propagaria um erro de cadastro para 4 contas.

## Resultado

**17 templates criados** (todos `PENDING` de revisão da Meta), 1 já existia,
12 recusados. Estado final:

| WABA | Nome | Plataforma | Templates |
|---|---|---|---|
| `306417967823808` | Master Clinic Odontologia Especializada | CLOUD_API | 6 (origem) |
| `1350953883747065` | Master Clinic (Financeiro) | CLOUD_API | 6 ✅ |
| `616632296165144` | Financeiro - Recepção | CLOUD_API | 6 ✅ |
| `105152822451126` | Danielle Carvalho Master Clinic | CLOUD_API | 6 ✅ |
| `695879211426557` | Master clinic (Mesquita) | **ON_PREMISE** | 0 ❌ |
| `108400492289717` | Master Clinic Odontologia Especializada | **ON_PREMISE** | 0 ❌ |

Templates replicados: `utilidade_01`, `utilidade_02` (header VIDEO),
`utilidade_03` (header IMAGE), `masterclinic_retorno_periodico`,
`masterclinic_aniversariante` (MARKETING), `masterclinic_confirmar`.

### Bloqueio nas WABAs ON_PREMISE

As duas recusas retornam `code 100`, `error_subcode 2494160` — *"A conta do
WhatsApp Business não tem permissão para gerenciar modelos"*. A correlação é
exata com `platform_type: ON_PREMISE`: a restrição é **da WABA**, não do token
(as outras quatro, todas `CLOUD_API`, aceitaram com o mesmo System User).

A API On-Premises foi descontinuada pela Meta e não aceita mais gerenciamento de
templates. Para usar esses dois números com template é preciso **migrá-los para
a Cloud API** e então rodar o script apontando para a WABA de destino.

⚠️ Diagnóstico enganoso: a Meta valida **conteúdo antes de permissão**. Um POST
de teste com corpo inválido nessas WABAs retorna erro de conteúdo
(`error_subcode 2388293`), o que dá a falsa impressão de que a escrita está
liberada. Só um payload válido revela o `2494160`.

## Consequências

- Os três números Cloud API adicionais passam a poder abrir conversa ativa assim
  que a Meta aprovar (24h típicas). Conferir com
  `GET /{waba}/message_templates?fields=name,status`.
- O script é reutilizável para qualquer nova WABA da BM: `--destino <id>`.
- A instância **Mesquita** (`695879211426557`), que é o principal canal de CTWA,
  segue sem templates — migrar para Cloud API é pré-requisito para disparo ativo
  por ela.
- `media/handles/` guarda as mídias baixadas dos headers (cache local do script).
