"""Consultas de métricas compartilhadas entre a API do dashboard e o diagnóstico IA.

Todas as janelas de "dia" usam o fuso America/Sao_Paulo.
"""
from . import config, db

FUSO = "America/Sao_Paulo"


def cards(dias: int = 1):
    """Números do topo do dashboard (janela = hoje por padrão)."""
    row = db.q1(
        f"""
        WITH janela AS (
          SELECT (date_trunc('day', now() AT TIME ZONE '{FUSO}') - make_interval(days => %s - 1))
                 AT TIME ZONE '{FUSO}' AS ini
        )
        SELECT
          (SELECT count(*) FROM leads, janela WHERE criado_em >= janela.ini)                          AS leads_novos,
          (SELECT count(*) FROM conversas, janela
             WHERE criada_em >= janela.ini AND origem = 'trafego' AND assunto = 'paciente')           AS leads_trafego,
          (SELECT count(*) FROM conversas
             WHERE ultima_msg_de_lead AND NOT COALESCE(finalizada, false)
               AND assunto = 'paciente'
               AND ultima_msg_em > now() - interval '7 days'
               AND ultima_msg_em < now() - interval '30 minutes')                                     AS sem_resposta,
          (SELECT count(*) FROM negocios, janela
             WHERE status = 'won' AND COALESCE(status_alterado_em, atualizado_em) >= janela.ini)      AS ganhos,
          (SELECT COALESCE(sum(total), 0) FROM negocios, janela
             WHERE status = 'won' AND COALESCE(status_alterado_em, atualizado_em) >= janela.ini)      AS receita_ganha,
          (SELECT count(*) FROM negocios WHERE status = 'in_process')                                 AS negocios_abertos
        """,
        (dias,),
    )
    gasto = db.q1(
        """SELECT COALESCE(sum(gasto), 0) AS gasto,
                  COALESCE(sum(conversas_iniciadas), 0) AS conversas_meta
           FROM meta_insights
           WHERE data >= (now() AT TIME ZONE %s)::date - (%s - 1) AND conta = %s""",
        (FUSO, dias, config.META_AD_ACCOUNTS[0] if config.META_AD_ACCOUNTS else ""),
    )
    # faturamento real vem do Clinicorp (pagamentos recebidos), não do CRM
    fat = db.q1(
        f"""SELECT COALESCE(sum(p.valor), 0) AS receita,
                   count(*)::int AS pagamentos,
                   count(DISTINCT p.paciente_id)::int AS pacientes,
                   COALESCE(sum(p.valor) FILTER (WHERE EXISTS (
                     SELECT 1 FROM clinicorp_pacientes c
                     JOIN conversas cv ON right(cv.telefone, 8) = right(c.telefone, 8)
                     WHERE c.id = p.paciente_id AND c.telefone IS NOT NULL
                       AND length(c.telefone) >= 8 AND cv.origem = 'trafego'
                   )), 0) AS receita_trafego
            FROM clinicorp_pagamentos p
            WHERE p.recebido_em >= (now() AT TIME ZONE '{FUSO}')::date - (%s - 1)
              AND p.recebido_em <= (now() AT TIME ZONE '{FUSO}')::date
              AND NOT p.cancelado AND p.recebido""",
        (dias,),
    )
    out = dict(row)
    out["gasto_meta"] = float(gasto["gasto"])
    out["conversas_meta"] = int(gasto["conversas_meta"])
    lt = out["leads_trafego"] or 0
    out["cpl_trafego"] = round(out["gasto_meta"] / lt, 2) if lt else None
    out["receita_ganha"] = float(out["receita_ganha"])  # CRM (business.total)
    out["receita_clinicorp"] = float(fat["receita"])
    out["pagamentos"] = fat["pagamentos"]
    out["pacientes_pagantes"] = fat["pacientes"]
    out["receita_trafego"] = float(fat["receita_trafego"])
    out["roas"] = (
        round(out["receita_clinicorp"] / out["gasto_meta"], 2) if out["gasto_meta"] else None
    )
    return out


