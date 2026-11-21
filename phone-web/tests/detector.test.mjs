// Tests for the on-device detector's decoding and closest-object logic.
// Run from phone-web/:  node --test
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

// detector.js is a plain browser script, so load it into a sandbox.
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(
  `${readFileSync(new URL("../public/detector.js", import.meta.url), "utf8")}
   globalThis.exported = { decodeDetections, summarizeDetections, COCO_LABELS };`,
  sandbox,
);
const { decodeDetections, summarizeDetections, COCO_LABELS } = sandbox.exported;

// Build a fake model output: [84 rows x N candidates], cx/cy/w/h then 80 scores.
function fakeOutput(candidates) {
  const count = candidates.length;
  const data = new Float32Array(84 * count);
  candidates.forEach(({ box: [cx, cy, w, h], label, score }, index) => {
    data[index] = cx;
    data[count + index] = cy;
    data[2 * count + index] = w;
    data[3 * count + index] = h;
    data[(4 + COCO_LABELS.indexOf(label)) * count + index] = score;
  });
  return { data, count };
}

test("decodes boxes back to photo pixels", () => {
  const { data, count } = fakeOutput([{ box: [320, 320, 100, 50], label: "cup", score: 0.9 }]);
  const [cup] = decodeDetections(data, count, 0.5);
  assert.equal(cup.label, "cup");
  assert.deepEqual([...cup.box], [540, 590, 740, 690]);
});

test("drops weak guesses below the confidence threshold", () => {
  const { data, count } = fakeOutput([{ box: [100, 100, 50, 50], label: "book", score: 0.1 }]);
  assert.equal(decodeDetections(data, count, 1).length, 0);
});

test("merges overlapping duplicate boxes of the same object", () => {
  const { data, count } = fakeOutput([
    { box: [100, 100, 80, 80], label: "bottle", score: 0.9 },
    { box: [102, 101, 80, 80], label: "bottle", score: 0.7 },
    { box: [400, 400, 80, 80], label: "bottle", score: 0.8 },
  ]);
  assert.equal(decodeDetections(data, count, 1).length, 2);
});

test("closest object is the largest non-person box; list is biggest first", () => {
  const { data, count } = fakeOutput([
    { box: [320, 320, 600, 600], label: "person", score: 0.95 },
    { box: [100, 100, 40, 40], label: "cup", score: 0.9 },
    { box: [300, 300, 300, 200], label: "laptop", score: 0.5 },
    { box: [500, 100, 60, 80], label: "book", score: 0.7 },
  ]);
  const { closest, objects } = summarizeDetections(decodeDetections(data, count, 1));
  assert.equal(closest.label, "laptop");
  assert.deepEqual([...objects], ["laptop", "book", "cup"]);
});

test("only people in view means no closest object", () => {
  const { data, count } = fakeOutput([{ box: [320, 320, 600, 600], label: "person", score: 0.9 }]);
  const { closest, objects } = summarizeDetections(decodeDetections(data, count, 1));
  assert.equal(closest, null);
  assert.equal(objects.length, 0);
});
