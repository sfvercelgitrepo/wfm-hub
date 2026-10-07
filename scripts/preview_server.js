/**
 * Local static server plus POST /api/audit.
 * Start with AUDIT_PASSPHRASE set in the environment. Do not print it.
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const root = path.resolve(__dirname, "..");
const secretFile = path.join(root, ".audit-passphrase");
if (!process.env.AUDIT_PASSPHRASE && fs.existsSync(secretFile)) {
  process.env.AUDIT_PASSPHRASE = fs.readFileSync(secretFile, "utf8").trim();
}
const audit = require("../api/audit");
const port = Number(process.env.PORT || 8767);
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

function send(res, status, body, type) {
  res.writeHead(status, { "Content-Type": type || "text/plain; charset=utf-8" });
  res.end(body);
}

function serveStatic(req, res) {
  const url = new URL(req.url, "http://127.0.0.1");
  let rel = decodeURIComponent(url.pathname);
  if (rel === "/") rel = "/index.html";
  if (rel.includes("..") || rel === "/api/audit-payload.json") {
    send(res, 404, "Not found");
    return;
  }
  const file = path.resolve(root, "." + rel);
  if (!file.startsWith(root + path.sep) && file !== root) {
    send(res, 400, "Bad path");
    return;
  }
  fs.readFile(file, (err, data) => {
    if (err) {
      send(res, 404, "Not found");
      return;
    }
    if (req.method === "HEAD") {
      res.writeHead(200, { "Content-Type": types[path.extname(file).toLowerCase()] || "application/octet-stream" });
      res.end();
      return;
    }
    send(res, 200, data, types[path.extname(file).toLowerCase()] || "application/octet-stream");
  });
}

const server = http.createServer((req, res) => {
  const pathOnly = (req.url || "/").split("?")[0];
  if (pathOnly === "/api/audit") {
    audit(req, res);
    return;
  }
  if (req.method !== "GET" && req.method !== "HEAD") {
    send(res, 405, "Method not allowed");
    return;
  }
  serveStatic(req, res);
});

server.listen(port, "127.0.0.1", () => {
  console.log("Preview http://127.0.0.1:" + port + "/WFMSprintProgress.html");
});
