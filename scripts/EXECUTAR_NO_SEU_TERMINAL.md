# Submeter templates Master Clinic — Passo a passo

Como meu token (`tiagolau@gmail.com`) não tem acesso de escrita à WABA da Master
Clinic, você precisa rodar com o token da sua conta admin (`tiago@rhinocrm.com.br`).

## Passo 1 — Gerar token User com sua conta admin

1. Abra https://developers.facebook.com/tools/explorer/
2. No canto superior direito, garanta que está logado como **tiago@rhinocrm.com.br**
3. Em **Meta App**, selecione o app "Integração Rhino" (ou qualquer outro app seu)
4. Em **User or Page**, clique em **"Get User Access Token"**
5. Marque as permissões: `whatsapp_business_management`, `whatsapp_business_messaging`, `business_management`
6. Clique em **Generate Access Token**
7. Copie o token que aparece (formato `EAA...`)

## Passo 2 — Exportar o token e rodar o script

```bash
cd /Users/tiagolau/Devs/MasterClinic

# Cola o token gerado no Passo 1
export FB_ACCESS_TOKEN_MASTERCLINIC="EAA..."

# Rodar o script com esse token (override do FB_ACCESS_TOKEN padrao)
FB_ACCESS_TOKEN="$FB_ACCESS_TOKEN_MASTERCLINIC" python3 scripts/submeter_templates.py --apenas-sem-video
```

## Passo 3 — Conferir resultado

```bash
ls -lt logs/submit_*.json | head -1
cat logs/submit_*.json | tail -1 | python3 -m json.tool | head -50
```

Esperado: 12 templates submetidos. Cada um com `status: 200` e `body.id` (ID do template criado) + `status: PENDING` ou `APPROVED`.

## Passo 4 — Me avisa

Quando rodar, me manda o resultado (`cat logs/submit_*.json` ou só o sumário no
final) que eu verifico, diagnostico rejeições e ajusto o que for necessário.

---

## Templates que serão enviados (12)

| # | Nome | Esqueleto |
|---|---|---|
| 1 | masterclinic_confirma_consulta | Header TEXT + body |
| 2 | masterclinic_retorno_periodico | Body longo institucional |
| 3 | masterclinic_atualizacao_cadastro | Sem variáveis (fallback) |
| 4 | masterclinic_retorno_4_meses | Body longo |
| 5 | masterclinic_retorno_segunda_etapa | 4 variáveis |
| 6 | masterclinic_aniversariante | Composto (risco médio) |
| 7 | masterclinic_envio_localizacao | Curto |
| 8 | masterclinic_agradecimento | Composto |
| 9 | masterclinic_final_de_semana | Aviso horário |
| 10 | masterclinic_ausencia_no_show | Header TEXT + body |
| 11 | masterclinic_primeira_consulta | Body longo |
| 12 | masterclinic_followup_fechamento_consulta | Body longo |

Os 2 templates com header VIDEO (utilidade_01, paciente_em_tratamento) ficam
pra segunda leva quando gerarmos os vídeos.
