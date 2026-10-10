// Photo color enhancement, a port of system/backend/domain/enhance (Go),
// which reproduces https://github.com/yuki-koyama/enhancer.
//
// The port keeps the arithmetic of the Go code, including its lookup tables
// for the sRGB transfer function, so that a parameter vector produces the
// photo the study participants saw.

/** The five parameters, each in [0, 1]. 0.5 is the neutral setting. */
export type Params = number[];

export const paramNames = ["Brightness", "Contrast", "Saturation", "Temperature", "Tint"];
export const numParams = 5;

const lutSize = 1024; // keep a power of 2
const lin2sRGBLut = new Float64Array(lutSize + 1);
const sRGB2linLut = new Float64Array(lutSize + 1);

function sRGB2linear(v: number): number {
  return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

function linear2sRGB(v: number): number {
  return v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1.0 / 2.4) - 0.055;
}

for (let i = 0; i < lutSize; i++) {
  lin2sRGBLut[i] = linear2sRGB(i / lutSize);
  sRGB2linLut[i] = sRGB2linear(i / lutSize);
}
lin2sRGBLut[lutSize] = lin2sRGBLut[lutSize - 1];
sRGB2linLut[lutSize] = sRGB2linLut[lutSize - 1];

function fromLinear2sRGB(v: number): number {
  if (v <= 0) return 0;
  if (v === 1) return 1;
  let i = v * lutSize;
  const ifloor = Math.trunc(i) & (lutSize - 1);
  i -= ifloor;
  return lin2sRGBLut[ifloor] * (1.0 - i) + lin2sRGBLut[ifloor + 1] * i;
}

function fromsRGB2Linear(v: number): number {
  if (v <= 0) return 0;
  if (v >= 1) return 1;
  let i = v * lutSize;
  const ifloor = Math.trunc(i) & (lutSize - 1);
  i -= ifloor;
  return sRGB2linLut[ifloor] * (1.0 - i) + sRGB2linLut[ifloor + 1] * i;
}

const clamp = (v: number): number => Math.max(0, Math.min(v, 1.0));

/**
 * Enhances every pixel of src (RGBA bytes) into dst. Both arrays have the
 * same length; alpha is copied.
 */
export function enhance(
  src: Uint8ClampedArray | Uint8Array,
  dst: Uint8ClampedArray | Uint8Array,
  params: Params,
): void {
  const brightness = clamp(params[0]) - 0.5;
  const contrast = clamp(params[1]) - 0.5;
  const saturation = clamp(params[2]) - 0.5;
  const temperature = clamp(params[3]) - 0.5;
  const tint = clamp(params[4]) - 0.5;

  const ttScale = 0.1;
  const du = -temperature * ttScale + tint * ttScale;
  const dv = temperature * ttScale + tint * ttScale;
  const gamma = 1.0 / (1.0 + 1.5 * brightness);
  const pi4 = 3.14159265358979 * 0.25;
  const contrastCoef = Math.tan(contrast + 1) * pi4;
  const satCoef = saturation + 1;

  for (let p = 0; p < src.length; p += 4) {
    let r = fromsRGB2Linear(src[p] / 255.0);
    let g = fromsRGB2Linear(src[p + 1] / 255.0);
    let b = fromsRGB2Linear(src[p + 2] / 255.0);

    // Temperature and tint, in Y'UV (BT.709).
    const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    const u = -0.09991 * r - 0.33609 * g + 0.436 * b + du;
    const v = 0.615 * r - 0.55861 * g - 0.05639 * b + dv;
    r = clamp(y + 1.28033 * v);
    g = clamp(y - 0.21482 * u - 0.38059 * v);
    b = clamp(y + 2.12798 * u);

    // Brightness.
    r = Math.pow(r, gamma);
    g = Math.pow(g, gamma);
    b = Math.pow(b, gamma);

    // Contrast, around the middle of the sRGB range.
    r = fromsRGB2Linear(Math.max(0, (fromLinear2sRGB(r) - 0.5) * contrastCoef + 0.5));
    g = fromsRGB2Linear(Math.max(0, (fromLinear2sRGB(g) - 0.5) * contrastCoef + 0.5));
    b = fromsRGB2Linear(Math.max(0, (fromLinear2sRGB(b) - 0.5) * contrastCoef + 0.5));

    // Saturation, in HSV.
    r = clamp(r);
    g = clamp(g);
    b = clamp(b);
    const M = Math.max(r, g, b);
    const m = Math.min(r, g, b);
    let h = 0.0;
    if (M === m) {
      h = 0.0;
    } else if (m === b) {
      h = (60.0 * (g - r)) / (M - m) + 60.0;
    } else if (m === r) {
      h = (60.0 * (b - g)) / (M - m) + 180.0;
    } else if (m === g) {
      h = (60.0 * (r - b)) / (M - m) + 300.0;
    }
    h /= 360.0;
    if (h < 0.0) h += 1;
    else if (h > 1.0) h -= 1;
    const s = (M < 1e-14 ? 0.0 : (M - m) / M) * satCoef;
    const val = M;

    if (s < 1e-14) {
      r = g = b = val;
    } else {
      // The one deliberate difference from the Go code, which computes
      // f = h6 - i. When rounding puts the hue at exactly 1.0, that gives
      // f = 6 and a stray saturated pixel; which pixels are hit depends on
      // the last bit of the arithmetic, so it differs between processors.
      const h6 = h * 6.0;
      const i = Math.floor(h6) % 6;
      const f = h6 - Math.floor(h6);
      const pp = val * (1 - s);
      const q = val * (1 - s * f);
      const t = val * (1 - s * (1 - f));
      switch (i) {
        case 0: r = val; g = t; b = pp; break;
        case 1: r = q; g = val; b = pp; break;
        case 2: r = pp; g = val; b = t; break;
        case 3: r = pp; g = q; b = val; break;
        case 4: r = t; g = pp; b = val; break;
        default: r = val; g = pp; b = q; break;
      }
    }

    // The Go code truncates when it converts back to bytes.
    dst[p] = Math.trunc(clamp(fromLinear2sRGB(r)) * 255);
    dst[p + 1] = Math.trunc(clamp(fromLinear2sRGB(g)) * 255);
    dst[p + 2] = Math.trunc(clamp(fromLinear2sRGB(b)) * 255);
    dst[p + 3] = src[p + 3];
  }
}
