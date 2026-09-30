# 003 — Trackeamento CAPI multi-instância (uazapi) da Master Clinic

**Data:** 2026-07-29
**Status:** aceito

## Contexto

O fluxo DataCrazy `X1 Uazapi` (tenant `69937b06-43cd-40d2-bd39-d3d3c9223283`) foi clonado de um
modelo escrito para **WhatsApp Cloud API** e reapontado para 3 instâncias **uazapi** (QR):
Mesquita, Gerência e Financeiro. Ao rodar em produção, a Meta rejeitava o evento:

```
code 100 / subcode 2804071 — "ctwa_clid ausente ... action_source business_messaging"
```

Duas causas:

1. **Formato de payload diferente.** No Cloud API o tracking vem em `referral.ctwa_clid`. No uazapi
   vem em `content.contextInfo.externalAdReply.ctwaClid` (e `sourceID` para o ad id). Todos os
   caminhos do fluxo (condição, `field-operation`, bloco JS) liam o formato Cloud API → vazio.
2. **Furo no wiring.** O ramo "lead não existe" (`create-lead-action`) ia direto para o
   `field-operation` → JS → API, **pulando** a condição que checa se há `ctwa_clid`. Ou seja: todo
   lead orgânico novo disparava uma chamada CAPI sem clid.

Além disso, o bloco `api` tinha o **dataset fixo** (`1296948068812416`, da WABA
`306417967823808` — que é o número Cloud API "Oficial", não os 3 uazapi) e o bloco JS tinha o
`whatsapp_business_account_id` hardcoded na mesma WABA errada.

## Decisão

### Mapeamento real (levantado via Graph API + API DataCrazy)

| Instância DataCrazy | Nome | Número | WABA | Dataset |
|---|---|---|---|---|
| `6a60fb2d9afe657f0c991354` | Mesquita Uazapi | 55 33 9136-0115 | `695879211426557` (Master clinic) | `1431423535578167` |
| `6a60fa47daf8b7fddb04ee7f` | Gerência Uazapi | 55 31 8489-1752 | `105152822451126` (Danielle Carvalho) | `1036765985424876` |
| `6a60fb7a9afe657f0c999799` | Financeiro Uazapi | 55 31 9076-1166 | `1350953883747065` (Master Clinic) | `1834437841272372` |

**Um dataset por WABA — não dá para usar um só para os 3.** O dataset é criado/obtido por
`POST /{WABA_ID}/dataset` (idempotente) e o `user_data.whatsapp_business_account_id` precisa bater
com a WABA dona do número que recebeu a mensagem. Os 3 números estão em WABAs distintas.

**O token é o mesmo para os 3** — System User `Conversions API System User`
(`122116067186885827`, app `CAPI Master Clinic`, `expires_at: 0`) da BM `476121126154261`.
Validado: o token lê e escreve nos 3 datasets.

### Arquitetura adotada — roteador JS + dataset dinâmico

Um único fluxo com 3 gatilhos. O bloco `javascript` carrega um `MAP` inline
`instanceId → {waba, dataset}`, resolve a instância por `session.getValue("instanceId")`
(fallback `Message-1.instanceData.id`) e devolve `resultado`, `dataset_id`, `waba_id`, `thumbnail`.
O bloco `api` monta a URL com interpolação:

```
https://graph.facebook.com/v23.0/{dataset_id|[Javascript-1]dataset_id}/events
```

Leitura do clid no JS com cascata **uazapi → cloud api → campo adicional**, o que deixa o mesmo
fluxo utilizável se algum número migrar para Cloud API.

### Mudanças aplicadas em `x1-uazapi.json`

1. Condição `field-has-value` → `[Message-1]content.contextInfo.externalAdReply.ctwaClid`.
2. `create-lead-action` agora aponta para a condição de `ctwa_clid` (fecha o furo do lead orgânico).
3. `field-operation`: caminhos uazapi corrigidos (`ctwaClid`, `sourceID`, `messageid`) — inclusive
   removendo o lixo de markdown `**sourceID**` que veio do modelo.
4. Bloco JS reescrito como roteador multi-instância.
5. Bloco `api` com dataset dinâmico.

### Refinamentos posteriores (mesma data)

6. **Anotação interna enriquecida.** O bloco de anotação passou a enviar, antes da imagem do
   criativo, um texto montado no JS (`anotacao`) com título do anúncio, `ad_id`, origem
   (instagram/facebook), link do post e o **texto do criativo** (normalizado e truncado em 900
   chars). O texto vai primeiro no array de `messages` de propósito: se a URL da thumbnail falhar, a
   anotação textual já foi entregue.
