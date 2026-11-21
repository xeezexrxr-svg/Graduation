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
   globalThis.exported = { decodeDetections, summarizeDetections };`,
  sandbox,
);
const { decodeDetections, summarizeDetections } = sandbox.exported;

const LABELS = ["person", "cup", "laptop", "book", "bottle", "wallet"];
const EXTRA_ROWS = 2; // the real model adds mask rows after the scores; they must be ignored

// Fake model output: rows = cx, cy, w, h, one score per label, then extra rows.
function fakeOutput(candidates) {
  const count = candidates.length;
  const data = new Float32Array((4 + LABELS.length + EXTRA_ROWS) * count).fill(0);
  candidates.forEach(({ box: [cx, cy, w, h], label, score }, index) => {
    data[index] = cx;
    data[count + index] = cy;
    data[2 * count + index] = w;
    data[3 * count + index] = h;
    data[(4 + LABELS.indexOf(label)) * count + index] = score;
    data[(4 + LABELS.length) * count + index] = 0.99; // mask row: not a score
  });
  return { data, count };
}

const decode = (data, count, scale = 1) => decodeDetections(data, count, scale, LABELS);

test("decodes boxes back to photo pixels with the right label", () => {
  const { data, count } = fakeOutput([{ box: [320, 320, 100, 50], label: "wallet", score: 0.9 }]);
  const [wallet] = decode(data, count, 0.5);
  assert.equal(wallet.label, "wallet");
  assert.deepEqual([...wallet.box], [540, 590, 740, 690]);
});

test("drops weak guesses below the confidence threshold", () => {
  const { data, count } = fakeOutput([{ box: [100, 100, 50, 50], label: "book", score: 0.35 }]);
  assert.equal(decode(data, count).length, 0);
});

test("merges overlapping duplicate boxes of the same object", () => {
  const { data, count } = fakeOutput([
    { box: [100, 100, 80, 80], label: "bottle", score: 0.9 },
    { box: [102, 101, 80, 80], label: "bottle", score: 0.7 },
    { box: [400, 400, 80, 80], label: "bottle", score: 0.8 },
  ]);
  assert.equal(decode(data, count).length, 2);
});

test("closest object is the largest non-person box; list is biggest first", () => {
  const { data, count } = fakeOutput([
    { box: [320, 320, 600, 600], label: "person", score: 0.95 },
    { box: [100, 100, 40, 40], label: "cup", score: 0.9 },
    { box: [300, 300, 300, 200], label: "laptop", score: 0.5 },
    { box: [500, 100, 60, 80], label: "book", score: 0.7 },
  ]);
  const { closest, objects } = summarizeDetections(decode(data, count));
  assert.equal(closest.label, "laptop");
  assert.deepEqual([...objects], ["laptop", "book", "cup"]);
});

test("only people in view means no closest object", () => {
  const { data, count } = fakeOutput([{ box: [320, 320, 600, 600], label: "person", score: 0.9 }]);
  const { closest, objects } = summarizeDetections(decode(data, count));
  assert.equal(closest, null);
  assert.equal(objects.length, 0);
});

test("the published label list matches vocabulary.txt", () => {
  const labels = JSON.parse(readFileSync(new URL("../public/models/labels.json", import.meta.url), "utf8"));
  const vocabulary = readFileSync(new URL("../../vocabulary.txt", import.meta.url), "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim().toLowerCase())
    .filter((line) => line && !line.startsWith("#"));
  assert.deepEqual(labels, [...new Set(vocabulary)]);
});
