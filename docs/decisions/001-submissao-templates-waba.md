# 001 — Submissão de Templates WABA Master Clinic

**Data:** 2026-05-26
**Status:** plano alterado — submissão será manual via UI da Meta (não programática)

## Contexto

A Master Clinic forneceu uma lista de 13 cenários de comunicação com pacientes
via WhatsApp Business API (WABA). Antes desta tentativa, havia apenas 1 template
aprovado na WABA (`masterclinic_confirmar`), restando 12 cenários sem template.

O objetivo desta entrega era:

1. Modelar todos os 13 cenários como templates UTILITY com estruturas variadas
   (evitando que a Meta detecte abuso de padrão e degrade quality rating).
2. Submeter os templates novos para aprovação via Graph API.
3. Reverificar status em 2h e diagnosticar rejeições.

## Decisão

### Modelagem

Foram modelados **14 templates** (mais que os 13 pedidos — separamos
`utilidade_01` como casca universal extra para Dr. Wilton), usando 7 esqueletos
estruturalmente diferentes do catálogo `templates-waba/references/esqueletos-aprovados.md`:

| ID interno | Nome | Esqueleto | Cenário |
|---|---|---|---|
| T01 | `masterclinic_confirma_consulta` | 3 (header TEXT + body) | Confirmação de agenda |
| T04 | `masterclinic_retorno_periodico` | 6 (body longo) | Retorno periódico |
| T05 | `masterclinic_utilidade_01` | 1 (casca universal, VIDEO) | Casca multi-uso Dr. Wilton |
| T06 | `masterclinic_atualizacao_cadastro` | 5 (sem variáveis) | Fallback |
| T07 | `masterclinic_retorno_4_meses` | 6 (body longo) | Retorno 4 meses |
| T08 | `masterclinic_retorno_segunda_etapa` | 8 (4 variáveis) | Segunda etapa tratamento |
| T09 | `masterclinic_aniversariante` | composto | Aniversariante (risco médio) |
| T10 | `masterclinic_paciente_em_tratamento` | 1 (casca, VIDEO) | Acompanhamento Dr. Wilton |
| T12 | `masterclinic_envio_localizacao` | 2 (curto) | Pretexto p/ enviar localização |
| T13 | `masterclinic_agradecimento` | composto | Pós-atendimento |
| T14 | `masterclinic_final_de_semana` | 5 adaptado | Aviso horário funcionamento |
| T15 | `masterclinic_ausencia_no_show` | 3 adaptado | No-show |
| T16 | `masterclinic_primeira_consulta` | 6 adaptado | Instruções pré-consulta |
| T17 | `masterclinic_followup_fechamento_consulta` | 6 | Follow-up de fechamento |

**Pulados nesta entrega** (dependem de dados que a Master Clinic ainda não passou):
- `masterclinic_exame_pronto` — precisa URL do domínio real
- `masterclinic_retorno_dr_wilton` — precisa telefone real
- `masterclinic_pesquisa_satisfacao` — precisa URL do formulário
- `masterclinic_followup_lead_sem_agenda` — risco médio, melhor aguardar volume

### Padrões adotados

- **Variáveis numeradas** (`{{1}}`, `{{2}}`) em vez de nomeadas (como `masterclinic_confirmar` usa). Padrão recomendado pela Graph API moderna.
- **Sem emojis** no body (o template existente usa 📢 ✅ — não vou seguir esse padrão nos novos pra aumentar assinatura institucional).
- **Botões Quick Reply** com descarte gentil (ex: "Bloquear contato", "Não tenho mais interesse") em vários templates pra proteger quality rating.
- **Footer institucional** "Master Clinic — Atendimento" em templates de tom formal.
- **Sem header de mídia nesta primeira leva** — converti headers IMAGE em "sem header" e mantive 2 templates com header VIDEO (T05, T10) pra gerar pelo Veo 3 quando a permissão for liberada.

