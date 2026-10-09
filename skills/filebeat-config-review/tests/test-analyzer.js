#!/usr/bin/env node

const assert = require("assert");
const path = require("path");
const { execFileSync } = require("child_process");

const skillRoot = path.resolve(__dirname, "..");
const output = execFileSync(
  process.execPath,
  [
    path.join(skillRoot, "scripts", "analyze-samples.js"),
    "--config",
    path.join(skillRoot, "fixtures", "iis", "filebeat.yml"),
    "--samples",
    path.join(skillRoot, "fixtures", "iis", "samples.log"),
    "--json",
  ],
  { encoding: "utf8" },
);

const result = JSON.parse(output);
assert.strictEqual(result.existing_dissects.length, 1);
assert.strictEqual(result.existing_dissects[0].fields, 23);

const access = result.detected_sections.find((item) => item.format === "iis_access");
assert(access, "IIS access format was not detected");
assert.strictEqual(access.header_field_count, 15);
assert.strictEqual(access.effective_field_count, 15);
assert.deepStrictEqual(access.row_token_counts, [15]);
assert(access.tokenizer.includes("%{http.response.status_code}"));

const httpError = result.detected_sections.find(
  (item) => item.format === "iis_http_error",
);
assert(httpError, "IIS HTTP error format was not detected");
assert.strictEqual(httpError.header_field_count, 13);
assert.strictEqual(httpError.effective_field_count, 14);
assert(httpError.tokenizer.includes("%{iis.error.stream_id}"));
assert(
  httpError.warnings.some((warning) => warning.includes("inferred streamid")),
  "HTTPERR header mismatch was not reported",
);

assert(
  result.other_formats.includes("windows_application_event"),
  "Windows Application event was not detected",
);

process.stdout.write("All filebeat-config-review analyzer tests passed.\n");
