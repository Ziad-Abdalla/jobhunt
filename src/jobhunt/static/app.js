// jobhunt — client. CSP-friendly (no inline handlers, no eval).
(function () {
  "use strict";

  // ---------- refresh sources ----------
  function setStatus(msg, opts) {
    var status = document.getElementById("refresh-status");
    if (!status) return;
    opts = opts || {};
    status.textContent = "";
    if (opts.spinner) {
      var sp = document.createElement("span");
      sp.className = "spinner";
      sp.setAttribute("aria-hidden", "true");
      status.appendChild(sp);
    }
    status.appendChild(document.createTextNode(msg));
  }

  function bindRefreshButton() {
    var btn = document.getElementById("refresh-btn");
    if (!btn) return;
    btn.addEventListener("click", async function () {
      var wasText = btn.textContent;
      btn.disabled = true;
      btn.textContent = "scraping...";
      setStatus("pulling from every source — takes about a minute", { spinner: true });
      document.body.classList.add("results-loading");
      try {
        var r = await fetch("/api/refresh", { method: "POST" });
        if (!r.ok) throw new Error("HTTP " + r.status);
        var j = await r.json();
        var msg = "added " + j.added + " · saw " + j.seen + " · removed " + j.removed;
        if (j.alerts && typeof j.alerts.notified === "number" && j.alerts.notified > 0) {
          msg += " · " + j.alerts.notified + " alert" + (j.alerts.notified === 1 ? "" : "s") + " sent";
        }
        setStatus(msg);
        var form = document.getElementById("filters");
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
    var form = document.getElementById("filters");
    if (!form) return;
    form.addEventListener("htmx:configRequest", function (evt) {
      var data = evt.detail.parameters;
      ["languages", "skills"].forEach(function (key) {
        var val = (data[key] || "").toString();
        delete data[key];
        var items = val.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        if (items.length) data[key] = items;
      });
    });
  }

  // ---------- confirm before destructive forms ----------
  function bindConfirmForms() {
    document.querySelectorAll("form[data-confirm]").forEach(function (f) {
      f.addEventListener("submit", function (evt) {
        var msg = f.getAttribute("data-confirm") || "Are you sure?";
        if (!window.confirm(msg)) evt.preventDefault();
      });
    });
  }

  // ---------- generic POST action buttons ----------
  async function postAction(url, statusEl, prefix) {
    if (statusEl) statusEl.textContent = "...";
    try {
      var r = await fetch(url, { method: "POST" });
      var j = await r.json();
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
        var refreshBtn = document.getElementById("refresh-btn");
        if (refreshBtn) refreshBtn.click();
      });
    });
  }

  // ---------- settings page: update + clear buttons ----------
  function bindSettingsButtons() {
    // Check for updates
    var updateBtn = document.getElementById("update-btn");
    if (updateBtn) {
      var updateSpinner = document.getElementById("update-spinner");
      var updateResult = document.getElementById("update-result");
      var updateMessage = document.getElementById("update-message");
      var updateDownload = document.getElementById("update-download");

      updateBtn.addEventListener("click", async function () {
        var was = updateBtn.textContent;
        updateBtn.disabled = true;
        updateBtn.textContent = "checking...";
        if (updateSpinner) updateSpinner.style.display = "inline-block";
        if (updateResult) updateResult.style.display = "none";
        if (updateDownload) updateDownload.style.display = "none";
        try {
          var r = await fetch("/api/update", { method: "POST" });
          var j = await r.json();
          if (updateMessage) updateMessage.textContent = j.message || "Done.";
          if (updateResult) updateResult.style.display = "block";
          if (j.download_url && updateDownload) {
            updateDownload.href = j.download_url;
            updateDownload.style.display = "inline-block";
          }
        } catch (e) {
          if (updateMessage) updateMessage.textContent = "Error: " + e.message;
          if (updateResult) updateResult.style.display = "block";
        } finally {
          updateBtn.disabled = false;
          updateBtn.textContent = was;
          if (updateSpinner) updateSpinner.style.display = "none";
        }
      });
    }

    // Clear all jobs
    var clearBtn = document.getElementById("clear-btn");
    if (clearBtn) {
      var clearStatus = document.getElementById("clear-status");
      clearBtn.addEventListener("click", async function () {
        if (!window.confirm("Delete all scraped jobs? They come back on next refresh.")) return;
        clearBtn.disabled = true;
        if (clearStatus) clearStatus.textContent = "";
        try {
          var r = await fetch("/api/clear-data", { method: "POST" });
          var j = await r.json();
          if (clearStatus) clearStatus.textContent = j.message || "Done.";
        } catch (e) {
          if (clearStatus) clearStatus.textContent = "Error: " + e.message;
        } finally {
          clearBtn.disabled = false;
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindRefreshButton();
    bindFilterFormShape();
    bindConfirmForms();
    bindActions();
    bindSettingsButtons();
  });
})();
