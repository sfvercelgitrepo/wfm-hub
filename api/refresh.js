/**
 * POST /api/refresh
 *
 * Triggers the GitHub Action that exports Jira data, rebuilds dashboards,
 * commits HTML, and lets Vercel redeploy.
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
 */

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

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");

  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    res.end();
    return;
  }

  if (req.method === "GET") {
    const configured = Boolean(
      (process.env.GITHUB_TOKEN || "").trim() && (process.env.GITHUB_REPO || "").trim()
    );
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({
        ok: true,
        configured,
        message: configured
          ? "POST with passphrase to start a Jira refresh + redeploy."
          : "Missing GITHUB_TOKEN / GITHUB_REPO on Vercel.",
      })
    );
    return;
  }

  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Method not allowed" }));
    return;
  }

  let body = {};
  try {
    body = await readBody(req);
  } catch (err) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Invalid JSON body" }));
    return;
  }

  if (!isAuthorized(req, body)) {
    res.statusCode = 401;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Unauthorized" }));
    return;
  }

  const token = (process.env.GITHUB_TOKEN || "").trim();
  const repo = (process.env.GITHUB_REPO || "").trim();
  const workflow =
    (process.env.GITHUB_WORKFLOW_FILE || "refresh-dashboards.yml").trim();
  const ref = (process.env.GITHUB_REF || "main").trim();

  if (!token || !repo) {
    res.statusCode = 503;
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({
        ok: false,
        error:
          "Refresh is not configured. Set GITHUB_TOKEN and GITHUB_REPO on Vercel.",
      })
    );
    return;
  }

  try {
    const url = `https://api.github.com/repos/${repo}/actions/workflows/${encodeURIComponent(
      workflow
    )}/dispatches`;
    const ghRes = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "wfm-hub-refresh",
      },
      body: JSON.stringify({ ref }),
    });

    if (!ghRes.ok) {
      const text = await ghRes.text();
      res.statusCode = 502;
      res.setHeader("Content-Type", "application/json");
      res.end(
        JSON.stringify({
          ok: false,
          error: `GitHub workflow dispatch failed (${ghRes.status})`,
          detail: text.slice(0, 500),
        })
      );
      return;
    }

    res.statusCode = 202;
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({
        ok: true,
        message:
          "Jira refresh started. Dashboards will update after the GitHub Action finishes and Vercel redeploys (usually 1–3 minutes). Reload this page then.",
      })
    );
  } catch (err) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({
        ok: false,
        error: err && err.message ? err.message : "Refresh failed",
      })
    );
  }
};
