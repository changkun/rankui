// Gaussian process models for the in-browser optimizer: a regression GP
// for rated options and a preference GP for compared options.
//
// The study ran BoTorch (SingleTaskGP and PairwiseGP, both with a Matern
// 5/2 kernel). This is a compact reimplementation for a few dozen points in
// five dimensions; hyperparameters are picked from a small grid instead of
// being fitted by gradient ascent.

export type Vec = number[];
export type Mat = number[][];

const sqrt5 = Math.sqrt(5);

/** Matern 5/2 kernel with unit variance. */
export function matern52(a: Vec, b: Vec, lengthscale: number): number {
  let d2 = 0;
  for (let i = 0; i < a.length; i++) {
    const d = a[i] - b[i];
    d2 += d * d;
  }
  const r = Math.sqrt(d2) / lengthscale;
  return (1 + sqrt5 * r + (5 / 3) * r * r) * Math.exp(-sqrt5 * r);
}

export function kernelMatrix(A: Vec[], B: Vec[], lengthscale: number): Mat {
  return A.map((a) => B.map((b) => matern52(a, b, lengthscale)));
}

/** Lower Cholesky factor of a symmetric positive definite matrix. */
export function cholesky(A: Mat): Mat {
  const n = A.length;
  const L: Mat = A.map(() => new Array<number>(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let sum = A[i][j];
      for (let k = 0; k < j; k++) sum -= L[i][k] * L[j][k];
      if (i === j) {
        if (sum <= 0) throw new Error("matrix is not positive definite");
        L[i][j] = Math.sqrt(sum);
      } else {
        L[i][j] = sum / L[j][j];
      }
    }
  }
  return L;
}

/** Solves L x = b for lower triangular L. */
export function forward(L: Mat, b: Vec): Vec {
  const x = new Array<number>(b.length);
  for (let i = 0; i < b.length; i++) {
    let sum = b[i];
    for (let k = 0; k < i; k++) sum -= L[i][k] * x[k];
    x[i] = sum / L[i][i];
  }
  return x;
}

/** Solves L^T x = b for lower triangular L. */
export function backward(L: Mat, b: Vec): Vec {
  const n = b.length;
  const x = new Array<number>(n);
  for (let i = n - 1; i >= 0; i--) {
    let sum = b[i];
    for (let k = i + 1; k < n; k++) sum -= L[k][i] * x[k];
    x[i] = sum / L[i][i];
  }
  return x;
}

