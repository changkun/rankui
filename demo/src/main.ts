// The demo page: pick an interface and a photo, give feedback, and watch the
// optimizer adapt. Everything runs in the browser and nothing is stored.

import { enhance, numParams, paramNames } from "./enhance.ts";
import type { Vec } from "./gp.ts";
import { belief, maxIterations, minIterations, nextOptions, random } from "./optimizer.ts";
import type { Feedback, InterfaceId, Iteration, Random } from "./optimizer.ts";
import { createWidget, h } from "./widgets.ts";
import type { Widget } from "./widgets.ts";

type InterfaceInfo = { id: InterfaceId; code: string; short: string; name: string; about: string };

const interfaces: InterfaceInfo[] = [
  {
    id: "pointwise",
    code: "UI1",
    short: "1-RS",
    name: "Single item Rating Scale",
    about:
      "One photo, one rating. The optimizer fits a utility model to your ratings, so it depends on you using the scale consistently from one photo to the next.",
  },
  {
    id: "pairwise",
    code: "UI2",
    short: "2-ANFC",
    name: "Two Alternative Non-Forced Choice",
    about:
      "Two photos, one choice. The optimizer learns from which photo won. If you say they are the same or that you don't know, this round teaches it nothing.",
  },
  {
    id: "listwise-rating",
    code: "UI3",
    short: "n-RS",
    name: "n-items Rating Scales",
    about:
      "Four photos, four ratings. The optimizer gets four data points per round, and seeing the photos side by side lets you rate them relative to each other.",
  },
  {
    id: "listwise-notie",
    code: "UI4",
    short: "n-AFR",
    name: "n-Alternative Forced Ranking",
    about:
      "Four photos in a strict order. Each ranking becomes six pairwise comparisons, even when two photos look the same to you.",
  },
  {
    id: "listwise-cantie",
    code: "UI5",
    short: "n-ANFR",
    name: "n-Alternative Non-Forced Ranking",
    about:
      "Four photos ranked, and photos may share a place. A shared place tells the optimizer that you are indifferent between them.",
  },
  {
    id: "listwise-ranking",
    code: "UI6",
    short: "n-ANFRD",
    name: "n-Alternative Non-Forced Ranking with Distance",
    about:
      "Four photos placed on a labelled scale. The labels anchor your ranking across rounds and show how far apart the photos are. As in the study, the optimizer itself only uses the order.",
  },
];

const photoCount = 3;
const width = 600;
const height = 400;

type Run = {
  ui: InterfaceInfo;
  photo: number;
  history: Iteration[];
  options: Vec[];
  rand: Random;
  shift: Vec;
  startedAt: number;
  presentedAt: number;
};

type Finished = {
  ui: InterfaceInfo;
  photo: number;
  iterations: number;
  seconds: number;
  unknown: number;
  result: Vec | undefined;
};

const sources: ImageData[] = [];
let ui = interfaces[0];
let photo = 0;
let run: Run;
let widget: Widget;
const finished: Finished[] = [];

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function loadPhoto(index: number): Promise<ImageData> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = h("canvas", { width, height });
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(img, 0, 0, width, height);
      resolve(ctx.getImageData(0, 0, width, height));
    };
    img.onerror = () => reject(new Error(`cannot load photo ${index + 1}`));
    img.src = `photos/${index + 1}.jpg`;
  });
}

/** A canvas with the photo, enhanced by params (or the original photo). */
function render(photoIndex: number, params?: Vec): HTMLCanvasElement {
  const canvas = h("canvas", { width, height });
  const source = sources[photoIndex];
  const ctx = canvas.getContext("2d")!;
  if (!params) {
    ctx.putImageData(source, 0, 0);
    return canvas;
  }
  const out = ctx.createImageData(width, height);
  enhance(source.data, out.data, params);
  ctx.putImageData(out, 0, 0);
  return canvas;
}

