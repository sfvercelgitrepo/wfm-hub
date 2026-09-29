/**
 * GET/PUT /api/design-visibility
 *
 * Shared field-visibility map for DesignSFDataDictionary.html.
 * Stored in-repo at data/design-sf-visibility.json via GitHub Contents API
 * so all viewers see the same locked-mode field set.
 *
 * Auth for writes:
 *   Body passphrase must equal wfmadmin + mmddyyyy (today, a few TZ-safe variants)
 *
 * Env:
 *   GITHUB_TOKEN, GITHUB_REPO (required for read/write against GitHub)
 *   GITHUB_VISIBILITY_PATH – optional, default data/design-sf-visibility.json
 *   GITHUB_REF – optional, default main
 */

const DEFAULT_PATH = "data/design-sf-visibility.json";

function sendJson(res, status, payload) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(payload));
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
      if (raw.length > 2e6) reject(new Error("Body too large"));
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

function pad2(n) {
  return String(n).padStart(2, "0");
}

function passwordForParts(year, month, day) {
  return `wfmadmin${pad2(month)}${pad2(day)}${year}`;
}

function passwordForDate(date) {
  return passwordForParts(
    date.getFullYear(),
    date.getMonth() + 1,
    date.getDate()
  );
}

function passwordForTimeZone(timeZone, baseDate) {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(baseDate);
    const map = {};
    parts.forEach((p) => {
      if (p.type !== "literal") map[p.type] = p.value;
    });
    return passwordForParts(
      Number(map.year),
      Number(map.month),
      Number(map.day)
    );
  } catch (err) {
    return null;
  }
}

function acceptedPasswords(now = new Date()) {
  const set = new Set();
  const days = [0, -1, 1].map((offset) => {
    const d = new Date(now.getTime());
    d.setUTCDate(d.getUTCDate() + offset);
    return d;
  });
  days.forEach((d) => {
    set.add(passwordForDate(d));
    set.add(passwordForParts(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()));
  });
  ["America/Chicago", "America/New_York", "America/Los_Angeles", "UTC"].forEach(
    (tz) => {
      days.forEach((d) => {
        const pw = passwordForTimeZone(tz, d);
        if (pw) set.add(pw);
      });
    }
  );
  return set;
}

function isAuthorized(passphrase) {
  const value = String(passphrase || "").trim();
  if (!value) return false;
  return acceptedPasswords().has(value);
}

function ghHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "wfm-hub-design-visibility",
  };
}

function config() {
  return {
    token: (process.env.GITHUB_TOKEN || "").trim(),
    repo: (process.env.GITHUB_REPO || "").trim(),
    path: (process.env.GITHUB_VISIBILITY_PATH || DEFAULT_PATH).trim(),
    ref: (process.env.GITHUB_REF || "main").trim(),
  };
}

function normalizePayload(input) {
  const visibility =
    input && typeof input.visibility === "object" && input.visibility
      ? input.visibility
      : {};
  const clean = {};
  Object.keys(visibility).forEach((key) => {
    if (typeof key !== "string" || !key.includes("::")) return;
    clean[key] = visibility[key] !== false;
  });
  return {
    updatedAt: input && input.updatedAt ? input.updatedAt : null,
    visibility: clean,
  };
}

async function readVisibilityFile(cfg) {
  const url =
    `https://api.github.com/repos/${cfg.repo}/contents/` +
    `${encodeURIComponent(cfg.path).replace(/%2F/g, "/")}?ref=${encodeURIComponent(
      cfg.ref
    )}`;
  const res = await fetch(url, { headers: ghHeaders(cfg.token) });
  if (res.status === 404) {
    return {
      sha: null,
      payload: { updatedAt: null, visibility: {} },
    };
  }
  if (!res.ok) {
    const text = await res.text();
    const err = new Error(`GitHub read failed (${res.status})`);
    err.detail = text.slice(0, 500);
    throw err;
  }
  const data = await res.json();
  const decoded = Buffer.from(data.content || "", "base64").toString("utf8");
  let parsed = { updatedAt: null, visibility: {} };
  try {
    parsed = normalizePayload(JSON.parse(decoded || "{}"));
  } catch (err) {
    parsed = { updatedAt: null, visibility: {} };
  }
  return { sha: data.sha, payload: parsed };
}

async function writeVisibilityFile(cfg, payload, sha) {
  const body = {
    message: "Update SF Data Dictionary field visibility.",
    content: Buffer.from(JSON.stringify(payload, null, 2) + "\n", "utf8").toString(
      "base64"
    ),
    branch: cfg.ref,
  };
  if (sha) body.sha = sha;

  const url =
    `https://api.github.com/repos/${cfg.repo}/contents/` +
    `${encodeURIComponent(cfg.path).replace(/%2F/g, "/")}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: {
      ...ghHeaders(cfg.token),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    const err = new Error(`GitHub write failed (${res.status})`);
    err.detail = text.slice(0, 500);
    throw err;
  }
  return res.json();
}

function readLocalVisibilityFile(relPath) {
  try {
    const fs = require("fs");
    const path = require("path");
    const full = path.join(process.cwd(), relPath);
    if (!fs.existsSync(full)) return null;
    const parsed = JSON.parse(fs.readFileSync(full, "utf8"));
    return normalizePayload(parsed);
  } catch (err) {
    return null;
  }
}

module.exports = async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    res.end();
    return;
  }

  const cfg = config();
  const ghReady = Boolean(cfg.token && cfg.repo);

  if (req.method === "GET") {
    try {
      if (ghReady) {
        const current = await readVisibilityFile(cfg);
        sendJson(res, 200, {
          ok: true,
          path: cfg.path,
          updatedAt: current.payload.updatedAt,
          visibility: current.payload.visibility,
        });
        return;
      }
      const local = readLocalVisibilityFile(cfg.path);
      sendJson(res, 200, {
        ok: true,
        path: cfg.path,
        source: "local",
        updatedAt: local ? local.updatedAt : null,
        visibility: local ? local.visibility : {},
      });
    } catch (err) {
      sendJson(res, 502, {
        ok: false,
        error: err && err.message ? err.message : "Failed to load visibility",
        detail: err && err.detail ? err.detail : undefined,
      });
    }
    return;
  }

  if (req.method !== "PUT" && req.method !== "POST") {
    sendJson(res, 405, { ok: false, error: "Method not allowed" });
    return;
  }

  if (!ghReady) {
    sendJson(res, 503, {
      ok: false,
      error:
        "Visibility API is not configured. Set GITHUB_TOKEN and GITHUB_REPO on Vercel.",
    });
    return;
  }

  let body = {};
  try {
    body = await readBody(req);
  } catch (err) {
    sendJson(res, 400, { ok: false, error: "Invalid JSON body" });
    return;
  }

  if (!isAuthorized(body.passphrase || body.password)) {
    sendJson(res, 401, { ok: false, error: "Unauthorized" });
    return;
  }

  try {
    const current = await readVisibilityFile(cfg);
    const next = normalizePayload({
      updatedAt: new Date().toISOString(),
      visibility: body.visibility || {},
    });
    await writeVisibilityFile(cfg, next, current.sha);
    sendJson(res, 200, {
      ok: true,
      updatedAt: next.updatedAt,
      visibility: next.visibility,
      message: "Visibility saved for all viewers.",
    });
  } catch (err) {
    sendJson(res, 502, {
      ok: false,
      error: err && err.message ? err.message : "Failed to save visibility",
      detail: err && err.detail ? err.detail : undefined,
    });
  }
};
