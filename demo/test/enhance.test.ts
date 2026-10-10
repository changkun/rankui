import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { enhance } from "../src/enhance.ts";

// golden/enhance.json holds the output of the study's Go enhancer
// (system/backend/domain/enhance) for 1000 colors under 20 parameter
// vectors. The port must reproduce it.
type Golden = { params: number[][]; pixels: number[][]; out: number[][][] };

test("enhance reproduces the Go enhancer", () => {
  const golden: Golden = JSON.parse(
    readFileSync(new URL("./golden/enhance.json", import.meta.url), "utf8"),
  );
  const src = new Uint8ClampedArray(golden.pixels.length * 4);
  golden.pixels.forEach((px, i) => src.set([px[0], px[1], px[2], 255], i * 4));
  const dst = new Uint8ClampedArray(src.length);

  let total = 0;
  let off = 0;
  golden.params.forEach((params, k) => {
    enhance(src, dst, params);
    golden.out[k].forEach((want, i) => {
      for (let c = 0; c < 3; c++) {
        total++;
        if (Math.abs(dst[i * 4 + c] - want[c]) > 1) off++;
      }
    });
  });
  // The Go code produces a stray saturated pixel when rounding puts a hue
  // at exactly 1.0 (see the note in enhance.ts). The reference, generated
  // with GOARCH=amd64, contains a few dozen of them; the port has none.
  // Everything else must match to within one level.
  assert.ok(off / total < 0.002, `${off} of ${total} channels differ by more than one level`);
});
