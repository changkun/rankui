import assert from "node:assert/strict";
import { test } from "node:test";
import { fitPreference, fitRegression } from "../src/gp.ts";
import type { Vec } from "../src/gp.ts";
import { belief, comparedData, initialIterations, maxIterations, nextOptions, numOptions, random, ratedData } from "../src/optimizer.ts";
import type { Feedback, InterfaceId, Iteration, Random } from "../src/optimizer.ts";

const dim = 5;
const distance = (a: Vec, b: Vec) => Math.sqrt(a.reduce((s, v, i) => s + (v - b[i]) ** 2, 0));
const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;

test("regression GP interpolates its data", () => {
  const rand = random(1);
  const X = Array.from({ length: 12 }, () => Array.from({ length: dim }, () => rand()));
  const y = X.map((x) => 100 - 60 * distance(x, [0.5, 0.5, 0.5, 0.5, 0.5]));
  const model = fitRegression(X, y);
  X.forEach((x, i) => assert.ok(Math.abs(model.predict(x).mean - y[i]) < 6));
  assert.ok(model.predict(X[0]).variance < model.predict([0.99, 0.01, 0.99, 0.01, 0.99]).variance);
});

test("preference GP recovers the order of compared points", () => {
  const rand = random(2);
  const target = [0.3, 0.7, 0.5, 0.4, 0.6];
  const X = Array.from({ length: 16 }, () => Array.from({ length: dim }, () => rand()));
  const comparisons: [number, number][] = [];
  for (let i = 0; i < X.length; i += 2) {
    comparisons.push(distance(X[i], target) < distance(X[i + 1], target) ? [i, i + 1] : [i + 1, i]);
  }
  const model = fitPreference(X, comparisons);
  for (const [w, l] of comparisons) assert.ok(model.trainMean[w] > model.trainMean[l]);
  const { mean: m, cov } = model.joint([X[0], X[1], target]);
  assert.ok(Math.abs(m[0] - model.predict(X[0]).mean) < 1e-9);
  assert.ok(Math.abs(cov[1][1] - model.predict(X[1]).variance) < 1e-9);
  assert.ok(Math.abs(cov[0][2] - cov[2][0]) < 1e-9);
});

test("feedback is converted as in the study", () => {
  const o = (v: number) => [v, v, v, v, v];
  const rated = ratedData([{ options: [o(0.1), o(0.2)], feedback: { kind: "ratings", ratings: [70, null] } }]);
  assert.deepEqual(rated, { X: [o(0.1)], y: [70] });

  const history: Iteration[] = [
    { options: [o(0.1), o(0.2)], feedback: { kind: "choice", choice: 1 } },
    { options: [o(0.3), o(0.4)], feedback: { kind: "choice", choice: "same" } },
    { options: [o(0.5), o(0.6)], feedback: { kind: "choice", choice: null } },
    { options: [o(1), o(2), o(3), o(4)], feedback: { kind: "levels", levels: [5, 5, null, 2] } },
  ];
  const compared = comparedData(history);
  assert.equal(compared.X.length, 6);
  assert.deepEqual(compared.comparisons, [[1, 0], [2, 3], [3, 2], [2, 5], [3, 5]]);
});

// A simulated participant who prefers photos close to a hidden target.
function answer(ui: InterfaceId, options: Vec[], target: Vec, rand: Random): Feedback {
  const d = options.map((x) => distance(x, target));
  switch (ui) {
    case "pointwise":
    case "listwise-rating":
      return { kind: "ratings", ratings: d.map((v) => Math.max(0, Math.min(100, 100 - 80 * v + 6 * (rand() - 0.5)))) };
    case "pairwise":
      return { kind: "choice", choice: Math.abs(d[0] - d[1]) < 0.02 ? "same" : d[0] < d[1] ? 0 : 1 };
    case "listwise-notie": {
      const order = d.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
      const levels = new Array<number>(d.length);
      order.forEach(([, i], rank) => (levels[i] = 5 - rank));
      return { kind: "levels", levels };
    }
    case "listwise-cantie":
      return { kind: "levels", levels: d.map((v) => 5 - Math.min(3, Math.floor(v / 0.2))) };
    case "listwise-ranking":
      return { kind: "levels", levels: d.map((v) => 5 - Math.min(4, Math.floor(v / 0.2))) };
  }
}

for (const ui of Object.keys(numOptions) as InterfaceId[]) {
  test(`${ui}: the optimizer moves toward what the participant prefers`, () => {
    const early: number[] = [];
    const late: number[] = [];
    const final: number[] = [];
    for (let seed = 1; seed <= 8; seed++) {
      const rand = random(seed);
      const target = Array.from({ length: dim }, () => 0.2 + 0.6 * rand());
      const shift = Array.from({ length: dim }, () => rand());
      const history: Iteration[] = [];
      for (let it = 0; it < maxIterations; it++) {
        const options = nextOptions(ui, history, dim, rand, shift);
        assert.equal(options.length, numOptions[ui]);
        for (const x of options) {
          assert.ok(x.every((v) => v >= 0 && v <= 1));
          (it < initialIterations ? early : it >= maxIterations - 6 ? late : []).push(distance(x, target));
        }
        history.push({ options, feedback: answer(ui, options, target, rand) });
      }
      final.push(distance(belief(ui, history)!.best, target));
    }
    // Options proposed late in the loop are closer to the target than the
    // initial quasi-random ones, and so is the optimizer's best guess.
    assert.ok(mean(late) < 0.75 * mean(early), `late ${mean(late).toFixed(3)} vs early ${mean(early).toFixed(3)}`);
    assert.ok(mean(final) < 0.6 * mean(early), `final ${mean(final).toFixed(3)} vs early ${mean(early).toFixed(3)}`);
  });
}
