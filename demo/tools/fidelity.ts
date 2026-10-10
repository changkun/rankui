// Checks the enhancer port against photos the study actually showed.
//
//   node tools/fidelity.ts <raw image data> <task photos> [sessions]
//
// <raw image data> is analysis/image/1 with the release archives extracted,
// <task photos> a tasks/ folder with 1.jpg to 3.jpg. For a sample of
// sessions, every stored option (a JPEG and the parameters it was made
// from) is recomputed from the task photo and compared pixel by pixel.
// Uses macOS `sips` to decode JPEGs.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { enhance } from "../src/enhance.ts";

const [raw, tasks, limit = "6"] = process.argv.slice(2);
if (!raw || !tasks) {
  console.error("usage: node tools/fidelity.ts <raw image data> <task photos> [sessions]");
  process.exit(2);
}
const cache = fileURLToPath(new URL("../.cache/fidelity", import.meta.url));
mkdirSync(cache, { recursive: true });

type Image = { width: number; height: number; data: Uint8Array };

/** Decodes an image through sips into RGBA. */
function decode(path: string): Image {
  const bmp = join(cache, "decode.bmp");
  execFileSync("sips", ["-s", "format", "bmp", path, "--out", bmp], { stdio: "ignore" });
  const b = readFileSync(bmp);
  const offset = b.readUInt32LE(10);
  const width = b.readInt32LE(18);
  const rawHeight = b.readInt32LE(22);
  const height = Math.abs(rawHeight);
  const bytes = b.readUInt16LE(28) / 8;
  const stride = Math.ceil((width * bytes) / 4) * 4;
  const data = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y++) {
    const row = offset + (rawHeight > 0 ? height - 1 - y : y) * stride;
    for (let x = 0; x < width; x++) {
      const p = row + x * bytes;
      data.set([b[p + 2], b[p + 1], b[p], 255], (y * width + x) * 4);
    }
  }
  return { width, height, data };
}

const photos = new Map<string, Image>();
const photo = (task: string) => {
  if (!photos.has(task)) photos.set(task, decode(join(tasks, `${task}.jpg`)));
  return photos.get(task)!;
};

let options = 0;
let worst = 0;
let sum = 0;
let sessions = 0;
for (const ui of readdirSync(raw)) {
  for (const session of readdirSync(join(raw, ui)).filter((d) => /^P\d+-S\d+$/.test(d))) {
    if (sessions >= Number(limit)) break;
    sessions++;
    const dir = join(raw, ui, session);
    for (const task of ["1", "2", "3"]) {
      const iter = join(dir, `${task}-iter.json`);
      if (!existsSync(iter)) continue;
      const source = photo(task);
      // Two iterations per task are enough to cover random and optimized options.
      for (const id of (JSON.parse(readFileSync(iter, "utf8")).iters as string[]).slice(3, 5)) {
        for (const file of readdirSync(join(dir, "parameters", id))) {
          const p = JSON.parse(readFileSync(join(dir, "parameters", id, file), "utf8"));
          const shown = decode(join(dir, "options", id, file.replace(".json", ".jpg")));
          const out = new Uint8Array(source.data.length);
          enhance(source.data, out, [p.brightness, p.contrast, p.saturation, p.temperature, p.tint]);
          let diff = 0;
          for (let i = 0; i < out.length; i += 4) {
            diff += Math.abs(out[i] - shown.data[i]) + Math.abs(out[i + 1] - shown.data[i + 1]) + Math.abs(out[i + 2] - shown.data[i + 2]);
          }
          const meanDiff = diff / ((out.length / 4) * 3);
          worst = Math.max(worst, meanDiff);
          sum += meanDiff;
          options++;
        }
      }
    }
  }
}
console.log(`${options} options from ${sessions} sessions: mean channel difference ${(sum / options).toFixed(2)} of 255, worst option ${worst.toFixed(2)}`);
