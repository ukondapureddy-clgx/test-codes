---
name: filebeat-config-review
description: Creates or reviews Filebeat configs, lists required settings, and suggests fixes. Use for log onboarding, parsing issues, and pipeline or mapping checks.
argument-hint: Provide organization, space, environment, and application labels, plus an existing config or log samples when reviewing.
compatibility: Node.js is needed for local helpers; Filebeat is optional for runtime validation.
metadata:
  version: 1.0.0
  owner: Elastic Platform Operations
  review_cadence: quarterly and after pipeline or mapping changes
---

# Filebeat Configuration Review Skill

## Purpose

Create or review a Filebeat or Winlogbeat configuration that collects the right logs, sends them
to the right destination, and produces correctly mapped fields. Before adding any parsing, trace
what the downstream Logstash pipelines and Elasticsearch mappings already do, so the configuration
never duplicates work that another layer already owns. Usage and example prompts:
[EXAMPLE_PROMPTS.md](EXAMPLE_PROMPTS.md).

## Scope and safety guardrails

- This skill is advisory and generative. It produces configuration text and review findings; it
  does not deploy anything.
- Never contact live outputs, send samples to a production cluster, deploy a configuration, or
  restart a service without explicit user approval.
- When testing samples, use isolated sample paths and a fresh `path.data`. Never reuse a
  production registry.
- Deployable format is not proof of end-to-end readiness. Never present generated YAML as verified.
- Never claim a check passed when it was not executed. Configuration tests, export, and the
  preliminary sample analyzer do not prove parser coverage.
- Repository evidence is not proof of deployed state. The skill reads IaC, not running Logstash.
- Never silently change an output destination, a label, or existing routing. Flag the conflict and
  confirm intent first.
- Preserve secret references and TLS settings. Use references, never literal secret values.

## Canonical statuses

Use these exact values when reporting evidence and findings:

| Status | Meaning |
|---|---|
| `VERIFIED` | Confirmed against a named branch and file, or by an executed command. Cite the source. |
| `MISSING_CONFIGURATION` | Inspected on the selected ref and confirmed absent. |
| `UNVERIFIED` | Could not be inspected: no access, missing branch, or missing file. Not the same as missing configuration. |
| `NOT_EXECUTED` | A check that was not run, such as parser coverage with no samples supplied. |
| `BLOCKER` | Must be resolved before the configuration can be deployed. |
| `PLATFORM_ACTION` | Work owned by Platform/Cloud Operations, not by the application user. |
| `ENVIRONMENT_UNRESOLVED` | The environment label is not in the lookup table. Ask before continuing. |
| `REGION_SCOPE_REQUIRED` | A `glb` organization needs US, AUS, or both confirmed before proceeding. |

Do not substitute synonyms. In particular, never write "missing" when the correct status is
`UNVERIFIED`.

## Evidence prerequisites

Confirm these before producing findings:

- The environment label resolves to exactly one tier and one release branch. An unknown label is
  `ENVIRONMENT_UNRESOLVED`, not a guess.
- Every repository read uses the explicit selected release ref or its pinned SHA. Branchless code
  search may discover candidate paths, but refetch each candidate on the selected ref before using it.
- A module being enabled does not prove its ingest pipeline runs. For Logstash output, the
  Elasticsearch output must set `pipeline => "%{[@metadata][pipeline]}"` or module parsing never executes.
- Custom parsing requires representative samples or an authoritative format header. Standard system
  logs do not.
- An endpoint does not establish TLS mode. Resolve them separately.

---

## How to invoke

Provide a natural-language prompt with labels. Examples:

- `"Use filebeat-config-review to generate Filebeat for my Linux syslog and auth logs"`
- `"Use filebeat-config-review to review my IIS Filebeat template and these samples"`
- `"Check which dissect processors I can remove given downstream parsing"`
- `"Review my Nginx config and preserve my labels and existing routing"`

---

## Inputs the agent reads from the prompt

| Parameter | Required | Default | Notes |
|---|---|---|---|
| `organization` | Yes | — | Label such as `insurance_uw_us`. The `us` / `aus` / `glb` suffix selects region. |
| `space` | Yes | — | Must pair with the organization in the registered mapping. |
| `environment` | Yes | — | Selects tier and release branch. Case-insensitive lookup only; the emitted label is unchanged. |
| `application` | Yes | — | Fourth required label. Missing labels route events to `dropped_logs`. |
| `mode` | No | _inferred_ | Create or review. A review needs an existing configuration; a new one does not. |
| existing configuration | For reviews | — | Reuse it. Preserve requested Jinja style. |
| samples or format headers | For custom parsing | — | Required for custom parsers. Current samples take precedence over fixtures and older samples. |
| source OS / paths / stack version | No | _ask only if OS unknown_ | Never infer the source OS from the assistant's machine. |
| output format | No | native YAML | Use Jinja only when requested. |

