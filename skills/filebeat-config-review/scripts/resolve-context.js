#!/usr/bin/env node

const ENVIRONMENTS = new Map([
  ...["int", "np", "nonprod", "nonprd", "dev", "uat", "sbx"].map((env) => [
    env, { tier: "NONPROD", branch: "release/int" },
  ]),
  ...["reg", "dr", "drg", "prd", "mgt"].map((env) => [
    env, { tier: "PRD", branch: "release/prd" },
  ]),
]);

function resolveContext(environment, organization) {
  if (typeof environment !== "string" || !environment.trim()) {
    throw new Error("An environment label is required.");
  }
  const profile = ENVIRONMENTS.get(environment.trim().toLowerCase());
  if (!profile) {
    throw new Error(`Unsupported environment "${environment}"; no branch fallback is allowed.`);
  }
  if (typeof organization !== "string" || !organization.trim()) {
    throw new Error("An organization label is required.");
  }
  const tags = [...new Set(organization.trim().toLowerCase().split(/[_-]/)
    .filter((tag) => ["us", "aus", "glb"].includes(tag)))];
  if (tags.length !== 1) {
    throw new Error("Organization must contain exactly one unambiguous us, aus, or glb region tag.");
  }
  const regions = tags[0] === "glb" ? ["US", "AUS"] : [tags[0].toUpperCase()];
  return {
    labels: { environment, organization },
    repository: {
      owner: "corelogic-private",
      repo: "platform_services_glb-elkmla-iac",
      url: "https://github.com/corelogic-private/platform_services_glb-elkmla-iac",
    },
    ...profile,
    ...(environment.trim().toLowerCase() === "sbx" ? { routing_environment: "nonprd" } : {}),
    ref: `refs/heads/${profile.branch}`,
    regions,
    requires_region_scope: tags[0] === "glb",
    endpoints: regions.map((region) => ({
      region,
      logs: region === "US"
        ? `${profile.tier === "PRD" ? "prd" : "nonprd"}-logs-listener-us.solutions.corelogic.com:8080`
        : null,
    })),
    endpoint_source: "references/us-observability-access.md (user supplied 2026-10-08); SBX uses the NONPROD endpoint per user confirmation (2026-10-09)",
  };
}

function main(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!["--env", "--org"].includes(flag)) {
      throw new Error(`Unknown argument: ${flag}`);
    }
    if (options[flag] !== undefined) throw new Error(`Duplicate argument: ${flag}`);
    const value = argv[++index];
    if (!value || value.startsWith("--")) throw new Error(`Missing value for ${flag}`);
    options[flag] = value;
  }
  process.stdout.write(`${JSON.stringify(resolveContext(options["--env"], options["--org"]), null, 2)}\n`);
}

if (require.main === module) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`filebeat-config-review: ${error.message}\n`);
    process.exitCode = 1;
  }
}

module.exports = { resolveContext };
