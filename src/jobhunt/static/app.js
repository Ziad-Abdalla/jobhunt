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
        if (j.ok === false) {
          setStatus(j.message || "refresh failed");
          return;
        }
        var msg = "added " + (j.added || 0) + " · saw " + (j.seen || 0) + " · removed " + (j.removed || 0);
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
        setStatus("scrape failed: " + e.message + " — try again in a minute");
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

  // ---------- settings page: check / install / uninstall / clear ----------
  function bindSettingsButtons() {
    var checkBtn = document.getElementById("check-btn");
    var installBtn = document.getElementById("install-btn");
    var spinner = document.getElementById("update-spinner");
    var result = document.getElementById("update-result");
    var message = document.getElementById("update-message");
    var download = document.getElementById("update-download");

    function showSpinner(on) {
      if (spinner) spinner.style.display = on ? "inline-block" : "none";
    }
    function showResult(text) {
      if (message) message.textContent = text || "";
      if (result) result.style.display = text ? "block" : "none";
    }

    if (checkBtn) {
      checkBtn.addEventListener("click", async function () {
        var was = checkBtn.textContent;
        checkBtn.disabled = true;
        checkBtn.textContent = "checking...";
        showSpinner(true);
        showResult("");
        if (download) download.style.display = "none";
        if (installBtn) installBtn.style.display = "none";
        try {
          // Passive check only — never installs.
          var r = await fetch("/api/check-update", { method: "GET" });
          var j = await r.json();
          showResult(j.message || "");
          if (j.update_available && installBtn) {
            installBtn.style.display = "inline-block";
          }
          if (j.url && download) {
            download.href = j.url;
            download.style.display = "inline-block";
          }
        } catch (e) {
          showResult("Couldn't check for updates: " + e.message + "\nTry again in a moment — your network might be flaky.");
        } finally {
          checkBtn.disabled = false;
          checkBtn.textContent = was;
          showSpinner(false);
        }
      });
    }

    if (installBtn) {
      installBtn.addEventListener("click", async function () {
        if (!window.confirm("Install the update now? jobhunt may need a restart after.")) return;
        var was = installBtn.textContent;
        installBtn.disabled = true;
        installBtn.textContent = "installing...";
        showSpinner(true);
        try {
          var r = await fetch("/api/update", { method: "POST" });
          var j = await r.json();
          var note = j.message || "Done.";
          if (j.ok) {
            note += "\n\nRestart jobhunt to pick up the new version.";
          }
          showResult(note);
          if (j.download_url && download) {
            download.href = j.download_url;
            download.style.display = "inline-block";
          }
        } catch (e) {
          showResult("Install failed: " + e.message);
        } finally {
          installBtn.disabled = false;
          installBtn.textContent = was;
          showSpinner(false);
        }
      });
    }

    var uninstallBtn = document.getElementById("uninstall-btn");
    var uninstallSpinner = document.getElementById("uninstall-spinner");
    var uninstallMessage = document.getElementById("uninstall-message");
    if (uninstallBtn) {
      uninstallBtn.addEventListener("click", async function () {
        if (!window.confirm("Uninstall jobhunt from your machine now?\nYour saved data won't be deleted.")) return;
        var was = uninstallBtn.textContent;
        uninstallBtn.disabled = true;
        uninstallBtn.textContent = "uninstalling...";
        if (uninstallSpinner) uninstallSpinner.style.display = "inline-block";
        if (uninstallMessage) uninstallMessage.style.display = "none";
        try {
          var r = await fetch("/api/uninstall-now", { method: "POST" });
          var j = await r.json();
          if (uninstallMessage) {
            uninstallMessage.textContent = j.message || "";
            uninstallMessage.style.display = "block";
          }
          if (j.uninstalled) {
            uninstallBtn.textContent = "uninstalled";
          } else {
            uninstallBtn.disabled = false;
            uninstallBtn.textContent = was;
          }
        } catch (e) {
          if (uninstallMessage) {
            uninstallMessage.textContent = "Uninstall failed: " + e.message;
            uninstallMessage.style.display = "block";
          }
          uninstallBtn.disabled = false;
          uninstallBtn.textContent = was;
        } finally {
          if (uninstallSpinner) uninstallSpinner.style.display = "none";
        }
      });
    }

    // Test API keys — live validate Jooble + Reed without saving.
    var testBtn = document.getElementById("test-keys-btn");
    if (testBtn) {
      var testStatus = document.getElementById("test-keys-status");
      var testResult = document.getElementById("test-keys-result");
      testBtn.addEventListener("click", async function () {
        testBtn.disabled = true;
        var was = testBtn.textContent;
        testBtn.textContent = "testing...";
        if (testStatus) testStatus.textContent = "";
        if (testResult) {
          while (testResult.firstChild) testResult.removeChild(testResult.firstChild);
          testResult.style.display = "none";
        }
        try {
          var form = testBtn.closest("form");
          var fd = new FormData();
          if (form) {
            var jk = form.querySelector('input[name="jooble_api_key"]');
            var rk = form.querySelector('input[name="reed_api_key"]');
            if (jk) fd.append("jooble_api_key", jk.value || "");
            if (rk) fd.append("reed_api_key", rk.value || "");
          }
          var r = await fetch("/api/settings/test-keys", { method: "POST", body: fd });
          var j = await r.json();
          if (testResult) {
            var providers = [["jooble", "Jooble"], ["reed", "Reed"]];
            for (var i = 0; i < providers.length; i++) {
              var key = providers[i][0];
              var label = providers[i][1];
              var item = j[key] || {};
              var row = document.createElement("div");
              if (item.ok === true) {
                row.style.color = "var(--green)";
                row.textContent = "✓ " + label + ": " + (item.message || "ok");
              } else if (item.ok === false) {
                row.style.color = "#c00";
                row.textContent = "✗ " + label + ": " + (item.message || "failed");
              } else {
                row.style.color = "var(--text-3)";
                row.textContent = "— " + label + ": " + (item.message || "skipped");
              }
              testResult.appendChild(row);
            }
            testResult.style.display = "block";
          }
        } catch (e) {
          if (testStatus) testStatus.textContent = "test failed: " + e.message;
        } finally {
          testBtn.disabled = false;
          testBtn.textContent = was;
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

  // ---------- keyboard shortcuts ----------
  // `/` focuses the keyword search; `r` triggers Refresh; `?` opens /help.
  // Skipped while the user is typing in any input/textarea so we never
  // hijack characters mid-edit.
  function bindKeyboardShortcuts() {
    document.addEventListener("keydown", function (e) {
      var tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.target.isContentEditable) {
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "/") {
        var q = document.querySelector('input[name="q"]') || document.querySelector('input[type="text"]');
        if (q) { q.focus(); e.preventDefault(); }
      } else if (e.key === "r") {
        var refresh = document.getElementById("refresh-btn");
        if (refresh && !refresh.disabled) { refresh.click(); e.preventDefault(); }
      } else if (e.key === "?" && e.shiftKey) {
        // Only navigate if we're not already on /help.
        if (!location.pathname.startsWith("/help")) {
          location.href = "/help";
          e.preventDefault();
        }
      }
    });
  }

  // ---------- htmx loading state on result area ----------
  function bindHtmxLoadingState() {
    var results = document.getElementById("results");
    if (!results) return;
    document.body.addEventListener("htmx:beforeRequest", function (e) {
      if (e.target === results || results.contains(e.target)) {
        results.classList.add("htmx-loading");
      }
    });
    document.body.addEventListener("htmx:afterRequest", function () {
      results.classList.remove("htmx-loading");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindRefreshButton();
    bindFilterFormShape();
    bindConfirmForms();
    bindActions();
    bindSettingsButtons();
    bindKeyboardShortcuts();
    bindHtmxLoadingState();
  });
})();
