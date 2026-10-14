# Review output template

Use three main response sections in the order below. Put supporting review
detail under section 3 rather than repeating the configuration.
Return all three sections in the chat response and save the complete section 1
configuration as a file in the current workspace root. Use
`filebeat.generated.yml` or `winlogbeat.generated.yml` (add `.j2` for a
requested Jinja template). Never overwrite an existing file; select the next
unused numbered name and report the saved path. If no workspace is open or
blockers prevent producing a configuration, explain why no file was created.

## 1. Configuration template

Start with the complete deployable-format configuration. Resolve known endpoints
and labels directly; prefer native Filebeat
environment/keystore variables for missing runtime settings. Reserve Jinja for
requested templates. Required variables deliberately fail startup if unset.
Do not equate runnable format with verified end-to-end deployment readiness.

Preserve verified parsing ownership and routing. Never add, inspect, validate, or comment on a
timestamp/timezone processor, override, or conversion; this is entirely out of scope. Do not
duplicate Dissect processing. If a required endpoint cannot be
resolved, report that blocker and require it explicitly rather than guessing.

## 2. What the user must add

Populate only missing or actionable runtime settings; never ask for labels or
an IaC URL already known. List paths, approved TLS values/certificate references,
versions, permissions, and timezone only when needed. Do not turn these into
repeated intake questions when generation can use safe fail-fast variables.

| Setting / variable | What the user must add or confirm | Example (not a verified value) | Required before start? |
|---|---|---|---|

## 3. Suggestions based on logs and deployment prerequisites

Separate optional improvements from blocking TLS, pipeline dispatch, label
registration, mapping, source permissions, and version requirements. State
what was inspected versus assumed or not executed.
When samples exist, connect suggestions to the actual format, fields/types,
and multiline behavior (timestamp/timezone handling is out of scope; see FB031). Without samples, give standard collector
guidance and explicitly report that parser coverage was not executed.

Investigate IaC and downstream configuration yourself; never ask the application
user whether ingest pipelines or mappings exist. Give Platform/Cloud Operations
actions for missing pipeline loading/selection, mapping additions, or label
registration. If evidence is unavailable, say "unverified", not "missing", and
identify the platform-team check needed before rollout.

## Detected formats

| Category / format / producer | Evidence/source lines | Input/fileset | Dataset / target data stream | Samples matched |
|---|---|---|---|---:|

State the resolved tier (NONPROD or PRD), source environment label, region
(AUS or US), repository branch checked, and mapping/template files inspected.
Distinguish current uploaded samples from local reference fixtures or prior
history. State ambiguous classifications rather than guessing.
For no-sample standard system collection, state the chosen OS/source/module,
assumptions, and "Parser coverage not executed; no samples supplied". Do not
invent samples, sample counts, or parsed documents.

For organizations tagged `glb`, state the selected deployment scope and report
US and AUS evidence separately if both are in scope. Include the Logstash and
ingest-pipeline files checked and which layer owns parsing, normalization,
numeric conversion, and routing (timestamp/timezone handling is out of scope). Explicitly list unavailable
pipeline evidence; repository configuration does not prove deployed state.

## Current configuration findings

List exact processor/sample mismatches, unsafe fallbacks, topology issues, and
configuration syntax concerns.

### Existing mapping/template comparison

| Field | Sample value/type | Existing mapping/template/type | Finding and recommendation |
|---|---|---|---|

For numeric HTTP status codes, explicitly state whether output is numeric or a
string and whether the existing mapping agrees. Distinguish a new-template fix
from the migration needed for existing indices.
For missing mappings, list exact fields and required types and identify the
applicable component template when known. Include a scoped mapping snippet when
useful; do not imply it belongs in Filebeat YAML. With `dynamic: false`, explain
that unmapped values can remain in `_source` without being indexed. Template
changes affect new indices; existing indices need compatible mapping updates,
and historical unmapped documents need reindexing to become searchable.

### Organization-baseline comparison

| Setting | Current value | Required/recommended value | Action or explicit exception |
|---|---|---|---|

Include Logstash enabled/host/ttl/pipelining/max_retries, disabled alternative
outputs, all four required labels, data_stream.type/dataset/namespace, and
event.dataset. Flag identity/environment conflicts requiring confirmation.
Explain that max_retries is retained as a standard although Filebeat retries
indefinitely regardless of this setting.

## Configuration review detail

Explain the configuration already provided in section 1; do not duplicate it.
Preserve template variables and secret references.
Combine the baseline output/labels with verified routing and only the processors
needed at Filebeat in one coherent configuration. Preserve index/ILM routing;
add per-format data-stream metadata only for an agreed, supported data-stream
topology. Offer a dissect alternative for stable text layouts when appropriate;
present alternatives as mutually exclusive, not double parsing. Explain why
dissect is unsuitable for JSON/native events/variable text where applicable.
Separate required Logstash/ingest/template changes and unknown deployment
prerequisites. Do not label unresolved placeholders or untested parser candidates
as production-ready.

## Expected parsed fields

When samples exist, show at least one representative expected parsed document
for each detected format. Without samples, list expected module fields/types
without inventing a parsed document.
Include labels, typed parsed values, and routing metadata appropriate
to the verified topology (nested data_stream fields and event.dataset when
applicable). Distinguish expected output from actual runtime output.

## Mapping-risk report

| Severity | Field | Observed types/values | Risk | Recommendation |
|---|---|---|---|---|

## Unmatched or malformed samples

Quote a short identifier or line number and explain what must be confirmed.

## Validation

Provide safe Filebeat commands, downstream ingest-pipeline checks, and Kibana
queries suitable for the detected output topology.

| Sample file / lines | Format / parser | Expected fields and types | Actual result or not executed | Status |
|---|---|---|---|---|

Report event counts before/after multiline aggregation, parser match/failure
counts, conversion failures, and unclassified records without hiding failures.
State the runtime/version used, or explicitly state static-only validation.
Check the proposed target stream and error fields in Kibana, and verify the
actual data stream/template and module pipeline downstream when access is
authorized. Never contact production merely to complete this report.
