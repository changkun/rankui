This folder contains the interactive demo at
[changkun.de/research/rankui](https://changkun.de/research/rankui/): the six
opinion measurement interfaces on the photo color enhancement task, running
entirely in the browser. Nothing a visitor does is recorded.

The demo is not the study system in [system](../system). To run without a
server, it reimplements two parts of it:

- `src/enhance.ts` ports the photo color enhancer from
  `system/backend/domain/enhance`. It reproduces the photos that participants
  saw: `tools/fidelity.ts` recomputes options from the released raw data and
  compares them pixel by pixel.
- `src/gp.ts` and `src/optimizer.ts` reimplement the Bayesian optimizers of
  `system/backend/optimizers`, which use BoTorch. Feedback is converted the
  same way: ratings train a utility model, choices and rankings become
  pairwise comparisons for a preference model, "I don't know" answers are
  left out, and a tie in a ranking counts in both directions. The models
  are smaller: they pick their hyperparameters from a grid, and search the
  next options among random candidates.

`src/widgets.ts` holds the six interfaces, with the wording of the study's
frontends, and `src/main.ts` the page around them.

## Usage

Requires Node.js 23.6 or newer, which runs TypeScript directly.

```
make dev       # serve at http://localhost:4410 and rebuild on change
make check     # tests, type check, and a headless browser run of every interface
make deploy    # check, then publish
```

The tests in `test` cover the enhancer against reference output of the Go
code, the feedback conversion, and a simulated participant for each
interface, whose hidden preference the optimizer has to approach.

The photos are by Yuki Koyama, released under CC0 with
[Sequential Gallery](https://github.com/yuki-koyama/sequential-gallery).
