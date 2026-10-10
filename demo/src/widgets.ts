// The six opinion measurement interfaces. Each widget lays out the options
// of one iteration with its input controls and reports the answer in the
// form the optimizer consumes. Layout and wording follow the study's
// interfaces (system/frontend): the enhanced photos sit in the center, and
// the listwise interfaces put their input next to them.

import type { Feedback, InterfaceId } from "./optimizer.ts";

export type Widget = {
  /** The enhanced photos, with any input that belongs directly to a photo. */
  stage: HTMLElement;
  /** Input shown in a column beside the photos, for the listwise interfaces. */
  panel: HTMLElement | null;
  /** The answer, or a message that says what is still missing. */
  read(): Feedback | string;
};

type Child = Node | string | null | undefined | false;

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Partial<HTMLElementTagNameMap[K]> & { class?: string } = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  const { class: className, ...rest } = props;
  if (className) el.className = className;
  Object.assign(el, rest);
  for (const child of children) if (child) el.append(child);
  return el;
}

const letters = ["A", "B", "C", "D"];
let uid = 0;

function photoCard(canvas: HTMLCanvasElement, label: string | null, ...below: Child[]): HTMLElement {
  return h("figure", { class: "option" }, canvas, label && h("figcaption", {}, label), ...below);
}

/** A rating scale with an "I don't know" checkbox. */
function ratingScale(): { element: HTMLElement; read(): number | null | undefined } {
  let touched = false;
  const range = h("input", { type: "range", min: "0", max: "100", value: "50", className: "scale" });
  range.setAttribute("aria-label", "Rating from strongly disagree to strongly agree");
  range.addEventListener("input", () => (touched = true));
  const unknown = h("input", { type: "checkbox" });
  const element = h(
    "div",
    { class: "rating" },
    h(
      "div",
      { class: "rating-scale" },
      range,
      h("div", { class: "scale-ends" }, h("span", {}, "Strongly Disagree"), h("span", {}, "Strongly Agree")),
    ),
    h("label", { class: "check" }, unknown, "I don't know"),
  );
  return {
    element,
    // undefined means the scale has not been used yet.
    read: () => (unknown.checked ? null : touched ? Number(range.value) : undefined),
  };
}

function pointwise(canvases: HTMLCanvasElement[]): Widget {
  const scale = ratingScale();
  return {
    stage: h(
      "div",
      { class: "stage stage-single" },
      photoCard(canvases[0], null),
      h("p", { class: "statement" }, "I think AI did an excellent color enhancement."),
      scale.element,
    ),
    panel: null,
    read() {
      const rating = scale.read();
      if (rating === undefined) return "Please use the slider to indicate your evaluation at least once.";
      return { kind: "ratings", ratings: [rating] };
    },
  };
}

function pairwise(canvases: HTMLCanvasElement[]): Widget {
  const name = `choice-${uid++}`;
  const radio = (value: string, label: string) =>
    h("label", { class: "check" }, h("input", { type: "radio", name, value }), label);
  const unknown = h("input", { type: "checkbox" });
  const stage = h(
    "div",
    { class: "stage stage-pair" },
    h(
      "div",
      { class: "pair" },
      ...canvases.map((canvas, i) =>
        h("div", { class: "pair-item" }, photoCard(canvas, null), radio(String(i), `This image (${letters[i]}) is better`)),
      ),
    ),
    h(
      "div",
      { class: "choice" },
      radio("same", "They have the same enhanced quality"),
      h("label", { class: "check" }, unknown, "I don't know which is better"),
    ),
  );
  return {
    stage,
    panel: null,
    read() {
      if (unknown.checked) return { kind: "choice", choice: null };
      const picked = stage.querySelector<HTMLInputElement>(`input[name="${name}"]:checked`);
      if (!picked) return "Please indicate your feedback.";
      return { kind: "choice", choice: picked.value === "same" ? "same" : picked.value === "0" ? 0 : 1 };
    },
  };
}

function listwiseRating(canvases: HTMLCanvasElement[]): Widget {
  const scales = canvases.map(() => ratingScale());
  return {
    stage: h(
      "div",
      { class: "stage stage-grid" },
      ...canvases.map((canvas, i) =>
        photoCard(
          canvas,
          null,
          h("p", { class: "statement" }, `I think AI did an excellent photo enhancement in this image (${letters[i]}).`),
          scales[i].element,
        ),
      ),
    ),
    panel: h("div", { class: "panel-input" }),
    read() {
      const ratings = scales.map((s) => s.read());
      if (ratings.some((r) => r === undefined)) {
        return "Please use every slider at least once, or check “I don't know” for it.";
      }
      return { kind: "ratings", ratings: ratings as (number | null)[] };
    },
  };
}

