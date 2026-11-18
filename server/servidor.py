"""
Servidor que recebe as leituras do ESP32 e guarda o histórico no MongoDB.

  POST /api/leituras   -> recebe o JSON do ESP32 e grava no banco
  GET  /api/leituras   -> devolve as últimas 50 leituras em JSON
  GET  /api/dados      -> leituras de um período (?minutos=60) para o dashboard
  GET  /               -> dashboard (atualiza sozinho a cada 5 s)

Como rodar:
  pip install -r requirements.txt
  python servidor.py
Depois abra http://localhost:5000 no navegador.
"""

import os
from datetime import datetime, timedelta, timezone

from flask import Flask, Response, jsonify, request
from pymongo import DESCENDING, MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = "monitoramento"

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000, tz_aware=True)
leituras = client[MONGO_DB]["leituras"]

app = Flask(__name__)


def numero_ou_none(valor):
    """Aceita número ou null; qualquer outra coisa é erro."""
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError
    return float(valor)


@app.post("/api/leituras")
def receber_leitura():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(erro="envie um JSON no corpo da requisição"), 400

    try:
        doc = {
            "dispositivo": str(dados.get("dispositivo", "desconhecido"))[:50],
            "temperatura": numero_ou_none(dados.get("temperatura")),
            "umidade": numero_ou_none(dados.get("umidade")),
            "luminosidade": str(dados.get("luminosidade", ""))[:20],
            "recebido_em": datetime.now(timezone.utc),
        }
    except ValueError:
        return jsonify(erro="temperatura e umidade devem ser números ou null"), 400

    resultado = leituras.insert_one(doc)
    print(f"[{doc['recebido_em'].astimezone():%H:%M:%S}] leitura recebida de {doc['dispositivo']}: "
          f"{doc['temperatura']} C, {doc['umidade']} %, {doc['luminosidade']}")
    return jsonify(ok=True, id=str(resultado.inserted_id)), 201


def para_json(d):
    return {
        "dispositivo": d.get("dispositivo"),
        "temperatura": d.get("temperatura"),
        "umidade": d.get("umidade"),
        "luminosidade": d.get("luminosidade"),
        "t": d["recebido_em"].isoformat(),
    }


@app.get("/api/leituras")
def listar_leituras():
    docs = leituras.find().sort("recebido_em", DESCENDING).limit(50)
    return jsonify([para_json(d) for d in docs])


@app.get("/api/dados")
def dados_periodo():
    minutos = request.args.get("minutos", default=60, type=int)
    agora = datetime.now(timezone.utc)
    filtro = {}
    if minutos and minutos > 0:
        filtro = {"recebido_em": {"$gte": agora - timedelta(minutes=minutos)}}
    docs = list(leituras.find(filtro).sort("recebido_em", DESCENDING).limit(5000))
    docs.reverse()  # mais antiga primeiro, para os gráficos
    ultima = leituras.find_one(sort=[("recebido_em", DESCENDING)])
    return jsonify(
        agora=agora.isoformat(),
        total=leituras.count_documents({}),
        ultima=para_json(ultima) if ultima else None,
        itens=[para_json(d) for d in docs],
    )


