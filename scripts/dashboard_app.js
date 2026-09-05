(function () {
  "use strict";
  var D = window.__DATA__;

  var SECTOR_LABELS = {
    "market_general": "Mercado general (EE.UU.)",
    "market_general_eu": "Mercado general (Europa)",
    "sector:tecnologia": "Tecnología",
    "sector:energia": "Energía",
    "sector:salud": "Salud",
    "sector:financiero": "Financiero",
    "sector:consumo": "Consumo",
    "sector:industrial": "Industrial",
    "sector:materiales": "Materiales",
    "sector:inmobiliario": "Inmobiliario",
    "sector:utilities": "Utilities",
    "sector:comunicaciones": "Comunicaciones",
    "sector:cripto": "Cripto",
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtMoney(n) {
    n = Number(n);
    if (!isFinite(n)) return "—";
    var abs = Math.abs(n);
    if (abs >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
    if (abs >= 1e3) return "$" + (n / 1e3).toFixed(1) + "K";
    return "$" + n.toFixed(0);
  }
  function fmtUSD(n) {
    return "$" + Math.round(n).toLocaleString("en-US");
  }
  function fmtEUR(n) {
    return Math.round(n).toLocaleString("es-ES") + " €";
  }
  function pctSpan(n) {
    n = Number(n);
    var cls = n > 0 ? "pos" : (n < 0 ? "neg" : "flat");
    var arrow = n > 0 ? "▲" : (n < 0 ? "▼" : "▬");
    return '<span class="pct ' + cls + '">' + arrow + " " + Math.abs(n).toFixed(2) + "%</span>";
  }
  function sentColor(compound) {
    if (compound >= 0.15) return "pos";
    if (compound <= -0.15) return "neg";
    return "neu";
  }
  function timeAgo(iso) {
    try {
      var d = new Date(iso);
      var diffMin = Math.round((Date.now() - d.getTime()) / 60000);
      if (diffMin < 1) return "justo ahora";
      if (diffMin < 60) return "hace " + diffMin + " min";
      var h = Math.round(diffMin / 60);
      if (h < 24) return "hace " + h + " h";
      return "hace " + Math.round(h / 24) + " d";
    } catch (e) { return ""; }
  }

  /* ---------------- Tabs ---------------- */
  var tabButtons = Array.prototype.slice.call(document.querySelectorAll(".tab-btn"));
  var screens = {};
  Array.prototype.slice.call(document.querySelectorAll(".screen")).forEach(function (el) {
    screens[el.dataset.tab] = el;
  });

  function activateTab(name) {
    tabButtons.forEach(function (b) { b.classList.toggle("active", b.dataset.tab === name); });
    Object.keys(screens).forEach(function (k) {
      var el = screens[k];
      if (k === name) {
        el.hidden = false;
        el.classList.remove("enter");
        void el.offsetWidth;
        el.classList.add("enter");
      } else {
        el.hidden = true;
      }
    });
    window.scrollTo(0, 0);
  }
  tabButtons.forEach(function (b) {
    b.addEventListener("click", function () { activateTab(b.dataset.tab); });
  });

  /* ---------------- HOY ---------------- */
  function renderHoy() {
    var gen = (D.news.sentiment_by_category.market_general || { avg_compound: 0, n: 0 });
    var genEu = (D.news.sentiment_by_category.market_general_eu || { avg_compound: 0, n: 0 });
    var avg = (gen.avg_compound + genEu.avg_compound) / 2;
    var mood = avg >= 0.15 ? "Positivo" : (avg <= -0.15 ? "Cauteloso" : "Neutral");
    document.getElementById("hero-value").textContent = mood;
    document.getElementById("hero-sub").textContent =
      "Puntaje " + (avg >= 0 ? "+" : "") + avg.toFixed(2) + " · basado en " + (gen.n + genEu.n) + " noticias · EE.UU. + Europa";

    document.getElementById("stat-news").textContent = D.news.items.length;
    document.getElementById("stat-sectors").textContent = Object.keys(D.news.sentiment_by_category).length;
    document.getElementById("stat-funds").textContent = D.funds_13f.filter(function (f) { return !f.error; }).length;
    document.getElementById("stat-alerts").textContent = D.alerts.length;

    var list = document.getElementById("alerts-list");
    var realAlerts = D.alerts.filter(function (a) { return a.indexOf("Primer snapshot 13F") !== 0; });
    if (!realAlerts.length) {
      list.innerHTML = '<div class="empty-state">Sin eventos destacados en este ciclo. Todo dentro de rangos normales.</div>';
    } else {
      list.innerHTML = realAlerts.map(function (a) {
        var cls = /baj|-\d|cerró|negativ/i.test(a) ? "neg" : (/sub|abrió|nueva|positiv/i.test(a) ? "pos" : "neu");
        return '<div class="row"><span class="dot" style="background:var(--' +
          (cls === "pos" ? "gain" : cls === "neg" ? "loss" : "ink-tertiary") + ')"></span>' +
          '<div class="main"><div class="title">' + esc(a) + "</div></div></div>";
      }).join("");
    }
  }

  /* ---------------- NOTICIAS ---------------- */
  var newsState = { cat: "market_general" };
  function renderNewsChips() {
    var cats = Object.keys(D.news.sentiment_by_category);
    var known = Object.keys(SECTOR_LABELS).filter(function (c) { return cats.indexOf(c) !== -1; });
    var rest = cats.filter(function (c) { return known.indexOf(c) === -1; });
    var all = known.concat(rest);
    var row = document.getElementById("news-chip-row");
    row.innerHTML = all.map(function (c) {
      var label = SECTOR_LABELS[c] || c;
      return '<button class="chip' + (c === newsState.cat ? " active" : "") + '" data-cat="' + esc(c) + '">' + esc(label) + "</button>";
    }).join("");
    Array.prototype.slice.call(row.querySelectorAll(".chip")).forEach(function (btn) {
      btn.addEventListener("click", function () {
        newsState.cat = btn.dataset.cat;
        renderNewsChips();
        renderNewsList();
      });
    });
  }
  function renderNewsList() {
    var items = D.news.items.filter(function (it) { return it.category === newsState.cat; });
    items.sort(function (a, b) {
      return Math.abs((b.sentiment || {}).compound || 0) - Math.abs((a.sentiment || {}).compound || 0);
    });
    var el = document.getElementById("news-list");
    if (!items.length) {
      el.innerHTML = '<div class="empty-state">Sin noticias recientes en esta categoría.</div>';
      return;
    }
    el.innerHTML = items.slice(0, 30).map(function (it) {
      var s = it.sentiment || { compound: 0, label: "neutral" };
      var cls = sentColor(s.compound);
      var dotVar = cls === "pos" ? "gain" : cls === "neg" ? "loss" : "ink-tertiary";
      return '<a class="row" href="' + esc(it.link) + '" target="_blank" rel="noopener">' +
        '<span class="dot" style="background:var(--' + dotVar + ')"></span>' +
        '<div class="main"><div class="title">' + esc(it.title) + '</div>' +
        '<div class="meta"><span>' + esc(it.source) + "</span><span>·</span><span>" + esc(s.label) + "</span></div></div></a>";
    }).join("");
  }

  /* ---------------- MERCADO ---------------- */
  var moversState = { region: "us", kind: "gainers" };
  function renderMoversControls() {
    var regionSeg = document.getElementById("region-segment");
    Array.prototype.slice.call(regionSeg.querySelectorAll(".segment")).forEach(function (b) {
      b.classList.toggle("active", b.dataset.val === moversState.region);
    });
    var kindSeg = document.getElementById("kind-segment");
    var kindsForRegion = moversState.region === "us" ? ["gainers", "losers", "active"] : ["gainers", "losers"];
    kindSeg.innerHTML = kindsForRegion.map(function (k) {
      var label = k === "gainers" ? "Subas" : (k === "losers" ? "Bajas" : "Activas");
      return '<button class="segment' + (k === moversState.kind ? " active" : "") + '" data-val="' + k + '">' + label + "</button>";
    }).join("");
    if (kindsForRegion.indexOf(moversState.kind) === -1) moversState.kind = "gainers";
    Array.prototype.slice.call(kindSeg.querySelectorAll(".segment")).forEach(function (b) {
      b.classList.toggle("active", b.dataset.val === moversState.kind);
      b.addEventListener("click", function () { moversState.kind = b.dataset.val; renderMoversControls(); renderMoversList(); });
    });
  }
  function renderMoversList() {
    var key = moversState.region + "_top_" + moversState.kind;
    if (moversState.kind === "active") key = "us_most_active";
    var rows = D.market_movers[key] || [];
    var el = document.getElementById("movers-list");
    if (!rows.length) {
      el.innerHTML = '<div class="empty-state">Sin datos disponibles.</div>';
      return;
    }
    el.innerHTML = rows.slice(0, 10).map(function (r) {
      return '<div class="row"><div class="main"><div class="ticker">' + esc(r.symbol) + '</div>' +
        '<div class="name">' + esc(r.name || "") + '</div></div>' +
        '<div class="trail"><div class="num tabular">' + (r.price != null ? r.price : "—") + '</div>' +
        '<div class="sub">' + pctSpan(r.change_pct) + "</div></div></div>";
    }).join("");
  }
  document.addEventListener("DOMContentLoaded", function () {
    var regionSeg = document.getElementById("region-segment");
    Array.prototype.slice.call(regionSeg.querySelectorAll(".segment")).forEach(function (b) {
      b.addEventListener("click", function () { moversState.region = b.dataset.val; renderMoversControls(); renderMoversList(); });
    });
  });

  /* ---------------- FONDOS ---------------- */
  function renderFunds() {
    var el = document.getElementById("funds-list");
    el.innerHTML = D.funds_13f.map(function (f, idx) {
      if (f.error) {
        return '<div class="row"><div class="main"><div class="title">' + esc(f.fund) + '</div>' +
          '<div class="meta">No disponible: ' + esc(f.error) + "</div></div></div>";
      }
      return '<button class="row" data-fund="' + idx + '"><div class="main"><div class="title">' + esc(f.fund) + '</div>' +
        '<div class="meta">Filing ' + esc(f.filing_date) + " · " + f.total_positions + ' posiciones</div></div>' +
        '<span class="chev">›</span></button>';
    }).join("");
    Array.prototype.slice.call(el.querySelectorAll(".row[data-fund]")).forEach(function (btn) {
      btn.addEventListener("click", function () { openFundSheet(D.funds_13f[Number(btn.dataset.fund)]); });
    });
  }

  var sheetBackdrop = document.getElementById("sheet-backdrop");
  var sheet = document.getElementById("fund-sheet");
  function openFundSheet(fund) {
    document.getElementById("sheet-title").textContent = fund.fund;
    var total = (fund.holdings || []).reduce(function (s, h) { return s + h.value_usd; }, 0);
    var diff = fund.diff_vs_previous;
    var diffHtml = "";
    if (diff && (diff.new_positions.length || diff.closed_positions.length || diff.changed_positions.length)) {
      var badges = [];
      diff.new_positions.slice(0, 4).forEach(function (h) { badges.push('<span class="badge pos">+ ' + esc(titleCase(h.issuer)) + "</span>"); });
      diff.closed_positions.slice(0, 4).forEach(function (h) { badges.push('<span class="badge neg">− ' + esc(titleCase(h.issuer)) + "</span>"); });
      diff.changed_positions.slice(0, 4).forEach(function (h) { badges.push('<span class="badge neu">' + (h.change_pct > 0 ? "+" : "") + h.change_pct + "% " + esc(titleCase(h.issuer)) + "</span>"); });
      diffHtml = '<div class="diff-badges">' + badges.join("") + "</div>";
    }
    var rows = (fund.holdings || []).slice(0, 20).map(function (h) {
      var pct = total ? (h.value_usd / total * 100) : 0;
      return '<div class="row"><div class="main"><div class="title">' + esc(titleCase(h.issuer)) + '</div></div>' +
        '<div class="trail"><div class="num tabular">' + fmtMoney(h.value_usd) + '</div>' +
        '<div class="sub">' + pct.toFixed(1) + "% cartera</div></div></div>";
    }).join("");
    document.getElementById("sheet-body").innerHTML =
      '<div class="fund-meta-line">Filing 13F-HR · ' + esc(fund.filing_date) +
      ' <span style="opacity:.75">(hasta 45 días de retraso)</span></div>' +
      diffHtml + '<div class="list">' + rows + "</div>";
    sheetBackdrop.classList.add("open");
    sheet.classList.add("open");
  }
  function closeSheet() { sheetBackdrop.classList.remove("open"); sheet.classList.remove("open"); }
  sheetBackdrop.addEventListener("click", closeSheet);
  document.getElementById("sheet-close").addEventListener("click", closeSheet);

  function titleCase(s) {
    return String(s || "").toLowerCase().replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  /* ---------------- SENTIMIENTO (dentro de Noticias, arriba) ---------------- */
  function renderSentiment() {
    var cats = Object.keys(D.news.sentiment_by_category);
    var known = Object.keys(SECTOR_LABELS).filter(function (c) { return cats.indexOf(c) !== -1; });
    var el = document.getElementById("sentiment-list");
    el.innerHTML = known.map(function (c) {
      var agg = D.news.sentiment_by_category[c];
      var cls = sentColor(agg.avg_compound);
      var pct = 50 + agg.avg_compound * 50;
      var left = Math.min(50, pct), width = Math.abs(pct - 50);
      var varName = cls === "pos" ? "gain" : cls === "neg" ? "loss" : "ink-tertiary";
      return '<div class="sent-row"><div class="sent-top"><span class="name">' + esc(SECTOR_LABELS[c]) +
        '</span><span class="val" style="color:var(--' + varName + ')">' + (agg.avg_compound >= 0 ? "+" : "") + agg.avg_compound.toFixed(2) + '</span></div>' +
        '<div class="sent-track"><div class="sent-mid"></div><div class="sent-fill" style="left:' + left + '%;width:' + width + '%;background:var(--' + varName + ')"></div></div></div>';
    }).join("");
  }

  /* ---------------- ASESOR ---------------- */
  var ALLOC = {
    "lt2":  { conservador: [0, 30, 70], moderado: [10, 30, 60], agresivo: [20, 30, 50] },
    "2a5":  { conservador: [30, 45, 25], moderado: [50, 35, 15], agresivo: [65, 25, 10] },
    "5a10": { conservador: [45, 40, 15], moderado: [65, 25, 10], agresivo: [80, 15, 5] },
    "10p":  { conservador: [55, 35, 10], moderado: [75, 20, 5], agresivo: [90, 8, 2] },
  };
  var HORIZON_LABELS = { lt2: "Menos de 2 años", "2a5": "2 a 5 años", "5a10": "5 a 10 años", "10p": "10+ años" };

  var advState = { horizon: "5a10", risk: "moderado", emergency: true };

  function wireSegment(id, stateKey, onChange) {
    var el = document.getElementById(id);
    Array.prototype.slice.call(el.querySelectorAll(".segment")).forEach(function (b) {
      b.classList.toggle("active", b.dataset.val === advState[stateKey]);
      b.addEventListener("click", function () {
        advState[stateKey] = b.dataset.val;
        Array.prototype.slice.call(el.querySelectorAll(".segment")).forEach(function (bb) {
          bb.classList.toggle("active", bb === b);
        });
        if (onChange) onChange();
      });
    });
  }

  function initAsesor() {
    wireSegment("horizon-segment", "horizon");
    wireSegment("risk-segment", "risk");
    var sw = document.getElementById("emergency-switch");
    sw.classList.toggle("on", advState.emergency);
    sw.addEventListener("click", function () {
      advState.emergency = !advState.emergency;
      sw.classList.toggle("on", advState.emergency);
    });
    document.getElementById("calc-btn").addEventListener("click", calcAsesor);
  }

  function calcAsesor() {
    var amountInput = document.getElementById("amount-input");
    var amount = parseFloat((amountInput.value || "0").replace(/[^0-9.]/g, "")) || 0;
    var mix = ALLOC[advState.horizon][advState.risk];
    var out = document.getElementById("asesor-result");
    out.hidden = false;

    var emergencyNote = "";
    if (!advState.emergency) {
      emergencyNote =
        '<div class="disclaimer" style="background:var(--warn-soft)"><span class="ic">⚠️</span>' +
        "<div><b>Antes de invertir:</b> la pauta general es tener primero de 3 a 6 meses de gastos esenciales " +
        "en una cuenta líquida separada, como colchón para imprevistos. Si todavía no lo tienes, considera destinar " +
        "parte de este monto a ese fondo antes de invertirlo todo.</div></div>";
    }

    var colors = ["var(--accent)", "var(--gold)", "var(--ink-tertiary)"];
    var labels = ["Acciones (renta variable)", "Bonos (renta fija)", "Efectivo / equivalentes"];
    // Explicación en una frase de qué es cada categoría y, en términos generales
    // (no personalizados, no una recomendación de compra), qué tipo de producto
    // suele usarse para cubrirla — nunca un ticker/empresa concreta.
    var explain = [
      "Fracción invertida en empresas (vía fondos, no acciones sueltas). Es la que más sube y baja a corto plazo, pero la que históricamente más crece a largo plazo.",
      "Préstamos a gobiernos o empresas que pagan un interés. Se mueve mucho menos que las acciones — sirve para suavizar los bajones.",
      "Dinero que se queda líquido y disponible casi al momento (cuenta remunerada, depósito corto). No crece apenas, pero no baja nunca y está ahí si lo necesitas ya.",
    ];
    var vehicles = [
      "Ej. un fondo indexado global diversificado (tipo \"MSCI World\" o \"S&amp;P 500\") — nunca una sola empresa suelta.",
      "Ej. un fondo o ETF de bonos gubernamentales o corporativos a corto/medio plazo.",
      "Ej. una cuenta remunerada, depósito a plazo fijo, o fondo monetario de tu banco.",
    ];
    var bar = mix.map(function (p, i) {
      return '<span style="width:' + p + '%;background:' + colors[i] + '"></span>';
    }).join("");
    var legend = mix.map(function (p, i) {
      return '<div class="li"><span class="sw" style="background:' + colors[i] + '"></span>' + labels[i] + " · " + p + "%</div>";
    }).join("");

    // Tarjeta por categoría: nombre, qué es en una frase, cuánto le toca del
    // monto (si el usuario puso uno) y un ejemplo genérico de dónde suele ir.
    var catCards = mix.map(function (p, i) {
      if (p <= 0) return "";
      return '<div class="card" style="margin-top:10px">' +
        '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px">' +
        '<div class="title" style="font-weight:700">' + labels[i] + "</div>" +
        '<div class="num tabular" style="font-weight:700">' + (amount ? fmtEUR(amount * p / 100) : p + "%") + "</div>" +
        "</div>" +
        '<p style="font-size:13px;color:var(--ink-soft);line-height:1.45;margin:6px 0 8px">' + explain[i] + "</p>" +
        '<p style="font-size:12.5px;color:var(--ink-soft);line-height:1.4;margin:0"><b style="color:var(--ink)">¿Dónde suele ir esto?</b> ' + vehicles[i] + "</p>" +
        "</div>";
    }).join("");

    var gen = (D.news.sentiment_by_category.market_general || { avg_compound: 0 });
    var moodTxt = gen.avg_compound >= 0.15 ? "optimista" : (gen.avg_compound <= -0.15 ? "cauteloso" : "neutral");

    out.innerHTML =
      emergencyNote +
      '<div class="card">' +
      '<div class="section-title" style="margin-top:0">' + (amount ? "Cómo repartir " + fmtEUR(amount) : "Asignación sugerida") + '</div>' +
      '<div class="alloc-bar">' + bar + "</div>" +
      '<div class="alloc-legend">' + legend + "</div>" +
      '<p style="font-size:13.5px;color:var(--ink-soft);line-height:1.5;margin:14px 0 0">' +
      "Para un horizonte de <b style=\"color:var(--ink)\">" + HORIZON_LABELS[advState.horizon] + "</b> y una tolerancia al riesgo " +
      "<b style=\"color:var(--ink)\">" + advState.risk + "</b>, esta es una distribución de referencia entre grandes categorías de activos — " +
      "no un consejo personalizado ni una lista de acciones concretas para comprar. Conviene revisar y reequilibrar la mezcla una o dos veces al año." +
      "</p></div>" +
      catCards +
      '<div class="section-title">Contexto de hoy</div>' +
      '<div class="card"><p style="font-size:13px;color:var(--ink-soft);line-height:1.5;margin:0">' +
      "El sentimiento general del mercado ahora mismo es <b style=\"color:var(--ink)\">" + moodTxt + "</b>. " +
      "Esto es ruido de corto plazo — no debería cambiar una estrategia pensada para " + HORIZON_LABELS[advState.horizon].toLowerCase() +
      ". Con un monto pequeño y puntual como este, lo que más importa no es acertar \"dónde\" sino la costumbre de aportar seguido — " +
      "aportar de forma periódica (en vez de todo de una vez) suele suavizar el efecto de comprar justo en un mal momento." +
      "</p></div>" +
      '<div class="disclaimer" style="margin-top:14px"><span class="ic">ⓘ</span><div>Esto es una guía educativa general sobre <b>tipos</b> de activos, no asesoría financiera personalizada ni una recomendación de compra/venta de ningún producto concreto. ' +
      "No soy asesor financiero certificado — para decisiones grandes, conviene contrastar con un profesional.</div></div>";

    out.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* ---------------- init ---------------- */
  renderHoy();
  renderSentiment();
  renderNewsChips();
  renderNewsList();
  renderMoversControls();
  renderMoversList();
  renderFunds();
  initAsesor();
  activateTab("hoy");
})();
