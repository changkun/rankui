// The optimization loop of the study, reimplemented for the browser.
//
// It follows system/backend: the first four iterations show quasi-random
// options, and from the fifth on the optimizer proposes the next options
// from all feedback so far. What each interface feeds the optimizer mirrors
// system/backend/optimizers/optimizers.py:
//
//   UI1, UI3  ratings          -> regression GP -> expected improvement
//   UI2       a choice of two  -> preference GP -> expected utility of the
//                                 best option (EUBO) over pairs
//   UI4-UI6   rankings         -> pairwise comparisons -> preference GP ->
//                                 its latent utilities -> regression GP ->
//                                 expected improvement
//
// As in the study, "I don't know" answers are left out, a tie in UI2 is left
// out, a tie in a ranking counts as a comparison in both directions, and the
// distance between ranking levels in UI6 is not used.

import { expectedImprovement, fitPreference, fitRegression, normalCdf, normalPdf } from "./gp.ts";
import type { Vec } from "./gp.ts";

export type InterfaceId =
  | "pointwise"
  | "pairwise"
  | "listwise-rating"
  | "listwise-notie"
  | "listwise-cantie"
  | "listwise-ranking";

/** How many options an interface shows per iteration. */
export const numOptions: Record<InterfaceId, number> = {
  pointwise: 1,
  pairwise: 2,
  "listwise-rating": 4,
  "listwise-notie": 4,
  "listwise-cantie": 4,
  "listwise-ranking": 4,
};

/**
 * The answer to one iteration. null stands for "I don't know".
 *  - ratings: one value in [0, 100] per option (UI1, UI3)
 *  - choice: the index of the better option, or "same" (UI2)
 *  - levels: one level per option, higher is better (UI4-UI6)
 */
export type Feedback =
  | { kind: "ratings"; ratings: (number | null)[] }
  | { kind: "choice"; choice: 0 | 1 | "same" | null }
  | { kind: "levels"; levels: (number | null)[] };

export type Iteration = { options: Vec[]; feedback: Feedback };

export const maxIterations = 20;
/** Iterations with quasi-random options before the optimizer takes over. */
export const initialIterations = 4;
/** "I'm satisfied" becomes available after this many iterations. */
export const minIterations = 5;

export type Random = () => number;