Ask **one question at a time**, and only for essential unresolved choices: create or review,
source OS or database engine, unknown environment, or global region scope. Put missing paths,
versions, permissions, approved TLS settings, and necessary timezone values in the user-settings
table instead of asking repeatedly.

---

## Tools to call

| Tool | When to call |
|---|---|
| [`scripts/resolve-context.js`](scripts/resolve-context.js) | First, before any repository read. Returns tier, branch, explicit ref, region candidates, and the known endpoint. |
| Authenticated GitHub repository read | Always for a review. Fetch the built-in IaC repository on the explicit selected ref. |
| [`scripts/analyze-samples.js`](scripts/analyze-samples.js) | Optional preliminary candidate generation only. Never cite its output as parser coverage. |
| `filebeat test config` | Only with an installed stack-compatible Filebeat and user approval. Static check only. |

The built-in repository is
[corelogic-private/platform_services_glb-elkmla-iac](https://github.com/corelogic-private/platform_services_glb-elkmla-iac).
Never ask the application user for this URL, for repository files, or whether pipelines and
mappings exist. Investigate it yourself.

---

## Environment and region resolution

| Environment labels | Tier | IaC branch |
|---|---|---|
| int, np, nonprod, nonprd, dev, uat | NONPROD | release/int |
| reg, dr, drg, prd, mgt | PRD | release/prd |
| sbx | NONPROD | release/sbx |

- Normalize for lookup only. Keep emitted labels exactly as the user supplied them.
- Organization tags `us` and `aus` select region. `glb` is `REGION_SCOPE_REQUIRED` until the user
  confirms US, AUS, or both. Review each selected region separately.
- Never use `master`, default-branch content, or another branch or region as a fallback, including
  when `release/sbx` is unavailable. Report the failure instead.
- SBX resolves to tier `NONPROD` and repository branch `release/sbx`, but its US Filebeat/Winlogbeat
  destination is `logstash-metrics-sbx-usw1.solutions.corelogic.com:8080`, not the generic
  `nonprd-logs-listener-us` endpoint. This SBX endpoint was supplied by the user; retain that
  provenance unless independently confirmed by the authoritative endpoint page.
- For SBX downstream review, inspect the SBX deployment configuration on `release/sbx` (including
  `sbx-usc1 values.yml` when present) for the endpoint, nonprod topic subscriptions, and VM log
  input/output pipelines. Follow the configured routing into the nonprod Logstash pipelines; do
  not switch the IaC ref to `release/int`.
- SBX may be classified as `nonprd` for Logstash routing. That routing classification must not
  rewrite the original `labels.environment: sbx` in generated Filebeat configuration or reports.
- Check the authoritative endpoint page when accessible. Otherwise use the
  [stored US reference](references/us-observability-access.md) and disclose its provenance. Never
  guess an endpoint and never substitute a US endpoint for AUS.

---

## Step-by-step execution

**Step 1 — Collect what the user already provided**

Reuse supplied labels, samples, and templates. Determine create versus review. Standard system logs
need no samples: use the Linux system module for text logs, supported journald collection for
journal-only sources, and Winlogbeat or the Windows integration for native Windows events. For
custom parsing, identify each sample's category, format, and producer, and mark uncertainty rather
than guessing.

**Step 2 — Resolve environment, region, and endpoint**

Run `resolve-context.js`. Record the tier, branch, explicit ref, region, endpoint, and any distinct
Logstash routing classification. Keep the emitted environment label unchanged. Stop and ask if the
result is `ENVIRONMENT_UNRESOLVED` or `REGION_SCOPE_REQUIRED`.

**Step 3 — Trace downstream before adding any parsing**

On the selected ref only, trace in this order:

1. The selected deployment's enabled Logstash inputs and the port matching the resolved endpoint.
   For SBX, inspect its `release/sbx` deployment values (including `sbx-usc1 values.yml` when
   present) and follow nonprod-topic/VM-log routing into the nonprod pipelines.
2. Required-label validation and any dropped-log routing.
3. Pipeline-to-pipeline dispatch, including the default branch for unlisted organizations.
4. The Elasticsearch output and actual destination topology: determine whether it writes to a
   legacy index/ILM route or a data stream, and record the concrete index/data-stream naming and
   routing conditions. Check whether `pipeline => "%{[@metadata][pipeline]}"` is set.
5. `index_templates.tf`, `componenttemplates.tf`, and the regional `spaces.csv` entry to find the
   applicable component templates.
6. The component mappings themselves, including `dynamic` and the type of every field the
   configuration produces.

Then establish **who owns** parsing, placeholder cleanup, numeric conversion, timestamps, and
routing. Compare expected fields and types against the matching component mappings. HTTP status
codes must be numeric (`long`); flag any incompatible existing type. With `dynamic: false`, explain
that unmapped values may remain in `_source` without being searchable. Separate template changes for
new indices, compatible existing-index updates, and historical reindexing. Record the topology result
as legacy index/ILM, data stream, or `UNVERIFIED`; do not infer it from the endpoint, labels, or
template names alone.

Cite the branch and every file checked.

**Step 4 — Generate the simplest complete configuration**

Prefer, in order: a supported module or native input, controlled JSON decoding, Dissect for stable
text, then downstream Grok for variable text. Grok belongs in an ingest pipeline or Logstash filter,
never in a fictional native Filebeat processor.

- Reuse verified downstream parsing. Never duplicate it. Dissect alternatives must be mutually exclusive.
- Prefer native processors; use scripts only when necessary.
- Keep unrelated formats in separate inputs or mutually exclusive conditions.
- Bound multiline aggregation and make parse failures observable.
- Fill in concrete labels and endpoints. Use fail-fast `${VAR:?explanation}` for required unknown
  runtime values.
- Make the proposed Filebeat configuration consistent with the traced downstream topology. For a
  verified legacy index/ILM route, preserve its routing and do not add data-stream metadata. Add
  `data_stream.*` fields and `event.dataset` only when a verified, supported downstream data-stream
  route requires and consumes them; confirm the expected values against its routing and templates.
  If topology is `UNVERIFIED`, do not assume or introduce a data-stream route: preserve confirmed
  settings, disclose the uncertainty, and mark any deployment dependency as a `BLOCKER`.
- Compare output settings and all four labels against the organization baseline.
- Add a timezone override only when genuinely needed, not for offset-bearing timestamps, correct
  module-local handling, verified downstream timezone handling, or timestamp-free logs. Without a
  source timestamp, explain collection-time semantics.

**Step 5 — Return the three-section response**

Use the output format below, in that order, with no section omitted.

**Step 6 — Validate safely and report honestly**

Report the runtime and version used, or state that validation was static only. Account for every
supplied sample as validated, not runtime-tested, unmatched, ambiguous, or malformed. Report parse
failures and multiline event counts without hiding them. With no samples, state verbatim:
`No samples supplied; standard collector selected, parser coverage not executed`.

---

## Output format

```
## 1. Configuration template

<complete native Filebeat YAML, or Jinja when requested>

## 2. What the user must add

| Setting / variable | What to add or confirm | Example (not a verified value) | Required before start? |
|---|---|---|---|
| ... | ... | ... | Yes / No |

## 3. Suggestions

**Routing traced:** <input pipeline> -> <filter pipeline> -> <legacy index/ILM or data stream>
Topology: <verified legacy index/ILM | verified data stream | UNVERIFIED>. Filebeat
`data_stream.*` / `event.dataset` decision: <settings and evidence, or why omitted>.
Branch checked: <release ref>. Files checked: <list>.

| Processor / parser | Downstream equivalent? | Action |
|---|---|---|
| ... | None / owned by <layer> | Keep / Remove / Replace |

### Mapping comparison
| Field | Produced type | Existing mapping | Finding and recommendation |
|---|---|---|---|

### Blockers
- `BLOCKER` <what must be resolved before deployment>

### Platform/Cloud Operations actions
- `PLATFORM_ACTION` <mapping additions, pipeline dispatch, label registration>

### Validation honesty
- <executed checks and results, or NOT_EXECUTED with the reason>
- <evidence provenance, and what remains UNVERIFIED versus MISSING_CONFIGURATION>
```

Always separate application-user settings from Platform/Cloud Operations work. Put supporting
detail under section 3 rather than repeating the configuration.

---

## Important notes for the agent

- Trace downstream **before** writing parsing, not after. Duplicate parsing is the most common defect.
- A stored pipeline file does not establish an active pipeline. Check enablement and migration configuration.
- Say `UNVERIFIED`, not "missing", when evidence was unavailable, and name the platform-team check needed.
- Never ask the application user whether ingest pipelines or mappings exist. Find out yourself.
- Never ask for the IaC repository URL. It is built in.
- Do not rely on an undocumented parsing-failure tag for fallback control.
- Do not decode arbitrary JSON into the root or expand untrusted dotted keys.
- Numeric placeholders such as `-` will reject a document against a `long` mapping. Normalize them
  before conversion.
- Report sample and header column-count inconsistencies rather than silently accepting them.
- Detailed rule IDs `FB001`–`FB031` live in [review-rules.md](references/review-rules.md). Cite them
  in findings so reviewers can reference a specific rule.

---

## Detailed guidance (read the applicable sections)

| Reference | Purpose |
|---|---|
| [Log formats](references/log-formats.md) | Source selection, samples, multiline, and timezone |
| [Organization baseline](references/organization-baseline.md) | Labels, region, outputs, and routing |
| [Repository access](references/repository-access.md) | Explicit-ref fetch and downstream tracing |
| [ECS fields](references/ecs-fields.md) | Field names and types |
| [Review rules](references/review-rules.md) | Detailed parsing and compatibility checks |
| [Output template](references/output-template.md) | Review tables, expected documents, and validation |
