/**
 * POST /api/audit
 *
 * Unlocks the Project Audit page. The passphrase is AUDIT_PASSPHRASE on the
 * server. It is not shipped in the page.
 *
 * Body: { "passphrase": "..." }
 * Success returns the audit payload. A wrong passphrase returns 401.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PAYLOAD_FILE = path.join(__dirname, "audit-payload.json");
// Referenced so the serverless bundle keeps the generated payload.
require.resolve("./audit-payload.json");

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

function sameSecret(given, expected) {
  const left = Buffer.from(String(given));
  const right = Buffer.from(String(expected));
  if (left.length !== right.length) {
    crypto.timingSafeEqual(right, right);
    return false;
  }
  return crypto.timingSafeEqual(left, right);
}

function loadPayload() {
  return JSON.parse(fs.readFileSync(PAYLOAD_FILE, "utf8"));
}

module.exports = async function audit(req, res) {
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Use POST." }));
    return;
  }

  let body;
  try {
    body = await readBody(req);
  } catch (err) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Could not read the request." }));
    return;
  }

  const expected = (process.env.AUDIT_PASSPHRASE || "").trim();
  const given = String(body.passphrase || body.password || "").trim();
  if (!expected) {
    res.statusCode = 503;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Audit passphrase is not configured on the server." }));
    return;
  }
  if (!given || !sameSecret(given, expected)) {
    res.statusCode = 401;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Incorrect passphrase." }));
    return;
  }

  let auditPayload;
  try {
    auditPayload = loadPayload();
  } catch (err) {
    res.statusCode = 503;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ ok: false, error: "Audit data is not available yet." }));
    return;
  }

  res.statusCode = 200;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify({ ok: true, audit: auditPayload }));
};