/** Seeded generator (mulberry32). */
export function random(seed: number): Random {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gaussian(rand: Random): number {
  return Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(2 * Math.PI * rand());
}

const primes = [2, 3, 5, 7, 11, 13, 17, 19];

function halton(index: number, base: number): number {
  let f = 1;
  let r = 0;
  for (let i = index; i > 0; i = Math.floor(i / base)) {
    f /= base;
    r += f * (i % base);
  }
  return r;
}

/** Quasi-random points for the initial iterations: a shifted Halton sequence. */
export function initialOptions(dim: number, count: number, offset: number, shift: Vec): Vec[] {
  return Array.from({ length: count }, (_, i) =>
    Array.from({ length: dim }, (_, d) => (halton(offset + i + 1, primes[d]) + shift[d]) % 1),
  );
}

type Rated = { X: Vec[]; y: Vec };
type Compared = { X: Vec[]; comparisons: [number, number][] };

/** Options with a rating, as the study's load_*_rating_data collects them. */
export function ratedData(history: Iteration[]): Rated {
  const X: Vec[] = [];
  const y: Vec = [];
  for (const { options, feedback } of history) {
    if (feedback.kind !== "ratings") continue;
    feedback.ratings.forEach((rating, i) => {
      if (rating === null) return;
      X.push(options[i]);
      y.push(rating);
    });
  }
  return { X, y };
}

/** Options with the comparisons the answers imply. */
export function comparedData(history: Iteration[]): Compared {
  const X: Vec[] = [];
  const comparisons: [number, number][] = [];
  for (const { options, feedback } of history) {
    const k = X.length;
    if (feedback.kind === "choice") {
      if (feedback.choice !== 0 && feedback.choice !== 1) continue;
      X.push(...options);
      comparisons.push(feedback.choice === 0 ? [k, k + 1] : [k + 1, k]);
    } else if (feedback.kind === "levels") {
      X.push(...options);
      const levels = feedback.levels;
      for (let i = 0; i < levels.length; i++) {
        for (let j = i + 1; j < levels.length; j++) {
          const a = levels[i];
          const b = levels[j];
          if (a === null || b === null) continue;
          if (a > b) comparisons.push([k + i, k + j]);
          else if (a < b) comparisons.push([k + j, k + i]);
          else comparisons.push([k + i, k + j], [k + j, k + i]);
        }
      }
    }
  }
  return { X, comparisons };
}

function randomPoint(dim: number, rand: Random): Vec {
  return Array.from({ length: dim }, () => rand());
}

/** Random candidates in the unit cube, plus perturbations of promising points. */
function candidates(dim: number, around: Vec[], global: number, local: number, rand: Random): Vec[] {
  const points = Array.from({ length: global }, () => randomPoint(dim, rand));
  for (let i = 0; i < local && around.length > 0; i++) {
    const center = around[i % around.length];
    points.push(center.map((v) => Math.min(1, Math.max(0, v + 0.08 * gaussian(rand)))));
  }
  return points;
}

function topPoints(X: Vec[], values: Vec, count: number): Vec[] {
  return values
    .map((v, i) => [v, i])
    .sort((a, b) => b[0] - a[0])
    .slice(0, count)
    .map(([, i]) => X[i]);
}

/**
 * q points by expected improvement on a regression GP. After each pick the
 * model is refitted with the pick at its predicted mean, so that the next
 * pick goes elsewhere.
 */
function utilityBO(data: Rated, dim: number, q: number, rand: Random): Vec[] {
  const X = [...data.X];
  const y = [...data.y];
  const picks: Vec[] = [];
  for (let k = 0; k < q; k++) {
    const model = fitRegression(X, y);
    const incumbent = Math.max(...model.trainMean);
    let best: Vec | undefined;
    let bestValue = -Infinity;
    for (const x of candidates(dim, topPoints(X, model.trainMean, 3), 1200, 400, rand)) {
      const { mean, variance } = model.predict(x);
      const value = expectedImprovement(mean, variance, incumbent);
      if (value > bestValue) {
        bestValue = value;
        best = x;
      }
    }
    picks.push(best!);
    y.push(model.predict(best!).mean);
    X.push(best!);
  }
  return picks;
}

/** The pair with the highest expected utility of its best option. */
function pairwiseBO(data: Compared, dim: number, rand: Random): Vec[] {
  const model = fitPreference(data.X, data.comparisons);
  const points = candidates(dim, topPoints(data.X, model.trainMean, 3), 160, 80, rand);
  const { mean, cov } = model.joint(points);
  let best: [number, number] = [0, 1];
  let bestValue = -Infinity;
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      const sd = Math.sqrt(Math.max(cov[i][i] + cov[j][j] - 2 * cov[i][j], 1e-12));
      const z = (mean[i] - mean[j]) / sd;
      const value = mean[i] * normalCdf(z) + mean[j] * normalCdf(-z) + sd * normalPdf(z);
      if (value > bestValue) {
        bestValue = value;
        best = [i, j];
      }
    }
  }
  return [points[best[0]], points[best[1]]];
}

/** The study's optimizer for the ranking interfaces. */
function mixedBO(data: Compared, dim: number, q: number, rand: Random): Vec[] {
  const utilities = fitPreference(data.X, data.comparisons).trainMean;
  return utilityBO({ X: data.X, y: utilities }, dim, q, rand);
}

/** The options to show in the next iteration. */
export function nextOptions(
  ui: InterfaceId,
  history: Iteration[],
  dim: number,
  rand: Random,
  shift: Vec,
): Vec[] {
  const q = numOptions[ui];
  if (history.length < initialIterations) {
    return initialOptions(dim, q, history.length * q, shift);
  }
  const fallback = () => Array.from({ length: q }, () => randomPoint(dim, rand));
  if (ui === "pointwise" || ui === "listwise-rating") {
    const data = ratedData(history);
    return data.X.length >= 2 ? utilityBO(data, dim, q, rand) : fallback();
  }
  const data = comparedData(history);
  if (data.comparisons.length === 0) return fallback();
  return ui === "pairwise" ? pairwiseBO(data, dim, rand) : mixedBO(data, dim, q, rand);
}

/**
 * What the optimizer currently believes about the options it has shown:
 * its estimated utility for each, and the one it considers best.
 */
export function belief(ui: InterfaceId, history: Iteration[]): { X: Vec[]; utility: Vec; best: Vec } | undefined {
  let X: Vec[];
  let utility: Vec;
  if (ui === "pointwise" || ui === "listwise-rating") {
    const data = ratedData(history);
    if (data.X.length === 0) return undefined;
    X = data.X;
    utility = data.X.length >= 2 ? fitRegression(data.X, data.y).trainMean : data.y;
  } else {
    const data = comparedData(history);
    if (data.comparisons.length === 0) return undefined;
    X = data.X;
    utility = fitPreference(data.X, data.comparisons).trainMean;
  }
  let best = 0;
  for (let i = 1; i < utility.length; i++) if (utility[i] > utility[best]) best = i;
  return { X, utility, best: X[best] };
}