PAGINA = r"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitoramento ambiental · ESP32</title>
<style>
  :root {
    color-scheme: light;
    --page: #f9f9f7;
    --surface: #fcfcfb;
    --ink: #0b0b0b;
    --ink-2: #52514e;
    --muted: #898781;
    --grid: #e1e0d9;
    --axis: #c3c2b7;
    --border: rgba(11, 11, 11, 0.10);
    --temp: #eb6834;
    --umid: #2a78d6;
    --claro: #eda100;
    --escuro: #52514e;
    --good: #0ca30c;
    --warning: #fab219;
    --wash: rgba(11, 11, 11, 0.05);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --page: #0d0d0d;
      --surface: #1a1a19;
      --ink: #f0efec;
      --ink-2: #c3c2b7;
      --muted: #898781;
      --grid: #2c2c2a;
      --axis: #383835;
      --border: rgba(255, 255, 255, 0.10);
      --temp: #d95926;
      --umid: #3987e5;
      --claro: #c98500;
      --escuro: #6b6a66;
      --wash: rgba(255, 255, 255, 0.06);
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--page); color: var(--ink);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  main { max-width: 1120px; margin: 0 auto; padding: 32px 24px 48px; }
  header { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
  h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--ink-2); font-size: 14px; }
  .status { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 999px;
            border: 1px solid var(--border); background: var(--surface); font-size: 13px; font-weight: 600; }
  .status svg { width: 14px; height: 14px; }
  .barra { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
  .periodos { display: inline-flex; gap: 4px; padding: 4px; border-radius: 10px; background: var(--surface); border: 1px solid var(--border); }
  .periodos button { border: 0; background: transparent; color: var(--ink-2); font: inherit; font-size: 13px;
                     padding: 6px 12px; border-radius: 7px; cursor: pointer; }
  .periodos button:hover { background: var(--wash); }
  .periodos button[aria-pressed="true"] { background: var(--ink); color: var(--surface); font-weight: 600; }
  .info { color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; margin-bottom: 16px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; }
  .card .rotulo { display: flex; align-items: center; gap: 8px; color: var(--ink-2); font-size: 13px; font-weight: 600; }
  .key { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }
  .card .valor { font-size: 40px; font-weight: 700; letter-spacing: -0.02em; margin: 8px 0 4px; line-height: 1.1; }
  .card .valor small { font-size: 18px; font-weight: 600; color: var(--ink-2); margin-left: 2px; }
  .card .det { color: var(--muted); font-size: 13px; }
  .graficos { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; margin-bottom: 16px; }
  .painel { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px 12px; position: relative; }
  .painel h2 { font-size: 15px; margin: 0 0 2px; }
  .painel .desc { color: var(--muted); font-size: 12.5px; margin-bottom: 8px; }
  .chart { width: 100%; position: relative; }
  .chart svg { display: block; width: 100%; overflow: visible; }
  .vazio { color: var(--muted); font-size: 14px; padding: 48px 0; text-align: center; }
  .legenda { display: flex; gap: 16px; font-size: 12.5px; color: var(--ink-2); margin-top: 6px; }
  .legenda span { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
  .tip { position: absolute; pointer-events: none; background: var(--surface); border: 1px solid var(--border);
         box-shadow: 0 4px 16px rgba(0,0,0,0.12); border-radius: 8px; padding: 8px 10px; font-size: 12.5px;
         white-space: nowrap; display: none; z-index: 5; }
  .tip b { display: block; font-size: 15px; }
  .tip .t { color: var(--muted); font-variant-numeric: tabular-nums; }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; font-variant-numeric: tabular-nums; }
  th { text-align: left; color: var(--muted); font-weight: 600; font-size: 12px; padding: 8px 10px; border-bottom: 1px solid var(--grid); }
  td { padding: 8px 10px; border-bottom: 1px solid var(--grid); }
  tr:last-child td { border-bottom: 0; }
  td.num, th.num { text-align: right; }
  .pill { display: inline-flex; align-items: center; gap: 6px; }
  footer { color: var(--muted); font-size: 12px; margin-top: 16px; }
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Monitoramento ambiental</h1>
      <div class="sub">ESP32 · DHT11 · sensor de luminosidade · dados gravados no MongoDB</div>
    </div>
    <div class="status" id="status" role="status"></div>
  </header>

  <div class="barra">
    <div class="periodos" role="group" aria-label="Período">
      <button data-min="15">15 min</button>
      <button data-min="60" aria-pressed="true">1 hora</button>
      <button data-min="360">6 horas</button>
      <button data-min="1440">24 horas</button>
      <button data-min="0">Tudo</button>
    </div>
    <div class="info" id="info"></div>
  </div>

  <section class="cards">
    <div class="card">
      <div class="rotulo"><span class="key" style="background:var(--temp)"></span>Temperatura</div>
      <div class="valor" id="v-temp">—</div>
      <div class="det" id="d-temp">&nbsp;</div>
    </div>
    <div class="card">
      <div class="rotulo"><span class="key" style="background:var(--umid)"></span>Umidade relativa</div>
      <div class="valor" id="v-umid">—</div>
      <div class="det" id="d-umid">&nbsp;</div>
    </div>
    <div class="card">
      <div class="rotulo"><span class="sw" style="background:var(--claro)"></span>Luminosidade</div>
      <div class="valor" id="v-luz">—</div>
      <div class="det" id="d-luz">&nbsp;</div>
    </div>
  </section>

  <section class="graficos">
    <div class="painel">
      <h2>Temperatura (°C)</h2>
      <div class="desc">Leituras do DHT11 ao longo do período</div>
      <div class="chart" id="g-temp"></div>
    </div>
    <div class="painel">
      <h2>Umidade relativa (%)</h2>
      <div class="desc">Leituras do DHT11 ao longo do período</div>
      <div class="chart" id="g-umid"></div>
    </div>
  </section>

  <section class="painel" style="margin-bottom:16px">
    <h2>Luminosidade ao longo do tempo</h2>
    <div class="desc">Saída digital do módulo LDR; trechos vazios = sem leitura</div>
    <div class="chart" id="g-luz"></div>
    <div class="legenda">
      <span><i class="sw" style="background:var(--claro)"></i>Claro</span>
      <span><i class="sw" style="background:var(--escuro)"></i>Escuro</span>
    </div>
  </section>

  <section class="painel">
    <h2>Últimas leituras</h2>
    <div class="desc">As 15 mais recentes do período, da mais nova para a mais antiga</div>
    <table>
      <thead><tr><th>Horário</th><th>Dispositivo</th><th class="num">Temperatura</th><th class="num">Umidade</th><th>Luminosidade</th></tr></thead>
      <tbody id="tabela"></tbody>
    </table>
  </section>

  <footer>Atualiza automaticamente a cada 5 segundos · API em <code>/api/dados</code></footer>
</main>

<script>
(() => {
  const INTERVALO_ESP = 10;          // segundos entre envios do ESP32
  const LACUNA_MS = INTERVALO_ESP * 4.5 * 1000; // acima disso, a linha é interrompida
  let minutos = 60;
  let ultimoPacote = null;

  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const fmt = (v, casas) => v == null ? '—' : v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
  const hora = d => d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const horaCurta = (d, longo) => longo
    ? d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs, pai) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (pai) pai.appendChild(e);
    return e;
  };

  function passoBonito(bruto) {
    const p = Math.pow(10, Math.floor(Math.log10(bruto)));
    const f = bruto / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }

  function dominioX(itens, agora) {
    const fim = agora.getTime();
    const ini = minutos > 0 ? fim - minutos * 60000 : (itens.length ? itens[0].d.getTime() : fim - 60000);
    return [ini, Math.max(fim, ini + 60000)];
  }

  function ticksX(x0, x1) {
    const passos = [60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400].map(s => s * 1000);
    const passo = passos.find(p => (x1 - x0) / p <= 6) || 86400000 * Math.ceil((x1 - x0) / 86400000 / 6);
    const off = new Date().getTimezoneOffset() * 60000;
    const t = [];
    for (let v = Math.ceil((x0 - off) / passo) * passo + off; v <= x1; v += passo) t.push(v);
    return t;
  }

  function mostrarTip(tip, caixa, px, py, html) {
    tip.replaceChildren(...html);
    tip.style.display = 'block';
    const w = tip.offsetWidth, W = caixa.clientWidth;
    let left = px + 14;
    if (left + w > W) left = px - w - 14;
    tip.style.left = Math.max(0, left) + 'px';
    tip.style.top = Math.max(0, py - 48) + 'px';
  }
  const linhaTip = (forte, fraco) => {
    const b = document.createElement('b'); b.textContent = forte;
    const s = document.createElement('div'); s.className = 't'; s.textContent = fraco;
    return [b, s];
  };

  function graficoLinha(caixa, itens, chave, cor, unidade, casas, agora) {
    caixa.replaceChildren();
    const pts = itens.filter(i => i[chave] != null);
    if (!pts.length) {
      const v = document.createElement('div'); v.className = 'vazio';
      v.textContent = 'Sem leituras neste período.'; caixa.appendChild(v); return;
    }
    const W = caixa.clientWidth, H = 230, m = { l: 44, r: 16, t: 12, b: 28 };
    const [x0, x1] = dominioX(itens, agora);
    let lo = Math.min(...pts.map(p => p[chave])), hi = Math.max(...pts.map(p => p[chave]));
    const folga = Math.max((hi - lo) * 0.25, chave === 'umidade' ? 4 : 1);
    lo -= folga; hi += folga;
    if (chave === 'umidade') { lo = Math.max(0, lo); hi = Math.min(100, hi); }
    const passo = passoBonito((hi - lo) / 4);
    lo = Math.floor(lo / passo) * passo; hi = Math.ceil(hi / passo) * passo;
    const X = t => m.l + (t - x0) / (x1 - x0) * (W - m.l - m.r);
    const Y = v => H - m.b - (v - lo) / (hi - lo) * (H - m.t - m.b);

    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, height: H, role: 'img',
      'aria-label': `${chave} ao longo do período` }, caixa);
    const casasTick = passo < 1 ? 1 : 0;
    for (let v = lo; v <= hi + 1e-9; v += passo) {
      el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: css('--grid'), 'stroke-width': 1 }, svg);
      const tx = el('text', { x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end', 'font-size': 11.5, fill: css('--muted'),
        style: 'font-variant-numeric: tabular-nums' }, svg);
      tx.textContent = fmt(v, casasTick);
    }
    el('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: css('--axis'), 'stroke-width': 1 }, svg);
    const longo = (x1 - x0) > 86400000;
    for (const t of ticksX(x0, x1)) {
      const tx = el('text', { x: X(t), y: H - 8, 'text-anchor': 'middle', 'font-size': 11.5, fill: css('--muted') }, svg);
      tx.textContent = horaCurta(new Date(t), longo);
    }

    let d = '', ant = null;
    for (const p of pts) {
      const t = p.d.getTime();
      d += (ant && t - ant <= LACUNA_MS ? 'L' : 'M') + X(t).toFixed(1) + ' ' + Y(p[chave]).toFixed(1);
      ant = t;
    }
    el('path', { d, fill: 'none', stroke: cor, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
    const ult = pts[pts.length - 1];
    el('circle', { cx: X(ult.d.getTime()), cy: Y(ult[chave]), r: 5, fill: cor, stroke: css('--surface'), 'stroke-width': 2 }, svg);

    // camada de hover: linha guia + ponto + tooltip
    const guia = el('line', { y1: m.t, y2: H - m.b, stroke: css('--axis'), 'stroke-width': 1, visibility: 'hidden' }, svg);
    const ponto = el('circle', { r: 5, fill: cor, stroke: css('--surface'), 'stroke-width': 2, visibility: 'hidden' }, svg);
    const area = el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: 'transparent', tabindex: 0 }, svg);
    const tip = document.createElement('div'); tip.className = 'tip'; caixa.appendChild(tip);
    const focar = p => {
      const px = X(p.d.getTime()), py = Y(p[chave]);
      guia.setAttribute('x1', px); guia.setAttribute('x2', px); guia.setAttribute('visibility', 'visible');
      ponto.setAttribute('cx', px); ponto.setAttribute('cy', py); ponto.setAttribute('visibility', 'visible');
      mostrarTip(tip, caixa, px * caixa.clientWidth / W, py, linhaTip(fmt(p[chave], casas) + ' ' + unidade, hora(p.d)));
    };
    const esconder = () => { guia.setAttribute('visibility', 'hidden'); ponto.setAttribute('visibility', 'hidden'); tip.style.display = 'none'; };
    area.addEventListener('pointermove', ev => {
      const r = svg.getBoundingClientRect();
      const t = x0 + ((ev.clientX - r.left) * W / r.width - m.l) / (W - m.l - m.r) * (x1 - x0);
      let melhor = pts[0];
      for (const p of pts) if (Math.abs(p.d - t) < Math.abs(melhor.d - t)) melhor = p;
      focar(melhor);
    });
    area.addEventListener('pointerleave', esconder);
    area.addEventListener('focus', () => focar(ult));
    area.addEventListener('blur', esconder);
  }

  function faixaLuz(caixa, itens, agora) {
    caixa.replaceChildren();
    const pts = itens.filter(i => i.luminosidade === 'claro' || i.luminosidade === 'escuro');
    if (!pts.length) {
      const v = document.createElement('div'); v.className = 'vazio'; v.style.padding = '20px 0';
      v.textContent = 'Sem leituras neste período.'; caixa.appendChild(v); return;
    }
    const W = caixa.clientWidth, H = 64, m = { l: 44, r: 16, t: 6, b: 26 };
    const [x0, x1] = dominioX(itens, agora);
    const X = t => m.l + (Math.min(Math.max(t, x0), x1) - x0) / (x1 - x0) * (W - m.l - m.r);
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, height: H, role: 'img', 'aria-label': 'Luminosidade ao longo do período' }, caixa);
    el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, rx: 4, fill: css('--wash') }, svg);
    const tip = document.createElement('div'); tip.className = 'tip'; caixa.appendChild(tip);
    // junta leituras seguidas com o mesmo estado em um único trecho
    const trechos = [];
    pts.forEach((p, i) => {
      const t0 = p.d.getTime();
      const prox = pts[i + 1] ? pts[i + 1].d.getTime() : Math.min(t0 + INTERVALO_ESP * 1000, agora.getTime());
      const t1 = (prox - t0 <= LACUNA_MS) ? prox : t0 + INTERVALO_ESP * 1000;
      const u = trechos[trechos.length - 1];
      if (u && u.estado === p.luminosidade && u.fim === t0) { u.fim = t1; u.n++; }
      else trechos.push({ estado: p.luminosidade, ini: t0, fim: t1, n: 1 });
    });
    for (const tr of trechos) {
      const xa = X(tr.ini), xb = X(tr.fim);
      const r = el('rect', { x: xa, y: m.t, width: Math.max(xb - xa, 1.5), height: H - m.t - m.b,
        fill: tr.estado === 'claro' ? css('--claro') : css('--escuro') }, svg);
      r.addEventListener('pointermove', ev => {
        const b = caixa.getBoundingClientRect();
        mostrarTip(tip, caixa, ev.clientX - b.left, 40,
          linhaTip(tr.estado === 'claro' ? 'Claro' : 'Escuro',
            `${hora(new Date(tr.ini))} a ${hora(new Date(tr.fim))} · ${tr.n} leituras`));
      });
      r.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
    }
    const longo = (x1 - x0) > 86400000;
    for (const t of ticksX(x0, x1)) {
      const tx = el('text', { x: X(t), y: H - 6, 'text-anchor': 'middle', 'font-size': 11.5, fill: css('--muted') }, svg);
      tx.textContent = horaCurta(new Date(t), longo);
    }
  }

  function icone(tipo) {
    const svg = el('svg', { viewBox: '0 0 16 16', 'aria-hidden': 'true' });
    if (tipo === 'ok') {
      el('circle', { cx: 8, cy: 8, r: 7, fill: css('--good') }, svg);
      el('path', { d: 'M4.5 8.2l2.2 2.2 4.6-4.8', fill: 'none', stroke: '#fff', 'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
    } else {
      el('path', { d: 'M8 1.5l7 12.5H1z', fill: css('--warning') }, svg);
      el('path', { d: 'M8 6v4', stroke: '#0b0b0b', 'stroke-width': 1.6, 'stroke-linecap': 'round' }, svg);
      el('circle', { cx: 8, cy: 12, r: 0.9, fill: '#0b0b0b' }, svg);
    }
    return svg;
  }

  function desenhar(p) {
    const agora = new Date(p.agora);
    const itens = p.itens.map(i => ({ ...i, d: new Date(i.t) }));
    const ult = p.ultima ? { ...p.ultima, d: new Date(p.ultima.t) } : null;

    // status de conexão
    const st = document.getElementById('status');
    const idade = ult ? (agora - ult.d) / 1000 : Infinity;
    if (idade <= INTERVALO_ESP * 3) {
      st.replaceChildren(icone('ok'), document.createTextNode('Recebendo dados · ' + ult.dispositivo));
    } else {
      const txt = ult ? 'Sem dados há ' + (idade < 120 ? Math.round(idade) + ' s' : Math.round(idade / 60) + ' min') : 'Aguardando o ESP32';
      st.replaceChildren(icone('aviso'), document.createTextNode(txt));
    }
    document.getElementById('info').textContent =
      `${itens.length.toLocaleString('pt-BR')} leituras no período · ${p.total.toLocaleString('pt-BR')} no banco` +
      (ult ? ` · última às ${hora(ult.d)}` : '');

    // cartões
    const resumo = (chave, casas, unidade) => {
      const vs = itens.map(i => i[chave]).filter(v => v != null);
      return vs.length ? `mín ${fmt(Math.min(...vs), casas)} · máx ${fmt(Math.max(...vs), casas)} ${unidade} no período` : 'sem leituras no período';
    };
    const valor = (id, v, casas, unidade) => {
      const e = document.getElementById(id);
      if (v == null) { e.textContent = '—'; return; }
      const s = document.createElement('small'); s.textContent = unidade;
      e.replaceChildren(document.createTextNode(fmt(v, casas)), s);
    };
    valor('v-temp', ult && ult.temperatura, 1, '°C');
    valor('v-umid', ult && ult.umidade, 0, '%');
    document.getElementById('d-temp').textContent = resumo('temperatura', 1, '°C');
    document.getElementById('d-umid').textContent = resumo('umidade', 0, '%');
    document.getElementById('v-luz').textContent = !ult ? '—' : ult.luminosidade === 'claro' ? 'Claro' : ult.luminosidade === 'escuro' ? 'Escuro' : '—';
    const luz = itens.filter(i => i.luminosidade === 'claro' || i.luminosidade === 'escuro');
    document.getElementById('d-luz').textContent = luz.length
      ? `claro em ${Math.round(luz.filter(i => i.luminosidade === 'claro').length / luz.length * 100)} % das leituras do período`
      : 'sem leituras no período';

    // gráficos
    graficoLinha(document.getElementById('g-temp'), itens, 'temperatura', css('--temp'), '°C', 1, agora);
    graficoLinha(document.getElementById('g-umid'), itens, 'umidade', css('--umid'), '%', 0, agora);
    faixaLuz(document.getElementById('g-luz'), itens, agora);

    // tabela
    const corpo = document.getElementById('tabela');
    const linhas = itens.slice(-15).reverse().map(i => {
      const tr = document.createElement('tr');
      const td = (txt, cls) => { const c = document.createElement('td'); if (cls) c.className = cls; c.textContent = txt; tr.appendChild(c); return c; };
      td(i.d.toLocaleString('pt-BR'));
      td(i.dispositivo || '—');
      td(i.temperatura == null ? '—' : fmt(i.temperatura, 1) + ' °C', 'num');
      td(i.umidade == null ? '—' : fmt(i.umidade, 0) + ' %', 'num');
      const c = td('');
      const sw = document.createElement('i'); sw.className = 'sw';
      sw.style.background = i.luminosidade === 'claro' ? 'var(--claro)' : 'var(--escuro)';
      const sp = document.createElement('span'); sp.className = 'pill';
      sp.append(sw, document.createTextNode(i.luminosidade === 'claro' ? 'Claro' : i.luminosidade === 'escuro' ? 'Escuro' : (i.luminosidade || '—')));
      c.appendChild(sp);
      return tr;
    });
    if (!linhas.length) {
      const tr = document.createElement('tr'); const c = document.createElement('td');
      c.colSpan = 5; c.className = 'vazio'; c.style.padding = '24px 0';
      c.textContent = 'Nenhuma leitura no período. Ligue o ESP32 e aguarde alguns segundos.';
      tr.appendChild(c); linhas.push(tr);
    }
    corpo.replaceChildren(...linhas);
  }

  async function atualizar() {
    try {
      const r = await fetch('/api/dados?minutos=' + minutos, { cache: 'no-store' });
      ultimoPacote = await r.json();
      desenhar(ultimoPacote);
    } catch (e) {
      const st = document.getElementById('status');
      st.replaceChildren(icone('aviso'), document.createTextNode('Servidor fora do ar'));
    }
  }

  document.querySelectorAll('.periodos button').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.periodos button').forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', 'true');
    minutos = Number(b.dataset.min);
    atualizar();
  }));
  let espera;
  window.addEventListener('resize', () => { clearTimeout(espera); espera = setTimeout(() => ultimoPacote && desenhar(ultimoPacote), 150); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => ultimoPacote && desenhar(ultimoPacote));

  atualizar();
  setInterval(atualizar, 5000);
})();
</script>
</body>
</html>
"""


@app.get("/")
def pagina():
    return Response(PAGINA, mimetype="text/html")


if __name__ == "__main__":
    try:
        client.admin.command("ping")
    except Exception:
        raise SystemExit(
            f"Não consegui conectar ao MongoDB em {MONGO_URI}. "
            "Inicie o MongoDB e rode de novo."
        )
    # host 0.0.0.0 para o ESP32 conseguir acessar pela rede
    app.run(host="0.0.0.0", port=5000)
