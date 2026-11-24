// Tests for who may call /api/identify.  Run from phone-web/:  node --test
import assert from "node:assert/strict";
import test from "node:test";

import { CLIENT_HEADER, isAllowedCaller, normalizeLabel, parseRecognition, readAiResult } from "../functions/api/identify.js";

test("the object's name is taken from the start of the description", () => {
  assert.equal(normalizeLabel("A black computer mouse. It is used to move the pointer."), "mouse");
  assert.equal(normalizeLabel("The main object is a blue bus parked on a city street."), "bus");
  assert.equal(normalizeLabel("A stapler with a silver top."), "stapler");
  assert.equal(normalizeLabel("A ceramic teapot. It is used to make tea."), "teapot");
  assert.equal(normalizeLabel("unknown"), null);
});

// Real Moondream answers from the 2026-11-22 photo test that were named wrongly.
test("openings like 'This is a' and 'A pair of' are not taken as the name", () => {
  assert.equal(normalizeLabel("This is a stainless steel refrigerator. It has a silver handle."), "refrigerator");
  assert.equal(normalizeLabel("This is a dust-free eraser from Faber-Castell."), "eraser");
  assert.equal(normalizeLabel("A pair of silver-framed eyeglasses. The lenses are clear."), "glasses");
  assert.equal(normalizeLabel("The main object is a pair of scissors. They are black."), "scissors");
  assert.equal(normalizeLabel("This is a clear plastic egg carton containing two eggs."), "egg");
});

test("the object's own name wins over a colour, material, or a later sentence", () => {
  assert.equal(normalizeLabel("The main object is a frosted glass mug. It has a grid pattern."), "mug");
  assert.equal(normalizeLabel("A clear plastic water bottle with a light teal lid."), "water bottle");
  assert.equal(normalizeLabel("The main object is a tablet computer. It has a white stylus resting on top."), "tablet");
  assert.equal(normalizeLabel("A pink clothes hanger. It is pink and has a hook at the end."), "hanger");
  assert.equal(normalizeLabel("The orange chair is the main object in the photo."), "chair");
});

// Real Moondream answers from the 2026-11-24 supermarket test: the packaging was named, not the product.
test("a bag, package or box of something is named by what is inside", () => {
  assert.equal(normalizeLabel("A plastic bag of ripe yellow bananas. Visible features: yellow color."), "banana");
  assert.equal(normalizeLabel("The main object is a plastic bag of broccoli. A white label is visible."), "broccoli");
  assert.equal(normalizeLabel("A plastic bag of tomatoes. The bag is clear plastic."), "tomato");
  assert.equal(normalizeLabel("A plastic bag containing several round bread rolls."), "bread");
  assert.equal(normalizeLabel("This is a package of Pentel EnerGel X pens. The package contains two pens."), "pen");
  assert.equal(normalizeLabel("The main object is a pack of Energizer Max batteries."), "battery");
  assert.equal(normalizeLabel("This is a package of Colgate toothbrushes. The package is red."), "toothbrush");
  assert.equal(normalizeLabel("This is a stack of Colgate toothpaste boxes. The boxes are red."), "toothpaste");
  assert.equal(normalizeLabel("The main objects are containers of Greek yogurt. They are blue."), "yogurt");
  assert.equal(normalizeLabel("This is a bag of Lay's potato chips. The bag is brown."), "chips");
});

test("objects not on the list keep the model's own words", () => {
  assert.equal(normalizeLabel("The main object is a ceiling light fixture. It has three bulbs."), "ceiling light fixture");
});

test("AI results are read whether they come as data, a Response, or a stream", async () => {
  const plain = { answer: "A computer mouse.", finish_reason: "stop" };
  assert.equal((await readAiResult(plain)).answer, "A computer mouse.");
  assert.equal((await readAiResult(new Response(JSON.stringify(plain)))).answer, "A computer mouse.");
  const events = 'data: {"answer":"A computer"}\n\ndata: {"answer":" mouse."}\n\ndata: [DONE]\n\n';
  assert.equal((await readAiResult(new Response(events).body)).answer, "A computer mouse.");
  // The shape Moondream actually returns on Cloudflare.
  const wrapped = { result: { answer: "A computer mouse.", finish_reason: "stop" }, usage: {} };
  assert.equal((await readAiResult(wrapped)).answer, "A computer mouse.");
});

const SITE = "https://graduation-6j1.pages.dev";

function request(headers) {
  return new Request(`${SITE}/api/identify`, { method: "POST", headers });
}

test("the ClearView website itself is allowed", () => {
  assert.equal(isAllowedCaller(request({ Origin: SITE })), true);
});

test("other websites are refused", () => {
  assert.equal(isAllowedCaller(request({ Origin: "https://example.com" })), false);
  assert.equal(
    isAllowedCaller(request({ Origin: "https://example.com", [CLIENT_HEADER]: "phone" })),
    false,
  );
});

test("the desktop app (no Origin, client header) is allowed", () => {
  assert.equal(isAllowedCaller(request({ [CLIENT_HEADER]: "desktop" })), true);
});

test("anonymous scripts (no Origin, no client header) are refused", () => {
  assert.equal(isAllowedCaller(request({})), false);
});

test("label reading ignores answers that echo the instructions instead of real text", () => {
  const read = (visible) => parseRecognition(JSON.stringify({ visible_text: visible, product: "mouse" }));
  assert.equal(read("Traditional Chinese characters").recognizedText, "");
  assert.equal(read("No visible text").recognizedText, "");
  assert.equal(read("").recognizedText, "");
  assert.equal(read("烏龍茶 無糖").recognizedText, "烏龍茶 無糖");
  assert.equal(read("cero emisiones").recognizedText, "cero emisiones");
});
