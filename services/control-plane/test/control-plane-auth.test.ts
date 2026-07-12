import assert from "node:assert/strict";
import { test } from "node:test";
import { isSharedSecretAuthorized } from "../src/utils/auth";

test("shared-secret authorization fails closed when the configured secret is missing", () => {
  assert.equal(isSharedSecretAuthorized(null, undefined), false);
  assert.equal(isSharedSecretAuthorized("presented-token", undefined), false);
});

test("shared-secret authorization requires an exact configured token", () => {
  assert.equal(isSharedSecretAuthorized(null, "configured-token"), false);
  assert.equal(isSharedSecretAuthorized("wrong-token", "configured-token"), false);
  assert.equal(isSharedSecretAuthorized("configured-token", "configured-token"), true);
});
