import assert from "node:assert/strict";
import { test } from "node:test";
import { chooseMultipartChunkSize } from "../src/r2/presign";

const MEBIBYTE = 1024 * 1024;

test("multipart planner targets about 24 parts for large basketball videos", () => {
  assert.equal(chooseMultipartChunkSize(64 * MEBIBYTE), 8 * MEBIBYTE);
  assert.equal(chooseMultipartChunkSize(128 * MEBIBYTE), 8 * MEBIBYTE);
  assert.equal(chooseMultipartChunkSize(380 * MEBIBYTE), 16 * MEBIBYTE);
  assert.equal(chooseMultipartChunkSize(500 * MEBIBYTE), 24 * MEBIBYTE);
});

test("multipart planner caps preferred memory while preserving the R2 part-count limit", () => {
  assert.equal(chooseMultipartChunkSize(2 * 1024 * MEBIBYTE), 32 * MEBIBYTE);

  const veryLargeUploadBytes = 400 * 1024 * MEBIBYTE;
  const chunkSizeBytes = chooseMultipartChunkSize(veryLargeUploadBytes);
  assert.ok(Math.ceil(veryLargeUploadBytes / chunkSizeBytes) <= 10_000);
});
