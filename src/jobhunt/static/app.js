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
      setStatus("pulling jobs in the background — keep browsing", { spinner: true });
      var elapsed = 0;

      function finish(last) {
        document.body.classList.remove("results-loading");
        btn.disabled = false;
        btn.textContent = wasText;
        last = last || {};
        var msg = "added " + (last.added || 0) + " · saw " + (last.seen || 0) + " · removed " + (last.removed || 0);
        if (last.alerts && typeof last.alerts.notified === "number" && last.alerts.notified > 0) {
          msg += " · " + last.alerts.notified + " alert" + (last.alerts.notified === 1 ? "" : "s") + " sent";
        }
        setStatus(msg);
        var form = document.getElementById("filters");
        if (form) form.dispatchEvent(new Event("submit", { bubbles: true }));
        if (document.body.dataset.page === "health") {
          setTimeout(function () { location.reload(); }, 800);
        }
      }

      try {
        var r = await fetch("/api/refresh", { method: "POST" });
        if (!r.ok) throw new Error("HTTP " + r.status);
        var j = await r.json();
        if (j.ok === false) {
          setStatus(j.message || "refresh failed");
          btn.disabled = false;
          btn.textContent = wasText;
          return;
        }
        // The scrape runs in the background; poll for completion so the button
        // never hangs and the page stays usable meanwhile.
        var fails = 0;
        var poll = setInterval(async function () {
          elapsed += 3;
          // Hard caps so the poll can never spin forever (a wedged server or a
          // stuck "running" flag won't keep hammering the endpoint).
          if (elapsed > 1800 || fails > 20) {
            clearInterval(poll);
            finish((typeof s !== "undefined" && s && s.last) || {});
            return;
          }
          try {
            var s = await (await fetch("/api/refresh/status")).json();
            fails = 0;
            if (!s.running) {
              clearInterval(poll);
              finish(s.last);
            } else {
              setStatus("scraping in the background — " + elapsed + "s — keep browsing", { spinner: true });
            }
          } catch (e) { fails += 1; }
        }, 3000);
      } catch (e) {
        document.body.classList.remove("results-loading");
        btn.disabled = false;
        btn.textContent = wasText;
        setStatus("scrape failed: " + e.message + " — try again in a minute");
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

  // ---------- first-run setup prompt (missing API keys / location) ----------
  function bindSetupModal() {
    var modal = document.getElementById("setup-modal");
    if (!modal) return;
    var DISMISS_KEY = "jobhunt_setup_dismissed";
    var $ = function (id) { return document.getElementById(id); };

    function dismissed() {
      try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch (e) { return false; }
    }
    function remember() {
      try { localStorage.setItem(DISMISS_KEY, "1"); } catch (e) { /* ignore */ }
    }

    fetch("/api/settings/missing").then(function (r) { return r.json(); }).then(function (d) {
      var v = (d && d.values) || {};
      if ($("setup-location")) $("setup-location").value = v.location || "";
      if ($("setup-reed")) $("setup-reed").value = v.reed || "";
      if ($("setup-jooble")) $("setup-jooble").value = v.jooble || "";
      if (d && d.prompt && !dismissed()) modal.hidden = false;
    }).catch(function () { /* offline — no prompt */ });

    if ($("setup-skip")) $("setup-skip").addEventListener("click", function () {
      remember();
      modal.hidden = true;
    });

    if ($("setup-save")) $("setup-save").addEventListener("click", async function () {
      var btn = this;
      var result = $("setup-result");
      var loc = ($("setup-location") || {}).value || "";
      var reed = (($("setup-reed") || {}).value || "").trim();
      var jooble = (($("setup-jooble") || {}).value || "").trim();
      btn.disabled = true;
      if (result) result.textContent = "Saving and testing…";
      try {
        var save = new URLSearchParams();
        save.set("user_location", loc);
        save.set("reed_api_key", reed);
        save.set("jooble_api_key", jooble);
        await fetch("/api/settings/save", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: save.toString(),
        });
        var tp = new URLSearchParams();
        tp.set("reed_api_key", reed);
        tp.set("jooble_api_key", jooble);
        var t = await (await fetch("/api/settings/test-keys", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: tp.toString(),
        })).json();
        var parts = [];
        if (reed) parts.push((t.reed && t.reed.ok === true ? "Reed ✓ " : "Reed ✗ ") + ((t.reed && t.reed.message) || ""));
        if (jooble) parts.push((t.jooble && t.jooble.ok === true ? "Jooble ✓ " : "Jooble ✗ ") + ((t.jooble && t.jooble.message) || ""));
        if (result) result.textContent = parts.join("   ·   ") || "Saved.";
        var reedOk = !reed || (t.reed && t.reed.ok === true);
        if (reedOk) {
          if (result) result.textContent += "   — all set! reloading…";
          setTimeout(function () { location.reload(); }, 1400);
        } else {
          btn.disabled = false;
        }
      } catch (e) {
        if (result) result.textContent = "Something went wrong: " + e.message;
        btn.disabled = false;
      }
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
    bindSetupModal();
  });
})();
