"""
Gera proposta de templates WhatsApp Business API (WABA) para a
Master Clinic Odontologia Especializada — Dr. Wilton.

Saída: docs/proposta-templates-whatsapp-master-clinic.docx
"""

from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ---------- Estilo ----------
NAVY = RGBColor(0x14, 0x2C, 0x4A)       # títulos principais
TEAL = RGBColor(0x0F, 0x6F, 0x7C)       # nomes de templates
GRAY = RGBColor(0x4A, 0x5A, 0x6A)       # corpo neutro
LIGHT_GRAY = RGBColor(0x70, 0x7A, 0x86) # legendas
GREEN = RGBColor(0x1F, 0x7A, 0x3A)
RED = RGBColor(0xB3, 0x1F, 0x1F)
AMBER = RGBColor(0xB7, 0x6A, 0x10)


def add_shading(cell, color_hex: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tc_pr.append(shd)


def set_cell_borders(cell, color="DDDDDD", size="6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), size)
        b.set(qn("w:color"), color)
        tc_borders.append(b)
    tc_pr.append(tc_borders)


def paragraph(doc, text="", *, bold=False, italic=False, size=11, color=GRAY,
              align=None, space_before=0, space_after=4, font="Calibri"):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        run = p.add_run(text)
        run.font.name = font
        run.font.size = Pt(size)
        run.bold = bold
        run.italic = italic
        run.font.color.rgb = color
    return p


def heading(doc, text, *, level=1):
    sizes = {0: 22, 1: 16, 2: 13}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level else 6)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(sizes.get(level, 13))
    run.bold = True
    run.font.color.rgb = NAVY
    return p


def divider(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "C8CED4")
    pBdr.append(bottom)
    pPr.append(pBdr)


def chip_row(doc, items):
    """items = [(label, fill_hex, font_hex)]"""
    table = doc.add_table(rows=1, cols=len(items))
    table.autofit = False
    for i, (label, fill, font_color) in enumerate(items):
        cell = table.cell(0, i)
        cell.width = Cm(5)
        add_shading(cell, fill)
        set_cell_borders(cell, color=fill)
        cell.paragraphs[0].paragraph_format.space_before = Pt(2)
        cell.paragraphs[0].paragraph_format.space_after = Pt(2)
        run = cell.paragraphs[0].add_run(f"  {label}  ")
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string(font_color)
        run.font.name = "Calibri"
    return table


def template_card(doc, *, idx, slug, situacao, categoria, body, footer,
                  botoes, variaveis, justificativa, risco, risco_nivel):
    # Cabeçalho do card
    heading(doc, f"{idx:02d}. {situacao}", level=1)

    # Chips
    cat_color = "1F7A3A" if categoria == "UTILITY" else "B76A10"
    risco_color = {
        "Baixo": "1F7A3A",
        "Médio": "B76A10",
        "Alto": "B31F1F",
    }[risco_nivel]
    chip_row(doc, [
        (f"slug: {slug}", "EEF2F6", "142C4A"),
        (f"categoria: {categoria}", f"{cat_color}", "FFFFFF"),
        (f"idioma: pt_BR", "EEF2F6", "142C4A"),
        (f"risco: {risco_nivel}", risco_color, "FFFFFF"),
    ])
    paragraph(doc, "", size=4)

    # Preview do balão (simulação do WhatsApp)
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    cell.width = Cm(15)
    add_shading(cell, "F5F7FA")
    set_cell_borders(cell, color="D7DEE5")
    # body do balão
    p_body = cell.paragraphs[0]
    p_body.paragraph_format.space_before = Pt(6)
    p_body.paragraph_format.space_after = Pt(2)
    for i, line in enumerate(body.split("\n")):
        if i > 0:
            p_body = cell.add_paragraph()
            p_body.paragraph_format.space_before = Pt(0)
            p_body.paragraph_format.space_after = Pt(2)
        run = p_body.add_run(line)
        run.font.size = Pt(11)
        run.font.name = "Calibri"
        run.font.color.rgb = RGBColor(0x1F, 0x2A, 0x36)
    # footer do balão
    if footer:
        p_foot = cell.add_paragraph()
        p_foot.paragraph_format.space_before = Pt(4)
        p_foot.paragraph_format.space_after = Pt(2)
        rf = p_foot.add_run(footer)
        rf.font.size = Pt(9)
        rf.font.color.rgb = LIGHT_GRAY
        rf.italic = True
        rf.font.name = "Calibri"
    # botões do balão
    if botoes:
        p_btn_label = cell.add_paragraph()
        p_btn_label.paragraph_format.space_before = Pt(6)
        p_btn_label.paragraph_format.space_after = Pt(2)
        rl = p_btn_label.add_run("Botões:")
        rl.font.size = Pt(9)
        rl.bold = True
        rl.font.color.rgb = NAVY
        rl.font.name = "Calibri"
        for tipo, texto in botoes:
            p_btn = cell.add_paragraph()
            p_btn.paragraph_format.left_indent = Cm(0.3)
            p_btn.paragraph_format.space_before = Pt(0)
            p_btn.paragraph_format.space_after = Pt(2)
            r_t = p_btn.add_run(f"[{tipo}] ")
            r_t.font.size = Pt(9)
            r_t.bold = True
            r_t.font.color.rgb = TEAL
            r_t.font.name = "Calibri"
            r_txt = p_btn.add_run(texto)
            r_txt.font.size = Pt(10)
            r_txt.font.color.rgb = RGBColor(0x1F, 0x2A, 0x36)
            r_txt.font.name = "Calibri"

    paragraph(doc, "", size=4)

    # Variáveis
    if variaveis:
        paragraph(doc, "Variáveis (exemplos preenchidos):",
                  bold=True, size=10, color=NAVY, space_after=2)
        for k, v in variaveis.items():
            paragraph(doc, f"   • {{{{{k}}}}} → {v}", size=10,
                      color=GRAY, space_after=1)

    # Justificativa
    paragraph(doc, "Por que essa mensagem funciona:",
              bold=True, size=10, color=NAVY, space_before=4, space_after=2)
    paragraph(doc, justificativa, size=10, color=GRAY, italic=True,
              space_after=2)

    # Risco
    paragraph(doc, "Observação técnica (Meta):",
              bold=True, size=10, color=NAVY, space_before=4, space_after=2)
    paragraph(doc, risco, size=10, color=GRAY, space_after=8)

    divider(doc)


# ---------- Conteúdo da proposta ----------

TEMPLATES = [
    {
        "slug": "util_master_agendamento_primeira_consulta",
        "situacao": "Agendamento da primeira consulta",
        "categoria": "UTILITY",
        "body": (
            "Olá, {{1}}! Aqui é da Master Clinic Odontologia Especializada.\n\n"
            "Recebemos sua solicitação de avaliação com o Dr. Wilton e separamos "
            "algumas janelas de horário nos próximos dias para encaixar sua "
            "primeira consulta.\n\n"
            "Posso te passar os horários disponíveis agora?"
        ),
        "footer": "Master Clinic • Atendimento",
        "botoes": [
            ("QUICK_REPLY", "Sim, pode passar"),
            ("QUICK_REPLY", "Quero em outro horário"),
        ],
        "variaveis": {1: "Ana"},
        "justificativa": (
            "A mensagem referencia uma ação real do paciente (a solicitação de "
            "avaliação) e abre um loop suave — só os horários disponíveis serão "
            "revelados na resposta. Curiosidade + baixa fricção (botão de uma palavra)."
        ),
        "risco": (
            "Risco baixo de reclassificação. Existe gatilho transacional claro "
            "(solicitação prévia do paciente). Sem preço, sem promoção, sem palavras "
            "promocionais. O CTA é completar um processo iniciado."
        ),
        "risco_nivel": "Baixo",
    },
    {
        "slug": "util_master_confirmacao_proxima_consulta",
        "situacao": "Confirmação da próxima consulta (paciente em tratamento)",
        "categoria": "UTILITY",
        "body": (
            "{{1}}, sua próxima consulta de continuidade do tratamento na "
            "Master Clinic com o Dr. Wilton está agendada para {{2}}, às {{3}}.\n\n"
            "Para garantir o horário, posso confirmar sua presença?"
        ),
        "footer": "Master Clinic • Agenda",
        "botoes": [
            ("QUICK_REPLY", "Confirmo presença"),
            ("QUICK_REPLY", "Preciso remarcar"),
        ],
        "variaveis": {1: "Carlos", 2: "23/05 (sexta)", 3: "14h30"},
        "justificativa": (
            "Confirmação de agendamento é o caso UTILITY mais clássico que existe. "
            "Mensagem objetiva, com data e hora reais, e dois botões de baixíssima "
            "fricção. Aumenta a taxa de comparecimento e reduz no-show."
        ),
        "risco": (
            "Risco baixo. Confirmação de agendamento é um dos casos de uso "
            "explicitamente listados pela Meta como UTILITY puro."
        ),
        "risco_nivel": "Baixo",
    },
    {
        "slug": "util_master_retorno_4_meses",
        "situacao": "Retorno de manutenção — 4 meses",
        "categoria": "UTILITY",
        "body": (
            "{{1}}, dando continuidade ao seu acompanhamento na Master Clinic, "
            "identificamos no seu prontuário que sua janela de retorno de 4 meses "
            "chegou.\n\n"
            "É um cuidado preventivo importante para manter o resultado do seu "
            "tratamento com o Dr. Wilton. Posso te enviar os horários disponíveis?"
        ),
        "footer": "Master Clinic • Acompanhamento",
        "botoes": [
            ("QUICK_REPLY", "Sim, quero agendar"),
            ("QUICK_REPLY", "Me lembre depois"),
        ],
        "variaveis": {1: "Mariana"},
        "justificativa": (
            "A mensagem se ancora no prontuário do paciente e no protocolo clínico "
            "do Dr. Wilton — informação técnica real. Enquadramento de continuidade "
            "('dando continuidade ao seu acompanhamento') cria sensação de processo "
            "em andamento, não de oferta nova."
        ),
        "risco": (
            "Risco baixo. O gatilho transacional é o histórico clínico real do "
            "paciente. Não há menção a preço, pacote ou promoção."
        ),
        "risco_nivel": "Baixo",
    },
    {
        "slug": "util_master_retorno_6_meses",
        "situacao": "Retorno de manutenção — 6 meses",
        "categoria": "UTILITY",
        "body": (
            "{{1}}, sua revisão preventiva semestral aqui na Master Clinic está "
            "prevista para este período.\n\n"
            "O Dr. Wilton recomenda esse intervalo para acompanhar a saúde da sua "
            "boca e prevenir qualquer alteração. Posso te mostrar os horários "
            "disponíveis com ele?"
        ),
        "footer": "Master Clinic • Acompanhamento",
        "botoes": [
            ("QUICK_REPLY", "Quero agendar"),
            ("QUICK_REPLY", "Depois eu confirmo"),
        ],
        "variaveis": {1: "Felipe"},
        "justificativa": (
            "Mesma lógica do retorno de 4 meses, mas com janela semestral. "
            "Personalização em nome do profissional ('o Dr. Wilton recomenda') "
            "aumenta a sensação de cuidado individual."
        ),
        "risco": (
            "Risco baixo. Revisão preventiva agendada é um dos casos clássicos de "
            "UTILITY na área da saúde."
        ),
        "risco_nivel": "Baixo",
    },
    {
        "slug": "util_master_aniversariante",
        "situacao": "Aniversariante do dia",
        "categoria": "UTILITY",
        "body": (
            "{{1}}, hoje é um dia especial. Toda a equipe da Master Clinic "
            "Odontologia Especializada e o Dr. Wilton desejam a você um feliz "
            "aniversário e muita saúde, sempre.\n\n"
            "Estamos por aqui para o que precisar."
        ),
        "footer": "Master Clinic • Equipe",
        "botoes": [
            ("QUICK_REPLY", "Obrigado(a)!"),
        ],
        "variaveis": {1: "Patrícia"},
        "justificativa": (
            "Mensagem 100% relacional, sem oferta, sem desconto, sem CTA comercial. "
            "Reforça vínculo com o paciente e é uma porta de entrada natural para "
            "ele lembrar que precisa marcar consulta — mas a iniciativa parte dele."
        ),
        "risco": (
            "Risco MÉDIO. A Meta tem oscilado: algumas mensagens de aniversário "
            "puramente relacionais são aprovadas como UTILITY, outras são "
            "reclassificadas como MARKETING. Recomendamos submeter como UTILITY "
            "(esta versão); se for reclassificada, o conteúdo continua adequado "
            "e o custo apenas sobe levemente. NÃO adicionar 'presente especial', "
            "'mimo', 'desconto' — isso garante reclassificação."
        ),
        "risco_nivel": "Médio",
    },
    {
        "slug": "mkt_master_campanha_mes",
        "situacao": "Campanha do mês (Maio Vermelho, Mês das Mães, Namorados, etc.)",
        "categoria": "MARKETING",
        "body": (
            "{{1}}, este mês a Master Clinic está com uma ação especial vinculada "
            "ao tema {{2}}.\n\n"
            "O Dr. Wilton preparou orientações específicas para os pacientes da "
            "clínica sobre esse assunto. Quer receber por aqui?"
        ),
        "footer": "Master Clinic • Campanha mensal",
        "botoes": [
            ("QUICK_REPLY", "Quero receber"),
            ("QUICK_REPLY", "Agora não"),
        ],
        "variaveis": {1: "Lucas", 2: "Maio Vermelho — prevenção ao câncer de boca"},
        "justificativa": (
            "Campanhas mensais (Maio Vermelho, Dia das Mães, Namorados, Outubro "
            "Rosa) são INERENTEMENTE de marketing pela definição da Meta — são "
            "iniciativas em massa, sem gatilho transacional individual. Tentar "
            "submeter como UTILITY com tema sazonal seria rejeitado ou "
            "reclassificado automaticamente."
        ),
        "risco": (
            "Categoria MARKETING (assumida desde a submissão). Custo por conversa "
            "maior, mas é a forma honesta e segura de operar campanhas sazonais. "
            "Variável {{2}} permite reaproveitar o mesmo template para todas as "
            "campanhas do ano sem precisar criar um template novo a cada mês."
        ),
        "risco_nivel": "Médio",
    },
    {
        "slug": "util_master_resgate_paciente",
        "situacao": "Resgate de paciente (sumido há tempos)",
        "categoria": "UTILITY",
        "body": (
            "{{1}}, fazendo uma análise de prontuários aqui na Master Clinic, "
            "identificamos que seu último acompanhamento com o Dr. Wilton foi "
            "há algum tempo.\n\n"
            "Ele pediu para verificarmos se está tudo bem com a sua saúde bucal "
            "e se podemos ajudar a reorganizar sua agenda. Posso te ajudar?"
        ),
        "footer": "Master Clinic • Acompanhamento",
        "botoes": [
            ("QUICK_REPLY", "Sim, me ajude"),
            ("QUICK_REPLY", "Está tudo bem"),
        ],
        "variaveis": {1: "Rodrigo"},
        "justificativa": (
            "O gancho é uma ação interna real (revisão de prontuários) feita pela "
            "clínica — não é um disparo genérico. A iniciativa do Dr. Wilton "
            "('ele pediu para verificarmos') humaniza e tira o cheiro de cobrança. "
            "Curiosidade + cuidado preventivo."
        ),
        "risco": (
            "Risco MÉDIO. Resgate de base é uma zona cinzenta — depende muito da "
            "redação. Esta versão evita gatilhos de marketing porque referencia "
            "atividade interna da clínica (análise de prontuário) e foca em "
            "verificação de saúde, não em vender. Se a Meta reclassificar, vira "
            "MARKETING e segue funcionando."
        ),
        "risco_nivel": "Médio",
    },
    {
        "slug": "util_master_followup_primeira_consulta",
        "situacao": "Follow-up de primeira consulta (lead que não agendou)",
        "categoria": "UTILITY",
        "body": (
            "{{1}}, dando continuidade à sua solicitação de avaliação na Master "
            "Clinic, registrada em {{2}}, identificamos que o agendamento ainda "
            "está em aberto.\n\n"
            "Conseguimos preservar algumas janelas de horário com o Dr. Wilton "
            "para esta semana. Quer que eu envie?"
        ),
        "footer": "Master Clinic • Atendimento",
        "botoes": [
            ("QUICK_REPLY", "Quero ver os horários"),
            ("QUICK_REPLY", "Não tenho mais interesse"),
        ],
        "variaveis": {1: "Beatriz", 2: "15/05"},
        "justificativa": (
            "Combina três técnicas: enquadramento de continuidade ('dando "
            "continuidade'), data específica da solicitação ({{2}}) e ação "
            "pendente ('agendamento ainda em aberto'). O botão de descarte "
            "('Não tenho mais interesse') protege a qualidade do template — "
            "leads que não responderiam viram um clique limpo de saída."
        ),
        "risco": (
            "Risco baixo. Existe gatilho transacional explícito e datado. A "
            "estrutura é praticamente a definição de UTILITY pela Meta."
        ),
        "risco_nivel": "Baixo",
    },
    {
        "slug": "util_master_followup_fechamento_tratamento",
        "situacao": "Follow-up de fechamento (paciente avaliado que não fechou tratamento)",
        "categoria": "UTILITY",
        "body": (
            "{{1}}, o Dr. Wilton finalizou a revisão do seu plano de tratamento da "
            "consulta de {{2}} aqui na Master Clinic.\n\n"
            "Há uma definição que precisa da sua parte para liberarmos o início. "
            "Posso te explicar os próximos passos por aqui?"
        ),
        "footer": "Master Clinic • Plano de tratamento",
        "botoes": [
            ("QUICK_REPLY", "Pode explicar"),
            ("QUICK_REPLY", "Preciso de mais tempo"),
        ],
        "variaveis": {1: "Hugo", 2: "10/05"},
        "justificativa": (
            "Loop aberto poderoso: 'há uma definição que precisa da sua parte'. "
            "O paciente que recebeu plano e ainda não decidiu sente que existe "
            "algo pendente do lado dele — porque existe. Não menciona preço nem "
            "tenta vender; só convida a retomar a conversa onde ela parou."
        ),
        "risco": (
            "Risco baixo. O paciente passou por consulta real, recebeu plano real "
            "e há etapa pendente real. É textualmente um aviso de status de "
            "processo — o caso de uso mais seguro de UTILITY."
        ),
        "risco_nivel": "Baixo",
    },
]


# ---------- Geração do documento ----------

def build_doc():
    doc = Document()

    # Margens
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)

    # Capa
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("Proposta de Templates WhatsApp")
    r.font.name = "Calibri"
    r.font.size = Pt(26)
    r.bold = True
    r.font.color.rgb = NAVY

    p = doc.add_paragraph()
    r = p.add_run("Master Clinic Odontologia Especializada")
    r.font.name = "Calibri"
    r.font.size = Pt(16)
    r.font.color.rgb = TEAL
    r.bold = True

    paragraph(doc, "Para aprovação — Dr. Wilton",
              size=12, color=LIGHT_GRAY, italic=True, space_after=14)

    divider(doc)

    # Resumo
    heading(doc, "Resumo da proposta", level=1)
    paragraph(
        doc,
        "Doutor, com base no áudio que você gravou, mapeei 9 situações "
        "principais em que a clínica conversa com paciente ou lead via "
        "WhatsApp. Para cada uma, escrevi um template específico, pronto "
        "para ser submetido à Meta e aprovado.",
        size=11, color=GRAY, space_after=6,
    )
    paragraph(
        doc,
        "Cada template foi escrito para passar como UTILITY na Meta (mais "
        "barato e com mais entregabilidade) sempre que isso é tecnicamente "
        "honesto. Em duas situações — Aniversariante e Campanha do Mês — "
        "explico abertamente o risco, porque a Meta tende a classificar "
        "esses casos como MARKETING.",
        size=11, color=GRAY, space_after=6,
    )
    paragraph(
        doc,
        "Cada template traz: (1) prévia do balão como o paciente vê no "
        "WhatsApp, (2) variáveis e exemplos, (3) por que a copy funciona, "
        "(4) observação técnica sobre o enquadramento na Meta.",
        size=11, color=GRAY, space_after=6,
    )

    # Legenda das categorias
    heading(doc, "Legenda", level=2)
    chip_row(doc, [
        ("UTILITY", "1F7A3A", "FFFFFF"),
        ("MARKETING", "B76A10", "FFFFFF"),
        ("Risco Baixo", "1F7A3A", "FFFFFF"),
        ("Risco Médio", "B76A10", "FFFFFF"),
    ])
    paragraph(doc, "", size=4)
    paragraph(
        doc,
        "UTILITY: tarifa de serviço (menor custo, melhor entrega). MARKETING: "
        "tarifa promocional. Risco refere-se à chance da Meta reclassificar o "
        "template depois de submetido.",
        size=9, color=LIGHT_GRAY, italic=True, space_after=10,
    )

    divider(doc)

    # Cards de cada template
    heading(doc, "Templates propostos", level=1)
    for idx, t in enumerate(TEMPLATES, start=1):
        template_card(doc, idx=idx, **t)

    # Próximos passos
    heading(doc, "Próximos passos sugeridos", level=1)
    items = [
        ("1.", "Você revisa os 9 templates e marca quais aprova como estão e "
               "quais quer ajustar."),
        ("2.", "Para os que precisarem de ajuste, anota a observação no "
               "próprio documento (ou me manda em áudio, do jeito que "
               "preferir)."),
        ("3.", "Eu submeto os aprovados na Meta via WABA. Aprovação "
               "costuma sair em até 1h, mas pode levar até 24h."),
        ("4.", "Depois de aprovados, os templates ficam disponíveis para a "
               "equipe disparar conforme cada situação acontecer."),
    ]
    for n, texto in items:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"{n}  ")
        r1.bold = True
        r1.font.color.rgb = TEAL
        r1.font.size = Pt(11)
        r1.font.name = "Calibri"
        r2 = p.add_run(texto)
        r2.font.size = Pt(11)
        r2.font.color.rgb = GRAY
        r2.font.name = "Calibri"

    paragraph(doc, "", size=4)
    paragraph(
        doc,
        "Observação importante: a Meta pode reclassificar um template como "
        "MARKETING mesmo que ele seja submetido como UTILITY. Quando isso "
        "acontece, a mensagem continua sendo entregue — só muda o custo. "
        "Nenhum template aqui propõe enganar o sistema; o que fazemos é usar "
        "a redação correta para cada caso real da clínica.",
        size=10, color=LIGHT_GRAY, italic=True, space_after=10,
    )

    # Rodapé final
    divider(doc)
    paragraph(
        doc,
        "Proposta preparada para Dr. Wilton — Master Clinic Odontologia "
        "Especializada.",
        size=9, color=LIGHT_GRAY, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=8,
    )

    return doc


def main():
    out_dir = Path(__file__).parent / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "proposta-templates-whatsapp-master-clinic.docx"

    doc = build_doc()
    doc.save(out_path)
    print(f"OK: {out_path}")


if __name__ == "__main__":
    main()