def serie_diaria(dias: int = 30):
    """Gasto Meta × leads de tráfego × leads totais × ganhos, por dia."""
    return db.q(
        f"""
        WITH ds AS (
          SELECT generate_series(
            (now() AT TIME ZONE '{FUSO}')::date - (%s - 1),
            (now() AT TIME ZONE '{FUSO}')::date, '1 day')::date AS dia
        ),
        gastos AS (
          SELECT data AS dia, sum(gasto) AS gasto, sum(conversas_iniciadas) AS conv_meta
          FROM meta_insights WHERE conta = %s GROUP BY 1
        ),
        lt AS (
          SELECT (criada_em AT TIME ZONE '{FUSO}')::date AS dia, count(*) AS leads_trafego
          FROM conversas WHERE origem = 'trafego' AND assunto = 'paciente' GROUP BY 1
        ),
        ln AS (
          SELECT (criado_em AT TIME ZONE '{FUSO}')::date AS dia, count(*) AS leads_novos
          FROM leads GROUP BY 1
        ),
        g AS (
          SELECT (COALESCE(status_alterado_em, atualizado_em) AT TIME ZONE '{FUSO}')::date AS dia,
                 count(*) AS ganhos, sum(total) AS receita
          FROM negocios WHERE status = 'won' GROUP BY 1
        ),
        fat AS (
          SELECT recebido_em AS dia, sum(valor) AS receita_cc, count(*) AS pagamentos
          FROM clinicorp_pagamentos
          WHERE NOT cancelado AND recebido GROUP BY 1
        )
        SELECT ds.dia::text, COALESCE(gastos.gasto, 0)::float AS gasto,
               COALESCE(gastos.conv_meta, 0)::int AS conversas_meta,
               COALESCE(lt.leads_trafego, 0)::int AS leads_trafego,
               COALESCE(ln.leads_novos, 0)::int AS leads_novos,
               COALESCE(g.ganhos, 0)::int AS ganhos,
               COALESCE(g.receita, 0)::float AS receita,
               COALESCE(fat.receita_cc, 0)::float AS receita_clinicorp,
               COALESCE(fat.pagamentos, 0)::int AS pagamentos
        FROM ds
        LEFT JOIN gastos ON gastos.dia = ds.dia
        LEFT JOIN lt ON lt.dia = ds.dia
        LEFT JOIN ln ON ln.dia = ds.dia
        LEFT JOIN g ON g.dia = ds.dia
        LEFT JOIN fat ON fat.dia = ds.dia
        ORDER BY ds.dia
        """,
        (dias, config.META_AD_ACCOUNTS[0] if config.META_AD_ACCOUNTS else ""),
    )


def funis():
    """Contagem e valor por etapa de cada pipeline (negócios em aberto)."""
    return db.q(
        """
        SELECT p.id AS pipeline_id, p.nome AS pipeline, p.grupo,
               e.id AS etapa_id, e.nome AS etapa, e.ordem,
               count(n.id) FILTER (WHERE n.status = 'in_process')::int AS abertos,
               count(n.id) FILTER (WHERE n.status = 'won')::int AS ganhos,
               count(n.id) FILTER (WHERE n.status = 'lost')::int AS perdidos,
               COALESCE(sum(n.total) FILTER (WHERE n.status = 'in_process'), 0)::float AS valor_aberto
        FROM etapas e
        JOIN pipelines p ON p.id = e.pipeline_id
        LEFT JOIN negocios n ON n.etapa_id = e.id
        GROUP BY 1, 2, 3, 4, 5, 6
        ORDER BY p.nome, e.ordem
        """
    )


def campanhas(dias: int = 30):
    """Performance por campanha + leads atribuídos por ad_id quando existir."""
    return db.q(
        f"""
        WITH m AS (
          SELECT campanha_id, max(campanha) AS campanha,
                 sum(gasto)::float AS gasto, sum(impressoes)::bigint AS impressoes,
                 sum(cliques)::bigint AS cliques,
                 sum(conversas_iniciadas)::int AS conversas_iniciadas,
                 sum(leads_meta)::int AS leads_meta
          FROM meta_insights
          WHERE data >= (now() AT TIME ZONE '{FUSO}')::date - (%s - 1)
          GROUP BY campanha_id
        ),
        attr AS (
          SELECT mi.campanha_id, count(DISTINCT c.id)::int AS leads_atribuidos
          FROM conversas c
          JOIN meta_insights mi ON mi.ad_id = c.ad_id
          WHERE c.ad_id IS NOT NULL
            AND c.criada_em >= now() - make_interval(days => %s)
          GROUP BY mi.campanha_id
        ),
        -- receita: anúncio → conversa → telefone → paciente Clinicorp → pagamentos.
        -- Depende de conversas.ad_id (só existe onde o fluxo X1 anotou / collector rodou).
        rec AS (
          SELECT mi.campanha_id, sum(p.valor)::float AS receita
          FROM conversas c
          JOIN meta_insights mi ON mi.ad_id = c.ad_id
          JOIN clinicorp_pacientes cp
            ON cp.telefone IS NOT NULL AND length(cp.telefone) >= 8
           AND right(cp.telefone, 8) = right(c.telefone, 8)
          JOIN clinicorp_pagamentos p ON p.paciente_id = cp.id
          WHERE c.ad_id IS NOT NULL AND NOT p.cancelado AND p.recebido
            AND p.recebido_em >= (now() AT TIME ZONE '{FUSO}')::date - (%s - 1)
          GROUP BY mi.campanha_id
        )
        SELECT m.*, COALESCE(attr.leads_atribuidos, 0) AS leads_atribuidos,
               rec.receita,
               CASE WHEN m.gasto > 0 AND rec.receita IS NOT NULL
                    THEN round((rec.receita / m.gasto)::numeric, 2)::float END AS roas,
               CASE WHEN m.conversas_iniciadas > 0
                    THEN round((m.gasto / m.conversas_iniciadas)::numeric, 2)::float END AS custo_por_conversa
        FROM m
        LEFT JOIN attr ON attr.campanha_id = m.campanha_id
        LEFT JOIN rec ON rec.campanha_id = m.campanha_id
        WHERE m.gasto > 0
        ORDER BY m.gasto DESC
        """,
        (dias, dias, dias),
    )


