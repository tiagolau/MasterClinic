# 007 — Monitor de desconexão das instâncias uazapi

**Data:** 2026-08-04
**Status:** aceito

## Contexto

As três instâncias uazapi da Master Clinic (Mesquita, Gerência, Financeiro) são conexões por
QR Code — caem sozinhas (celular sem bateria, sessão expirada, WhatsApp Web desconectado por
outro dispositivo). Enquanto estão fora, o CRM não recebe nem envia mensagens, e **ninguém é
avisado**: a clínica só descobre quando alguém estranha o silêncio. Levantando o estado durante
o desenho desta automação, a Mesquita apareceu em `connecting` — o problema é corrente, não
hipotético.

A pergunta original era se dava para o DataCrazy receber um webhook da uazapi nesse evento.

## Decisão

Sim, e o desenho é webhook → automação DataCrazy, com duas escolhas que definem o resto.

### Webhook adicional, não o webhook existente

`GET /webhook` da uazapi devolve um **array**: a API suporta múltiplos webhooks por instância
(`action: add | update | delete`, cada um com `id`). Hoje cada instância tem um único webhook,
apontando para `messaging.g1.datacrazy.io` — é ele que entrega as mensagens ao CRM.

O monitor entra como um **segundo** webhook, assinando só `events: ["connection"]`. Usar o
"modo simples" da uazapi (POST sem `action`) sobrescreveria o webhook do canal e derrubaria o
atendimento das três unidades — esse é o principal risco operacional do procedimento, e está
sinalizado no README de importação.

### O webhook acorda, o `GET /instance/status` decide

O payload do evento `connection` não tem schema publicado (o OpenAPI da uazapi descreve `data`
como `map[string]interface{}` genérico). Em vez de apostar num formato, o bloco JS lê de forma
defensiva e, na dúvida, **deixa passar**: só interrompe o fluxo quando o payload afirma
explicitamente `connected`. A confirmação vem de `GET /instance/status`, cujo formato eu validei
nas três instâncias (`instance.status`, `instance.lastDisconnectReason`, `status.connected`).

Consequência: um erro de parsing do webhook custa uma chamada HTTP a mais, não um alerta perdido
nem um alarme falso.

### Debounce de 3 min + anti-flood de 30 min

Queda de rede gera rajada de eventos `connection`. Duas defesas:

1. **Debounce** — espera 3 min antes de checar o status. Reconexão automática cai fora sozinha.
2. **Anti-flood** — campo adicional `uaz_alertas` no lead do responsável guarda um JSON
   `{instancia: timestamp}`; só alerta se passaram 30 min desde o último aviso daquela instância.

Se o campo não existir, o JS degrada para "sempre alerta" em vez de quebrar.

### O alerta não sai pela instância que caiu

Condição sobre `instancia_dc`: se caiu a Mesquita, envia pela Gerência; caso contrário, pela
Mesquita. A Cloud API "Oficial" foi descartada como remetente — mensagem livre fora da janela de
24 h exige template aprovado, e a WABA segue `not_verified` sem permissão de escrita
([ADR 001](001-submissao-templates-waba.md)).

## Alternativas Consideradas

- **Polling via n8n** (`GET /instance/status` a cada N minutos): funcionaria e não dependeria do
  formato do webhook, mas adiciona um sistema fora do CRM para uma automação que o próprio
  DataCrazy resolve, e detecta a queda com atraso de até um ciclo.
- **Sobrescrever o webhook existente incluindo a URL da automação**: impossível — um webhook tem
  uma URL só, e a do canal DataCrazy é obrigatória.
- **`addUrlEvents: true` no webhook do canal** (uazapi sufixa o evento na URL, ex.
  `/webhook/connection`): elegante em tese, mas mudaria a URL que o DataCrazy espera receber nas
  mensagens. Mexe no caminho crítico do atendimento para economizar um webhook.
- **Alerta só por notificação interna do CRM** (`send-notification-action`, sem lead nem
  instância): mais simples, mas só é visto por quem já está com o CRM aberto — inútil justamente
  no fim de semana ou de madrugada, quando a instância cai e ninguém está olhando.
- **Notificar a queda sem confirmar por API**: geraria alarme a cada oscilação de rede. O evento
  `connection` dispara também em `connecting` e reconexões normais.

## Consequências

- 14 blocos, um único fluxo para as três instâncias. Adicionar um quarto número é uma entrada no
  dicionário `INSTANCIAS` + um `POST /webhook` — mesmo padrão do [ADR 003](003-trackeamento-capi-uazapi-multi-instancia.md).
- **Os tokens uazapi das três instâncias ficam embutidos no bloco JS** do `.dc`, como já acontece
  com o token CAPI no `x1-uazapi.json`. Não versionar o arquivo em repositório público.
- Pendente para ativar: definir `TELEFONE_ALERTA` (placeholder no script) e criar o campo
  adicional `uaz_alertas`.
- Não cobre o caminho inverso (avisar que a instância **voltou**). O fluxo tem o gancho — o evento
  `connection` de reconexão chega no mesmo webhook — mas ficou fora do escopo pedido.
- O `.dc` não é editável por API: qualquer ajuste exige regerar e reimportar
  ([ADR 005](005-chatbot-trafego-por-unidade.md) documenta a mesma limitação).