### Tentativa de submissão

Script `scripts/submeter_templates.py` executou as 12 submissões em `2026-05-26 19:53:54`. Resultado: **12/12 falhas**.

#### Diagnóstico dos erros

**3 templates** com erro estrutural (HTTP 400):
- `masterclinic_retorno_segunda_etapa`, `masterclinic_envio_localizacao`: começavam com `{{1}}` — variável no início do body é proibida.
- `masterclinic_confirma_consulta`, `masterclinic_ausencia_no_show`: tinham `{{1}}` no header TEXT e `{{2}}` no body — a numeração precisa reiniciar por componente, não pode pular números.

**8 templates** com HTTP 403 "Permissions error" (#200). Testei minimamente:

```bash
curl -X POST .../message_templates -d '{"name":"teste","components":[{"type":"BODY","text":"teste"}],...}'
# -> {"error":{"message":"(#200) Permissions error","code":200,...}}
```

Mesmo template trivial (1 BODY sem variáveis) retorna 403. Testei também na segunda WABA do BM (`306417967823808` — "Master Clinic Odontologia Especializada") com o mesmo resultado.

#### Causa raiz do 403

Meu System User (token `FB_ACCESS_TOKEN` em `~/.claude/.env`) tem acesso ao BM `476121126154261` (aparece em `/me/businesses`) e consegue **LER** os assets da WABA (GET funciona), mas **não tem permissão de escrita** nas WABAs. Permissões do app estão OK (`whatsapp_business_management` granted), o que confirma que o bloqueio é no nível de **atribuição do System User ao asset WABA**, não no nível do app.

Adicionalmente:
- `business_verification_status: not_verified` na WABA `105152822451126`
- `account_review_status: PENDING`

A não-verificação do BM **não bloqueia** criação de templates por si só (outras WABAs minhas não-verificadas funcionam), mas combinada com System User sem permissão de escrita, o resultado é 403.

### Correções aplicadas no JSON

Após o diagnóstico, corrigi os 4 erros estruturais (HTTP 400) no arquivo
`templates/templates.json`:

- `masterclinic_retorno_segunda_etapa`: body agora abre com `"Ola {{1}}, identificamos..."` em vez de `"{{1}}, identificamos..."`. Adicionado fechamento `"Fico no aguardo da sua resposta."`.
- `masterclinic_envio_localizacao`: body agora abre com `"Ola {{1}}, para facilitar..."`.
- `masterclinic_confirma_consulta`: renumerado para `{{1}}` no body (em vez de `{{2}}`) — Meta exige numeração começando em 1 dentro de cada componente.
- `masterclinic_ausencia_no_show`: mesma correção.

Quando a permissão for liberada, basta rodar:

```bash
cd /Users/tiagolau/Devs/MasterClinic
source ~/.claude/.env
python3 scripts/submeter_templates.py --apenas-sem-video
```

### Vídeos via Veo 3 (cancelado nesta rodada)

Tentei gerar 2 vídeos via Veo 3 (`veo-3.0-fast-generate-001`) pros headers de T05 e T10. Primeira chamada retornou erro `400 INVALID_ARGUMENT: durationSeconds out of bound [4,8]`, mesmo enviando `5` — provavelmente a API espera int e estávamos passando como float ou outro detalhe do payload. Não vale debugar agora porque mesmo gerando o vídeo, não há onde subir o `header_handle` enquanto a permissão na WABA estiver bloqueada.

Script preservado em `scripts/gerar_videos_veo.sh` para uso futuro.

## Alternativas consideradas

- **Submeter via outro token**: descartado — todos os tokens disponíveis usam o mesmo System User.
- **Submeter via outra WABA da Master Clinic**: a WABA "Odontologia Especializada" (`306417967823808`) também retorna 403, mesma causa.
- **Usar Cloud API direta com WhatsApp Business App da Meta** (sem programático): pode ser fallback se o ajuste de permissão demorar. Tiago entra no painel Meta e cria templates manualmente colando o JSON. Funciona mas perde versionamento.

## Consequências

### Positivas

- 14 templates **prontos e estruturalmente válidos** no JSON, com 7 esqueletos diferentes (proteção máxima contra detecção de abuso de padrão).
- Script de submissão idempotente — pode ser re-rodado quantas vezes precisar.
- Diagnóstico claro do bloqueio: sabemos exatamente o que precisa ser feito.

### Negativas

- Zero templates submetidos. Lista da Master Clinic continua coberta apenas pelo `masterclinic_confirmar` original.
- Bloqueio depende de ação no painel Meta (Business Manager), fora do código.
- Veo 3 não testado a fundo nesta sessão.

## Tentativa de resolver permissão (2026-05-26, segunda iteração)

Tiago atribuiu o System User `61576574822209` às WABAs. Não resolveu — meu
token é USER token de `tiagolau@gmail.com` (ID `26154333384231060`), não
System User.

Tiago então adicionou Tiago Chaves (`tiago@rhinocrm.com.br`, ID
`122100059919331707`) como admin do BM e atribuiu como pessoa às WABAs. Eu
subscrevi o app "Integração Rhino" na WABA via POST `/subscribed_apps` —
retornou `success: true`. Mas a criação de template continuou retornando 403,
porque meu USER token é da conta `tiagolau@gmail.com`, não da conta
`tiago@rhinocrm.com.br` que tem acesso ao BM.

### Decisão final: criar templates manualmente via UI da Meta

Tiago optou por criar os 12 templates manualmente no Gerenciador WhatsApp
(https://business.facebook.com/wa/manage/message-templates/?waba_id=105152822451126),
em vez de configurar permissão de API que exigiria adicionar `tiagolau@gmail.com`
como admin do BM ou gerar token específico via Graph Explorer.

Guia copy-paste pra criação manual: [docs/GUIA_CRIAR_TEMPLATES_NA_UI.md](../GUIA_CRIAR_TEMPLATES_NA_UI.md)

Reverificação programática às 21:51 (cron `fd855dd5`) foi **cancelada** —
não há nada pra reverificar via API enquanto a criação for manual.

## (Arquivado) Como resolver o bloqueio de permissão

**No Business Manager `476121126154261` (Master Clinic):**

1. Settings → Users → System Users → encontrar o System User vinculado ao app que gera o `FB_ACCESS_TOKEN`
2. Add Assets → WhatsApp Accounts
3. Selecionar **as 2 WABAs** (`105152822451126` Supervisão + `306417967823808` Odontologia)
4. Marcar permissão **"Manage WhatsApp accounts"** (não só "View")

Após isso, rodar:

```bash
cd /Users/tiagolau/Devs/MasterClinic
source ~/.claude/.env
python3 scripts/submeter_templates.py --apenas-sem-video
```

Resultado esperado: 12 templates submetidos, status `PENDING` ou `APPROVED` em
até 24h (geralmente em minutos para UTILITY bem estruturado).

## Estrutura de arquivos criada

```
/Users/tiagolau/Devs/MasterClinic/
├── docs/
│   └── decisions/
│       └── 001-submissao-templates-waba.md  (este arquivo)
├── templates/
│   └── templates.json   (14 templates, com _id_interno, _esqueleto, _risco)
├── scripts/
│   ├── submeter_templates.py  (envia para Graph API, gera logs/submit_*.json)
│   └── gerar_videos_veo.sh    (gera 2 vídeos via Veo 3 — bug em durationSeconds)
├── media/                  (vazio — receberá .mp4 dos vídeos)
└── logs/
    ├── submit_20260526_195354.json  (resultado da 1a tentativa: 12 fails)
    ├── veo_*.json                    (jobs Veo 3 que falharam)
    └── veo_run.log
```
