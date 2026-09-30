# 010 — Deploy do painel em produção (VPS Tecminas)

**Data:** 2026-08-04
**Status:** aceito

## Contexto

O painel (ADRs 008/009) estava validado localmente. O usuário indicou a **VPS
Tecminas** (Contabo `173.212.205.156`, hostname `Mapeamento`, Ubuntu 24.04,
12 cores/47GB, credenciais em `VPS_TECMINAS_*` no `~/.claude/.env`) como host,
entregou um **token Gemini do cliente** (`GEMINI_API_KEY_MASTERCLINIC`) e deixou
o domínio definitivo em aberto.

## Decisão

- **Stack `painel-mc`** (app + postgres:16) via Docker Swarm em `/opt/painel-mc`,
  atrás do **Traefik v3 já existente** na VPS (rede overlay `Mapeamento`,
  certresolver `letsencryptresolver`) — stack.yml parametrizado com
  `TRAEFIK_NETWORK`/`CERT_RESOLVER`.
- **Domínio provisório:** `painel.mapeamento.online` — CNAME → `vps.mapeamento.online`
  criado via API da Hostinger (zona do próprio Tiago; registro novo, nada existente
  alterado). Cert Let's Encrypt emitido. ⚠️ O primeiro ACME falhou por NXDOMAIN
  (deploy antes da propagação); resolveu com `docker service update --force
  painel-mc_app` após o TTL negativo (600s) vencer.
- **Banco migrado** do ambiente local por `pg_dump -Fp | psql` (pg_dump 17 em
  formato custom **não restaura** no pg_restore 16 do container — usar SQL puro).
- **IA em produção: Gemini do cliente.** A conta nova só acessa modelos Gemini 3+
  (2.5-* respondem 404 "no longer available to new users"); `gemini-3-pro-preview`
  também 404 para essa chave — em uso `AI_MODEL_GEMINI=gemini-3-flash-preview,...`
  com fallback em lista no código. O parse do JSON usa `raw_decode` (o flash
  devolve conteúdo extra após o objeto).
- **Digest WhatsApp ativo:** envia da instância uazapi **Mesquita** (token lido de
  `instance_list` no DataCrazy) para o número da **Gerência** (`5531984891752`).
  Validado: `enviado_whatsapp=true`.
- Acessos salvos no `~/.claude/.env`: `PAINEL_MC_URL`, `PAINEL_MC_PASSWORD`,
  `PAINEL_MC_INGEST_TOKEN`. `.env` de produção em `/opt/painel-mc/.env` (600).

### Atualização de versão

```bash
rsync -az --exclude .venv --exclude .env --exclude __pycache__ dashboard/ root@173.212.205.156:/opt/painel-mc/
ssh root@173.212.205.156 'cd /opt/painel-mc && docker build -q -t painel-mc:latest . && docker service update --force --image painel-mc:latest painel-mc_app -d'
```

## Domínio do cliente (investigado)

`masterclinicodontologia.com.br`: registrado no **Registro.br** em nome de
CARVALHO E VARGAS LTDA (CNPJ 09.586.465/0001-40), DNS em nameservers próprios
(`ns1-4.masterclinicodontologia.com.br` → `199.193.117.202`) administrados pela
agência **Inovatório** (SOA rname `roger.paulino@inovatorio.com.br`), mesma infra
do WordPress. O acesso WP **não** permite editar DNS. Caminhos para
`painel.masterclinicodontologia.com.br`:
1. Pedir ao Roger/Inovatório um `A painel → 173.212.205.156` (mais rápido);
2. Dr. Wilton recuperar o login do Registro.br pelo CNPJ e trocar/gerir a zona.
Quando existir, basta trocar `PAINEL_DOMAIN` no `.env` e redeployar a stack.

## Alternativas Consideradas

- **Expor por IP:porta até ter domínio:** rejeitado — dados de pacientes sem TLS;
  o subdomínio provisório em domínio próprio dá HTTPS imediato.
- **Redirect no WordPress do cliente:** possível (`/painel` → URL do painel), mas
  adiado — mexer no WP de produção do cliente sem necessidade é risco gratuito.

## Consequências

- Painel em produção: https://painel.mapeamento.online (senha em
  `PAINEL_MC_PASSWORD`). Jobs ativos: sync incremental 5min, completo 60min,
  Meta 60min, Clinicorp 30min, diagnóstico 20h30 com digest no WhatsApp.
- O app local foi desligado para não disputar o rate limit do DataCrazy com a
  produção (30 req/min é global do tenant).
- Pendências: collector no fluxo X1 (adiado pelo usuário), domínio definitivo,
  e monitorar o custo/limite do token Gemini do cliente.