7. **`event_time` do horário real da mensagem** (`messageTimestamp`), não do `Date.now()` da
   execução — com clamp na janela de 7 dias aceita pela Meta. Antes, reprocessamento ou atraso da
   automação gravava o horário errado.
8. **`event_id`** (= `messageid` do WhatsApp) no payload, para a Meta deduplicar caso o mesmo evento
   seja enviado duas vezes. Validado: a CAPI de `business_messaging` aceita `event_id`.
9. **`custom_data.ad_id`** com o `sourceID` do criativo — validado e aceito.
10. **Guard antes da chamada CAPI.** O JS zera `dataset_id` quando não se deve enviar e um bloco
    `condition field-has-value [Javascript-1]dataset_id` desvia direto para a anotação. Três casos:
    instância fora do `MAP`, mensagem sem `ctwa_clid`, e anúncio de RH. O motivo vai na anotação
    (`status_capi`), então o skip é visível em vez de silencioso.
11. **Ramo de erro da CAPI separado.** O `errorNextBlockId` do bloco `api` deixou de apontar para o
    mesmo destino do sucesso e passa por uma anotação `⚠️ FALHA NO ENVIO CAPI` com dataset, WABA,
    ad_id e o `error.message` da Meta. Antes, rejeição da Meta passava despercebida.
12. **Filtro de anúncios de RH.** Vaga de emprego e captação de paciente dividem o mesmo WhatsApp,
    então candidatos viravam `LeadSubmitted` e poluíam a otimização comercial. Filtro por **texto do
    criativo**, com termos que exigem contexto de RH:

    ```
    #vagas?\b | vaga de emprego | vagadeemprego | estamos contratando | contrata-?\s?se |
    processo seletivo | trabalhe conosco | banco de talentos | currículo |
    se identifica com a vaga | candidatar
    ```

    A hashtag `#vaga` é o gatilho canônico — combinado com o cliente incluí-la nos criativos de RH.
    Os demais termos são rede de segurança para os anúncios já publicados.

    **Por que não filtrar por "vaga" solto:** varrendo os 200 anúncios ativos da conta
    `act_146238145960571`, "vaga" aparece em 5 — e 3 são comerciais (`"Vagas limitadas"` ×2,
    `"nas horas vagas a Dani ama estar em família"`). O padrão contextual pega 4 anúncios de RH
    (incluindo dois `"Contrata-se"` que "vaga" não pegaria) com zero falso positivo.

## Alternativas Consideradas

- **Um fluxo por número (3 fluxos):** rejeitado — triplica manutenção e é o anti-padrão que a skill
  `trackeamento-capi-datacrazy` já resolveu em outros clientes.
- **Dataset único para as 3 instâncias:** rejeitado — impossível: dataset é por WABA, e enviar com
  `whatsapp_business_account_id` de outra WABA quebra a atribuição.
- **`page_id` em vez de `whatsapp_business_account_id`:** desnecessário — apesar de conectados por
  QR (uazapi), os 3 números estão registrados em WABAs da BM (um deles como `ON_PREMISE`, dois em
  coexistência com Cloud API).
- **Buscar o mapa via bloco `api` antes do JS:** rejeitado — o bloco JS do DataCrazy não tem `fetch`
  e o mapa é estático; `MAP` inline é mais simples e sem latência extra.

## Consequências

- Positivo: 1 fluxo cobre os 3 números; adicionar um 4º número é 1 gatilho + 1 linha no `MAP`.
- Positivo: leads orgânicos param de gerar chamada CAPI inválida (menos ruído/erro na conta Meta).
- Validado end-to-end: `POST /1431423535578167/events` com o `ctwa_clid` real da Mesquita retornou
  `{"events_received":1}`.
- **Financeiro x CRC Master Clinic:** o número 55 31 9076-1166 aparece em duas instâncias DataCrazy
  — a uazapi `Financeiro` (`6a60fb7a9afe657f0c999799`) e a Cloud API `CRC Master Clinic`
  (`6a26c3e1ffc3b7ba0ae3495b`). A uazapi **substituiu** a Cloud API; a Cloud ficou como resquício e
  não deve receber gatilho de trackeamento. Sem duplicidade enquanto isso valer.
- **Não desregistrar o número da WABA `1350953883747065`.** Mesmo com o atendimento migrado para o
  uazapi, o `user_data.whatsapp_business_account_id` do Financeiro depende dessa WABA existir com o
  número. Remover o número da WABA na Meta quebra o trackeamento dessa instância.
- O token CAPI segue **embutido** no arquivo exportado (`query.access_token`) — não versionar esse
  JSON em repositório público.
- Pendências fora do escopo do trackeamento: o fluxo ainda tem placeholders vazios em `tagIds`,
  `pipelineId` e `stageId` dos blocos comerciais a jusante.
