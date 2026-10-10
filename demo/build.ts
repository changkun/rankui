// Builds the demo into dist/: the bundled script, the page, its style, and
// the photos. With --serve, also serves dist/ at http://localhost:4410 and
// rebuilds the script when a source file changes.

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";

const root = fileURLToPath(new URL(".", import.meta.url));
const dist = join(root, "dist");
const serve = process.argv.includes("--serve");

rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });
for (const file of ["index.html", "style.css"]) cpSync(join(root, file), join(dist, file));
cpSync(join(root, "public"), dist, { recursive: true });

const options: esbuild.BuildOptions = {
  entryPoints: [join(root, "src/main.ts")],
  outfile: join(dist, "app.js"),
  bundle: true,
  format: "iife",
  target: "es2020",
  minify: !serve,
  sourcemap: serve,
  logLevel: "info",
};

if (!serve) {
  await esbuild.build(options);
} else {
  const context = await esbuild.context(options);
  await context.watch();
  const types: Record<string, string> = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".jpg": "image/jpeg",
    ".map": "application/json",
  };
  createServer((req, res) => {
    const path = normalize(decodeURIComponent((req.url ?? "/").split("?")[0]));
    // index.html and style.css are served from the source tree, so that
    // edits show up on reload.
    let file = join(dist, path === "/" ? "index.html" : path);
    for (const live of ["index.html", "style.css"]) if (file === join(dist, live)) file = join(root, live);
    if (!file.startsWith(root) || !existsSync(file) || !statSync(file).isFile()) {
      res.writeHead(404).end("not found");
      return;
    }
    res.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream" });
    res.end(readFileSync(file));
  }).listen(4410, () => console.log("serving http://localhost:4410"));
}
