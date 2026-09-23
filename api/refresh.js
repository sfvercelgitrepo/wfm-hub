/**
 * POST /api/refresh
 *
 * Triggers the GitHub Action that exports Jira data, rebuilds dashboards,
 * commits HTML, and lets Vercel redeploy.
 *
 * Rate limit: one successful dispatch per hour (based on latest workflow run).
 *
 * Auth (either):
 *   - Header: x-refresh-secret: $REFRESH_SECRET
 *   - Body:   { "passphrase": "$HUB_PASSPHRASE" }  (default passphrase: wfm)
 *
 * Vercel env:
 *   HUB_PASSPHRASE      – optional, defaults to wfm
 *   REFRESH_SECRET      – optional stronger secret via header
 *   GITHUB_TOKEN        – PAT with actions:write on the hub repo
 *   GITHUB_REPO         – e.g. sfvercelgitrepo/wfm-hub
 *   GITHUB_WORKFLOW_FILE – optional, default refresh-dashboards.yml
 *   REFRESH_COOLDOWN_MS  – optional, default 3600000 (1 hour)
 */

const DEFAULT_COOLDOWN_MS = 60 * 60 * 1000;

function cooldownMs() {
  const raw = Number(process.env.REFRESH_COOLDOWN_MS || DEFAULT_COOLDOWN_MS);
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_COOLDOWN_MS;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    if (req.body && typeof req.body === "object") {
      resolve(req.body);
      return;
    }
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 1e6) reject(new Error("Body too large"));
    });
    req.on("end", () => {
      if (!raw) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

function isAuthorized(req, body) {
  const refreshSecret = (process.env.REFRESH_SECRET || "").trim();
  const hubPass = (process.env.HUB_PASSPHRASE || "wfm").trim();
  const headerSecret = (req.headers["x-refresh-secret"] || "").trim();
  const bodyPass = String(body.passphrase || body.password || "").trim();

  if (refreshSecret && headerSecret && headerSecret === refreshSecret) return true;
  if (bodyPass && bodyPass === hubPass) return true;
  return false;
}

function ghHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "wfm-hub-refresh",
  };
}

async function getLatestDispatchRun(token, repo, workflow) {
  const url =
    `https://api.github.com/repos/${repo}/actions/workflows/` +
    `${encodeURIComponent(workflow)}/runs?event=workflow_dispatch&per_page=1`;
  const res = await fetch(url, { headers: ghHeaders(token) });
  if (!res.ok) {
    const text = await res.text();
    const err = new Error(`GitHub runs lookup failed (${res.status})`);
    err.detail = text.slice(0, 500);
    err.status = res.status;
    throw err;
  }
  const data = await res.json();
  return (data.workflow_runs && data.workflow_runs[0]) || null;
}

function cooldownStatus(run, windowMs) {
  if (!run || !run.created_at) {
    return { allowed: true, retryAfterMs: 0, lastRefreshAt: null };
  }
  const created = Date.parse(run.created_at);
  if (!Number.isFinite(created)) {
    return { allowed: true, retryAfterMs: 0, lastRefreshAt: run.created_at };
  }
  const elapsed = Date.now() - created;
  if (elapsed >= windowMs) {
    return { allowed: true, retryAfterMs: 0, lastRefreshAt: run.created_at };
  }
  return {
    allowed: false,
    retryAfterMs: windowMs - elapsed,
    lastRefreshAt: run.created_at,
  };
}

function formatRetryMessage(retryAfterMs) {
  const mins = Math.max(1, Math.ceil(retryAfterMs / 60000));
  return `Refresh allowed once per hour. Try again in about ${mins} minute${
    mins === 1 ? "" : "s"
  }.`;
}

function sendJson(res, status, payload) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(payload));
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");

  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    res.end();
    return;
  }

  const token = (process.env.GITHUB_TOKEN || "").trim();
  const repo = (process.env.GITHUB_REPO || "").trim();
  const workflow =
    (process.env.GITHUB_WORKFLOW_FILE || "refresh-dashboards.yml").trim();
  const ref = (process.env.GITHUB_REF || "main").trim();
  const windowMs = cooldownMs();
  const configured = Boolean(token && repo);

  if (req.method === "GET") {
    if (!configured) {
      sendJson(res, 200, {
        ok: true,
        configured: false,
        cooldownMs: windowMs,
        allowed: false,
        message: "Missing GITHUB_TOKEN / GITHUB_REPO on Vercel.",
      });
      return;
    }
    try {
      const run = await getLatestDispatchRun(token, repo, workflow);
      const status = cooldownStatus(run, windowMs);
      sendJson(res, 200, {
        ok: true,
        configured: true,
        cooldownMs: windowMs,
        allowed: status.allowed,
        retryAfterMs: status.retryAfterMs,
        lastRefreshAt: status.lastRefreshAt,
        message: status.allowed
          ? "POST with passphrase to start a Jira refresh + redeploy."
          : formatRetryMessage(status.retryAfterMs),
      });
    } catch (err) {
      sendJson(res, 200, {
        ok: true,
        configured: true,
        cooldownMs: windowMs,
        allowed: true,
        retryAfterMs: 0,
        message:
          "Cooldown check unavailable; POST may still be rate-limited after dispatch.",
        detail: err && err.message ? err.message : "lookup failed",
      });
    }
    return;
  }

  if (req.method !== "POST") {
    sendJson(res, 405, { ok: false, error: "Method not allowed" });
    return;
  }

  let body = {};
  try {
    body = await readBody(req);
  } catch (err) {
    sendJson(res, 400, { ok: false, error: "Invalid JSON body" });
    return;
  }

  if (!isAuthorized(req, body)) {
    sendJson(res, 401, { ok: false, error: "Unauthorized" });
    return;
  }

  if (!configured) {
    sendJson(res, 503, {
      ok: false,
      error:
        "Refresh is not configured. Set GITHUB_TOKEN and GITHUB_REPO on Vercel.",
    });
    return;
  }

  try {
    const run = await getLatestDispatchRun(token, repo, workflow);
    const status = cooldownStatus(run, windowMs);
    if (!status.allowed) {
      res.setHeader(
        "Retry-After",
        String(Math.max(1, Math.ceil(status.retryAfterMs / 1000)))
      );
      sendJson(res, 429, {
        ok: false,
        error: formatRetryMessage(status.retryAfterMs),
        retryAfterMs: status.retryAfterMs,
        lastRefreshAt: status.lastRefreshAt,
        cooldownMs: windowMs,
      });
      return;
    }

    const url = `https://api.github.com/repos/${repo}/actions/workflows/${encodeURIComponent(
      workflow
    )}/dispatches`;
    const ghRes = await fetch(url, {
      method: "POST",
      headers: {
        ...ghHeaders(token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref }),
    });

    if (!ghRes.ok) {
      const text = await ghRes.text();
      sendJson(res, 502, {
        ok: false,
        error: `GitHub workflow dispatch failed (${ghRes.status})`,
        detail: text.slice(0, 500),
      });
      return;
    }

    sendJson(res, 202, {
      ok: true,
      cooldownMs: windowMs,
      message:
        "Jira refresh started. Dashboards will update after the GitHub Action finishes and Vercel redeploys (usually 1–3 minutes). Reload this page then. Next refresh is available in 1 hour.",
    });
  } catch (err) {
    sendJson(res, 500, {
      ok: false,
      error: err && err.message ? err.message : "Refresh failed",
      detail: err && err.detail ? err.detail : undefined,
    });
  }
};
