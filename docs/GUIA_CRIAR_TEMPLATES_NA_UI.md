# Guia — Criar os 12 templates Master Clinic na UI da Meta

**Onde criar:** https://business.facebook.com/wa/manage/message-templates/?waba_id=105152822451126

**Para cada template, siga:**
1. Clicar em **Criar modelo**
2. Categoria: **Utilidade**
3. Nome: copiar da seção abaixo (snake_case, sem acento)
4. Idiomas: **Português (BR)**
5. Avançar
6. Preencher Cabeçalho / Corpo / Rodapé / Botões conforme cada seção abaixo
7. Em "Exemplos", preencher com os valores indicados (a Meta usa isso pra revisão)
8. Enviar para revisão

**Dicas globais:**
- Não adicione emojis nos textos novos (mesmo que o template antigo `masterclinic_confirmar` tenha — quero manter assinatura institucional pura)
- Variáveis aparecem no editor como `{{1}}`, `{{2}}` — clique no botão **"Adicionar variável"** pra inserir
- Botões **Quick Reply (Resposta rápida)** são os mais usados aqui

---

## Template 1: `masterclinic_confirma_consulta`

**Categoria:** Utilidade
**Cabeçalho:** Texto
```
Confirmacao de consulta — {{1}}
```
Exemplo {{1}}: `amanha as 14h`

**Corpo:**
```
Ola {{1}}, registramos sua consulta na Master Clinic. Pedimos que confirme sua presenca para garantirmos o atendimento.

Caso precise reagendar, basta responder aqui.
```
Exemplo {{1}}: `Carlos`

**Rodapé:**
```
Master Clinic — Atendimento
```

**Botões (Resposta rápida):**
- `Confirmo presenca`
- `Preciso reagendar`

---

## Template 2: `masterclinic_retorno_periodico`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}},

verificamos em nosso sistema que o seu acompanhamento de {{2}} na Master Clinic esta com revisao periodica em aberto. Para mantermos seu historico em dia e garantir a continuidade do cuidado dentro do prazo recomendado, precisamos da sua confirmacao.

Voce pode responder por aqui mesmo. Nossa equipe esta disponivel para te orientar nos proximos passos.
```
Exemplos: {{1}}=`Ana`, {{2}}=`rotina clinica`

**Rodapé:** `Master Clinic — Atendimento`

**Botões:**
- `Quero agendar`
- `Nao tenho mais interesse`

---

## Template 3: `masterclinic_atualizacao_cadastro`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Identificamos uma atualizacao importante no seu cadastro na Master Clinic. Para que possamos seguir, precisamos apenas de uma confirmacao sua.

Voce pode responder por aqui quando puder.
```
(sem variáveis)

**Rodapé:** nenhum

**Botões:**
- `Pode prosseguir`

---

## Template 4: `masterclinic_retorno_4_meses`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}},

verificamos em nosso sistema que sua ultima consulta na Master Clinic foi em {{2}}. Pelo seu protocolo de acompanhamento, o retorno em 4 meses esta previsto para este periodo.

Para mantermos a continuidade do seu tratamento, podemos ja reservar um horario. Basta responder por aqui.
```
Exemplos: {{1}}=`Ana`, {{2}}=`janeiro de 2026`

**Rodapé:** `Master Clinic — Atendimento`

**Botões:**
- `Quero agendar retorno`
- `Prefiro outro momento`

---

## Template 5: `masterclinic_retorno_segunda_etapa`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}}, identificamos que sua {{2}} na Master Clinic esta com a segunda etapa prevista para {{3}}. Para darmos continuidade, podemos {{4}} agora mesmo.

Fico no aguardo da sua resposta.
```
Exemplos: {{1}}=`Rafael`, {{2}}=`sequencia de tratamento`, {{3}}=`as proximas duas semanas`, {{4}}=`reservar seu horario`

**Rodapé:** nenhum

**Botões:**
- `Pode agendar`
- `Preciso reagendar`
- `Pode encerrar`

---

## Template 6: `masterclinic_aniversariante`

**⚠️ Risco médio de virar MARKETING.** Se rejeitar, tenta de novo enfatizando "verificação de cadastro".

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}},

aqui e da equipe da Master Clinic. Em nossa verificacao periodica de cadastro, identificamos que hoje e uma data especial para voce.

O Dr. Wilton e a equipe registraram aqui os votos de um bom dia. Caso queira aproveitar para revisar seu acompanhamento conosco, basta responder por aqui.
```
Exemplo: {{1}}=`Carla`

**Rodapé:** `Master Clinic — Atendimento`

**Botões:**
- `Obrigado(a)`
- `Quero revisar acompanhamento`

---

## Template 7: `masterclinic_envio_localizacao`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}}, para facilitar seu deslocamento ate a Master Clinic, podemos enviar a localizacao exata pelo WhatsApp. Posso enviar agora?
```
Exemplo: {{1}}=`Joao`

