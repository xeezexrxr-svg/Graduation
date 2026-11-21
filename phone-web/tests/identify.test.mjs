// Tests for who may call /api/identify.  Run from phone-web/:  node --test
import assert from "node:assert/strict";
import test from "node:test";

import { CLIENT_HEADER, isAllowedCaller, readAiResult } from "../functions/api/identify.js";

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
