import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.join(__dirname, "dist");
const BASE = "/AI-News-Automation-WebApp";

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".csv": "text/csv; charset=utf-8",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
};

const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url.split("?")[0]);

  // If root requested, redirect to base path
  if (urlPath === "/" || urlPath === "") {
    res.writeHead(302, { Location: `${BASE}/` });
    res.end();
    return;
  }

  // Strip BASE prefix if present to find local file in dist
  let relative = urlPath;
  if (relative.startsWith(BASE)) {
    relative = relative.slice(BASE.length);
  }
  if (!relative || relative === "/") {
    relative = "/index.html";
  }
  if (!relative.startsWith("/")) {
    relative = "/" + relative;
  }

  let filePath = path.join(distDir, relative);

  // If path is a directory, append index.html
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, "index.html");
  }

  // If file doesn't exist, try appending .html (clean URLs)
  if (!fs.existsSync(filePath) && fs.existsSync(filePath + ".html")) {
    filePath = filePath + ".html";
  }

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || "application/octet-stream";
    res.writeHead(200, {
      "Content-Type": contentType,
      "Access-Control-Allow-Origin": "*",
    });
    fs.createReadStream(filePath).pipe(res);
  } else {
    // 404 fallback
    res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
    res.end(`<!DOCTYPE html><html><head><title>Not Found</title></head><body><h1>404 Not Found</h1><p><a href="${BASE}/">Return to Home</a></p></body></html>`);
  }
});

server.listen(4321, "0.0.0.0", () => {
  console.log(`Server listening on port 4321: http://localhost:4321/ -> http://localhost:4321${BASE}/`);
});
