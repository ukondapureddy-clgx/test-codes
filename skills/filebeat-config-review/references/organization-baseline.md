# Organization baseline

Apply this baseline to every uploaded Filebeat review. It is a recommendation,
not permission to deploy, connect to production, or silently change destinations.
Explicit user overrides take precedence and must be recorded as deviations.

## Fixed output and labels

| Setting | Required baseline |
|---|---|
| `output.logstash.enabled` | `true` |
| `output.logstash.hosts` | Resolve environment/region using the Confluence page or the user-supplied [US endpoint reference](us-observability-access.md); prefer NEW endpoints |
| `output.logstash.ttl` | `300s`; `50s` for known non-GCP sources per the endpoint reference |
| `output.logstash.pipelining` | `0` |
| `output.logstash.max_retries` | `-1` |
| `output.console.enabled` | `false` |
| `labels.organization` | `data_portals_us` |
| `labels.environment` | Preserve the actual configured environment; use `prd` only for PRD |
| `labels.space` | `corebatch` |
| `labels.application` | `cb-app` |

Keep `add_host_metadata` and `add_cloud_metadata` unless explicitly excluded.
Merge required labels with existing non-conflicting labels rather than dropping
custom metadata. Report conflicting values before presenting the proposed
replacement. These labels are the user-provided baseline, not values inferred from IIS or
Nginx. Resolve environment aliases from uploaded labels/configuration:

| Environment label | Tier | Repository branch |
|---|---|---|
| `int`, `np`, `nonprod`, `nonprd`, `dev`, `uat` | NONPROD | `release/int` |
| `reg`, `dr`, `drg`, `prd`, `mgt` | PRD | `release/prd` |
| `sbx` | NONPROD | `release/sbx` |

Use [repository-access.md](repository-access.md) and the context resolver for
explicit release refs. Never use `master`, a default branch, or another release
branch as a fallback. SBX uses its specific US endpoint
`logstash-metrics-sbx-usw1.solutions.corelogic.com:8080` and the `release/sbx`
repo branch. Trace its configured `nonprd` routing into the nonprod pipelines;
preserve `labels.environment: sbx`.

Resolve region from the organization label's delimited tag (for example,
`tax-us`, `tax_us`, or an equivalent `aus`/`glb` tag):

| Organization tag | Region scope | Action |
|---|---|---|
| `us` | US | Inspect the matching US configuration; do not ask again unless evidence conflicts. |
| `aus` | AUS | Inspect the matching AUS configuration; do not ask again unless evidence conflicts. |
| `glb` | US and AUS | Ask whether this request targets US, AUS, or both unless already specified; inspect each selected region separately. |

Match whole delimited tags, not arbitrary substrings. Preserve the organization
label exactly; do not rewrite hyphens to underscores to match repository naming.
Missing, multiple, or conflicting region tags require clarification. A `glb`
label does not mean that one endpoint/template applies in both regions.
Cross-check the resolved scope with uploaded configuration and inspect the
matching region path (for example, `observability-ause1` or
`observability-usc1`) on that branch.
These environment aliases select the tier and repository branch; they do not by
themselves establish a canonical `labels.environment` or data-stream namespace.
Preserve the concrete configured label/namespace unless a repository mapping or
the user explicitly supplies its canonical value. If environment or region is
missing or conflicting, ask before presenting deployment-ready settings. Do not
silently route non-production logs to a production listener.

Verify endpoints on the Confluence page when accessible. If it requires
authentication, use the user-supplied [US endpoint reference](us-observability-access.md)
for the resolved US tier and disclose its capture date and provenance. This
reference supersedes the earlier unverified hostname snapshot. Do not ask again
for an endpoint already provided. Ask for missing AUS endpoints or confirmation
when newer evidence conflicts; never invent a hostname from the environment name.
Preserve `service.name` and existing `env` unless the user requests a change.

Retain SSL/TLS, proxy, and authentication/keystore references. Do not disable
TLS, replace certificates, or remove security settings to fit the example.
Only Logstash should be enabled in the production recommendation; retain other
output configurations as disabled where supported. Never enable console and
Logstash simultaneously in a validation configuration.

