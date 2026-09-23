"""Shared Refresh-from-Jira button markup + script for hub pages."""

from __future__ import annotations

import html
from datetime import datetime


def refresh_button_html() -> str:
    return '<button type="button" class="refresh-btn" id="jiraRefreshBtn" onclick="refreshFromJira()">Refresh from Jira</button>'


def generated_iso_stamp() -> str:
    """ISO-8601 timestamp with offset; browser formats into local timezone."""
    return datetime.now().astimezone().isoformat(timespec="minutes")


def last_refreshed_html(generated_iso: str | None = None) -> str:
    iso = html.escape(generated_iso or generated_iso_stamp())
    return (
        f'<div class="last-refreshed" id="lastRefreshedAt" data-refreshed-at="{iso}">'
        f"Last refreshed: …"
        f"</div>"
    )


def refresh_css() -> str:
    return """
    .refresh-btn {
      font-size: 11px; font-weight: 700; color: #fff; cursor: pointer;
      border: 1px solid rgba(255,255,255,.35); border-radius: 999px;
      padding: 6px 12px; background: rgba(232,113,42,.92);
    }
    .refresh-btn:hover { background: #e8712a; }
    .refresh-btn:disabled { opacity: 0.65; cursor: not-allowed; }
    .last-refreshed {
      margin-top: 10px; font-size: 11px; font-weight: 600;
      color: rgba(255,255,255,0.82); letter-spacing: 0.02em;
    }
    .refresh-toast {
      position: fixed; right: 16px; bottom: 16px; z-index: 10000;
      max-width: min(420px, calc(100vw - 32px));
      background: #1a2332; color: #e8edf4; border: 1px solid #2a3544;
      border-radius: 10px; padding: 12px 14px; font-size: 12px; line-height: 1.45;
      box-shadow: 0 8px 24px rgba(0,0,0,.35); display: none;
    }
    .refresh-toast.show { display: block; }
    .refresh-toast.error { border-color: rgba(248,113,113,.5); }
    .refresh-toast.ok { border-color: rgba(52,211,153,.45); }
"""


def refresh_js() -> str:
    return """
    function formatLastRefreshedStamp(iso) {
      try {
        var d = new Date(iso);
        if (isNaN(d.getTime())) return iso || "—";
        return d.toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          year: "numeric",
          hour: "numeric",
          minute: "2-digit"
        });
      } catch (err) {
        return iso || "—";
      }
    }

    function initLastRefreshed() {
      var el = document.getElementById("lastRefreshedAt");
      if (!el) return;
      var iso = el.getAttribute("data-refreshed-at") || "";
      el.textContent = "Last refreshed: " + formatLastRefreshedStamp(iso);
    }

    function showRefreshToast(message, kind) {
      var el = document.getElementById("refreshToast");
      if (!el) {
        el = document.createElement("div");
        el.id = "refreshToast";
        el.className = "refresh-toast";
        document.body.appendChild(el);
      }
      el.className = "refresh-toast show " + (kind || "");
      el.textContent = message;
      clearTimeout(window.__refreshToastTimer);
      window.__refreshToastTimer = setTimeout(function () {
        el.classList.remove("show");
      }, 10000);
    }

    function setRefreshButtonState(opts) {
      var btn = document.getElementById("jiraRefreshBtn");
      if (!btn) return;
      var allowed = !opts || opts.allowed !== false;
      var label = (opts && opts.label) || (allowed ? "Refresh from Jira" : "Refresh (wait 1h)");
      btn.disabled = !allowed || Boolean(opts && opts.busy);
      btn.textContent = label;
      btn.title = (opts && opts.title) || (allowed
        ? "Refresh dashboards from Jira (once per hour)"
        : ((opts && opts.message) || "Refresh allowed once per hour"));
    }

    async function syncRefreshCooldown() {
      try {
        var res = await fetch("/api/refresh", { method: "GET", cache: "no-store" });
        var data = {};
        try { data = await res.json(); } catch (e) { data = {}; }
        if (data && data.configured === false) {
          setRefreshButtonState({
            allowed: false,
            label: "Refresh (not configured)",
            title: data.message || "Refresh is not configured"
          });
          return data;
        }
        if (data && data.allowed === false) {
          var mins = Math.max(1, Math.ceil((data.retryAfterMs || 0) / 60000));
          setRefreshButtonState({
            allowed: false,
            label: "Refresh in " + mins + "m",
            message: data.message || ("Refresh allowed once per hour. Try again in about " + mins + " minutes."),
            title: data.message
          });
        } else {
          setRefreshButtonState({ allowed: true });
        }
        return data;
      } catch (err) {
        setRefreshButtonState({ allowed: true });
        return null;
      }
    }

    async function refreshFromJira() {
      var btn = document.getElementById("jiraRefreshBtn");
      if (btn && btn.disabled) return;
      setRefreshButtonState({ allowed: true, busy: true, label: "Refreshing…" });
      try {
        var passphrase = (typeof PASSPHRASE === "string" && PASSPHRASE)
          || (typeof HUB_PASS === "string" && HUB_PASS)
          || "wfm";
        var res = await fetch("/api/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ passphrase: passphrase }),
        });
        var data = {};
        try { data = await res.json(); } catch (e) { data = {}; }
        if (res.status === 429 || (data && data.ok === false && data.retryAfterMs)) {
          showRefreshToast((data && data.error) ? data.error : "Refresh allowed once per hour.", "error");
          await syncRefreshCooldown();
          return;
        }
        if (!res.ok || !data.ok) {
          showRefreshToast((data && data.error) ? data.error : ("Refresh failed (" + res.status + ")"), "error");
          await syncRefreshCooldown();
          return;
        }
        showRefreshToast(
          (data.message || "Refresh started.") +
          " Watch the Last refreshed timestamp after reload (1–3 min).",
          "ok"
        );
        setRefreshButtonState({
          allowed: false,
          label: "Refresh in 60m",
          title: "Refresh allowed once per hour"
        });
      } catch (err) {
        showRefreshToast(err && err.message ? err.message : "Refresh request failed", "error");
        await syncRefreshCooldown();
      }
    }

    initLastRefreshed();
    syncRefreshCooldown();
"""
