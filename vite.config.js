import { defineConfig } from "vite";
import fs from "node:fs";
import path from "node:path";

function contentTypeFor(filename) {
  const ext = path.extname(filename).toLowerCase();
  if (ext === ".json") return "application/json; charset=utf-8";
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".png") return "image/png";
  return "application/octet-stream";
}

function decodeBase64Url(value) {
  const normalized = String(value || "")
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const padding = "=".repeat((4 - normalized.length % 4) % 4);
  return Buffer.from(normalized + padding, "base64").toString("utf8");
}

function resolveLocalFilesystemPath(requested) {
  const raw = String(requested || "").trim();
  if (!raw) throw new Error("No local filesystem path was supplied.");

  const isWindowsAbsolute = /^[A-Za-z]:[\\\\/]/.test(raw);
  if (process.platform === "win32") {
    if (!isWindowsAbsolute && !path.win32.isAbsolute(raw)) {
      throw new Error(`An absolute Windows path is required: ${raw}`);
    }
    return path.win32.normalize(raw.replace(/\//g, "\\\\"));
  }

  if (isWindowsAbsolute) {
    const drive = raw[0].toLowerCase();
    const suffix = raw.slice(2).replace(/\\\\/g, "/").replace(/^\/+/, "");
    const candidates = [
      `/mnt/${drive}/${suffix}`,
      `/run/desktop/mnt/host/${drive}/${suffix}`,
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) return candidate;
    }
    throw new Error(
      `The Vite server is running on ${process.platform} and cannot access Windows path ${raw}. `
      + `When using WSL, enter /mnt/${drive}/${suffix} instead, or use Select primary folder.`
    );
  }

  if (!path.isAbsolute(raw)) {
    throw new Error(`An absolute path is required: ${raw}`);
  }
  return path.resolve(raw);
}

function localFilesystemPlugin() {
  const install = (middlewares) => {
    middlewares.use((req, res, next) => {
      try {
        const requestUrl = new URL(req.url || "", "http://127.0.0.1");
        if (!requestUrl.pathname.startsWith("/__localfs__/")) {
          next();
          return;
        }

        const encoded = requestUrl.pathname.slice("/__localfs__/".length);
        const requested = decodeBase64Url(encoded);
        const resolved = resolveLocalFilesystemPath(requested);
        const stat = fs.statSync(resolved);
        if (!stat.isFile()) {
          res.statusCode = 404;
          res.end(`Not a file: ${resolved}`);
          return;
        }

        res.statusCode = 200;
        res.setHeader("Content-Type", contentTypeFor(resolved));
        res.setHeader("Content-Length", String(stat.size));
        res.setHeader("Cache-Control", "no-store");
        fs.createReadStream(resolved).pipe(res);
      } catch (error) {
        res.statusCode = error?.code === "ENOENT" ? 404 : 500;
        res.setHeader("Content-Type", "text/plain; charset=utf-8");
        res.end(error?.message || "Could not read local file");
      }
    });
  };

  return {
    name: "dynamo-viewer-local-filesystem",
    configureServer(server) {
      install(server.middlewares);
    },
    configurePreviewServer(server) {
      install(server.middlewares);
    },
  };
}

export default defineConfig({
  plugins: [localFilesystemPlugin()],
  server: { host: "127.0.0.1" },
  preview: { host: "127.0.0.1" },
});