`pipelining: 0` keeps the client synchronous so `ttl: 300s` can take effect.
Filebeat's Logstash output currently ignores `max_retries` and retries
indefinitely; retain `-1` as the requested standard, but do not claim that it
changes this behavior. Port 8080 must accept the Beats protocol, not HTTP.

## Data-stream recommendation

Preserve verified existing index/ILM routing. Do not migrate it to data streams
unless the user explicitly agrees and downstream prerequisites are verified.
For a data-stream topology, each log format needs root-level object fields:

| Field | Recommendation |
|---|---|
| `data_stream.type` | `logs` |
| `data_stream.dataset` | Stable dataset chosen from the actual format |
| `data_stream.namespace` | Environment-appropriate; use `prd` only for PRD |
| `event.dataset` | Same value as `data_stream.dataset` |

Use `fields_under_root: true` with nested objects, or `add_fields` with the
appropriate target. Do not put these fields under `labels` or `@metadata`.
Validate dataset and namespace against the target version's naming rules; use
lowercase names without hyphens, spaces, or index-name forbidden characters.
Never derive a dataset from an unbounded URL, filename, user ID, or timestamp.

Examples: `iis.access`, `iis.error`, `nginx.access`, `nginx.error`, `system.syslog`,
`system.auth`, `windows.application`, or an application-specific dataset such as
`corebatch.application`. The resulting name is
`logs-<dataset>-<environment-appropriate-namespace>`; use `prd` only for PRD.
Do not force all formats into `corebatch.application`. Preserve a valid existing
dataset or a module's dataset when it matches the actual format; reconcile any
downstream pipeline that overwrites `event.dataset`. Set routing per input,
fileset, channel, or mutually exclusive condition, not a global dataset that
overwrites every event.

### Logstash and Elasticsearch prerequisites

Filebeat fields do not create or guarantee a data stream. Inspect the supplied
Logstash output/template, or mark downstream support as unverified. Recommend:

- An Elasticsearch output with `data_stream => true`,
  `data_stream_auto_routing => true`, and supported ECS compatibility (`v8`
  for a compatible stack, otherwise verify the version).
- A matching data-stream-enabled index template with an `@timestamp` date
  mapping and consistent ECS/custom field mappings; verify priorities against
  existing templates and legacy index/ILM routing.
- Create operations, appropriate permissions, and preservation of
  `data_stream.*` through all filters. Do not rely on fallback
  `logs-generic-default` routing.
- For modules, loaded ingest pipelines and conditional use of
  `pipeline => "%{[@metadata][pipeline]}"` only when that metadata exists.
  Events without it need a non-module branch; never interpolate a missing value.

Provide exact downstream changes only when its existing configuration and
versions are known. Otherwise provide clearly marked prerequisites, not invented
Elasticsearch hosts, credentials, or a claim that routing has been verified.

## Authoritative references

- [US Observability Access endpoint reference](us-observability-access.md):
  user-provided page contents, preferred/legacy ingestion endpoints, non-GCP
  connection settings, firewall guidance, and MCP addresses; no tokens stored.
- Mapping/configuration repository: [platform_services_glb-elkmla-iac](https://github.com/corelogic-private/platform_services_glb-elkmla-iac).
  The URL is built in; do not ask users to provide it. Follow
  [repository-access.md](repository-access.md). Read the selected branch's
  `clgx-obs-configuration/terraform/env/` deployment
  configuration, `index_templates.tf`, `componenttemplates.tf`, and applicable
  `files/<region>/components/` files. Discover current paths and template
  composition; do not assume all applications use the same tax components.
- Locate actual Logstash configuration and referenced ingest pipelines on the
  matching environment/region before generating Filebeat parsing. No separate
  application-pipeline repository/path is verified in this reference yet;
  discover it from configuration; if discovery fails, report missing evidence
  and suggest relevant runtime files or authenticated access, not an IaC URL. Do not
  equate a CI/build repository with deployed Logstash filter configuration.
- Store repository links and navigation guidance here, not copied code or
  credentials. Fetch current branch content on each review through authenticated
  repository access or a local checkout; ask only for unavailable evidence.
- https://www.elastic.co/docs/reference/beats/filebeat/logstash-output
- https://www.elastic.co/docs/reference/logstash/plugins/plugins-outputs-elasticsearch

Check documentation for the user's installed versions before deployment.
