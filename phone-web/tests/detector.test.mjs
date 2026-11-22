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
   globalThis.exported = { decodeDetections, summarizeDetections, mergeDetections, worthCropping, photoProblem };`,
  sandbox,
);
const { decodeDetections, summarizeDetections, mergeDetections, worthCropping, photoProblem } = sandbox.exported;

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

// --- Combining the everyday-object model with YOLO26 ---
const COCO = ["person", "cell phone", "mouse", "cup", "book", "laptop"];
const box = (x) => [x, 0, x + 100, 100];
const names = (list) => [...list].map((d) => d.label);

test("YOLO26 corrects the everyday model on objects it knows (mouse seen as a phone)", () => {
  const merged = mergeDetections(
    [{ label: "cell phone", confidence: 0.52, box: box(0) }],
    [{ label: "mouse", confidence: 0.49, box: box(2) }],
    COCO,
  );
  assert.deepEqual(names(merged), ["computer mouse"]);
});

test("YOLO26 can't overrule objects it doesn't know (a wallet stays a wallet)", () => {
  const merged = mergeDetections(
    [{ label: "wallet", confidence: 0.6, box: box(0) }],
    [{ label: "cell phone", confidence: 0.7, box: box(1) }],
    COCO,
  );
  assert.deepEqual(names(merged), ["wallet"]);
});

test("objects found by only one model are all kept", () => {
  const merged = mergeDetections(
    [{ label: "keys", confidence: 0.5, box: box(0) }],
    [{ label: "cup", confidence: 0.8, box: box(500) }],
    COCO,
  );
  assert.deepEqual(names(merged).sort(), ["cup", "keys"]);
});

test("things worn by a person can't be the closest object (skier's hat vs skis)", () => {
  const { closest, objects } = summarizeDetections([
    { label: "person", confidence: 0.9, box: [100, 0, 300, 400] },
    { label: "hat", confidence: 0.8, box: [150, 0, 260, 90] },
    { label: "skis", confidence: 0.6, box: [80, 380, 330, 420] },
  ]);
  assert.equal(closest.label, "skis");
  assert.deepEqual([...objects].sort(), ["hat", "skis"]);
});

test("a worn item is still chosen if it's the only object", () => {
  const { closest } = summarizeDetections([
    { label: "person", confidence: 0.9, box: [100, 0, 300, 400] },
    { label: "glasses", confidence: 0.7, box: [160, 40, 240, 70] },
  ]);
  assert.equal(closest.label, "glasses");
});

test("the desk under an object is never the closest object", () => {
  const { closest } = summarizeDetections([
    { label: "desk", confidence: 0.6, box: [0, 0, 640, 480] },
    { label: "cup", confidence: 0.8, box: [200, 100, 350, 300] },
  ]);
  assert.equal(closest.label, "cup");
});

test("the cloud sees the whole photo when the chosen box is tiny", () => {
  // The open-wallet photo: only a corner of the keyboard was found.
  assert.equal(worthCropping({ label: "keyboard", box: [0, 0, 250, 250] }, 1000, 1000), false);
  assert.equal(worthCropping({ label: "cup", box: [0, 0, 400, 300] }, 1000, 1000), true);
});

// Grey photos as RGBA pixels: value(x, y) gives each pixel's brightness.
function greyPhoto(width, height, value) {
  const pixels = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      pixels[index] = pixels[index + 1] = pixels[index + 2] = value(x, y);
      pixels[index + 3] = 255;
    }
  }
  return pixels;
}

test("a sharp, bright photo has no problem", () => {
  const checkerboard = greyPhoto(40, 40, (x, y) => ((x >> 2) + (y >> 2)) % 2 ? 230 : 40);
  assert.equal(photoProblem(checkerboard, 40, 40), null);
});

test("a smooth, featureless photo is called blurry", () => {
  const smooth = greyPhoto(40, 40, (x) => 100 + x);
  assert.equal(photoProblem(smooth, 40, 40), "blurry");
});

test("a near-black photo is called too dark, even if sharp", () => {
  const darkCheckerboard = greyPhoto(40, 40, (x, y) => ((x >> 2) + (y >> 2)) % 2 ? 20 : 0);
  assert.equal(photoProblem(darkCheckerboard, 40, 40), "dark");
});
