# Monitor de instâncias uazapi — importação e ativação

Alerta no WhatsApp quando uma instância uazapi da Master Clinic cai.
Arquivo: [monitor-instancias-uazapi.dc](monitor-instancias-uazapi.dc) — gerado por
[`scripts/gerar_dc_monitor_instancias.py`](../scripts/gerar_dc_monitor_instancias.py).
Desenho e justificativas: [ADR 007](../docs/decisions/007-monitor-instancias-uazapi.md).

O arquivo vem com `active: false` — importa desligado de propósito.

## Ordem dos passos

### 1. Definir o telefone do alerta

Editar `TELEFONE_ALERTA` no topo do script (E.164, só dígitos) e regerar:

```bash
python3 scripts/gerar_dc_monitor_instancias.py
```

Enquanto for o placeholder `5531000000000`, o script avisa no final.

### 2. Criar o campo adicional do anti-flood

Campo de texto na entidade **lead**, nome exato `uaz_alertas`. Guarda um JSON
`{"mesquita": <timestamp>, ...}` com o último alerta de cada instância — é o que
impede uma rajada de eventos virar uma rajada de mensagens.

Pelo painel (Configurações → Campos adicionais) ou pelo MCP:

```bash
source ~/.claude/.env
curl -s -X POST https://mcp.g1.datacrazy.io/api/mcp \
  -H "Authorization: Bearer $DATACRAZY_API_KEY_MASTERCLINIC" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"additional_field_create",
       "arguments":{"name":"uaz_alertas","type":"text","entity":"lead"}}}'
```

⚠️ Conferir o `inputSchema` em `tools/list` antes — o MCP responde `success` para
argumento errado sem criar nada. Validar depois com um `GET` na REST.

Sem o campo o fluxo continua funcionando, só perde o anti-flood (pode repetir alerta).

### 3. Importar a automação

Automações → Importar → selecionar o `.dc`. Deixar **desativada** por enquanto.

### 4. Copiar a URL do gatilho

Abrir o bloco de gatilho (Requisição HTTP) e copiar a URL gerada. É ela que vai
para a uazapi no passo 5.

### 5. Adicionar o webhook nas 3 instâncias

**`action: "add"` é obrigatório.** Sem ele a uazapi entra no "modo simples" e
**sobrescreve** o webhook existente — que é o que entrega as mensagens ao
DataCrazy. Isso derruba o atendimento das 3 unidades.

```bash
URL_GATILHO="<cole aqui a URL do passo 4>"

source ~/.claude/.env
for TOKEN in \
  "$UAZAPI_TOKEN_MASTERCLINIC_MESQUITA" \
  "$UAZAPI_TOKEN_MASTERCLINIC_GERENCIA" \
  "$UAZAPI_TOKEN_MASTERCLINIC_FINANCEIRO"
do
  curl -s -X POST https://masterclinic.uazapi.com/webhook \
    -H "token: $TOKEN" -H "Content-Type: application/json" \
    -d "{\"action\":\"add\",\"enabled\":true,\"url\":\"$URL_GATILHO\",\"events\":[\"connection\"]}"
  echo
done
```

Conferir que cada instância ficou com **dois** webhooks (o do DataCrazy intacto +
o novo, só com `connection`):

```bash
curl -s https://masterclinic.uazapi.com/webhook \
  -H "token: $UAZAPI_TOKEN_MASTERCLINIC_MESQUITA" | python3 -m json.tool
```

### 6. Ativar e testar

Ativar a automação. Para testar sem derrubar o atendimento, use uma instância
descartável: crie uma nova instância na uazapi, adicione nela o mesmo webhook,
conecte e desconecte. A instância de teste cai no ramo "não mapeada" e o alerta
sai mesmo assim, com dados parciais — o que já valida o caminho todo.

## Remover o webhook depois

```bash
curl -s -X POST https://masterclinic.uazapi.com/webhook \
  -H "token: <token>" -H "Content-Type: application/json" \
  -d '{"action":"delete","id":"<id do webhook retornado no GET>"}'
```

## Ajustes comuns

| O que | Onde |
|---|---|
| Telefone do alerta | `TELEFONE_ALERTA` no script |
| Janela do anti-flood (30 min) | `JANELA_DEDUP_MIN` |
| Debounce antes de confirmar (3 min) | `DEBOUNCE_MIN` |
| Texto da mensagem | `JS_DEDUP`, variável `mensagem` |
| Nova instância uazapi | dicionário `INSTANCIAS` (token → metadados) |

Depois de qualquer ajuste: regerar, **reimportar** e reativar. Não há API para
editar automação já importada — a reimportação é o único caminho.
