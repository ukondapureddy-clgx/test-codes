#!/usr/bin/env node

const assert = require("node:assert/strict");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { resolveContext } = require("../scripts/resolve-context");

for (const [aliases, tier, branch] of [
  [["int", "np", "nonprod", "nonprd", "dev", "uat"], "NONPROD", "release/int"],
  [["reg", "dr", "drg", "prd", "mgt"], "PRD", "release/prd"],
  [["sbx"], "NONPROD", "release/sbx"],
]) {
  for (const alias of aliases) {
    const label = ` ${alias.toUpperCase()} `;
    const context = resolveContext(label, "common_services_us");
    assert.equal(context.tier, tier);
    assert.equal(context.branch, branch);
    assert.equal(context.ref, `refs/heads/${branch}`);
    assert.equal(context.labels.environment, label);
    assert.equal(context.repository.repo, "platform_services_glb-elkmla-iac");
    assert.equal(context.endpoints[0].logs, alias === "sbx"
      ? "logstash-metrics-sbx-usw1.solutions.corelogic.com:8080"
      : `${tier === "PRD" ? "prd" : "nonprd"}-logs-listener-us.solutions.corelogic.com:8080`);
    if (alias === "sbx") assert.equal(context.routing_environment, "nonprd");
  }
}

assert.deepEqual(resolveContext("int", "tax-us").regions, ["US"]);
const aus = resolveContext("prd", "tax_aus");
assert.deepEqual(aus.regions, ["AUS"]);
assert.equal(aus.endpoints[0].logs, null);
const global = resolveContext("sbx", "platform_services_glb");
assert.deepEqual(global.regions, ["US", "AUS"]);
assert.equal(global.requires_region_scope, true);
assert.equal(global.endpoints[0].logs, "logstash-metrics-sbx-usw1.solutions.corelogic.com:8080");
assert.equal(global.endpoints[1].logs, null);
for (const env of ["master", "main", "production", "", undefined]) {
  assert.throws(() => resolveContext(env, "tax_us"));
}
for (const org of ["business", "tax_us_aus", "tax_glb_us", "", undefined]) {
  assert.throws(() => resolveContext("int", org));
}

const script = path.join(__dirname, "..", "scripts", "resolve-context.js");
const valid = spawnSync(process.execPath, [script, "--env", "sbx", "--org", "tax_us"], { encoding: "utf8" });
assert.equal(valid.status, 0);
const sbx = JSON.parse(valid.stdout);
assert.equal(sbx.ref, "refs/heads/release/sbx");
assert.equal(sbx.labels.environment, "sbx");
assert.equal(sbx.routing_environment, "nonprd");
assert.equal(sbx.endpoints[0].logs, "logstash-metrics-sbx-usw1.solutions.corelogic.com:8080");
for (const args of [
  [], ["--env"], ["--env", "--org", "tax_us"], ["--bogus", "int"],
  ["--env", "int", "--env", "prd", "--org", "tax_us"],
]) {
  const invalid = spawnSync(process.execPath, [script, ...args], { encoding: "utf8" });
  assert.equal(invalid.status, 1);
  assert.equal(invalid.stdout, "");
  assert.match(invalid.stderr, /filebeat-config-review:/);
}
process.stdout.write("All environment/region context tests passed.\n");