**Rodapé:** nenhum

**Botões:**
- `Pode enviar`
- `Ja tenho o endereco`

---

## Template 8: `masterclinic_agradecimento`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}}, registramos a finalizacao do seu atendimento na Master Clinic.

O Dr. Wilton e a equipe agradecem a confianca. Caso surja qualquer duvida sobre as orientacoes passadas, basta responder por aqui.
```
Exemplo: {{1}}=`Lucia`

**Rodapé:** nenhum

**Botões:**
- `Tudo certo`
- `Tenho uma duvida`

---

## Template 9: `masterclinic_final_de_semana`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}}, informamos que nesta sexta-feira nosso atendimento na Master Clinic encerra as {{2}}, retornando na segunda-feira a partir das {{3}}.

Em caso de urgencia durante o final de semana, basta responder por aqui que direcionamos seu contato.
```
Exemplos: {{1}}=`Pedro`, {{2}}=`18h`, {{3}}=`8h`

**Rodapé:** nenhum

**Botões:**
- `Entendi`
- `Tenho uma urgencia`

---

## Template 10: `masterclinic_ausencia_no_show`

**Categoria:** Utilidade
**Cabeçalho:** Texto
```
Consulta nao realizada — {{1}}
```
Exemplo {{1}}: `ontem as 14h`

**Corpo:**
```
Ola {{1}}, registramos que sua consulta na Master Clinic prevista nao foi realizada. Para que possamos reservar um novo horario e manter seu acompanhamento em dia, basta nos confirmar por aqui.
```
Exemplo {{1}}: `Bruno`

**Rodapé:** `Master Clinic — Atendimento`

**Botões:**
- `Quero reagendar`
- `Nao quero mais`

---

## Template 11: `masterclinic_primeira_consulta`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}}, sua primeira consulta na Master Clinic esta confirmada para {{2}}.

Para agilizar seu atendimento, pedimos que chegue com 15 minutos de antecedencia e traga documento com foto e exames recentes, se houver.

Caso precise reagendar ou tirar alguma duvida antes do dia, basta responder por aqui.
```
Exemplos: {{1}}=`Patricia`, {{2}}=`quinta-feira as 10h`

**Rodapé:** `Master Clinic — Atendimento`

**Botões:**
- `Confirmo presenca`
- `Tenho uma duvida`
- `Preciso reagendar`

---

## Template 12: `masterclinic_followup_fechamento_consulta`

**Categoria:** Utilidade
**Cabeçalho:** Nenhum
**Corpo:**
```
Ola {{1}}, em nossa verificacao de agenda da Master Clinic, identificamos que seu agendamento para {{2}} ficou com a confirmacao em aberto.

Para que possamos garantir seu horario antes que ele seja liberado para a fila de espera, precisamos da sua confirmacao final.

Voce pode responder por aqui mesmo.
```
Exemplos: {{1}}=`Renato`, {{2}}=`consulta de avaliacao inicial`

**Rodapé:** `Master Clinic — Atendimento`

**Botões:**
- `Confirmo o horario`
- `Preciso de outro horario`
- `Nao quero mais`

---

## Ordem sugerida pra submeter (não tudo de uma vez)

Pra não estressar a revisão automática da Meta, submeta em ondas de 2-3 por dia:

| Dia | Templates | Motivo |
|---|---|---|
| 1 | T01 (confirma), T10 (no-show) | Casos clássicos, aprovam fácil — aquecem a revisão |
| 2 | T03 (atualização), T07 (localização) | Curtos, sem mídia, sem variável complexa |
| 3 | T02 (retorno periódico), T11 (primeira consulta) | Body longo institucional, muito robusto |
| 4 | T04 (4 meses), T05 (segunda etapa) | Acompanhamento clínico |
| 5 | T08 (agradecimento), T12 (followup) | Encerramento e retomada |
| 6 | T09 (final de semana) | Aviso operacional |
| 7 | T06 (aniversariante) | Submete por último — é o de risco médio. Se os anteriores aprovaram, a WABA tem boa reputação e tolera melhor. |

## Quando algum for REJEITADO

Me avisa o nome do template e a razão que a Meta deu. Eu reescrevo a versão 2.

## Templates pulados nesta leva (fica pra depois)

- `masterclinic_exame_pronto` (precisa URL do domínio real)
- `masterclinic_retorno_dr_wilton` (precisa telefone real)
- `masterclinic_pesquisa_satisfacao` (precisa URL do formulário)
- `masterclinic_utilidade_01` (precisa vídeo header — Veo 3)
- `masterclinic_paciente_em_tratamento` (precisa vídeo header — Veo 3)
- `masterclinic_followup_lead_sem_agenda` (risco médio, melhor depois que o número aquecer)
