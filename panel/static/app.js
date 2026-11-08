/* 予其真实 · P1 前端（无依赖、无 CDN）
   只读：这里没有一处写接口；所有交互都留在本页。 */
(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };
  var DATA = window.__BOOT__ || null;
  var SERVER_EPOCH = DATA ? DATA.epoch : null;
  var CLIENT_AT = Date.now();
  var LAST_OK = DATA ? Date.now() : 0;
  var OFFLINE = false;
  var RETRY = null;
  var CHART_GEOM = null;
  var EMO = [];
  var MASK = true;
  var FEATURES = {};
  var MEM_OPEN_ID = null;
  var MEM_VIEW = false;
  var SIM_VIEW = false;
  var SIM_SCENARIO = null;
  var CMD_VIEW = false;

  try {
    var params = new URLSearchParams(window.location.search);
    var query = params.get("mask");
    if (query === "0") MASK = false;
    else if (query === "1") MASK = true;
    else if (window.localStorage.getItem("brainMask") === "0") MASK = false;
    MEM_VIEW = params.get("view") === "memory";
    SIM_VIEW = params.get("view") === "sim";
    SIM_SCENARIO = params.get("scenario");
    CMD_VIEW = params.get("view") === "cmd";
    MEM_OPEN_ID = params.get("open");
  } catch (e) { /* 本地存储不可用就按默认上镜模式 */ }

  var WEEK = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function serverNow() {
    if (SERVER_EPOCH == null) return Date.now() / 1000;
    return SERVER_EPOCH + (Date.now() - CLIENT_AT) / 1000;
  }
  function fmtAge(sec) {
    if (sec == null) return "—";
    if (sec < 90) return "刚刚";
    if (sec < 3600) return Math.round(sec / 60) + " 分钟前";
    if (sec < 86400) return (sec / 3600).toFixed(1) + " 小时前";
    return (sec / 86400).toFixed(1) + " 天前";
  }
  function fmtDur(min) {
    min = Math.max(0, Math.round(min));
    var h = Math.floor(min / 60), m = min % 60;
    if (h && m) return h + " 小时 " + m + " 分";
    if (h) return h + " 小时";
    return m + " 分钟";
  }
  function setText(id, value) {
    var el = $("#" + id);
    if (el) el.textContent = value == null ? "" : value;
  }
  function setWidth(id, percent) {
    var el = $("#" + id);
    if (el) el.style.width = Math.max(0, Math.min(100, percent || 0)) + "%";
  }

  /* ---------------- 渲染 ---------------- */
  function applyProfile(data) {
    var profile = (data && data.profile) || {};
    var features = (data && data.features) || {};
    FEATURES = features;
    setText("her-name", profile.her_name || "她");
    setText("brand-title", profile.title || "予其真实");
    setText("brand-sub", profile.subtitle || "COMPANION · STATE");
    document.title = (profile.her_name || "她") + " · " + (profile.title || "予其真实");
    [["open-sim", "sim"], ["open-memory", "memory"], ["open-command", "commands"]].forEach(function (pair) {
      var el = $("#" + pair[0]);
      if (el) el.style.display = features[pair[1]] === false ? "none" : "";
    });
    var actions = $("#mem-actions");
    if (actions) actions.style.display = features.memory_edit ? "" : "none";
  }

  function render(data) {
    DATA = data;
    SERVER_EPOCH = data.epoch;
    CLIENT_AT = Date.now();
    LAST_OK = Date.now();

    applyProfile(data);
    renderClock(true);
    renderNow(data.state);
    renderEmotions(data.emotions);
    renderGrowth(data.growth);
    renderFoot(data);
  }

  function renderClock() {
    var d = new Date(serverNow() * 1000);
    setText("clock", pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds()));
    if (DATA && DATA.state && DATA.state.date) {
      setText("date", DATA.state.date.full + " · " + DATA.state.date.weekday);
    }
    var age = serverNow() - (DATA ? DATA.epoch : serverNow());
    var pill = $("#updated");
    if (pill) {
      pill.textContent = age < 10 ? "刚刚更新" : Math.round(age) + " 秒前更新";
    }
  }

  function updateMaskUI() {
    var btn = $("#maskel-toggle");
    if (btn) btn.setAttribute("aria-pressed", MASK ? "true" : "false");
    var memBtn = $("#memory-mask");
    if (memBtn) memBtn.setAttribute("aria-pressed", MASK ? "true" : "false");
    setText("maskel-label", MASK ? "上镜模式" : "完整模式");
    setText("memory-maskel-label", MASK ? "上镜模式" : "完整模式");
    setText("life-foot-note", MASK ? "上镜模式已遮" : "本机完整可见");
    document.body.classList.toggle("is-masked", MASK);
  }

  function applyMask() {
    updateMaskUI();
    if (DATA) {
      renderNow(DATA.state);
      if (window.__memoryMaskChanged) window.__memoryMaskChanged();
    }
    if (window.__simMaskChanged) window.__simMaskChanged();
  }

  function renderNow(state) {
    if (!state) return;
    var act = state.activity || {};
    setText("activity", act.display || act.label || "——");

    var sub = [];
    if (act.started_text) sub.push("从 " + act.started_text + " 开始");
    if (act.elapsed_text) sub.push("已 " + act.elapsed_text);
    if (act.remaining_text) sub.push(act.remaining_text);
    setText("activity-sub", sub.join(" · "));

    var glyph = (act.display || act.label || "·").charAt(0);
    if ((act.with_owner && act.id === "intimacy") || (act.with_owner && ["sit","lie","cuddle","chat_together","hug","lean","hand","together_idle"].indexOf(act.id) >= 0)) { glyph = "你"; }
    setText("orb-glyph", glyph);
    var orb = $("#orb");
    if (orb) {
      orb.style.setProperty("--orb", act.color || "#8E96C8");
      var p = act.progress == null ? 0 : Math.max(0, Math.min(1, act.progress));
      orb.style.setProperty("--p", (p * 100).toFixed(1));
    }

    var room = state.room || {};
    setText("room", room.short || room.name || "——");
    setText("outfit", (state.outfit && state.outfit.text) || "——");
    setText("weather-inline", (state.weather && state.weather.text) || "——");
    setText("life-date", state.date ? state.date.short : "—");

    var narrative = $("#narrative");
    if (narrative) {
      var lines = state.narrative && state.narrative.length ? state.narrative : ["她正在过自己的日子。"];
      narrative.innerHTML = lines.map(function (line) { return "<span>" + esc(line) + "</span>"; }).join("<br>");
    }

    renderDay(state.day, state.activity);
    renderLife(state.life);
    renderMeters(state);
  }

  function renderLife(life) {
    var box = $("#life-card");
    if (!box) return;
    box.style.display = "";
    var list = $("#life-list");
    if (MASK) {
      list.innerHTML = '<div class="life-mask">' +
        '<div class="maskel-line w1"></div><div class="maskel-line w2"></div><div class="maskel-line w3"></div>' +
        '<div class="maskel-tag">上镜模式 · 已遮</div></div>';
      return;
    }
    if (!life || !life.available || !life.events || !life.events.length) {
      list.innerHTML = '<div class="life-mask"><div class="maskel-tag">今天还没有记录</div></div>';
      return;
    }
    var html = life.events.map(function (item) {
      return '<div class="life-item" title="' + esc(item) + '">' + esc(item) + "</div>";
    }).join("");
    if (life.discovery) {
      html += '<div class="life-discovery" title="' + esc(life.discovery) + '"><b>发现</b>' + esc(life.discovery) + "</div>";
    }
    list.innerHTML = html;
  }

  function renderDay(day, act) {
    if (!day) return;
    var track = $("#ribbon-track");
    var segs = day.segments || [];
    track.innerHTML = segs.map(function (seg) {
      return '<div class="seg" style="left:' + seg.left + "%;width:" + seg.width + "%;background:" + seg.color + '" title="' +
        esc(seg.start_text + " · " + seg.label + " · " + fmtDur(seg.minutes)) + '"></div>';
    }).join("");

    var nowPct = Math.max(0, Math.min(100, day.elapsed_seconds / 86400 * 100));
    $("#ribbon-now").style.left = nowPct + "%";
    $("#ribbon-future").style.left = nowPct + "%";
    setText("today-sub", "已过 " + day.elapsed_text);

    var byId = {}, order = [];
    segs.forEach(function (seg) {
      if (!byId[seg.id]) { byId[seg.id] = { label: seg.label, color: seg.color, minutes: 0 }; order.push(seg.id); }
      byId[seg.id].minutes += seg.minutes;
    });
    order.sort(function (a, b) { return byId[b].minutes - byId[a].minutes; });
    $("#legend").innerHTML = order.slice(0, 4).map(function (id) {
      var item = byId[id];
      return '<span><i style="background:' + item.color + '"></i>' + esc(item.label) + " <b>" + esc(fmtDur(item.minutes)) + "</b></span>";
    }).join("");
  }

  function renderMeters(state) {
    var body = state.body || {};
    var mood = state.mood || {};
    var growth = state.growth || {};

    setText("energy-val", body.energy_percent == null ? "——" : body.energy_percent + "%");
    setWidth("energy-bar", body.energy_percent == null ? 0 : body.energy_percent);

    setText("mood-val", mood.available ? mood.percent + "%" : "——");
    setWidth("mood-bar", mood.available ? mood.percent : 0);
    setText("mood-sub", mood.available ? mood.text : " ");

    var desireMeter = $("#meter-desire");
    var desireLabel = $("#desire-label");
    if (MASK) {
      if (desireLabel) desireLabel.textContent = "私密";
      setText("desire-val", "已遮");
      setWidth("desire-bar", 0);
      if (desireMeter) desireMeter.classList.add("masked");
    } else {
      if (desireLabel) desireLabel.textContent = "欲望";
      setText("desire-val", body.libido_percent == null ? "——" : body.libido_percent + "%");
      setWidth("desire-bar", body.libido_percent == null ? 0 : body.libido_percent);
      if (desireMeter) desireMeter.classList.remove("masked");
    }

    setText("growth-val", growth.count == null ? "——" : growth.count + " 条");
    var dots = "";
    var total = growth.count == null ? 0 : Math.min(5, growth.count);
    for (var i = 0; i < 5; i++) dots += '<i class="' + (i < total ? "" : "ghost") + '"></i>';
    $("#growth-dots").innerHTML = dots;
    var note = growth.count == null ? "暂无" : "";
    setText("growth-note", note);
  }

  function renderEmotions(emo) {
    if (!emo) return;
    EMO = emo;
    setText("emotion-mode", emo.mode_label || "");

    var hotName = emo.strongest || "";
    $("#emo-row").innerHTML = (emo.emotions || []).map(function (item) {
      var cur = item.current || {};
      var peak = Math.round((item.peak || 0) * 100);
      var hot = item.name === hotName && (cur.value || 0) > 0.02;
      return '<div class="emo' + (hot ? " hot" : "") + '" style="--c:' + item.color + '">' +
        '<div class="emo-head"><span class="emo-name">' + esc(item.name) + '</span>' +
        '<span class="emo-peak" title="24 小时内到过的最高值">今日最高 ' + peak + '%</span></div>' +
        '<div class="emo-val">' + Math.round(cur.percent || 0) + '<small>%</small></div>' +
        '<div class="emo-bar"><i style="width:' + Math.round(cur.percent || 0) + '%"></i></div>' +
        "</div>";
    }).join("");

    var events = emo.events || [];
    $("#chart-empty").classList.toggle("show", events.length === 0);

    var topNow = { name: "", percent: 0 };
    var bestVal = -1;
    (emo.emotions || []).forEach(function (item) {
      var cur = item.current || {};
      if ((cur.value || 0) > bestVal) {
        bestVal = cur.value || 0;
        topNow = { name: item.name, percent: Math.round(cur.percent || 0) };
      }
    });
    var nowLine = $("#emo-now");
    if (nowLine) {
      nowLine.innerHTML = topNow.percent > 2
        ? "此刻 · <b>" + esc(topNow.name) + " " + topNow.percent + "%</b>"
        : "此刻 · <b>平静</b>，情绪都淡下去了";
    }

    renderEventStrip(events);
    requestAnimationFrame(drawChart);
  }

  function renderEventStrip(events) {
    var box = $("#events");
    if (!events.length) {
      box.innerHTML = '<div class="ev-empty">过去 24 小时，她没什么情绪起伏。</div>';
      return;
    }
    var colors = {};
    (EMO.emotions || []).forEach(function (item) { colors[item.name] = item.color; });
    var last = events.slice(-3).reverse();
    box.innerHTML = last.map(function (ev) {
      var name = ev.dom || "";
      var pct = Math.round((ev.e && ev.e[name] ? ev.e[name] : ev.i || 0) * 100);
      var what = ev.label || ev.kind || "";
      if (ev.stimulus) what += "「" + ev.stimulus + "」";
      return '<div class="ev" title="' + esc(ev.at + " · " + (ev.would || "")) + '">' +
        '<span class="ev-time">' + esc((ev.at || "").slice(6, 11)) + "</span>" +
        '<span class="ev-dot" style="background:' + (colors[name] || "#888") + '"></span>' +
        '<span class="ev-name">' + esc(name) + "</span>" +
        '<span class="ev-val">' + pct + "%</span>" +
        '<span class="ev-what">' + esc(what) + "</span>" +
        "</div>";
    }).join("");
  }

  function renderGrowth(growth) {
    if (!growth) return;
    setText("growth-count", growth.count == null ? "——" : growth.count + " 条里程碑");
    var items = (growth.items || []).slice(-5);
    var nodes = items.map(function (item) {
      return '<div class="node">' +
        '<div class="node-date">' + esc(item.date_short) + "</div>" +
        '<div class="node-dot"></div>' +
        '<div class="node-body"><span class="kind">' + esc(item.kind_label || "第一次") + "</span>" +
        "<p>" + esc(item.text) + "</p></div></div>";
    }).join("");
    nodes += '<div class="node ghost"><div class="node-date">现在</div><div class="node-dot"></div>' +
      '<div class="node-body"><p>还在长</p></div></div>';
    $("#timeline").innerHTML = nodes;
    requestAnimationFrame(layoutTimeline);

    var foot = $("#growth-foot");
    if (!growth.available) {
      foot.textContent = growth.error || "成长库暂时读不到（面板只读副本，不影响她）。";
    } else if (growth.count > 5) {
      foot.textContent = "更早的 " + (growth.count - 5) + " 条记在 growth.db 里；这里只放最近五条。";
    } else if (!items.length) {
      foot.textContent = "还没有成长记录——第一条会自己长出来。";
    } else {
      foot.textContent = "只记第一次：去过的地方、看完的番、学会的事、说出的「不」。";
    }
  }

  function layoutTimeline() {
    var tl = $("#timeline");
    if (!tl) return;
    var dots = tl.querySelectorAll(".node-dot");
    if (!dots.length) return;
    var tr = tl.getBoundingClientRect();
    var dr = dots[dots.length - 1].getBoundingClientRect();
    tl.style.setProperty("--line-end", Math.max(8, tr.right - (dr.left + dr.width / 2)) + "px");
  }

  function renderFoot(data) {
    var fresh = (data.state && data.state.freshness) || {};
    var ages = ["rhythm", "body", "mood"].map(function (key) {
      return fresh[key] ? fresh[key].age_seconds : 0;
    });
    setText("fresh-state", "状态 " + fmtAge(Math.min.apply(null, ages)));

    var events = (data.emotions && data.emotions.events) || [];
    var lastEvent = events.length ? events[events.length - 1].ts : null;
    setText("fresh-emotion", lastEvent ? "最近情绪 " + fmtAge(serverNow() - lastEvent) : "情绪 暂无记录");
  }

  /* ---------------- 24h 曲线 ---------------- */
  function buildSamples(events, from, to) {
    var names = EMO.emotions.map(function (item) { return item.name; });
    var half = {};
    EMO.emotions.forEach(function (item) { half[item.name] = item.half_life || 600; });
    var set = { from: true, to: true };
    var times = [from, to];
    var offsets = [20, 60, 150, 300, 600, 1200, 2400, 4800];
    events.forEach(function (ev) {
      if (ev.ts < from || ev.ts > to) return;
      [ev.ts - 0.5, ev.ts].forEach(function (t) { if (t >= from && t <= to) times.push(t); });
      offsets.forEach(function (off) {
        var t = ev.ts + off;
        if (t >= from && t <= to) times.push(t);
      });
    });
    times.sort(function (a, b) { return a - b; });
    var uniq = [];
    times.forEach(function (t) { if (!uniq.length || t - uniq[uniq.length - 1] > 0.2) uniq.push(t); });

    var vals = {};
    names.forEach(function (n) { vals[n] = 0; });
    var ei = 0;
    var last = uniq[0];
    var out = { ts: uniq, v: {}, max: [], dom: [] };
    names.forEach(function (n) { out.v[n] = []; });

    uniq.forEach(function (t) {
      var dt = t - last;
      if (dt > 0) {
        names.forEach(function (n) {
          vals[n] *= Math.pow(0.5, dt / half[n]);
          if (vals[n] < 0.001) vals[n] = 0;
        });
      }
      while (ei < events.length && events[ei].ts <= t + 1e-6) {
        var ev = events[ei++];
        Object.keys(ev.e || {}).forEach(function (n) {
          if (n in vals) vals[n] = ev.e[n];
        });
      }
      last = t;
      var mx = 0, dm = "";
      names.forEach(function (n) {
        out.v[n].push(vals[n]);
        if (vals[n] > mx) { mx = vals[n]; dm = n; }
      });
      out.max.push(mx);
      out.dom.push(dm);
    });
    return out;
  }

  function drawChart() {
    var canvas = $("#emotion-chart");
    var wrap = $("#chart-wrap");
    if (!canvas || !wrap || !EMO.emotions) return;
    var rect = wrap.getBoundingClientRect();
    var W = Math.max(240, Math.floor(rect.width));
    var H = Math.max(120, Math.floor(rect.height));
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.floor(W * dpr) || canvas.height !== Math.floor(H * dpr)) {
      canvas.width = Math.floor(W * dpr);
      canvas.height = Math.floor(H * dpr);
    }
    var ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    var win = EMO.window || {};
    var from = win.from, to = win.to;
    if (!from || !to || to <= from) return;
    var P = { l: 34, r: 10, t: 12, b: 22 };
    var iw = W - P.l - P.r, ih = H - P.t - P.b;
    var x = function (t) { return P.l + (t - from) / (to - from) * iw; };
    var y = function (v) { return P.t + (1 - Math.max(0, Math.min(1, v))) * ih; };

    ctx.font = "9.5px 'Cascadia Mono', 'Microsoft YaHei UI', monospace";
    ctx.textBaseline = "middle";

    // 横向网格
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v, i) {
      var yy = y(v);
      ctx.strokeStyle = i === 0 || i === 4 ? "rgba(24,66,90,.16)" : "rgba(24,66,90,.06)";
      ctx.beginPath();
      ctx.moveTo(P.l, yy + 0.5);
      ctx.lineTo(W - P.r, yy + 0.5);
      ctx.stroke();
      if (i % 2 === 0) {
        ctx.fillStyle = "rgba(94,116,128,.78)";
        ctx.textAlign = "right";
        ctx.fillText(Math.round(v * 100) + "%", P.l - 8, yy);
      }
    });

    var samples = buildSamples(EMO.events || [], from, to);
    var names = EMO.emotions.map(function (item) { return item.name; });
    var colors = {};
    EMO.emotions.forEach(function (item) { colors[item.name] = item.color; });

    // 无记录区
    var cov = win.coverage_start;
    if (cov && cov > from + 60) {
      ctx.fillStyle = "rgba(255,255,255,.55)";
      ctx.fillRect(P.l, P.t, x(cov) - P.l, ih);
      ctx.setLineDash([3, 5]);
      ctx.strokeStyle = "rgba(24,66,90,.18)";
      ctx.beginPath();
      ctx.moveTo(x(cov), P.t);
      ctx.lineTo(x(cov), P.t + ih);
      ctx.stroke();
      ctx.setLineDash([]);
      if (x(cov) - P.l > 90) {
        ctx.fillStyle = "rgba(94,116,128,.7)";
        ctx.textAlign = "left";
        ctx.fillText("日志从这里开始", x(cov) + 7, P.t + 9);
      }
    }

    // 情绪包络的面积
    ctx.beginPath();
    ctx.moveTo(x(samples.ts[0]), y(0));
    samples.ts.forEach(function (t, i) { ctx.lineTo(x(t), y(samples.max[i])); });
    ctx.lineTo(x(samples.ts[samples.ts.length - 1]), y(0));
    ctx.closePath();
    var grad = ctx.createLinearGradient(0, P.t, 0, P.t + ih);
    grad.addColorStop(0, "rgba(10,159,150,.16)");
    grad.addColorStop(0.65, "rgba(47,111,235,.045)");
    grad.addColorStop(1, "rgba(47,111,235,0)");
    ctx.fillStyle = grad;
    ctx.fill();

    // 七条线
    var hot = EMO.strongest || "";
    names.forEach(function (name) {
      ctx.beginPath();
      samples.ts.forEach(function (t, i) {
        var xx = x(t), yy = y(samples.v[name][i]);
        if (i === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
      });
      var isHot = name === hot;
      ctx.strokeStyle = hexA(colors[name], isHot ? 0.95 : 0.38);
      ctx.lineWidth = isHot ? 1.8 : 1;
      ctx.lineJoin = "round";
      if (isHot) { ctx.shadowColor = hexA(colors[name], 0.55); ctx.shadowBlur = 10; }
      ctx.stroke();
      ctx.shadowBlur = 0;
    });

    // 事件点
    (EMO.events || []).forEach(function (ev) {
      if (ev.ts < from || ev.ts > to) return;
      var name = ev.dom || "";
      var value = 0;
      Object.keys(ev.e || {}).forEach(function (n) { if (ev.e[n] > value) value = ev.e[n]; });
      var xx = x(ev.ts), yy = y(value);
      ctx.beginPath();
      ctx.fillStyle = hexA(colors[name] || "#6fe3d0", 0.95);
      ctx.shadowColor = hexA(colors[name] || "#6fe3d0", 0.8);
      ctx.shadowBlur = 8;
      ctx.arc(xx, yy, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // 时间刻度（每 4 小时）
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(94,116,128,.72)";
    var step = 4 * 3600;
    for (var t = Math.ceil(from / step) * step; t <= to; t += step) {
      var d = new Date(t * 1000);
      var label = pad(d.getHours()) + ":00";
      var xx2 = x(t);
      if (xx2 < P.l + 16 || xx2 > W - P.r - 12) continue;
      ctx.fillText(label, xx2, H - 9);
    }
    ctx.textAlign = "right";
    ctx.fillStyle = "rgba(10,159,150,.85)";
    ctx.fillText("现在", W - P.r, H - 9);

    CHART_GEOM = { x: x, y: y, from: from, to: to, P: P, W: W, H: H, samples: samples };
  }

  function hexA(hex, alpha) {
    if (!hex || hex.charAt(0) !== "#") return "rgba(10,159,150," + alpha + ")";
    var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
  }

  function onMove(ev) {
    if (!CHART_GEOM || !DATA) return;
    var wrap = $("#chart-wrap");
    var tip = $("#tooltip");
    var rect = wrap.getBoundingClientRect();
    var px = ev.clientX - rect.left;
    var py = ev.clientY - rect.top;
    var nearest = null, best = 16;
    (EMO.events || []).forEach(function (event) {
      var dx = Math.abs(CHART_GEOM.x(event.ts) - px);
      if (dx < best) { best = dx; nearest = event; }
    });
    if (!nearest) { tip.classList.remove("show"); return; }
    var name = nearest.dom || "";
    var value = 0;
    Object.keys(nearest.e || {}).forEach(function (n) { if (nearest.e[n] > value) value = nearest.e[n]; });
    var at = (nearest.at || "").slice(6, 11);
    var what = nearest.label || nearest.kind || "";
    if (nearest.stimulus) what += "「" + nearest.stimulus + "」";
    tip.innerHTML = "<b>" + esc(at) + " · " + esc(name) + " " + Math.round(value * 100) + "%</b><br>" + esc(what);
    tip.style.left = CHART_GEOM.x(nearest.ts) + "px";
    tip.style.top = CHART_GEOM.y(value) + "px";
    tip.classList.add("show");
  }

  /* ---------------- 记忆页 ---------------- */
  var MEM = null;
  var MEM_LOADED = false;
  var MEM_FILTER = { q: "", kind: "全部", day: "", recall: false, sort: "time" };
  var MEM_SHOWN = 60;
  var MEM_SEL = null;
  var MEM_RELATED = [];
  var MEM_RESULT_TIMER = null;
  var MEM_PENDING = null;
  var MEM_OPEN_TIMER = null;

  var KIND_COLORS = {
    "事实": "#2f6feb",
    "事件": "#0a9f96",
    "计划": "#b8860b",
    "偏好": "#b45fa8",
    "关系": "#7a5cd6",
    "其他": "#7b8c98"
  };
  var KIND_ORDER = ["事实", "事件", "计划", "偏好", "关系", "其他"];

  var NEB = {
    stars: [],
    clouds: [],
    bg: [],
    cam: { yaw: 0.55, pitch: -0.16, dist: 2.65, tx: 0, ty: 0, tz: 0 },
    tween: null,
    running: false,
    raf: 0,
    last: 0,
    drag: null,
    lastDrag: 0,
    W: 0,
    H: 0,
    dpr: 1,
    shift: 0,
    shiftTarget: 0,
    projected: []
  };

  var MINI = {
    stars: [],
    cam: { yaw: 0.35, pitch: -0.12, dist: 2.3 },
    running: false,
    raf: 0,
    last: 0,
    drag: null,
    flashAt: 0,
    W: 0,
    H: 0,
    dpr: 1
  };

  function hashStr(text) {
    var h = 2166136261;
    for (var i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function rand(seed) {
    var x = Math.sin(seed * 12.9898) * 43758.5453;
    return x - Math.floor(x);
  }

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function easeInOut(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function kindColor(kind) {
    return KIND_COLORS[kind] || KIND_COLORS["其他"];
  }

  function loadMemoryCount() {
    if (FEATURES.memory === false) return;
    fetch("/api/memory/stats", { cache: "no-store" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data || !data.available) return;
        setText("mem-count", data.total);
        setText("mem-title-count", data.total);
        var when = (data.generated_at || "").slice(11, 16);
        if (when) setText("mem-export", "导出 " + when);
      })
      .catch(function () { /* 记忆页打不开不影响此刻 */ });
  }

  function openMemory() {
    if (FEATURES.memory === false) return;
    closeCommand();
    $("#memory").classList.add("open");
    $("#memory").setAttribute("aria-hidden", "false");
    if (MEM_LOADED) {
      renderMemory();
      buildNebula();
      startNebula();
      maybeOpenFromQuery();
    } else {
      loadMemory();
    }
  }

  function maybeOpenFromQuery() {
    if (!MEM_OPEN_ID || !MEM_LOADED) return;
    var id = MEM_OPEN_ID;
    MEM_OPEN_ID = null;
    selectMemory(id);
  }

  function closeMemory() {
    closeDetail();
    stopNebula();
    $("#memory").classList.remove("open");
    $("#memory").setAttribute("aria-hidden", "true");
  }

  function loadMemory() {
    setText("mem-status", "读取导出…");
    fetch("/api/memory", { cache: "no-store" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        MEM = data;
        MEM_LOADED = true;
        if (!data.available) {
          setText("mem-status", data.error || "记忆导出不可用");
          return;
        }
        initMemoryFilters();
        renderMemory();
        buildNebula();
        startNebula();
        maybeOpenFromQuery();
      })
      .catch(function (err) {
        setText("mem-status", "读取失败：" + err.message);
      });
  }

  function initMemoryFilters() {
    var stats = MEM.stats || {};
    var byKind = stats.by_kind || {};
    var kinds = Object.keys(byKind).sort(function (a, b) {
      return (byKind[b] || 0) - (byKind[a] || 0);
    });
    if (!kinds.length) {
      var seen = {};
      (MEM.items || []).forEach(function (item) { seen[item.kind] = (seen[item.kind] || 0) + 1; });
      kinds = Object.keys(seen);
    }
    var html = '<button class="mem-kind-btn on" data-kind="全部">全部</button>';
    kinds.forEach(function (kind) {
      html += '<button class="mem-kind-btn" data-kind="' + esc(kind) + '">' + esc(kind) + " " + (byKind[kind] || "") + "</button>";
    });
    $("#mem-kinds").innerHTML = html;

    var daily = {};
    (MEM.items || []).forEach(function (item) {
      if (item.date) daily[item.date] = (daily[item.date] || 0) + 1;
    });
    var days = Object.keys(daily).sort().reverse();
    var opts = '<option value="">全部日期</option>';
    days.forEach(function (day) {
      opts += '<option value="' + esc(day) + '">' + esc(day.slice(5)) + " · " + daily[day] + "</option>";
    });
    $("#mem-day").innerHTML = opts;

    var recallTotal = 0;
    (MEM.items || []).forEach(function (item) { recallTotal += item.recall || 0; });
    var recallBox = $("#mem-recall");
    if (!recallTotal) {
      recallBox.disabled = true;
      setText("mem-recall-note", "暂无次数");
    } else {
      recallBox.disabled = false;
      setText("mem-recall-note", "");
    }

    var total = (MEM.items || []).length;
    $("#mem-stats").innerHTML = "共 <b>" + total + "</b> 条";
    $("#stage-legend").innerHTML = kinds.map(function (kind) {
      return '<span><i style="background:' + kindColor(kind) + '"></i>' + esc(kind) + "</span>";
    }).join("");
  }

  function filteredMemory() {
    var q = MEM_FILTER.q.trim().toLowerCase();
    var list = (MEM.items || []).filter(function (item) {
      if (MEM_FILTER.kind !== "全部" && item.kind !== MEM_FILTER.kind) return false;
      if (MEM_FILTER.day && item.date !== MEM_FILTER.day) return false;
      if (MEM_FILTER.recall && !(item.recall > 0)) return false;
      if (q) {
        var hay = (item.text + " " + (item.tags || []).join(" ") + " " + item.kind).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
    if (MEM_FILTER.sort === "recall") {
      list.sort(function (a, b) { return (b.recall || 0) - (a.recall || 0) || b.ts - a.ts; });
    } else {
      list.sort(function (a, b) { return b.ts - a.ts; });
    }
    return list;
  }

  function renderMemory() {
    if (!MEM || !MEM.available) return;
    var list = filteredMemory();
    var shown = list.slice(0, MEM_SHOWN);
    setText("mem-shown", "显示 " + shown.length + " / " + list.length);
    setText("mem-status", "只读导出");
    $("#mem-more").classList.toggle("hidden", list.length <= MEM_SHOWN);

    $("#mem-list").innerHTML = shown.map(function (item) {
      var date = item.date ? item.date.slice(5) + " " + (item.time || "") : "—";
      if (item.time_source === "created") date = "记 " + date;
      var textHtml = MASK
        ? '<div class="mem-maskel-line w1"></div><div class="mem-maskel-line w2"></div>'
        : '<div class="mem-row-text">' + esc(item.text) + "</div>";
      var tags = !MASK && item.tags && item.tags.length
        ? '<div class="mem-row-tags">' + item.tags.slice(0, 3).map(function (tag) { return "<span>" + esc(tag) + "</span>"; }).join("") + "</div>"
        : "";
      var active = MEM_SEL && String(MEM_SEL.id) === String(item.id) ? " active" : "";
      return '<div class="mem-row' + (MASK ? " masked" : "") + active + '" data-id="' + esc(item.id) + '">' +
        '<div><div class="mem-row-date">' + esc(date) + "</div>" +
        '<div class="mem-row-kind' + (item.pinned ? " pinned" : "") + '">' + (item.pinned ? "PIN · " : "") + esc(item.kind) + "</div></div>" +
        "<div>" + textHtml + tags + "</div></div>";
    }).join("");

    if (!shown.length) {
      $("#mem-list").innerHTML = '<div class="mem-empty">没有符合条件的记忆。</div>';
    }
  }

  function relatedFor(item) {
    var tags = {};
    (item.tags || []).forEach(function (tag) { tags[tag] = true; });
    var out = [];
    (MEM.items || []).forEach(function (other) {
      if (String(other.id) === String(item.id)) return;
      var shared = 0;
      (other.tags || []).forEach(function (tag) { if (tags[tag]) shared += 1; });
      var score = shared * 2 + (other.date === item.date ? 1 : 0) + (other.kind === item.kind ? 0.5 : 0);
      if (score > 0) out.push({ item: other, score: score });
    });
    out.sort(function (a, b) { return b.score - a.score || b.item.ts - a.item.ts; });
    return out.slice(0, 9);
  }

  /* ---------- 大星图（3D 星云） ---------- */
  function buildNebula() {
    if (!MEM || !MEM.items || !MEM.items.length) return;
    var kindList = [];
    (MEM.items || []).forEach(function (item) {
      if (kindList.indexOf(item.kind) < 0) kindList.push(item.kind);
    });
    var maxTs = 0;
    (MEM.items || []).forEach(function (item) { if (item.ts > maxTs) maxTs = item.ts; });
    NEB.stars = (MEM.items || []).map(function (item) {
      var h = hashStr(String(item.id));
      var ki = kindList.indexOf(item.kind);
      if (ki < 0) ki = kindList.length;
      var n = Math.max(1, kindList.length);
      var days = Math.max(0, (maxTs - item.ts) / 86400);
      var age = clamp(Math.log(1 + days) / Math.log(31), 0, 1);
      var u = rand(h + 1);
      var radius = 0.10 + 0.82 * Math.pow(u, 0.9);
      if (age < 0.12) radius *= 0.55;
      var arm = (ki % 2) * Math.PI;
      var angle = arm + radius * 5.6 + (rand(h) - 0.5) * 0.60;
      var y = (rand(h + 2) - 0.5) * 0.42 * (1 - radius * 0.55);
      return {
        item: item,
        x: Math.cos(angle) * radius,
        y: y,
        z: Math.sin(angle) * radius,
        color: kindColor(item.kind),
        age: age,
        halo: (h % 29 === 0),
        px: 0, py: 0, pz: 0
      };
    });

    // 整个星云居中，旋转围绕中心
    var mx = 0, my = 0, mz = 0;
    NEB.stars.forEach(function (star) { mx += star.x; my += star.y; mz += star.z; });
    var count = Math.max(1, NEB.stars.length);
    mx /= count; my /= count; mz /= count;
    NEB.stars.forEach(function (star) { star.x -= mx; star.y -= my; star.z -= mz; });

    NEB.clouds = kindList.map(function (kind) {
      var sx = 0, sy = 0, sz = 0, count = 0;
      NEB.stars.forEach(function (star) {
        if (star.item.kind !== kind) return;
        sx += star.x; sy += star.y; sz += star.z; count += 1;
      });
      return {
        kind: kind,
        color: kindColor(kind),
        x: count ? sx / count : 0,
        y: count ? sy / count : 0,
        z: count ? sz / count : 0
      };
    });
  }

  function resizeNebula() {
    var canvas = $("#nebula");
    var stage = $("#mem-stage");
    if (!canvas || !stage) return;
    var rect = stage.getBoundingClientRect();
    NEB.W = Math.max(320, Math.floor(rect.width));
    NEB.H = Math.max(240, Math.floor(rect.height));
    NEB.dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(NEB.W * NEB.dpr);
    canvas.height = Math.floor(NEB.H * NEB.dpr);
  }

  function buildBgStars() {
    NEB.bg = [];
    for (var i = 0; i < 320; i++) {
      var h = hashStr("bg" + i);
      NEB.bg.push({
        x: rand(h),
        y: rand(h + 1),
        s: 0.7 + rand(h + 2) * 1.5,
        a: 0.05 + rand(h + 3) * 0.13,
        c: i % 9 === 0 ? "#2f6feb" : (i % 13 === 0 ? "#b8860b" : "#6b7c88")
      });
    }
  }

  function drawFieldRings(ctx, cx, cy, scale) {
    var cam = NEB.cam;
    var radii = [0.55, 0.95, 1.30, 1.72];
    radii.forEach(function (radius, index) {
      ctx.beginPath();
      var started = false;
      for (var a = 0; a <= Math.PI * 2 + 0.01; a += Math.PI / 72) {
        var p = project3D(Math.cos(a) * radius, 0, Math.sin(a) * radius, cam, cx, cy, scale);
        if (!p) { started = false; continue; }
        if (!started) { ctx.moveTo(p.x, p.y); started = true; }
        else ctx.lineTo(p.x, p.y);
      }
      ctx.strokeStyle = index === radii.length - 1 ? "rgba(24,66,90,.19)" : "rgba(24,66,90,.06)";
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    var outer = radii[radii.length - 1];
    for (var a = 0; a < Math.PI * 2; a += Math.PI / 48) {
      var p1 = project3D(Math.cos(a) * outer, 0, Math.sin(a) * outer, cam, cx, cy, scale);
      var p2 = project3D(Math.cos(a) * outer * 1.035, 0, Math.sin(a) * outer * 1.035, cam, cx, cy, scale);
      if (!p1 || !p2) continue;
      ctx.beginPath();
      ctx.strokeStyle = "rgba(24,66,90,.26)";
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }

    for (var s = 0; s < Math.PI * 2; s += Math.PI / 12) {
      var end = project3D(Math.cos(s) * outer, 0, Math.sin(s) * outer, cam, cx, cy, scale);
      if (!end) continue;
      ctx.beginPath();
      ctx.strokeStyle = "rgba(24,66,90,.035)";
      ctx.moveTo(cx, cy);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
    }
  }

  function project3D(x, y, z, cam, cx, cy, scale) {    var cyaw = Math.cos(cam.yaw), syaw = Math.sin(cam.yaw);
    var x1 = x * cyaw - z * syaw;
    var z1 = x * syaw + z * cyaw;
    var cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    var y1 = y * cp - z1 * sp;
    var z2 = y * sp + z1 * cp;
    var zz = z2 + cam.dist;
    if (zz < 0.12) return null;
    var s = scale / zz;
    return { x: cx + x1 * s, y: cy + y1 * s, z: zz, s: s };
  }

  function startNebula() {
    if (NEB.running) return;
    resizeNebula();
    if (!NEB.bg.length) buildBgStars();
    NEB.running = true;
    NEB.last = performance.now();
    NEB.raf = requestAnimationFrame(nebulaLoop);
  }

  function stopNebula() {
    NEB.running = false;
    if (NEB.raf) cancelAnimationFrame(NEB.raf);
    NEB.raf = 0;
  }

  function nebulaLoop(now) {
    if (!NEB.running) return;
    var dt = Math.min(0.05, (now - NEB.last) / 1000 || 0.016);
    NEB.last = now;
    updateNebula(now / 1000, dt);
    drawNebula();
    NEB.raf = requestAnimationFrame(nebulaLoop);
  }

  function updateNebula(now, dt) {
    var cam = NEB.cam;
    if (NEB.tween) {
      var k = clamp((now - NEB.tween.t0) / NEB.tween.dur, 0, 1);
      var e = easeInOut(k);
      var from = NEB.tween.from, to = NEB.tween.to;
      cam.tx = from.tx + (to.tx - from.tx) * e;
      cam.ty = from.ty + (to.ty - from.ty) * e;
      cam.tz = from.tz + (to.tz - from.tz) * e;
      cam.dist = from.dist + (to.dist - from.dist) * e;
      cam.yaw = from.yaw + (to.yaw - from.yaw) * e;
      cam.pitch = from.pitch + (to.pitch - from.pitch) * e;
      if (k >= 1) NEB.tween = null;
    } else if (!NEB.drag && !MEM_SEL && now - NEB.lastDrag > 2.2) {
      cam.yaw += dt * 0.045;
    }
    NEB.shift += (NEB.shiftTarget - NEB.shift) * Math.min(1, dt * 7);
  }

  function drawNebula() {
    var canvas = $("#nebula");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (canvas.width !== Math.floor(NEB.W * NEB.dpr) || canvas.height !== Math.floor(NEB.H * NEB.dpr)) {
      canvas.width = Math.floor(NEB.W * NEB.dpr);
      canvas.height = Math.floor(NEB.H * NEB.dpr);
    }
    ctx.setTransform(NEB.dpr, 0, 0, NEB.dpr, 0, 0);
    ctx.clearRect(0, 0, NEB.W, NEB.H);

    var W = NEB.W, H = NEB.H;
    var cx = W / 2 - NEB.shift;
    var cy = H / 2 + 6;
    var scale = Math.min(W, H) * 1.95;

    // 远景星尘（装饰，不映射数据）
    var parallax = NEB.cam.yaw * 16;
    NEB.bg.forEach(function (dot) {
      var x = dot.x * W + parallax;
      x = ((x % W) + W) % W;
      ctx.fillStyle = hexA(dot.c, dot.a);
      ctx.fillRect(x, dot.y * H, dot.s, dot.s);
    });

    // 星云底色
    var core = ctx.createRadialGradient(cx, cy, 4, cx, cy, Math.min(W, H) * 0.34);
    core.addColorStop(0, "rgba(10,159,150,.16)");
    core.addColorStop(0.28, "rgba(47,111,235,.06)");
    core.addColorStop(0.62, "rgba(122,92,214,.035)");
    core.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = core;
    ctx.fillRect(0, 0, W, H);

    NEB.clouds.forEach(function (cloud) {
      var p = project3D(cloud.x, cloud.y, cloud.z, NEB.cam, cx, cy, scale);
      if (!p) return;
      var radius = Math.min(W, H) * 0.30;
      var grad = ctx.createRadialGradient(p.x, p.y, 2, p.x, p.y, radius);
      grad.addColorStop(0, hexA(cloud.color, 0.18));
      grad.addColorStop(0.5, hexA(cloud.color, 0.065));
      grad.addColorStop(1, hexA(cloud.color, 0));
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
      ctx.fill();
    });

    // 星云气团（少量、很淡）
    for (var pi = 0; pi < NEB.stars.length; pi += 53) {
      var puff = NEB.stars[pi];
      var pp = project3D(puff.x, puff.y, puff.z, NEB.cam, cx, cy, scale);
      if (!pp) continue;
      var rr = 64 + (pi % 6) * 16;
      var pg = ctx.createRadialGradient(pp.x, pp.y, 0, pp.x, pp.y, rr);
      pg.addColorStop(0, hexA(puff.color, 0.07));
      pg.addColorStop(1, hexA(puff.color, 0));
      ctx.fillStyle = pg;
      ctx.beginPath();
      ctx.arc(pp.x, pp.y, rr, 0, Math.PI * 2);
      ctx.fill();
    }

    // 星图环 / 刻度 / 辐条
    drawFieldRings(ctx, cx, cy, scale);
    ctx.beginPath();
    ctx.fillStyle = "rgba(10,159,150,.55)";
    ctx.arc(cx, cy, 2.2, 0, Math.PI * 2);
    ctx.fill();

    var cam = NEB.cam;
    var projected = [];
    NEB.stars.forEach(function (star) {
      var p = project3D(star.x, star.y, star.z, cam, cx, cy, scale);
      if (!p) return;
      star.px = p.x; star.py = p.y; star.pz = p.z;
      projected.push(star);
    });
    projected.sort(function (a, b) { return b.pz - a.pz; });

    var selectedStar = null;
    projected.forEach(function (star) {
      var depth = clamp(1.45 / star.pz, 0.22, 1.0);
      var bright = clamp(1.18 - (star.age || 0) * 0.4, 0.7, 1.18);
      var size = (1.1 + depth * 2.2) * bright;
      if (MEM_SEL && String(star.item.id) === String(MEM_SEL.id)) {
        size = 4.6;
        selectedStar = star;
      }
      if (star.halo) {
        ctx.beginPath();
        ctx.fillStyle = hexA(star.color, 0.06);
        ctx.arc(star.px, star.py, 8 + depth * 8, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.beginPath();
      ctx.fillStyle = hexA(star.color, (0.26 + depth * 0.66) * bright);
      ctx.arc(star.px, star.py, size, 0, Math.PI * 2);
      ctx.fill();
    });

    if (selectedStar) {
      var relatedStars = [];
      MEM_RELATED.forEach(function (rel) {
        var found = projected.filter(function (star) { return String(star.item.id) === String(rel.item.id); })[0];
        if (found) relatedStars.push(found);
      });
      relatedStars.forEach(function (star) {
        ctx.beginPath();
        ctx.strokeStyle = "rgba(10,159,150,.22)";
        ctx.lineWidth = 0.8;
        ctx.moveTo(selectedStar.px, selectedStar.py);
        ctx.lineTo(star.px, star.py);
        ctx.stroke();
        ctx.beginPath();
        ctx.fillStyle = hexA(star.color, 0.95);
        ctx.arc(star.px, star.py, 2.6, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.beginPath();
      ctx.strokeStyle = "rgba(10,159,150,.55)";
      ctx.lineWidth = 1;
      ctx.arc(selectedStar.px, selectedStar.py, 11, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.fillStyle = "#0a9f96";
      ctx.arc(selectedStar.px, selectedStar.py, 3.2, 0, Math.PI * 2);
      ctx.fill();

      var focus = $("#stage-focus");
      focus.textContent = "#" + MEM_SEL.id + " · " + (MEM_SEL.date || "").slice(5) + " · " + MEM_SEL.kind;
      focus.style.left = (selectedStar.px + 16) + "px";
      focus.style.top = (selectedStar.py - 10) + "px";
      focus.classList.add("show");
    } else {
      $("#stage-focus").classList.remove("show");
    }

    NEB.projected = projected;
  }

  function nebulaPick(clientX, clientY) {
    var canvas = $("#nebula");
    var rect = canvas.getBoundingClientRect();
    var x = clientX - rect.left, y = clientY - rect.top;
    var best = null, bestDist = 12;
    NEB.projected.forEach(function (star) {
      var dx = star.px - x, dy = star.py - y;
      var dist = dx * dx + dy * dy;
      if (dist < bestDist * bestDist) { bestDist = Math.sqrt(dist); best = star; }
    });
    return best;
  }

  function zoomToStar(star) {
    NEB.shiftTarget = 218;
    NEB.tween = {
      t0: performance.now() / 1000,
      dur: 0.85,
      from: {
        tx: NEB.cam.tx, ty: NEB.cam.ty, tz: NEB.cam.tz, dist: NEB.cam.dist,
        yaw: NEB.cam.yaw, pitch: NEB.cam.pitch
      },
      to: {
        tx: star.x, ty: star.y, tz: star.z, dist: 1.35,
        yaw: NEB.cam.yaw, pitch: NEB.cam.pitch
      }
    };
  }

  function overviewNebula() {
    NEB.shiftTarget = 0;
    NEB.tween = {
      t0: performance.now() / 1000,
      dur: 0.8,
      from: {
        tx: NEB.cam.tx, ty: NEB.cam.ty, tz: NEB.cam.tz, dist: NEB.cam.dist,
        yaw: NEB.cam.yaw, pitch: NEB.cam.pitch
      },
      to: { tx: 0, ty: 0, tz: 0, dist: 2.65, yaw: NEB.cam.yaw, pitch: -0.16 }
    };
  }

  /* ---------- 小星图 ---------- */
  function buildMini() {
    MINI.stars = [];
    if (!MEM_SEL) return;
    MINI.stars.push({
      item: MEM_SEL, x: 0, y: 0, z: 0, center: true, color: kindColor(MEM_SEL.kind)
    });
    var n = Math.max(1, MEM_RELATED.length);
    MEM_RELATED.forEach(function (rel, index) {
      var angle = (index / n) * Math.PI * 2 + 0.35;
      var radius = 0.86 + rand(index + 3) * 0.16;
      MINI.stars.push({
        item: rel.item,
        x: Math.cos(angle) * radius,
        y: (rand(index + 7) - 0.5) * 0.62,
        z: Math.sin(angle) * radius,
        color: kindColor(rel.item.kind)
      });
    });
  }

  function resizeMini() {
    var canvas = $("#mem-mini");
    if (!canvas) return;
    var rect = canvas.getBoundingClientRect();
    MINI.W = Math.max(240, Math.floor(rect.width));
    MINI.H = Math.max(160, Math.floor(rect.height));
    MINI.dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(MINI.W * MINI.dpr);
    canvas.height = Math.floor(MINI.H * MINI.dpr);
  }

  function startMini() {
    if (MINI.running) return;
    resizeMini();
    MINI.running = true;
    MINI.last = performance.now();
    MINI.raf = requestAnimationFrame(miniLoop);
  }

  function stopMini() {
    MINI.running = false;
    if (MINI.raf) cancelAnimationFrame(MINI.raf);
    MINI.raf = 0;
  }

  function miniLoop(now) {
    if (!MINI.running) return;
    var dt = Math.min(0.05, (now - MINI.last) / 1000 || 0.016);
    MINI.last = now;
    if (!MINI.drag) MINI.cam.yaw += dt * 0.10;
    drawMini();
    MINI.raf = requestAnimationFrame(miniLoop);
  }

  function drawMini() {
    var canvas = $("#mem-mini");
    if (!canvas || !MINI.stars.length) return;
    var ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (canvas.width !== Math.floor(MINI.W * MINI.dpr) || canvas.height !== Math.floor(MINI.H * MINI.dpr)) {
      canvas.width = Math.floor(MINI.W * MINI.dpr);
      canvas.height = Math.floor(MINI.H * MINI.dpr);
    }
    ctx.setTransform(MINI.dpr, 0, 0, MINI.dpr, 0, 0);
    ctx.clearRect(0, 0, MINI.W, MINI.H);

    var W = MINI.W, H = MINI.H;
    var cx = W / 2, cy = H / 2;
    var scale = Math.min(W, H) * 1.35;
    var cam = MINI.cam;

    var projected = [];
    MINI.stars.forEach(function (star) {
      var p = project3D(star.x, star.y, star.z, cam, cx, cy, scale);
      if (!p) return;
      var node = {
        item: star.item, center: !!star.center, color: star.color,
        x: p.x, y: p.y, z: p.z
      };
      projected.push(node);
    });

    var flashAge = MINI.flashAt ? (performance.now() - MINI.flashAt) / 1000 : 9;
    var flash = flashAge < 0.9 ? Math.max(0, 1 - flashAge / 0.9) : 0;

    var core = projected.filter(function (node) { return node.center; })[0];
    if (core) {
      projected.forEach(function (node) {
        if (node.center) return;
        ctx.beginPath();
        ctx.strokeStyle = "rgba(10,159,150,.22)";
        ctx.lineWidth = 0.8;
        ctx.moveTo(core.x, core.y);
        ctx.lineTo(node.x, node.y);
        ctx.stroke();
      });
    }

    projected.sort(function (a, b) { return b.z - a.z; });
    projected.forEach(function (node) {
      var size = node.center ? 5.2 : 3.4;
      ctx.beginPath();
      ctx.fillStyle = hexA(node.color, node.center ? 1 : 0.92);
      ctx.arc(node.x, node.y, size, 0, Math.PI * 2);
      ctx.fill();
      if (node.center) {
        ctx.beginPath();
        ctx.strokeStyle = "rgba(10,159,150," + (0.5 + flash * 0.4) + ")";
        ctx.lineWidth = 1.6;
        ctx.arc(node.x, node.y, 11 + (1 - flash) * 8, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.strokeStyle = "rgba(10,159,150,.25)";
        ctx.lineWidth = 1;
        ctx.arc(node.x, node.y, 17, 0, Math.PI * 2);
        ctx.stroke();
      }
      if (node.center) {
        ctx.fillStyle = "rgba(10,159,150,.95)";
        ctx.font = "bold 8px 'Cascadia Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText("选中", node.x, node.y - 15);
        ctx.fillStyle = "rgba(94,116,128,.85)";
        ctx.font = "8px 'Cascadia Mono', monospace";
        ctx.fillText((node.item.date || "").slice(5), node.x, node.y + 20);
      } else {
        ctx.fillStyle = "rgba(94,116,128,.85)";
        ctx.font = "8px 'Cascadia Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText((node.item.date || "").slice(5), node.x, node.y + 13);
      }
    });

    MINI.projected = projected;
  }

  function miniPick(clientX, clientY) {
    var canvas = $("#mem-mini");
    var rect = canvas.getBoundingClientRect();
    var x = clientX - rect.left, y = clientY - rect.top;
    var best = null, bestDist = 16;
    (MINI.projected || []).forEach(function (node) {
      if (node.center) return;
      var dx = node.x - x, dy = node.y - y;
      var dist = dx * dx + dy * dy;
      if (dist < bestDist * bestDist) { bestDist = Math.sqrt(dist); best = node; }
    });
    return best;
  }

  /* ---------- 详情 / 命令 ---------- */
  function fillDetail() {
    if (!MEM_SEL) return;
    var item = MEM_SEL;
    setText("md-kind", item.kind);
    setText("md-id", "#" + item.id);
    var miniHint = document.querySelector(".mem-mini-hint");
    if (miniHint) miniHint.textContent = "选中 #" + item.id + " · 拖动旋转 · 点节点跳转";
    var when = (item.date || "") + " " + (item.time || "");
    var prefix = item.time_source === "conversation" ? "对话 " : (item.time_source === "event" ? "发生 " : "记于 ");
    setText("md-date", prefix + when.trim());
    var text = $("#md-text");
    var maskBlock = $("#md-mask");
    if (MASK) {
      text.textContent = "";
      text.classList.add("masked");
      if (maskBlock) maskBlock.classList.add("show");
    } else {
      text.textContent = item.text;
      text.classList.remove("masked");
      if (maskBlock) maskBlock.classList.remove("show");
    }
    $("#md-tags").innerHTML = (!MASK && item.tags && item.tags.length)
      ? item.tags.map(function (tag) { return "<span>" + esc(tag) + "</span>"; }).join("")
      : "";
    var meta = [];
    meta.push("ATOM #" + esc(item.id));
    if (item.time_source === "conversation") {
      meta.push("对话 " + esc(item.source_at || when));
      meta.push("记于 " + esc(item.created_at || ""));
      if (item.event_plausible && item.event_at && item.event_at !== item.source_at) {
        meta.push("标注 " + esc(item.event_at));
      }
    } else if (item.time_source === "event") {
      meta.push("发生 " + esc(item.event_at || when));
      meta.push("记于 " + esc(item.created_at || ""));
    } else {
      meta.push("记于 " + esc(item.created_at || ""));
    }
    if (item.recall) meta.push("召回 " + item.recall + " 次");
    if (item.pinned) meta.push("已置顶");
    $("#md-meta").innerHTML = meta.join("<br>");
    var pin = $("#md-pin");
    pin.textContent = item.pinned ? "取消置顶" : "置顶";
    $("#mem-editor").classList.remove("open");
    $("#mem-result").className = "mem-result";
    setText("mem-result", "");
    resetDeleteButton();
  }

  function selectMemory(id) {
    var item = (MEM.items || []).filter(function (row) { return String(row.id) === String(id); })[0];
    if (!item) return;
    MEM_SEL = item;
    MEM_RELATED = relatedFor(item);
    renderMemory();
    var star = NEB.stars.filter(function (row) { return String(row.item.id) === String(id); })[0];
    if (star) zoomToStar(star);

    if (MEM_OPEN_TIMER) { clearTimeout(MEM_OPEN_TIMER); MEM_OPEN_TIMER = null; }
    fillDetail();
    $("#mem-detail").classList.add("open");
    $("#mem-detail").setAttribute("aria-hidden", "false");
    MINI.flashAt = performance.now();
    buildMini();
    startMini();
    drawMini();
  }

  function stepMemory(delta) {
    if (!MEM_SEL) return;
    var list = filteredMemory();
    if (!list.length) return;
    var index = -1;
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].id) === String(MEM_SEL.id)) { index = i; break; }
    }
    if (index < 0) index = 0;
    var next = list[(index + delta + list.length) % list.length];
    if (next) selectMemory(next.id);
  }

  function closeDetail() {
    if (MEM_OPEN_TIMER) { clearTimeout(MEM_OPEN_TIMER); MEM_OPEN_TIMER = null; }
    $("#mem-detail").classList.remove("open");
    $("#mem-detail").setAttribute("aria-hidden", "true");
    stopMini();
    MEM_SEL = null;
    MEM_RELATED = [];
    var focus = $("#stage-focus");
    if (focus) focus.classList.remove("show");
    if (MEM_LOADED) {
      renderMemory();
      overviewNebula();
    }
  }

  function setResult(text, kind) {
    var el = $("#mem-result");
    el.textContent = text || "";
    el.className = "mem-result" + (kind ? " " + kind : "");
  }

  function sendMemoryCommand(op, payload) {
    if (!MEM_SEL) return;
    MEM_PENDING = { op: op, payload: payload, target: MEM_SEL.id, item: MEM_SEL };
    setResult("提交中…");
    fetch("/api/memory/command", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Panel": "1" },
      body: JSON.stringify({ op: op, target: MEM_SEL.id, payload: payload, confirm: op === "delete" ? String(MEM_SEL.id) : undefined })
    })
      .then(function (res) { return res.json().then(function (body) { return { ok: res.ok, body: body }; }); })
      .then(function (result) {
        if (!result.ok) throw new Error(result.body.error || "提交失败");
        setResult("已提交 · 等记忆管理消费（≤1 分钟）");
        pollMemoryResult(result.body.id, 0);
      })
      .catch(function (err) {
        setResult("失败：" + err.message, "bad");
        MEM_PENDING = null;
      });
  }

  function pollMemoryResult(cmdId, tries) {
    if (MEM_RESULT_TIMER) clearTimeout(MEM_RESULT_TIMER);
    if (tries > 45) {
      setResult("已提交，等下一分钟执行");
      return;
    }
    MEM_RESULT_TIMER = setTimeout(function () {
      fetch("/api/memory/result/" + encodeURIComponent(cmdId), { cache: "no-store" })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          var result = data.result;
          if (!result || result.status === "pending") {
            pollMemoryResult(cmdId, tries + 1);
            return;
          }
          if (result.status === "done") {
            applyMemoryCommand(cmdId);
          } else {
            setResult("执行失败：" + (result.reason || "记忆管理未给原因"), "bad");
            MEM_PENDING = null;
          }
        })
        .catch(function () { pollMemoryResult(cmdId, tries + 1); });
    }, 1000);
  }

  function applyMemoryCommand(cmdId) {
    var pending = MEM_PENDING;
    if (!pending) return;
    var item = pending.item;
    if (!item) { MEM_PENDING = null; return; }
    var stillSelected = MEM_SEL && String(MEM_SEL.id) === String(item.id);
    var message = "";
    if (pending.op === "pin") {
      item.pinned = !!pending.payload.pinned;
      message = "已执行 · " + (item.pinned ? "已置顶" : "已取消置顶");
    } else if (pending.op === "tag") {
      item.tags = pending.payload.tags;
      message = "已执行 · 标签已更新";
    } else if (pending.op === "edit") {
      item.text = pending.payload.text;
      message = "已执行 · 正文已更新";
    } else if (pending.op === "delete") {
      MEM.items = (MEM.items || []).filter(function (row) { return String(row.id) !== String(item.id); });
      renderMemory();
      if (stillSelected) {
        setResult("已执行 · 软删（原文保留在库）", "ok");
        setTimeout(closeDetail, 700);
      }
      logCommand("done", cmdId, pending.op);
      MEM_PENDING = null;
      return;
    }
    if (stillSelected) {
      fillDetail();
      setResult(message, "ok");
    }
    renderMemory();
    logCommand("done", cmdId, pending.op);
    MEM_PENDING = null;
  }

  function logCommand(status, cmdId, op) {
    if (window.console) console.info("memory command", status, cmdId, op);
  }

  function openEditor(mode) {
    if (!MEM_SEL) return;
    if (mode === "edit" && MASK) {
      setResult("上镜模式已遮，切完整模式再编辑", "bad");
      return;
    }
    var body = $("#mem-editor-body");
    if (mode === "tag") {
      body.innerHTML = '<input id="mem-editor-input" value="' + esc((MEM_SEL.tags || []).join("、")) + '" placeholder="标签，用、或逗号分隔">';
    } else {
      body.innerHTML = '<textarea id="mem-editor-input">' + esc(MEM_SEL.text) + "</textarea>";
    }
    $("#mem-editor").classList.add("open");
    $("#mem-save").dataset.mode = mode;
    var input = $("#mem-editor-input");
    if (input) input.focus();
  }

  function saveEditor() {
    var mode = $("#mem-save").dataset.mode;
    var input = $("#mem-editor-input");
    if (!mode || !input) return;
    if (mode === "tag") {
      var tags = input.value.split(/[,，、\s]+/).filter(function (tag) { return tag.trim(); });
      sendMemoryCommand("tag", { tags: tags });
    } else {
      var text = input.value.trim();
      if (!text) { setResult("正文不能为空", "bad"); return; }
      sendMemoryCommand("edit", { text: text });
    }
    $("#mem-editor").classList.remove("open");
  }

  function resetDeleteButton() {
    var btn = $("#md-delete");
    if (!btn) return;
    btn.dataset.armed = "0";
    btn.classList.remove("armed");
    btn.textContent = "删除";
  }

  function armDelete() {
    var btn = $("#md-delete");
    if (!MEM_SEL) return;
    if (btn.dataset.armed !== "1") {
      btn.dataset.armed = "1";
      btn.classList.add("armed");
      btn.textContent = "确认删除（5s）";
      setTimeout(function () {
        if (btn.dataset.armed === "1") resetDeleteButton();
      }, 5000);
      return;
    }
    resetDeleteButton();
    sendMemoryCommand("delete", {});
  }

  function bindStagePointer() {
    var canvas = $("#nebula");
    canvas.addEventListener("pointerdown", function (ev) {
      NEB.drag = {
        x: ev.clientX, y: ev.clientY,
        yaw: NEB.cam.yaw, pitch: NEB.cam.pitch,
        moved: 0
      };
      try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
    });
    canvas.addEventListener("pointermove", function (ev) {
      if (!NEB.drag) return;
      var dx = ev.clientX - NEB.drag.x;
      var dy = ev.clientY - NEB.drag.y;
      NEB.drag.moved += Math.abs(dx) + Math.abs(dy);
      NEB.cam.yaw = NEB.drag.yaw + dx * 0.0055;
      NEB.cam.pitch = clamp(NEB.drag.pitch + dy * 0.0045, -1.15, 1.15);
      NEB.lastDrag = performance.now() / 1000;
    });
    canvas.addEventListener("pointerup", function (ev) {
      if (!NEB.drag) return;
      var moved = NEB.drag.moved;
      NEB.drag = null;
      NEB.lastDrag = performance.now() / 1000;
      if (moved < 5) {
        var star = nebulaPick(ev.clientX, ev.clientY);
        if (star) selectMemory(star.item.id);
      }
    });
    canvas.addEventListener("pointercancel", function () { NEB.drag = null; });
    var reset = $("#stage-reset");
    if (reset) reset.addEventListener("click", function () { overviewNebula(); });
    canvas.addEventListener("pointermove", function (ev) {
      var hover = $("#stage-hover");
      if (!hover) return;
      if (NEB.drag) { hover.classList.remove("show"); return; }
      var star = nebulaPick(ev.clientX, ev.clientY);
      if (!star) { hover.classList.remove("show"); return; }
      var rect = canvas.getBoundingClientRect();
      hover.textContent = "#" + star.item.id + " · " + (star.item.date || "").slice(5) + " · " + star.item.kind;
      hover.style.left = (ev.clientX - rect.left + 14) + "px";
      hover.style.top = (ev.clientY - rect.top - 10) + "px";
      hover.classList.add("show");
    });
    canvas.addEventListener("pointerleave", function () {
      var hover = $("#stage-hover");
      if (hover) hover.classList.remove("show");
    });
    canvas.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      NEB.cam.dist = clamp(NEB.cam.dist + ev.deltaY * 0.0011, 0.95, 5.2);
      NEB.lastDrag = performance.now() / 1000;
    }, { passive: false });
  }

  function bindMiniPointer() {
    var canvas = $("#mem-mini");
    canvas.addEventListener("pointerdown", function (ev) {
      MINI.drag = { x: ev.clientX, y: ev.clientY, yaw: MINI.cam.yaw, pitch: MINI.cam.pitch, moved: 0 };
      try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
    });
    canvas.addEventListener("pointermove", function (ev) {
      if (!MINI.drag) return;
      var dx = ev.clientX - MINI.drag.x;
      var dy = ev.clientY - MINI.drag.y;
      MINI.drag.moved += Math.abs(dx) + Math.abs(dy);
      MINI.cam.yaw = MINI.drag.yaw + dx * 0.008;
      MINI.cam.pitch = clamp(MINI.drag.pitch + dy * 0.006, -1.1, 1.1);
    });
    canvas.addEventListener("pointerup", function (ev) {
      if (!MINI.drag) return;
      var moved = MINI.drag.moved;
      MINI.drag = null;
      if (moved < 5) {
        var node = miniPick(ev.clientX, ev.clientY);
        if (node) selectMemory(node.item.id);
      }
    });
    canvas.addEventListener("pointercancel", function () { MINI.drag = null; });
  }

  function bindMemory() {
    $("#open-memory").addEventListener("click", openMemory);
    $("#close-memory").addEventListener("click", closeMemory);
    $("#md-close").addEventListener("click", closeDetail);
    $("#md-prev").addEventListener("click", function () { stepMemory(-1); });
    $("#md-next").addEventListener("click", function () { stepMemory(1); });
    $("#mem-more").addEventListener("click", function () { MEM_SHOWN += 60; renderMemory(); });
    $("#mem-q").addEventListener("input", function (ev) {
      MEM_FILTER.q = ev.target.value;
      MEM_SHOWN = 60;
      renderMemory();
    });
    $("#mem-day").addEventListener("change", function (ev) {
      MEM_FILTER.day = ev.target.value;
      MEM_SHOWN = 60;
      renderMemory();
    });
    $("#mem-sort").addEventListener("change", function (ev) {
      MEM_FILTER.sort = ev.target.value;
      renderMemory();
    });
    $("#mem-recall").addEventListener("change", function (ev) {
      MEM_FILTER.recall = ev.target.checked;
      MEM_SHOWN = 60;
      renderMemory();
    });
    $("#mem-kinds").addEventListener("click", function (ev) {
      var btn = ev.target.closest(".mem-kind-btn");
      if (!btn) return;
      MEM_FILTER.kind = btn.dataset.kind || "全部";
      MEM_SHOWN = 60;
      var all = document.querySelectorAll(".mem-kind-btn");
      for (var i = 0; i < all.length; i++) all[i].classList.toggle("on", all[i] === btn);
      renderMemory();
    });
    $("#mem-list").addEventListener("click", function (ev) {
      var row = ev.target.closest(".mem-row");
      if (row) selectMemory(row.dataset.id);
    });
    $("#md-pin").addEventListener("click", function () {
      if (!MEM_SEL) return;
      sendMemoryCommand("pin", { pinned: !MEM_SEL.pinned });
    });
    $("#md-tag").addEventListener("click", function () { openEditor("tag"); });
    $("#md-edit").addEventListener("click", function () { openEditor("edit"); });
    $("#md-delete").addEventListener("click", armDelete);
    $("#mem-cancel").addEventListener("click", function () { $("#mem-editor").classList.remove("open"); });
    $("#mem-save").addEventListener("click", saveEditor);
    $("#mem-refresh").addEventListener("click", function () {
      closeDetail();
      MEM_LOADED = false;
      loadMemory();
    });
    $("#memory-mask").addEventListener("click", function () {
      MASK = !MASK;
      try { window.localStorage.setItem("brainMask", MASK ? "1" : "0"); } catch (e) { /* ignore */ }
      applyMask();
    });
    bindStagePointer();
    bindMiniPointer();
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        if ($("#mem-detail").classList.contains("open")) closeDetail();
        else if ($("#memory").classList.contains("open")) closeMemory();
        return;
      }
      if ($("#mem-detail").classList.contains("open") &&
          (ev.key === "ArrowLeft" || ev.key === "ArrowRight") &&
          !$("#mem-editor").classList.contains("open") &&
          !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName || "")) {
        ev.preventDefault();
        stepMemory(ev.key === "ArrowLeft" ? -1 : 1);
      }
    });
  }

  window.__memoryMaskChanged = function () {
    if (!MEM_LOADED) return;
    renderMemory();
    if (MEM_SEL) fillDetail();
  };

  /* ---------------- 隔离模拟页 ---------------- */
  var SIM_DATA = null;
  var SIM_POLL = null;
  var SIM_META = {
    full: { label: "引擎自检", adult: false, safe: true, params: [] },
    weather_matrix: { label: "天气 × 身体矩阵", adult: false, safe: true, params: [] },
    outing_day: { label: "一日出门", adult: false, safe: true, params: ["place", "weather", "mood", "pain", "energy", "scene"] },
    custom_outing: {
      label: "自定义出门", adult: false, safe: true,
      params: ["place_name", "address", "district", "station", "line", "location",
               "route_minutes", "fare", "weather_text", "scene_name",
               "mood", "pain", "energy", "seed"]
    }
  };
  var SIM_PARAM_IDS = {
    place: "#sim-place",
    weather: "#sim-weather",
    mood: "#sim-mood",
    pain: "#sim-pain",
    energy: "#sim-energy",
    scene: "#sim-scene",
    place_name: "#sim-custom-place-name",
    address: "#sim-custom-address",
    district: "#sim-custom-district",
    station: "#sim-custom-station",
    line: "#sim-custom-line",
    location: "#sim-custom-location",
    route_minutes: "#sim-custom-route",
    fare: "#sim-custom-fare",
    weather_text: "#sim-custom-weather",
    scene_name: "#sim-custom-scene",
    seed: "#sim-custom-seed"
  };

  function refreshSimScenarioOptions() {
    var sel = $("#sim-scenario");
    if (!sel) return;
    var current = sel.value;
    var ids = Object.keys(SIM_META).filter(function (id) {
      return !MASK || SIM_META[id].safe;
    });
    sel.innerHTML = ids.map(function (id) {
      var meta = SIM_META[id];
      var label = meta.label;
      return '<option value="' + esc(id) + '">' + esc(label) + "</option>";
    }).join("");
    if (ids.indexOf(current) >= 0) sel.value = current;
    else sel.value = ids.indexOf("outing_day") >= 0 ? "outing_day" : ids[0];
    var note = $("#sim-param-note");
    if (note) {
      note.textContent = MASK
        ? "上镜模式：只开放 outing_day；引擎自检 / 天气矩阵在完整模式。"
        : "完整模式：3 个模拟场景（引擎自检 / 天气矩阵 / 一日出门），全部只跑示例数据。";
    }
    updateSimParams();
  }

  function updateSimParams() {
    var scenario = $("#sim-scenario").value;
    var meta = SIM_META[scenario] || { label: scenario, adult: false, safe: false, params: [] };
    Object.keys(SIM_PARAM_IDS).forEach(function (key) {
      var el = $(SIM_PARAM_IDS[key]);
      if (!el) return;
      var allowed = meta.params.indexOf(key) >= 0;
      el.disabled = !allowed;
      if (el.parentElement) el.parentElement.classList.toggle("off", !allowed);
    });
    var custom = $("#sim-custom-grid");
    if (custom) custom.style.display = scenario === "custom_outing" ? "" : "none";
    var adult = $("#sim-adult");
    if (adult) {
      var show = !MASK && !meta.safe;
      adult.classList.toggle("show", show);
      adult.textContent = meta.adult ? "成人场景 · 不上镜" : "含成人内容 · 不上镜";
    }
    setText("sim-current", "场景 " + meta.label + " · " + (meta.params.length ? meta.params.join(" / ") : "固定套件"));
  }

  function buildSimPayload() {
    var scenario = $("#sim-scenario").value;
    var meta = SIM_META[scenario] || { params: [] };
    var payload = { scenario: scenario, camera: !!MASK };
    meta.params.forEach(function (key) {
      var el = $(SIM_PARAM_IDS[key]);
      if (!el || el.disabled) return;
      var raw = el.value;
      if (raw === "") return;
      if (key === "mood" || key === "pain" || key === "energy") {
        var number = Number(raw);
        if (!isFinite(number)) return;
        payload[key] = Math.max(0, Math.min(1, number));
      } else if (key === "route_minutes" || key === "fare") {
        var numeric = Number(raw);
        if (!isFinite(numeric)) return;
        payload[key] = numeric;
      } else if (key === "seed") {
        var integer = parseInt(raw, 10);
        if (!isFinite(integer)) return;
        payload[key] = integer;
      } else {
        payload[key] = raw;
      }
    });
    return payload;
  }

  function simMeta(scenario) {
    return SIM_META[scenario] || { label: scenario || "—", adult: false, safe: false, params: [] };
  }

  function simLabel(status) {
    if (status === "running") return "运行中";
    if (status === "stopping") return "停止中";
    if (status === "passed") return "PASS";
    if (status === "failed") return "FAIL";
    if (status === "stopped") return "已停止";
    return "待机";
  }

  function stopSimPoll() {
    if (SIM_POLL) {
      clearTimeout(SIM_POLL);
      SIM_POLL = null;
    }
  }

  function openSim() {
    if (FEATURES.sim === false) return;
    closeCommand();
    $("#sim").classList.add("open");
    $("#sim").setAttribute("aria-hidden", "false");
    refreshSimScenarioOptions();
    if (SIM_SCENARIO && SIM_META[SIM_SCENARIO] && (!MASK || SIM_META[SIM_SCENARIO].safe)) {
      $("#sim-scenario").value = SIM_SCENARIO;
      updateSimParams();
    }
    fetchSimStatus();
  }

  function closeSim() {
    $("#sim").classList.remove("open");
    $("#sim").setAttribute("aria-hidden", "true");
    stopSimPoll();
  }

  function fetchSimStatus() {
    fetch("/api/sim/status", { cache: "no-store" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        renderSim(data);
        if (data.status === "running" || data.status === "stopping") {
          stopSimPoll();
          SIM_POLL = setTimeout(fetchSimStatus, 700);
        }
      })
      .catch(function (err) {
        setText("sim-log-note", "状态读取失败：" + err.message);
      });
  }

  function renderSim(data) {
    SIM_DATA = data;
    var status = data.status || "idle";
    var label = simLabel(status);
    var meta = simMeta(data.scenario);
    var running = status === "running" || status === "stopping";
    var blocked = MASK && data.scenario && !meta.safe;

    if (blocked) {
      refreshSimScenarioOptions();
      $("#sim-scenario").value = "outing_day";
      updateSimParams();
      if (running) $("#sim-scenario").disabled = true;
      var blockedPill = $("#sim-pill");
      blockedPill.textContent = "已隐藏";
      blockedPill.className = "sim-pill";
      setText("sim-title", "已隐藏");
      $("#sim-run").disabled = running;
      $("#sim-stop").disabled = !running;
      setText("sim-current", "上镜模式 · 已隐藏非上镜模拟");
      var blockedResult = $("#sim-result");
      blockedResult.textContent = "已隐藏";
      blockedResult.className = "";
      setText("sim-counts", "—");
      var blockedReal = $("#sim-real");
      blockedReal.textContent = "—";
      blockedReal.className = "";
      setText("sim-time", "—");
      setText("sim-last", "上镜模式 · 已隐藏");
      setText("sim-fact-checks", "—");
      $("#sim-log").innerHTML = '<div class="ln dim">上镜模式：成人/非上镜模拟已隐藏。切到 outing_day，或关掉上镜模式。</div>';
      setText("sim-log-note", "上镜模式 · 已隐藏");
      return;
    }

    var pill = $("#sim-pill");
    pill.textContent = label;
    pill.className = "sim-pill" + (status === "running" || status === "stopping" ? " running" : (status === "passed" ? " passed" : (status === "failed" ? " failed" : "")));
    setText("sim-title", label);

    $("#sim-run").disabled = running;
    $("#sim-stop").disabled = !running;

    if (!running && data.scenario) $("#sim-scenario").value = data.scenario;
    if (!running && data.params) {
      Object.keys(SIM_PARAM_IDS).forEach(function (key) {
        if (data.params[key] === undefined) return;
        var el = $(SIM_PARAM_IDS[key]);
        if (el) el.value = data.params[key];
      });
    }
    updateSimParams();
    if (running) {
      $("#sim-scenario").disabled = true;
      Object.keys(SIM_PARAM_IDS).forEach(function (key) {
        var el = $(SIM_PARAM_IDS[key]);
        if (el) el.disabled = true;
      });
    }

    var paramText = "";
    if (data.params && Object.keys(data.params).length) {
      paramText = " · " + Object.keys(data.params).map(function (key) {
        return key + "=" + data.params[key];
      }).join(" ");
    }
    setText("sim-current", (running ? "运行中 · " : "") + "场景 " + meta.label + paramText);

    var summary = data.summary || {};
    var result = summary.result || (running ? "RUNNING" : "—");
    var resultEl = $("#sim-result");
    resultEl.textContent = result;
    resultEl.className = summary.all_pass ? "ok" : (summary.has_failure || status === "failed" ? "bad" : "");

    setText("sim-counts", (summary.pass || 0) + " / " + (summary.fail || 0));
    setText("sim-fact-checks", summary.total ? summary.total + " 项" : "随场景");
    var realEl = $("#sim-real");
    if (!data.lines || !data.lines.length) {
      realEl.textContent = "—";
      realEl.className = "";
    } else if (summary.real_ok) {
      realEl.textContent = "未变";
      realEl.className = "ok";
    } else {
      realEl.textContent = summary.changed ? summary.changed + " 个变动" : "未见比对";
      realEl.className = "bad";
    }
    setText("sim-time", data.elapsed ? data.elapsed + "s" : "—");

    if (data.ended) {
      var d = new Date(data.ended * 1000);
      var hh = d.getHours() < 10 ? "0" + d.getHours() : "" + d.getHours();
      var mm = d.getMinutes() < 10 ? "0" + d.getMinutes() : "" + d.getMinutes();
      setText("sim-last", hh + ":" + mm + " · " + meta.label + " · " + (summary.result || label));
    }

    var log = $("#sim-log");
    var lines = data.lines || [];
    if (!lines.length) {
      log.innerHTML = '<div class="ln dim">尚未运行。</div>';
    } else {
      log.innerHTML = lines.map(function (line) {
        var cls = "";
        if (line.indexOf("[FAIL]") === 0) cls = "bad";
        else if (line.indexOf("[PASS]") === 0) cls = "ok";
        else if (line === "ALL_PASS" || line.indexOf("RESULT ") === 0) cls = "ok strong";
        else if (line === "HAS_FAILURE") cls = "bad strong";
        else if (line.indexOf("REAL_SHA256") === 0 || line.indexOf("sim_dir=") === 0 || line.indexOf("  ") === 0) cls = "dim";
        return '<div class="ln ' + cls + '">' + esc(line || " ") + "</div>";
      }).join("");
      log.scrollTop = log.scrollHeight;
    }

    var note = "等待开始";
    if (status === "running") note = meta.label + " · 运行中 · 自动刷新";
    else if (status === "stopping") note = "正在停止…";
    else if (status === "passed") note = meta.label + " · 完成 · 全过";
    else if (status === "failed") note = meta.label + " · " + (summary.error || "失败");
    else if (status === "stopped") note = "已手动停止";
    else if (lines.length) note = meta.label + " · 上次运行";
    setText("sim-log-note", note);
  }

  function startSim() {
    stopSimPoll();
    var payload = buildSimPayload();
    var meta = simMeta(payload.scenario);
    setText("sim-log-note", "启动中… " + meta.label);
    fetch("/api/sim/run", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Panel": "1" },
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json().then(function (body) { return { ok: res.ok, body: body }; }); })
      .then(function (result) {
        if (!result.ok) throw new Error(result.body.error || "启动失败");
        fetchSimStatus();
      })
      .catch(function (err) {
        setText("sim-log-note", "启动失败：" + err.message);
      });
  }

  function stopSim() {
    fetch("/api/sim/stop", {
      method: "POST",
      headers: { "X-Panel": "1" }
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.ok) throw new Error(data.error || "停止失败");
        fetchSimStatus();
      })
      .catch(function (err) { setText("sim-log-note", "停止失败：" + err.message); });
  }

  function bindSim() {
    $("#open-sim").addEventListener("click", openSim);
    $("#close-sim").addEventListener("click", closeSim);
    $("#sim-run").addEventListener("click", startSim);
    $("#sim-stop").addEventListener("click", stopSim);
    $("#sim-scenario").addEventListener("change", updateSimParams);
    refreshSimScenarioOptions();
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && $("#sim").classList.contains("open")) closeSim();
    });
  }

  window.__simMaskChanged = function () {
    refreshSimScenarioOptions();
    if (SIM_DATA && $("#sim").classList.contains("open")) renderSim(SIM_DATA);
  };

  /* ---------------- 命令面板 ---------------- */
  var CMD_DATA = null;
  var CMD_POLL = null;
  var CMD_LAST_SENT = 0;
  var CMD_LAST_ID = null;
  var CMD_BUILT = false;
  var CMD_SENDING = false;

  function cmdStatusText(status) {
    if (status === "queued") return "排队";
    if (status === "done") return "已执行";
    if (status === "failed") return "失败";
    if (status === "expired") return "过期";
    if (status === "unknown") return "丢弃";
    if (status === "missing") return "已消费";
    return status || "—";
  }

  function openCommand() {
    if (FEATURES.commands === false) return;
    $("#cmd-panel").classList.add("open");
    $("#cmd-backdrop").classList.add("open");
    $("#cmd-panel").setAttribute("aria-hidden", "false");
    fetchCmdStatus();
  }

  function closeCommand() {
    $("#cmd-panel").classList.remove("open");
    $("#cmd-backdrop").classList.remove("open");
    $("#cmd-panel").setAttribute("aria-hidden", "true");
    if (CMD_POLL) { clearTimeout(CMD_POLL); CMD_POLL = null; }
  }

  function fetchCmdStatus() {
    fetch("/api/cmd/status", { cache: "no-store" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        renderCmd(data);
        var queued = (data.history || []).some(function (item) { return item.status === "queued"; });
        var recently = Date.now() - CMD_LAST_SENT < 90000;
        if (queued || recently) {
          if (CMD_POLL) clearTimeout(CMD_POLL);
          CMD_POLL = setTimeout(fetchCmdStatus, 3000);
        }
      })
      .catch(function (err) {
        setText("cmd-status", "状态读取失败：" + err.message);
      });
  }

  function buildCmdButtons(allowed) {
    if (CMD_BUILT) return;
    $("#cmd-grid").innerHTML = allowed.map(function (item) {
      return '<button class="cmd-btn" data-cmd="' + esc(item.cmd) + '">' +
        '<span class="cmd-label">' + esc(item.label) + "</span>" +
        '<span class="cmd-desc">' + esc(item.desc) + "</span>" +
        '<span class="cmd-code">' + esc(item.cmd) + "</span></button>";
    }).join("");
    CMD_BUILT = true;
  }

  function renderCmd(data) {
    CMD_DATA = data;
    var current = data.current || {};
    var activity = current.activity || {};
    var nowText = "她此刻 · " + (activity.label || "—");
    if (current.room) nowText += " · " + current.room;
    setText("cmd-now", nowText);

    buildCmdButtons(data.allowed || []);
    var history = data.history || [];
    var queued = history.some(function (item) { return item.status === "queued"; });
    var buttons = document.querySelectorAll(".cmd-btn");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = CMD_SENDING || queued;
    }

    $("#cmd-history").innerHTML = history.slice(0, 7).map(function (item) {
      var cls = item.status === "done" || item.status === "missing" ? "ok" : (item.status === "queued" ? "wait" : "bad");
      return '<div class="cmd-hist">' +
        '<span class="cmd-hist-time">' + esc((item.time || "").slice(0, 5)) + "</span>" +
        '<span class="cmd-hist-label">' + esc(item.label || item.cmd) + "</span>" +
        '<span class="cmd-hist-status ' + cls + '">' + esc(cmdStatusText(item.status)) + "</span></div>";
    }).join("") || '<div class="cmd-empty">还没有指令。</div>';

    if (history.length) {
      var latest = history[0];
      if (latest.id === CMD_LAST_ID) {
        if (latest.status === "queued") setText("cmd-status", "已投递 · 等心跳（≤1 分钟）");
        else if (latest.status === "done") setText("cmd-status", "已执行 · " + (latest.label || latest.cmd));
        else if (latest.status === "failed") setText("cmd-status", "执行失败 · 会被丢弃，不重试");
        else if (latest.status === "expired") setText("cmd-status", "超过 10 分钟，已过期丢弃");
        else if (latest.status === "unknown") setText("cmd-status", "不认识，已丢弃");
      } else if (!CMD_LAST_ID && queued) {
        setText("cmd-status", "队列里还有一条没被消费");
      } else if (!CMD_LAST_ID && latest) {
        setText("cmd-status", "最近一条 · " + cmdStatusText(latest.status) + " · " + (latest.label || latest.cmd));
      }
    }
  }

  function sendCmd(cmd) {
    if (CMD_SENDING) return;
    CMD_SENDING = true;
    var buttons = document.querySelectorAll(".cmd-btn");
    for (var i = 0; i < buttons.length; i++) buttons[i].disabled = true;
    setText("cmd-status", "发送中…");
    fetch("/api/cmd", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Panel": "1" },
      body: JSON.stringify({ cmd: cmd })
    })
      .then(function (res) { return res.json().then(function (body) { return { ok: res.ok, body: body }; }); })
      .then(function (result) {
        if (!result.ok) throw new Error(result.body.error || "发送失败");
        CMD_LAST_SENT = Date.now();
        CMD_LAST_ID = result.body.command.id;
        setText("cmd-status", "已投递 · 等心跳（≤1 分钟）");
        fetchCmdStatus();
      })
      .catch(function (err) {
        setText("cmd-status", "发送失败：" + err.message);
      })
      .finally(function () {
        CMD_SENDING = false;
        fetchCmdStatus();
      });
  }

  function bindCommand() {
    $("#open-command").addEventListener("click", openCommand);
    $("#cmd-close").addEventListener("click", closeCommand);
    $("#cmd-backdrop").addEventListener("click", closeCommand);
    $("#cmd-grid").addEventListener("click", function (ev) {
      var btn = ev.target.closest(".cmd-btn");
      if (btn) sendCmd(btn.dataset.cmd);
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && $("#cmd-panel").classList.contains("open")) closeCommand();
    });
  }

  /* ---------------- 取数 ---------------- */
  function setOffline(on) {
    if (on === OFFLINE) return;
    OFFLINE = on;
    $("#offline").classList.toggle("show", on);
  }

  function load() {
    var url = "/api/all?t=" + Date.now();
    fetch(url, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        render(data);
        setOffline(false);
      })
      .catch(function (err) {
        setOffline(true);
        if (window.console) console.warn("panel refresh failed:", err);
        if (!RETRY) {
          RETRY = setTimeout(function () { RETRY = null; load(); }, 15000);
        }
      });
  }

  function boot() {
    updateMaskUI();
    var maskBtn = $("#maskel-toggle");
    if (maskBtn) {
      maskBtn.addEventListener("click", function () {
        MASK = !MASK;
        try { window.localStorage.setItem("brainMask", MASK ? "1" : "0"); } catch (e) { /* ignore */ }
        applyMask();
      });
    }
    if (DATA) render(DATA);
    else load();
    bindMemory();
    bindSim();
    bindCommand();
    loadMemoryCount();
    if (MEM_VIEW) setTimeout(openMemory, 120);
    if (SIM_VIEW) setTimeout(openSim, 120);
    if (CMD_VIEW) setTimeout(openCommand, 120);
    setInterval(load, 60 * 1000);
    setInterval(renderClock, 1000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && Date.now() - LAST_OK > 55000) load();
    });
    var moveTimer = null;
    $("#chart-wrap").addEventListener("mousemove", function (ev) {
      if (moveTimer) return;
      moveTimer = requestAnimationFrame(function () {
        moveTimer = null;
        onMove(ev);
      });
    });
    $("#chart-wrap").addEventListener("mouseleave", function () {
      $("#tooltip").classList.remove("show");
    });
    var resizeTimer = null;
    window.addEventListener("resize", function () {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        drawChart();
        layoutTimeline();
        if ($("#memory").classList.contains("open")) {
          resizeNebula();
          if ($("#mem-detail").classList.contains("open")) {
            resizeMini();
            drawMini();
          }
        }
      }, 160);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
