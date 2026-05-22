// jobhunt — small client. CSP-friendly (no inline handlers, no eval).
(function () {
  "use strict";

  // ---------- refresh sources ----------
  function setStatus(msg, opts) {
    const status = document.getElementById("refresh-status");
    if (!status) return;
    opts = opts || {};
    status.textContent = "";
    if (opts.spinner) {
      const sp = document.createElement("span");
      sp.className = "spinner";
      sp.setAttribute("aria-hidden", "true");
      status.appendChild(sp);
    }
    status.appendChild(document.createTextNode(msg));
  }

  function bindRefreshButton() {
    const btn = document.getElementById("refresh-btn");
    if (!btn) return;
    btn.addEventListener("click", async function () {
      const wasText = btn.textContent;
      btn.disabled = true;
      btn.textContent = "scraping…";
      setStatus("pulling from every source — this takes ~1 minute", { spinner: true });
      document.body.classList.add("results-loading");
      try {
        const r = await fetch("/api/refresh", { method: "POST" });
        if (!r.ok) throw new Error("HTTP " + r.status);
        const j = await r.json();
        let msg = "added " + j.added + " · saw " + j.seen + " · removed " + j.removed;
        if (j.alerts && typeof j.alerts.notified === "number" && j.alerts.notified > 0) {
          msg += " · " + j.alerts.notified + " alert" + (j.alerts.notified === 1 ? "" : "s") + " sent";
        }
        setStatus(msg);
        const form = document.getElementById("filters");
        if (form) form.dispatchEvent(new Event("submit", { bubbles: true }));
        if (document.body.dataset.page === "health") {
          setTimeout(function () { location.reload(); }, 800);
        }
      } catch (e) {
        setStatus("scrape failed: " + e.message);
      } finally {
        document.body.classList.remove("results-loading");
        btn.disabled = false;
        btn.textContent = wasText;
      }
    });
  }

  // ---------- HTMX: split comma-separated lists into repeated params ----------
  function bindFilterFormShape() {
    const form = document.getElementById("filters");
    if (!form) return;
    form.addEventListener("htmx:configRequest", function (evt) {
      const data = evt.detail.parameters;
      ["languages", "skills"].forEach(function (key) {
        const val = (data[key] || "").toString();
        delete data[key];
        const items = val.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        if (items.length) data[key] = items;
      });
    });
  }

  // ---------- danger: confirm before destructive submit ----------
  function bindConfirmForms() {
    document.querySelectorAll("form[data-confirm]").forEach(function (f) {
      f.addEventListener("submit", function (evt) {
        const msg = f.getAttribute("data-confirm") || "Are you sure?";
        if (!window.confirm(msg)) evt.preventDefault();
      });
    });
  }

  // ---------- generic action buttons (CV match, alerts check) ----------
  async function postAction(url, statusEl, prefix) {
    if (statusEl) statusEl.textContent = "…";
    try {
      const r = await fetch(url, { method: "POST" });
      const j = await r.json();
      if (statusEl) {
        if (typeof j.updated === "number") statusEl.textContent = prefix + j.updated + " jobs";
        else if (typeof j.notified === "number") statusEl.textContent = "notified " + j.notified + " from " + j.searches + " saved searches";
        else statusEl.textContent = JSON.stringify(j);
      }
    } catch (e) {
      if (statusEl) statusEl.textContent = "failed: " + e.message;
    }
  }
  function bindActions() {
    document.querySelectorAll("[data-action='cv-rematch']").forEach(function (btn) {
      btn.addEventListener("click", function () {
        postAction("/cv/match", document.getElementById("match-status"), "re-scored ");
      });
    });
    document.querySelectorAll("[data-action='check-alerts']").forEach(function (btn) {
      btn.addEventListener("click", function () {
        postAction("/api/alerts/check", document.getElementById("check-status"), "");
      });
    });
    document.querySelectorAll("[data-action='refresh-now']").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const refreshBtn = document.getElementById("refresh-btn");
        if (refreshBtn) refreshBtn.click();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindRefreshButton();
    bindFilterFormShape();
    bindConfirmForms();
    bindActions();
  });
})();