function parameterBars(params: Vec): HTMLElement {
  return h(
    "dl",
    { class: "params" },
    ...params.flatMap((v, i) => {
      const fill = h("span", { class: "bar-fill" });
      fill.style.width = `${(v * 100).toFixed(1)}%`;
      return [h("dt", {}, paramNames[i]), h("dd", {}, h("span", { class: "bar" }, fill))];
    }),
  );
}

function countUnknown(feedback: Feedback): number {
  if (feedback.kind === "ratings") return feedback.ratings.filter((r) => r === null).length;
  if (feedback.kind === "levels") return feedback.levels.filter((l) => l === null).length;
  return feedback.choice === null ? 1 : 0;
}

function formatSeconds(s: number): string {
  if (s < 10) return `${s.toFixed(1)} s`;
  return s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}

function renderToolbar() {
  $("interfaces").replaceChildren(
    ...interfaces.map((info) => {
      const button = h(
        "button",
        { type: "button", class: "tab", title: info.name },
        h("span", { class: "tab-code" }, info.code),
        h("span", { class: "tab-name" }, info.short),
      );
      button.setAttribute("aria-pressed", String(info === ui));
      button.addEventListener("click", () => {
        ui = info;
        start();
      });
      return button;
    }),
  );
  $("photos").replaceChildren(
    ...Array.from({ length: photoCount }, (_, i) => {
      const button = h("button", { type: "button", class: "thumb" }, h("img", { src: `photos/${i + 1}.jpg`, alt: `Photo ${i + 1}` }));
      button.setAttribute("aria-pressed", String(i === photo));
      button.addEventListener("click", () => {
        photo = i;
        start();
      });
      return button;
    }),
  );
}

function renderSidebar() {
  const current = belief(run.ui.id, run.history);
  $("original").replaceChildren(render(run.photo));
  $("best").replaceChildren(
    current
      ? h("div", {}, render(run.photo, current.best), parameterBars(current.best))
      : h("p", { class: "muted" }, "Appears after your first usable feedback."),
  );
  $("about-ui").replaceChildren(
    h("h2", {}, `${run.ui.code} · ${run.ui.short}`),
    h("p", { class: "about-name" }, run.ui.name),
    h("p", {}, run.ui.about),
  );
}

function present() {
  const iteration = run.history.length + 1;
  widget = createWidget(run.ui.id, run.options.map((params) => render(run.photo, params)));
  const message = h("p", { class: "message", role: "alert" });
  const submit = h("button", { type: "button", class: "primary" }, "Submit feedback");
  const satisfied = h("button", { type: "button", class: "primary" }, "I'm satisfied");
  satisfied.disabled = run.history.length < minIterations;
  satisfied.title = satisfied.disabled ? "This button will be available after a few iterations." : "";
  submit.title = "AI will try to improve itself based on your feedback";

  const act = (stop: boolean) => {
    const feedback = widget.read();
    if (typeof feedback === "string") {
      message.textContent = feedback;
      return;
    }
    run.history.push({ options: run.options, feedback });
    if (stop || run.history.length >= maxIterations) {
      finish();
      return;
    }
    $("workspace").classList.add("busy");
    // Let the browser paint the busy state before the optimizer runs.
    setTimeout(() => {
      run.options = nextOptions(run.ui.id, run.history, numParams, run.rand, run.shift);
      $("workspace").classList.remove("busy");
      renderSidebar();
      present();
    }, 30);
  };
  submit.addEventListener("click", () => act(false));
  satisfied.addEventListener("click", () => act(true));
  for (const type of ["input", "click", "drop"]) {
    widget.element.addEventListener(type, () => (message.textContent = ""));
  }

  const phase =
    run.history.length < 4
      ? "The first rounds show a spread of options so that the optimizer can get its bearings."
      : "The optimizer now proposes options based on your feedback so far.";
  $("workspace").replaceChildren(
    h(
      "div",
      { class: "progress" },
      h("strong", {}, `Iteration ${iteration} of ${maxIterations}`),
      h("span", { class: "muted" }, phase),
    ),
    widget.element,
    message,
    h("div", { class: "actions" }, submit, satisfied),
  );
  run.presentedAt = performance.now();
}