type Row = { label: string; level: number | null };

const unknownRow: Row = { label: "I don't know", level: null };
const choiceRows: Row[] = [
  { label: "1st Choice", level: 5 },
  { label: "2nd Choice", level: 4 },
  { label: "3rd Choice", level: 3 },
  { label: "4th Choice", level: 2 },
  unknownRow,
];
const distanceRows: Row[] = [
  { label: "Excellent", level: 5 },
  { label: "Good", level: 4 },
  { label: "Fair", level: 3 },
  { label: "Poor", level: 2 },
  { label: "Terrible", level: 1 },
  unknownRow,
];

/**
 * A ranking board: four boxes that are dragged, or clicked and then placed,
 * into rows. With exclusive rows, a row other than "I don't know" holds one
 * box, and a box dropped on a taken row trades places with its occupant.
 */
function ranking(canvases: HTMLCanvasElement[], rows: Row[], exclusive: boolean): Widget {
  const place: (number | null)[] = canvases.map(() => null); // row index per box
  let selected: number | null = null;
  const board = h("div", { class: "board" });

  const move = (box: number, row: number | null) => {
    if (row !== null && exclusive && rows[row].level !== null) {
      const occupant = place.findIndex((r, i) => r === row && i !== box);
      if (occupant >= 0) place[occupant] = place[box];
    }
    place[box] = row;
    selected = null;
    render();
  };

  const chip = (box: number) => {
    const el = h("button", { type: "button", class: "chip-box", draggable: true }, letters[box]);
    el.setAttribute("aria-label", `Photo ${letters[box]}`);
    el.setAttribute("aria-pressed", String(selected === box));
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      selected = selected === box ? null : box;
      render();
    });
    el.addEventListener("dragstart", (e) => {
      e.dataTransfer?.setData("text/plain", String(box));
      if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
    });
    return el;
  };

  const target = (el: HTMLElement, row: number | null) => {
    el.addEventListener("click", () => {
      if (selected !== null) move(selected, row);
    });
    el.addEventListener("dragover", (e) => {
      e.preventDefault();
      el.classList.add("over");
    });
    el.addEventListener("dragleave", () => el.classList.remove("over"));
    el.addEventListener("drop", (e) => {
      e.preventDefault();
      el.classList.remove("over");
      const box = Number(e.dataTransfer?.getData("text/plain"));
      if (Number.isInteger(box) && box >= 0 && box < place.length) move(box, row);
    });
    return el;
  };

  function render() {
    const tray = target(h("div", { class: "tray" }), null);
    canvases.forEach((_, box) => {
      tray.append(h("div", { class: "slot" }, place[box] === null && chip(box)));
    });
    board.replaceChildren(
      tray,
      ...rows.map((row, r) => {
        const el = target(
          h(
            "div",
            { class: row.level === null ? "rank-row unknown" : "rank-row" },
            h("div", { class: "rank-boxes" }, ...place.map((p, box) => p === r && chip(box))),
            h("span", { class: "rank-label" }, row.label),
          ),
          r,
        );
        if (selected !== null) el.classList.add("armed");
        return el;
      }),
    );
  }
  render();

  return {
    stage: h(
      "div",
      { class: "stage stage-grid" },
      ...canvases.map((canvas, i) => photoCard(canvas, `AI Enhanced Photo ${letters[i]}`)),
    ),
    panel: h(
      "div",
      { class: "panel-input" },
      h(
        "p",
        { class: "usage" },
        "Drag and drop the following boxes to ",
        h("strong", {}, "rank"),
        " AI enhanced results. You can also click a box, then a row.",
      ),
      board,
    ),
    read() {
      if (place.some((p) => p === null)) return "Please indicate feedback to all results.";
      return { kind: "levels", levels: place.map((p) => rows[p!].level) };
    },
  };
}

export function createWidget(ui: InterfaceId, canvases: HTMLCanvasElement[]): Widget {
  switch (ui) {
    case "pointwise":
      return pointwise(canvases);
    case "pairwise":
      return pairwise(canvases);
    case "listwise-rating":
      return listwiseRating(canvases);
    case "listwise-notie":
      return ranking(canvases, choiceRows, true);
    case "listwise-cantie":
      return ranking(canvases, choiceRows, false);
    case "listwise-ranking":
      return ranking(canvases, distanceRows, false);
  }
}
