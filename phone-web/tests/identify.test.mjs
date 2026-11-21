// Tests for who may call /api/identify.  Run from phone-web/:  node --test
import assert from "node:assert/strict";
import test from "node:test";

import { CLIENT_HEADER, isAllowedCaller } from "../functions/api/identify.js";

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