/** Solves A X = B by Gaussian elimination with partial pivoting. */
export function solve(A: Mat, B: Mat): Mat {
  const n = A.length;
  const m = B[0].length;
  const M = A.map((row, i) => [...row, ...B[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) {
      if (Math.abs(M[r][col]) > Math.abs(M[pivot][col])) pivot = r;
    }
    [M[col], M[pivot]] = [M[pivot], M[col]];
    const d = M[col][col];
    for (let r = col + 1; r < n; r++) {
      const f = M[r][col] / d;
      if (f === 0) continue;
      for (let c = col; c < n + m; c++) M[r][c] -= f * M[col][c];
    }
  }
  const X: Mat = B.map(() => new Array<number>(m).fill(0));
  for (let j = 0; j < m; j++) {
    for (let i = n - 1; i >= 0; i--) {
      let sum = M[i][n + j];
      for (let k = i + 1; k < n; k++) sum -= M[i][k] * X[k][j];
      X[i][j] = sum / M[i][i];
    }
  }
  return X;
}

export function normalPdf(z: number): number {
  return Math.exp(-0.5 * z * z) / Math.sqrt(2 * Math.PI);
}

/** Standard normal CDF (Abramowitz and Stegun 7.1.26 on erf). */
export function normalCdf(z: number): number {
  const x = Math.abs(z) / Math.SQRT2;
  const t = 1 / (1 + 0.3275911 * x);
  const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
  const erf = 1 - poly * Math.exp(-x * x);
  return z >= 0 ? 0.5 * (1 + erf) : 0.5 * (1 - erf);
}

/** A fitted model that predicts a mean and a variance at new points. */
export interface Posterior {
  /** Posterior mean at the training points. */
  trainMean: Vec;
  predict(x: Vec): { mean: number; variance: number };
}

const lengthscales = [0.2, 0.35, 0.5, 0.8, 1.2];
const noises = [0.01, 0.05, 0.2];

/**
 * Regression GP on standardized targets. Lengthscale and noise are the grid
 * point with the highest marginal likelihood.
 */
export function fitRegression(points: Vec[], y: Vec): Posterior {
  const X = [...points];
  const n = X.length;
  const mean = y.reduce((a, b) => a + b, 0) / n;
  const std = Math.sqrt(y.reduce((a, b) => a + (b - mean) * (b - mean), 0) / n) || 1;
  const z = y.map((v) => (v - mean) / std);

  let best: { ll: number; lengthscale: number; L: Mat; alpha: Vec } | undefined;
  for (const lengthscale of lengthscales) {
    const K = kernelMatrix(X, X, lengthscale);
    for (const noise of noises) {
      const Kn = K.map((row, i) => row.map((v, j) => (i === j ? v + noise : v)));
      const L = cholesky(Kn);
      const alpha = backward(L, forward(L, z));
      let ll = 0;
      for (let i = 0; i < n; i++) ll -= 0.5 * z[i] * alpha[i] + Math.log(L[i][i]);
      if (!best || ll > best.ll) best = { ll, lengthscale, L, alpha };
    }
  }
  const { lengthscale, L, alpha } = best!;

  const predict = (x: Vec) => {
    const k = X.map((xi) => matern52(xi, x, lengthscale));
    let m = 0;
    for (let i = 0; i < n; i++) m += k[i] * alpha[i];
    const v = forward(L, k);
    let variance = 1;
    for (let i = 0; i < n; i++) variance -= v[i] * v[i];
    return { mean: mean + std * m, variance: Math.max(variance, 1e-10) * std * std };
  };
  return { trainMean: X.map((x) => predict(x).mean), predict };
}

/**
 * Preference GP after Chu and Ghahramani (2005): a latent utility with a
 * probit likelihood on pairwise comparisons, fitted with a Laplace
 * approximation. comparisons[k] = [winner, loser] indexes into X.
 *
 * trainMean is the latent utility at the training points, which is what the
 * study's optimizer for the ranking interfaces reads from its PairwiseGP.
 */
export function fitPreference(points: Vec[], comparisons: [number, number][], lengthscale = 0.5): Posterior & {
  /** Posterior mean and covariance of the latent utility at new points. */
  joint(points: Vec[]): { mean: Vec; cov: Mat };
} {
  const X = [...points];
  const n = X.length;
  const K = kernelMatrix(X, X, lengthscale).map((row, i) => row.map((v, j) => (i === j ? v + 1e-6 : v)));
  const identity = (): Mat => K.map((_, i) => K.map((_, j) => (i === j ? 1 : 0)));

  let f = new Array<number>(n).fill(0);
  let g = new Array<number>(n).fill(0);
  let W: Mat = K.map(() => new Array<number>(n).fill(0));

  const derivatives = (f: Vec) => {
    const g = new Array<number>(n).fill(0);
    const W: Mat = K.map(() => new Array<number>(n).fill(0));
    for (const [w, l] of comparisons) {
      const z = (f[w] - f[l]) / Math.SQRT2;
      const ratio = normalPdf(z) / Math.max(normalCdf(z), 1e-12);
      g[w] += ratio / Math.SQRT2;
      g[l] -= ratio / Math.SQRT2;
      const c = (ratio * (z + ratio)) / 2;
      W[w][w] += c;
      W[l][l] += c;
      W[w][l] -= c;
      W[l][w] -= c;
    }
    return { g, W };
  };

  // Newton iterations on the posterior mode: f = K (I + W K)^-1 (W f + g).
  for (let iter = 0; iter < 50; iter++) {
    ({ g, W } = derivatives(f));
    const B = identity();
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        let s = 0;
        for (let k = 0; k < n; k++) s += W[i][k] * K[k][j];
        B[i][j] += s;
      }
    }
    const rhs = g.map((gi, i) => [gi + W[i].reduce((s, wij, j) => s + wij * f[j], 0)]);
    const a = solve(B, rhs).map((r) => r[0]);
    const next = K.map((row) => row.reduce((s, kij, j) => s + kij * a[j], 0));
    let change = 0;
    for (let i = 0; i < n; i++) change = Math.max(change, Math.abs(next[i] - f[i]));
    f = next;
    if (change < 1e-6) break;
  }
  ({ g, W } = derivatives(f));

  // Predictive covariance: k(a, b) - k_a^T W (I + K W)^-1 k_b.
  const IKW = identity();
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      let s = 0;
      for (let k = 0; k < n; k++) s += K[i][k] * W[k][j];
      IKW[i][j] += s;
    }
  }
  const inv = solve(IKW, identity());
  const M: Mat = W.map((row) => inv[0].map((_, j) => row.reduce((s, wik, k) => s + wik * inv[k][j], 0)));

  const kvec = (x: Vec) => X.map((xi) => matern52(xi, x, lengthscale));
  const times = (k: Vec) => M.map((row) => row.reduce((s, mij, j) => s + mij * k[j], 0));
  const dot = (a: Vec, b: Vec) => a.reduce((s, ai, i) => s + ai * b[i], 0);
  const mode = f;
  const grad = g;
  return {
    trainMean: mode,
    predict(x) {
      const k = kvec(x);
      // At the mode, K^-1 f equals the gradient of the log likelihood.
      return { mean: dot(k, grad), variance: Math.max(1 - dot(k, times(k)), 1e-10) };
    },
    joint(points) {
      const ks = points.map(kvec);
      const Mk = ks.map(times);
      const mean = ks.map((k) => dot(k, grad));
      const cov = points.map((a, i) =>
        points.map((b, j) => (i === j ? Math.max(1 - dot(ks[i], Mk[i]), 1e-10) : matern52(a, b, lengthscale) - dot(ks[i], Mk[j]))),
      );
      return { mean, cov };
    },
  };
}

/** Expected improvement of a normal prediction over the incumbent value. */
export function expectedImprovement(mean: number, variance: number, incumbent: number): number {
  const sd = Math.sqrt(variance);
  const z = (mean - incumbent) / sd;
  return (mean - incumbent) * normalCdf(z) + sd * normalPdf(z);
}