function finish() {
  const seconds = (performance.now() - run.startedAt) / 1000;
  const result = belief(run.ui.id, run.history)?.best;
  finished.push({
    ui: run.ui,
    photo: run.photo,
    iterations: run.history.length,
    seconds,
    unknown: run.history.reduce((n, it) => n + countUnknown(it.feedback), 0),
    result,
  });
  renderSidebar();

  const again = h("button", { type: "button", class: "primary" }, "Run again");
  again.addEventListener("click", start);
  const next = interfaces[(interfaces.indexOf(run.ui) + 1) % interfaces.length];
  const other = h("button", { type: "button", class: "secondary" }, `Try ${next.code} · ${next.short}`);
  other.addEventListener("click", () => {
    ui = next;
    start();
  });

  $("workspace").replaceChildren(
    h(
      "div",
      { class: "progress" },
      h("strong", {}, `Finished after ${run.history.length} iteration${run.history.length === 1 ? "" : "s"}`),
      h("span", { class: "muted" }, `${formatSeconds(seconds)} with ${run.ui.code} · ${run.ui.short}`),
    ),
    result
      ? h(
          "div",
          { class: "options options-2 result" },
          h("figure", { class: "option" }, render(run.photo), h("figcaption", {}, "Original")),
          h("figure", { class: "option" }, render(run.photo, result), h("figcaption", {}, "What the optimizer believes you like best")),
        )
      : h("p", {}, "The optimizer received no feedback it could learn from, so it has no result to show."),
    h(
      "p",
      { class: "muted" },
      "Now try the same photo with another interface. The paper compares how long each one takes, how often people cannot or will not decide, and how well the optimizer does with what it is told.",
    ),
    h("div", { class: "actions" }, other, again),
  );
  renderRuns();
}

function renderRuns() {
  const section = $("runs");
  section.hidden = finished.length === 0;
  if (finished.length === 0) return;
  const table = h(
    "table",
    {},
    h(
      "thead",
      {},
      h("tr", {}, ...["#", "Interface", "Iterations", "Time", "Per iteration", "“I don't know”", "Result"].map((t) => h("th", {}, t))),
    ),
    h(
      "tbody",
      {},
      ...finished.map((f, i) => {
        const thumb = f.result ? render(f.photo, f.result) : null;
        return h(
          "tr",
          {},
          h("td", {}, String(i + 1)),
          h("td", {}, `${f.ui.code} · ${f.ui.short}`),
          h("td", {}, String(f.iterations)),
          h("td", {}, formatSeconds(f.seconds)),
          h("td", {}, formatSeconds(f.seconds / f.iterations)),
          h("td", {}, String(f.unknown)),
          h("td", { class: "run-thumb" }, thumb ?? "none"),
        );
      }),
    ),
  );
  $("runs-table").replaceChildren(table);
}

function start() {
  const seed = (Math.random() * 2 ** 32) >>> 0;
  const rand = random(seed);
  const shift = Array.from({ length: numParams }, () => rand());
  run = {
    ui,
    photo,
    history: [],
    options: [],
    rand,
    shift,
    startedAt: performance.now(),
    presentedAt: 0,
  };
  run.options = nextOptions(run.ui.id, run.history, numParams, run.rand, run.shift);
  renderToolbar();
  renderSidebar();
  present();
}

async function main() {
  try {
    sources.push(...(await Promise.all(Array.from({ length: photoCount }, (_, i) => loadPhoto(i)))));
  } catch (err) {
    $("workspace").replaceChildren(h("p", { class: "message" }, `The demo could not start: ${(err as Error).message}.`));
    return;
  }
  $("restart").addEventListener("click", start);
  start();
}

main();
