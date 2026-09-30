/* Painel Master Clinic — SPA sem dependências */
(() => {
  "use strict";

  const $ = (s) => document.querySelector(s);
  let DIAS = 30;
  let TIMER = null;

  const fmtBRL = (v) =>
    (v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const fmtN = (v) => (v ?? 0).toLocaleString("pt-BR");
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(caminho, opts) {
    const r = await fetch(caminho, { credentials: "same-origin", ...opts });
    if (r.status === 401) {
      mostrarLogin();
      throw new Error("401");
    }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  // ---------- login ----------
  function mostrarLogin() {
    $("#login").classList.remove("hidden");
    $("#app").classList.add("hidden");
  }
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ senha: $("#senha").value }),
      });
      $("#login").classList.add("hidden");
      carregar();
    } catch {
      $("#login-erro").textContent = "Senha incorreta";
    }
  });

  // ---------- filtro de período ----------
  $("#filtro-periodo").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    document.querySelectorAll("#filtro-periodo button").forEach((x) => x.classList.remove("ativo"));
    b.classList.add("ativo");
    DIAS = +b.dataset.dias;
    carregar();
  });

  $("#btn-diag").addEventListener("click", async () => {
    if (!confirm("Gerar diagnóstico de IA agora? (leva ~1 min)")) return;
    await api("/api/diagnostico/rodar", { method: "POST" });
    alert("Diagnóstico disparado — recarregue em ~1 minuto.");
  });

  // ---------- tiles ----------
  function renderTiles(hoje, periodo) {
    const cpl = hoje.cpl_trafego != null ? fmtBRL(hoje.cpl_trafego) : "—";
    const tiles = [
      { r: "Leads hoje", v: fmtN(hoje.leads_novos), x: `${fmtN(hoje.leads_trafego)} de tráfego` },
      { r: "Gasto Meta hoje", v: fmtBRL(hoje.gasto_meta), x: `CPL tráfego: ${cpl}` },
      {
        r: "Aguardando resposta", v: fmtN(hoje.sem_resposta),
        x: "pacientes com a bola na clínica",
        cls: hoje.sem_resposta > 10 ? "critico" : hoje.sem_resposta > 3 ? "atencao" : "",
      },
      { r: "Negócios abertos", v: fmtN(hoje.negocios_abertos), x: "em todos os funis" },
      {
        r: "Faturamento hoje", v: fmtBRL(hoje.receita_clinicorp),
        x: `${fmtN(hoje.pagamentos)} pagamentos · ${fmtN(hoje.pacientes_pagantes)} pacientes`,
        cls: hoje.receita_clinicorp > 0 ? "bom" : "",
      },
      {
        r: `Faturamento (${DIAS}d)`, v: fmtBRL(periodo.receita_clinicorp),
        x: periodo.roas
          ? `ROAS ${periodo.roas}× sobre a mídia`
          : `${fmtN(periodo.pagamentos)} pagamentos`,
        cls: "bom",
      },
      { r: `Gasto Meta (${DIAS}d)`, v: fmtBRL(periodo.gasto_meta), x: `${fmtN(periodo.leads_trafego)} leads de tráfego` },
    ];
    const cc = window.__resumo?.clinicorp_hoje;
    if (cc && cc.consultas != null) {
      tiles.splice(3, 0, {
        r: "Consultas hoje",
        v: fmtN(cc.consultas),
        x: `${fmtN(cc.comparecimentos)} chegaram · ${fmtN(cc.de_trafego)} de tráfego`,
      });
    }
    $("#tiles").innerHTML = tiles
      .map(
        (t) => `<div class="tile ${t.cls || ""}">
          <div class="rotulo">${t.r}</div>
          <div class="valor">${t.v}</div>
          <div class="extra">${t.x}</div>
        </div>`
      )
      .join("");
  }

  // ---------- série temporal (2 painéis empilhados, mesmo eixo x) ----------
  const tooltip = document.createElement("div");
  tooltip.className = "tooltip hidden";
  document.body.appendChild(tooltip);

  function renderSerie(serie) {
    const el = $("#chart-serie");
    if (!serie.length) {
      el.innerHTML = '<div class="vazio">sem dados ainda</div>';
      return;
    }
    const W = el.clientWidth || 800;
    const H1 = 150, H2 = 130, PAD = { t: 18, r: 10, b: 20, l: 46 };
    const n = serie.length;
    const x = (i) => PAD.l + (i * (W - PAD.l - PAD.r)) / Math.max(n - 1, 1);

    const painel = (dados, series, altura, titulo, fmtY) => {
      const maxY = Math.max(...series.flatMap((s) => dados.map((d) => d[s.k])), 1) * 1.15;
      const y = (v) => altura - PAD.b - (v / maxY) * (altura - PAD.t - PAD.b);
      const ticks = [0, maxY / 2, maxY];
      let g = `<svg viewBox="0 0 ${W} ${altura}" data-painel>`;
      g += `<text x="${PAD.l}" y="12" class="titulo-painel">${titulo}</text>`;
      for (const t of ticks) {
        g += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${y(t)}" y2="${y(t)}" stroke="var(--grade)" stroke-width="1"/>`;
        g += `<text x="${PAD.l - 6}" y="${y(t) + 3}" text-anchor="end" fill="var(--ink-3)" font-size="10">${fmtY(t)}</text>`;
      }
      const passo = Math.ceil(n / 8);
      dados.forEach((d, i) => {
        if (i % passo === 0)
          g += `<text x="${x(i)}" y="${altura - 5}" text-anchor="middle" fill="var(--ink-3)" font-size="10">${d.dia.slice(8)}/${d.dia.slice(5, 7)}</text>`;
      });
      for (const s of series) {
        const pts = dados.map((d, i) => `${x(i)},${y(d[s.k])}`).join(" ");
        if (s.area) {
          const area = `${PAD.l},${y(0)} ${pts} ${x(n - 1)},${y(0)}`;
          g += `<polygon points="${area}" fill="${s.cor}" opacity="0.12"/>`;
        }
        g += `<polyline points="${pts}" fill="none" stroke="${s.cor}" stroke-width="2" stroke-linejoin="round"/>`;
      }
      g += `<line data-crosshair x1="0" x2="0" y1="${PAD.t}" y2="${altura - PAD.b}" stroke="var(--eixo)" stroke-width="1" opacity="0"/>`;
      g += "</svg>";
      return g;
    };

    const s1 = [{ k: "gasto", cor: "var(--s2)", area: true }];
    const s2 = [
      { k: "leads_trafego", cor: "var(--s1)", area: true },
      { k: "leads_novos", cor: "var(--s3)" },
    ];
    const s3 = [{ k: "receita_clinicorp", cor: "var(--bom)", area: true }];
    el.innerHTML =
      `<div class="paineis-serie">` +
      painel(serie, s1, H1, "GASTO META (R$)", (v) => Math.round(v)) +
      painel(serie, s2, H2, "LEADS — tráfego (verde) × novos no CRM (azul)", (v) => Math.round(v)) +
      painel(serie, s3, H2, "FATURAMENTO CLINICORP (R$ recebidos)", (v) => Math.round(v)) +
      `</div>`;

    // crosshair + tooltip compartilhados entre os dois painéis
    const svgs = el.querySelectorAll("svg");
    const mover = (ev) => {
      const rect = svgs[0].getBoundingClientRect();
      const px = ((ev.clientX - rect.left) / rect.width) * W;
      let i = Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (n - 1));
      i = Math.max(0, Math.min(n - 1, i));
      const d = serie[i];
      svgs.forEach((s) => {
        const c = s.querySelector("[data-crosshair]");
        c.setAttribute("x1", x(i));
        c.setAttribute("x2", x(i));
        c.setAttribute("opacity", "1");
      });
      tooltip.classList.remove("hidden");
      tooltip.style.left = Math.min(ev.clientX + 14, window.innerWidth - 240) + "px";
      tooltip.style.top = ev.clientY + 14 + "px";
      tooltip.innerHTML = `<div class="t-data">${d.dia.split("-").reverse().join("/")}</div>
        <div class="t-linha"><span class="t-cor" style="background:var(--s2)"></span>Gasto: ${fmtBRL(d.gasto)}</div>
        <div class="t-linha"><span class="t-cor" style="background:var(--s1)"></span>Leads tráfego: ${d.leads_trafego}</div>
        <div class="t-linha"><span class="t-cor" style="background:var(--s3)"></span>Leads novos: ${d.leads_novos}</div>
        ${d.receita_clinicorp ? `<div class="t-linha"><span class="t-cor" style="background:var(--bom)"></span>Faturamento: ${fmtBRL(d.receita_clinicorp)} (${d.pagamentos} pgto)</div>` : ""}
        ${d.ganhos ? `<div class="t-linha"><span class="t-cor" style="background:var(--marca-clara)"></span>Ganhos CRM: ${d.ganhos}</div>` : ""}`;
    };
    const sair = () => {
      tooltip.classList.add("hidden");
      svgs.forEach((s) => s.querySelector("[data-crosshair]").setAttribute("opacity", "0"));
    };
    el.querySelector(".paineis-serie").addEventListener("mousemove", mover);
    el.querySelector(".paineis-serie").addEventListener("mouseleave", sair);
  }

  // ---------- funis ----------
  function renderFunis(funis) {
    const porPipeline = {};
    for (const f of funis) {
      (porPipeline[f.pipeline] = porPipeline[f.pipeline] || []).push(f);
    }
    const ordem = ["Funil Principal - Ipatinga", "Funil Principal - Mesquita"];
    const rank = (n) => (ordem.indexOf(n) === -1 ? 999 : ordem.indexOf(n));
    const nomes = Object.keys(porPipeline).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    // rampa ordinal no verde da marca — validada com --ordinal (dark, surface #1a1a19):
    // L monotônica, gaps ≥ 0.06, ponta escura 2.79:1, hue spread 13°
    const rampa = ["#8fe3ba", "#5cd096", "#2bbb77", "#00a55c", "#008e45", "#00702f"];
    let html = "";
    for (const nome of nomes) {
      const etapas = porPipeline[nome].sort((a, b) => a.ordem - b.ordem);
      const total = etapas.reduce((s, e) => s + e.abertos, 0);
      if (!total && !etapas.some((e) => e.ganhos || e.perdidos)) continue;
      const max = Math.max(...etapas.map((e) => e.abertos), 1);
      html += `<div class="funil-bloco"><h3>${esc(nome)} <small style="color:var(--ink-3)">(${total} abertos)</small></h3>`;
      etapas.forEach((e, i) => {
        html += `<div class="funil-linha" title="${esc(e.etapa)}: ${e.abertos} abertos, ${e.ganhos} ganhos, ${e.perdidos} perdidos${e.valor_aberto ? ", " + fmtBRL(e.valor_aberto) + " em aberto" : ""}">
          <span class="funil-nome">${esc(e.etapa)}</span>
          <span class="funil-barra-wrap"><span class="funil-barra" style="width:${(e.abertos / max) * 100}%;background:${rampa[Math.min(i, rampa.length - 1)]}"></span></span>
          <span class="funil-qtd">${e.abertos}</span>
        </div>`;
      });
      html += "</div>";
    }
    $("#funis").innerHTML = html || '<div class="vazio">sem negócios ainda</div>';
  }

  // ---------- campanhas ----------
  function renderCampanhas(campanhas) {
    if (!campanhas.length) {
      $("#campanhas").innerHTML = '<div class="vazio">sem gasto no período</div>';
      return;
    }
    const maxGasto = Math.max(...campanhas.map((c) => c.gasto), 1);
    const linhas = campanhas
      .map(
        (c) => `<tr>
        <td class="nome-campanha" title="${esc(c.campanha)}">${esc(c.campanha)}</td>
        <td class="num"><span class="minibar" style="width:${Math.max((c.gasto / maxGasto) * 70, 2)}px"></span>${fmtBRL(c.gasto)}</td>
        <td class="num">${fmtN(c.conversas_iniciadas)}</td>
        <td class="num">${c.custo_por_conversa != null ? fmtBRL(c.custo_por_conversa) : "—"}</td>
        <td class="num">${fmtN(c.leads_meta)}</td>
        <td class="num">${c.leads_atribuidos ? fmtN(c.leads_atribuidos) : "—"}</td>
        <td class="num">${c.receita ? fmtBRL(c.receita) : "—"}</td>
        <td class="num" style="color:${c.roas == null ? "var(--ink-3)" : c.roas >= 1 ? "var(--bom)" : "var(--critico)"}">${
          c.roas != null ? c.roas + "×" : "—"
        }</td>
      </tr>`
      )
      .join("");
    $("#campanhas").innerHTML = `<table>
      <thead><tr><th>Campanha</th><th class="num">Gasto</th><th class="num">Conversas</th>
      <th class="num">R$/conversa</th><th class="num">Leads (CAPI)</th><th class="num">Leads CRM</th>
      <th class="num">Receita</th><th class="num">ROAS</th></tr></thead>
      <tbody>${linhas}</tbody></table>
      <p class="nota-rodape">Receita e ROAS por campanha dependem do <code>ad_id</code> na conversa —
      só aparecem nos leads em que o fluxo X1 registrou o anúncio de origem.</p>`;
  }

  // ---------- oportunidades ----------
  const MOTIVO = {
    nunca_respondido: "nunca respondido",
    pediu_preco_sem_resposta: "pediu preço e espera",
    sem_resposta: "esperando resposta",
  };
  function renderOportunidades(oport) {
    $("#oport-n").textContent = oport.length;
    if (!oport.length) {
      $("#oportunidades").innerHTML = '<div class="vazio">🎉 ninguém esperando resposta</div>';
      return;
    }
    $("#oportunidades").innerHTML = oport
      .map((o) => {
        const cor = o.motivo === "nunca_respondido" ? "var(--critico)" : o.pediu_preco ? "var(--serio)" : "var(--alerta)";
        const horas = o.horas_sem_resposta >= 24 ? `${Math.round(o.horas_sem_resposta / 24)}d` : `${Math.round(o.horas_sem_resposta)}h`;
        return `<div class="oport" data-conversa="${o.id}">
          <span class="ponto" style="background:${cor}"></span>
          <span class="info">
            <span class="nome">${esc(o.nome || o.telefone)}</span>
            ${o.origem === "trafego" ? '<span class="etiqueta trafego">tráfego</span>' : ""}
            <div class="det">${MOTIVO[o.motivo] || o.motivo} · ${esc(o.instancia_nome || "")}</div>
          </span>
          <span class="tempo">${horas}</span>
        </div>`;
      })
      .join("");
  }

  // ---------- agenda Clinicorp ----------
  function renderAgenda(agenda, ccHoje) {
    const card = $("#card-agenda");
    if (!agenda || !agenda.length) {
      card.classList.toggle("hidden", !ccHoje || !Object.keys(ccHoje).length);
      $("#agenda").innerHTML = '<div class="vazio">sem agendamentos hoje</div>';
      return;
    }
    card.classList.remove("hidden");
    $("#agenda-meta").textContent = `${ccHoje.consultas} consultas hoje · ${ccHoje.comparecimentos} chegaram · ${ccHoje.de_trafego} de tráfego`;
    const hoje = agenda[0]?.data;
    $("#agenda").innerHTML = `<table>
      <thead><tr><th>Hora</th><th>Paciente</th><th>Procedimento</th><th>Categoria</th><th>Origem</th><th>Status</th></tr></thead>
      <tbody>${agenda
        .filter((a) => a.data === hoje)
        .map((a) => {
          const origem =
            a.origem_conversa === "trafego"
              ? '<span class="etiqueta trafego">tráfego</span>'
              : a.conversa_id
              ? '<span class="etiqueta">no CRM</span>'
              : "—";
          const status = a.checkin_em
            ? `<span style="color:var(--bom)">✓ chegou ${esc(a.checkin_em)}</span>`
            : a.primeira_consulta
            ? '<span style="color:var(--s1)">1ª consulta</span>'
            : "";
          return `<tr ${a.conversa_id ? `data-conversa="${a.conversa_id}" style="cursor:pointer"` : ""}>
            <td>${esc(a.hora_ini || "")}</td>
            <td>${esc(a.paciente || "")}</td>
            <td class="nome-campanha" title="${esc(a.procedimentos)}">${esc(a.procedimentos || "—")}</td>
            <td>${esc(a.categoria || "—")}</td>
            <td>${origem}</td><td>${status}</td>
          </tr>`;
        })
        .join("")}</tbody></table>`;
  }

  // ---------- estagnados ----------
  function renderEstagnados(lista) {
    if (!lista.length) {
      $("#estagnados").innerHTML = '<div class="vazio">nenhum negócio estagnado 🎯</div>';
      return;
    }
    $("#estagnados").innerHTML = `<table>
      <thead><tr><th>Lead</th><th>Funil</th><th>Etapa</th><th class="num">Valor</th><th class="num">Parado há</th></tr></thead>
      <tbody>${lista
        .map(
          (n) => `<tr>
          <td>${esc(n.nome || n.telefone || "—")}</td>
          <td>${esc(n.pipeline)}</td><td>${esc(n.etapa)}</td>
          <td class="num">${n.total ? fmtBRL(n.total) : "—"}</td>
          <td class="num" style="color:${n.dias_parado > 14 ? "var(--critico)" : "var(--serio)"}">${Math.round(n.dias_parado)} dias</td>
        </tr>`
        )
        .join("")}</tbody></table>`;
  }

  // ---------- diagnóstico ----------
  function renderDiagnostico(diags) {
    const el = $("#diagnostico");
    if (!diags.length) {
      el.innerHTML = '<div class="vazio">nenhum diagnóstico gerado ainda — clique em 🧠 Diagnóstico</div>';
      return;
    }
    const d = diags[0];
    const j = typeof d.json === "string" ? JSON.parse(d.json) : d.json;
    $("#diag-meta").textContent = `${d.data.split("-").reverse().join("/")} · ${d.modelo}${d.enviado_whatsapp ? " · 📱 enviado" : ""}`;
    const oport = (j.oportunidades || [])
      .map(
        (o) => `<div class="diag-oport">
        <span class="prio ${esc(o.prioridade || "media")}">${esc(o.prioridade || "")}</span>
        <div class="quem">${esc(o.nome || "")} <small style="color:var(--ink-3)">${esc(o.telefone || "")}</small></div>
        <div class="oque">${esc(o.diagnostico || "")}</div>
        <div class="acao">→ ${esc(o.acao || "")}</div>
      </div>`
      )
      .join("");
    const alertas = (j.alertas_atendimento || []).map((a) => `<li>${esc(a)}</li>`).join("");
    const temas = (j.temas_do_dia || []).map((t) => `<li>${esc(t)}</li>`).join("");
    el.innerHTML = `
      <p class="diag-resumo">${esc(j.resumo_executivo || d.resumo || "")}
        ${j.nota_do_dia != null ? `<span class="nota-dia" style="float:right;color:${j.nota_do_dia >= 7 ? "var(--bom)" : j.nota_do_dia >= 5 ? "var(--alerta)" : "var(--critico)"}">${j.nota_do_dia}<small style="font-size:13px;color:var(--ink-3)">/10</small></span>` : ""}
      </p>
      <div class="diag-grid">
        <div class="diag-sec"><h3>Oportunidades apontadas pela IA</h3>${oport || '<div class="vazio">nenhuma</div>'}</div>
        <div class="diag-sec">
          ${alertas ? `<h3>Alertas de atendimento</h3><ul class="diag-lista">${alertas}</ul>` : ""}
          ${j.insight_trafego ? `<h3>Tráfego</h3><p style="color:var(--ink-2);font-size:13px">${esc(j.insight_trafego)}</p>` : ""}
          ${temas ? `<h3>Temas do dia</h3><ul class="diag-lista">${temas}</ul>` : ""}
        </div>
      </div>`;
  }

  // ---------- modal de conversa ----------
  document.addEventListener("click", async (e) => {
    const o = e.target.closest("[data-conversa]");
    if (o) {
      const d = await api(`/api/conversa/${o.dataset.conversa}`);
      $("#modal-titulo").textContent = `${d.conversa.nome || d.conversa.telefone} · ${d.conversa.instancia_nome || ""}`;
      $("#modal-corpo").innerHTML = d.mensagens
        .map((m) => {
          const cls = m.interna ? "interna" : m.recebida ? "lead" : "clinica";
          const hora = new Date(m.criada_em).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
          return `<div class="msg ${cls}">${esc(m.corpo || "(mídia)")}<span class="hora">${hora}</span></div>`;
        })
        .join("");
      $("#modal").classList.remove("hidden");
      $("#modal-corpo").scrollTop = 1e9;
    }
    if (e.target.id === "modal-fechar" || e.target.id === "modal") $("#modal").classList.add("hidden");
  });

  // ---------- ciclo principal ----------
  async function carregar() {
    try {
      const [resumo, diags, health] = await Promise.all([
        api(`/api/resumo?dias=${DIAS}`),
        api("/api/diagnosticos?n=1"),
        api("/api/health"),
      ]);
      $("#app").classList.remove("hidden");
      window.__resumo = resumo;
      document.querySelectorAll(".periodo-label").forEach((x) => (x.textContent = `últimos ${DIAS} dias`));
      renderTiles(resumo.hoje, resumo.periodo);
      renderSerie(resumo.serie);
      renderFunis(resumo.funis);
      renderCampanhas(resumo.campanhas);
      renderOportunidades(resumo.oportunidades);
      renderAgenda(resumo.agenda, resumo.clinicorp_hoje);
      renderEstagnados(resumo.estagnados);
      renderDiagnostico(diags);
      const inc = health.sync?.incremental?.ate;
      $("#sync-info").textContent = inc
        ? `sync ${new Date(inc).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`
        : "sync pendente";
    } catch (e) {
      if (e.message !== "401") console.error(e);
    }
    clearTimeout(TIMER);
    TIMER = setTimeout(carregar, 60_000);
  }

  carregar();
})();