def oportunidades(limite: int = 30):
    """Oportunidades em aberto, determinísticas (independem da IA)."""
    return db.q(
        """
        SELECT c.id, c.nome, c.telefone, c.instancia_nome, c.origem, c.assunto,
               c.procedimentos, c.pediu_preco, c.ultima_msg_em, c.primeira_msg_lead,
               c.n_clinica,
               round(extract(epoch FROM (now() - c.ultima_msg_em)) / 3600, 1)::float AS horas_sem_resposta,
               CASE
                 WHEN c.n_clinica = 0 THEN 'nunca_respondido'
                 WHEN c.pediu_preco THEN 'pediu_preco_sem_resposta'
                 ELSE 'sem_resposta'
               END AS motivo
        FROM conversas c
        WHERE c.ultima_msg_de_lead
          AND NOT COALESCE(c.finalizada, false)
          AND c.assunto = 'paciente'
          AND c.ultima_msg_em > now() - interval '7 days'
          AND c.ultima_msg_em < now() - interval '30 minutes'
        ORDER BY (c.origem = 'trafego') DESC, c.pediu_preco DESC, c.ultima_msg_em DESC
        LIMIT %s
        """,
        (limite,),
    )


def agenda_clinicorp(dias_futuro: int = 1):
    """Agenda de hoje (+ amanhã) com cruzamento por telefone com conversas de tráfego."""
    return db.q(
        f"""
        SELECT a.id, a.paciente, a.telefone, a.data::text, a.hora_ini, a.hora_fim,
               a.procedimentos, a.categoria, a.checkin_em, a.primeira_consulta,
               c.id AS conversa_id, c.origem AS origem_conversa
        FROM clinicorp_agendamentos a
        LEFT JOIN LATERAL (
          SELECT id, origem FROM conversas c
          WHERE a.telefone IS NOT NULL AND length(a.telefone) >= 8
            AND right(c.telefone, 8) = right(a.telefone, 8)
          ORDER BY (c.origem = 'trafego') DESC, c.ultima_msg_em DESC
          LIMIT 1
        ) c ON true
        WHERE a.data >= (now() AT TIME ZONE '{FUSO}')::date
          AND a.data <= (now() AT TIME ZONE '{FUSO}')::date + %s
          AND COALESCE(a.dados->>'Deleted', '') = ''
        ORDER BY a.data, lpad(a.hora_ini, 5, '0')
        """,
        (dias_futuro,),
    )


def cards_clinicorp(dias: int = 1):
    """Consultas do período: total, comparecimentos, primeiras consultas, vindas de tráfego."""
    row = db.q1(
        f"""
        SELECT count(*)::int AS consultas,
               count(*) FILTER (WHERE checkin_em IS NOT NULL)::int AS comparecimentos,
               count(*) FILTER (WHERE primeira_consulta)::int AS primeiras,
               count(*) FILTER (WHERE EXISTS (
                 SELECT 1 FROM conversas c
                 WHERE clinicorp_agendamentos.telefone IS NOT NULL
                   AND length(clinicorp_agendamentos.telefone) >= 8
                   AND right(c.telefone, 8) = right(clinicorp_agendamentos.telefone, 8)
                   AND c.origem = 'trafego'
               ))::int AS de_trafego
        FROM clinicorp_agendamentos
        WHERE data >= (now() AT TIME ZONE '{FUSO}')::date - (%s - 1)
          AND data <= (now() AT TIME ZONE '{FUSO}')::date
          AND COALESCE(dados->>'Deleted', '') = ''
        """,
        (dias,),
    )
    return dict(row) if row else {}


def negocios_estagnados(dias: int = 5, limite: int = 30):
    return db.q(
        """
        SELECT n.id, l.nome, l.telefone, p.nome AS pipeline, e.nome AS etapa,
               n.total::float, n.movido_em,
               round(extract(epoch FROM (now() - n.movido_em)) / 86400, 1)::float AS dias_parado
        FROM negocios n
        JOIN etapas e ON e.id = n.etapa_id
        JOIN pipelines p ON p.id = e.pipeline_id
        LEFT JOIN leads l ON l.id = n.lead_id
        WHERE n.status = 'in_process'
          AND n.movido_em < now() - make_interval(days => %s)
          AND p.grupo IN ('Clínico', 'Comercial')
          AND e.nome NOT ILIKE '%%perdido%%'
        ORDER BY n.total DESC NULLS LAST, n.movido_em ASC
        LIMIT %s
        """,
        (dias, limite),
    )
