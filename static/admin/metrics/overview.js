(function () {
  "use strict";

  const overview = document.querySelector(".metrics-overview");
  const detail = document.querySelector(".metrics-detail");
  const main = overview || detail;
  if (!main) return;

  const slug = detail ? detail.dataset.slug : "overview";
  const pollMs = Math.max(1000, parseInt(main.dataset.pollMs || "5000", 10));
  const apiUrl = "/admin/metrics/api?module=" + encodeURIComponent(slug);

  let lastTick = 0;
  let timerId = null;
  let inflight = false;

  function applyOverview(payload) {
    const grid = overview.querySelector(".cards-grid");
    if (!grid) return;
    const modules = payload.modules || [];
    const cards = modules.map(function (m) {
      const kvs = (m.kvs || [])
        .map(function (kv) {
          return (
            '<div class="kv"><span class="k">' +
            escapeHtml(kv.label) +
            '</span><span class="v sev-' +
            escapeHtml(kv.severity || "neutral") +
            '">' +
            escapeHtml(kv.value) +
            "</span></div>"
          );
        })
        .join("");
      return (
        '<a class="modcard" href="/admin/metrics/' +
        encodeURIComponent(m.slug) +
        '" data-slug="' +
        escapeHtml(m.slug) +
        '"><div class="arrow">&rarr;</div><div class="ttl">' +
        escapeHtml(m.name) +
        "</div>" +
        kvs +
        "</a>"
      );
    });
    grid.innerHTML = cards.join("");
  }

  function applyDetail(payload) {
    const sections = payload.sections || [];
    const panels = detail.querySelectorAll(".panel");
    if (!panels.length) return;
    sections.forEach(function (section, idx) {
      const panel = panels[idx];
      if (!panel) return;
      const kvs = section.payload && section.payload.kvs;
      if (Array.isArray(kvs)) {
        const html = kvs
          .map(function (pair) {
            const label = pair[0];
            const value = pair[1];
            return (
              '<div class="metric"><span class="label">' +
              escapeHtml(label) +
              '</span><span class="value">' +
              escapeHtml(value) +
              "</span></div>"
            );
          })
          .join("");
        const heading = panel.querySelector("h2");
        panel.innerHTML = (heading ? heading.outerHTML : "") + html;
      }
    });
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function tick() {
    if (inflight || document.hidden) return;
    inflight = true;
    try {
      const resp = await fetch(apiUrl, { credentials: "same-origin" });
      if (!resp.ok) throw new Error("status " + resp.status);
      const payload = await resp.json();
      if (overview) applyOverview(payload);
      else applyDetail(payload);
      lastTick = Date.now();
      document.body.classList.remove("stale");
    } catch (err) {
      console.warn("metrics fetch failed", err);
      if (lastTick && Date.now() - lastTick > 2 * pollMs) {
        document.body.classList.add("stale");
      }
    } finally {
      inflight = false;
    }
  }

  function start() {
    if (timerId) return;
    timerId = setInterval(tick, pollMs);
  }

  function stop() {
    if (!timerId) return;
    clearInterval(timerId);
    timerId = null;
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stop();
    else start();
  });
  window.addEventListener("beforeunload", stop);
  start();
})();
