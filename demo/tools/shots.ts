// Drives the built demo in a headless browser: runs every interface for a
// few iterations with scripted answers, saves screenshots to .cache/shots/,
// and fails on any console or page error.
//
//   node build.ts && node tools/shots.ts
//
// With a URL as argument, it drives that page instead of the local build,
// which checks a deployment:
//
//   node tools/shots.ts https://changkun.de/research/rankui/
//
// Needs a Chromium that playwright-core can launch: set CHROME, or install
// one with `npx playwright install chromium`.

import { existsSync, mkdirSync, readdirSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { homedir } from "node:os";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
import type { Page } from "playwright-core";

const root = fileURLToPath(new URL("..", import.meta.url));
const dist = join(root, "dist");
const out = join(root, ".cache/shots");
mkdirSync(out, { recursive: true });

function chromePath(): string | undefined {
  if (process.env.CHROME) return process.env.CHROME;
  const base = join(homedir(), "Library/Caches/ms-playwright");
  if (!existsSync(base)) return undefined;
  for (const d of readdirSync(base).filter((d) => d.startsWith("chromium-")).sort().reverse()) {
    const p = join(base, d, "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
    if (existsSync(p)) return p;
    const q = join(base, d, "chrome-mac/Chromium.app/Contents/MacOS/Chromium");
    if (existsSync(q)) return q;
  }
  return undefined;
}

// The demo is deployed below a path prefix; serve it the same way.
const prefix = "/research/rankui/";
const types: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".jpg": "image/jpeg",
};
const server = createServer((req, res) => {
  const url = decodeURIComponent((req.url ?? "/").split("?")[0]);
  const rel = url.startsWith(prefix) ? url.slice(prefix.length) || "index.html" : "";
  const file = normalize(join(dist, rel));
  if (!rel || !file.startsWith(dist) || !existsSync(file) || !statSync(file).isFile()) {
    res.writeHead(404).end("not found");
    return;
  }
  res.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream" });
  res.end(readFileSync(file));
});
await new Promise<void>((resolve) => server.listen(0, resolve));
const base = process.argv[2] ?? `http://localhost:${(server.address() as AddressInfo).port}${prefix}`;

const browser = await chromium.launch({ executablePath: chromePath() });
const errors: string[] = [];

async function setSliders(page: Page, values: number[]) {
  await page.evaluate((values) => {
    document.querySelectorAll<HTMLInputElement>("#workspace input.scale").forEach((el, i) => {
      el.value = String(values[i % values.length]);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }, values);
}

/** Answers the current iteration of the given interface. */
async function answer(page: Page, ui: number, iteration: number) {
  if (ui === 0) {
    await setSliders(page, [30 + 10 * iteration]);
  } else if (ui === 1) {
    await page.locator("#workspace input[type=radio]").nth(iteration % 3).check();
  } else if (ui === 2) {
    await setSliders(page, [80, 60, 40, 20]);
    if (iteration === 1) await page.locator("#workspace input[type=checkbox]").first().check();
  } else {
    // Rows: 0..3 (UI4, UI5) or 0..4 (UI6), then "I don't know".
    const rows = ui === 3 ? [0, 1, 2, 3] : ui === 4 ? [0, 0, 2, 4] : [0, 1, 1, 5];
    for (let box = 0; box < 4; box++) {
      const chip = page.locator("#workspace .tray .chip-box").first();
      const row = page.locator("#workspace .rank-row").nth(rows[box]);
      if (box === 0 && iteration === 0) {
        await chip.dragTo(row);
      } else {
        await chip.click();
        await row.click();
      }
    }
  }
}

async function runAll(viewport: { width: number; height: number }, tag: string, iterations: number) {
  const page = await browser.newPage({ viewport });
  page.on("console", (m) => m.type() === "error" && errors.push(`${tag}: console: ${m.text()}`));
  page.on("pageerror", (e) => errors.push(`${tag}: ${e.message}`));
  page.on("requestfailed", (r) => errors.push(`${tag}: request failed: ${r.url()}`));
  await page.goto(base);
  await page.waitForSelector("#workspace .actions");

  for (let ui = 0; ui < 6; ui++) {
    await page.locator("#interfaces .tab").nth(ui).click();
    await page.waitForSelector("#workspace .actions");

    // Submitting without an answer must show a message, not advance.
    await page.getByRole("button", { name: "Submit feedback" }).click();
    const message = (await page.locator("#workspace .message").textContent()) ?? "";
    if (!message.trim()) errors.push(`${tag}: ui ${ui + 1}: no message for an empty answer`);

    for (let it = 0; it < iterations; it++) {
      await answer(page, ui, it);
      if (it === 0) await page.screenshot({ path: join(out, `${tag}-ui${ui + 1}.png`), fullPage: true });
      const last = it === iterations - 1;
      await page.getByRole("button", { name: last ? "I'm satisfied" : "Submit feedback" }).click();
      if (!last) await page.waitForFunction((n) => document.querySelector("#workspace .progress strong")?.textContent?.startsWith(`Iteration ${n} `), it + 2);
    }
    await page.waitForSelector("#workspace .result, #workspace > p");
    const title = await page.locator("#workspace .progress strong").textContent();
    if (!title?.startsWith(`Finished after ${iterations} `)) errors.push(`${tag}: ui ${ui + 1}: unexpected end state: ${title}`);
    if (ui === 5) await page.screenshot({ path: join(out, `${tag}-finished.png`), fullPage: true });
  }
  const runs = await page.locator("#runs tbody tr").count();
  if (runs !== 6) errors.push(`${tag}: expected 6 finished runs, found ${runs}`);
  await page.close();
}

await runAll({ width: 1280, height: 900 }, "desktop", 7);
await runAll({ width: 390, height: 844 }, "phone", 6);

await browser.close();
server.close();
if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log(`ok: all six interfaces ran on desktop and phone at ${base}; screenshots in ${out}`);
