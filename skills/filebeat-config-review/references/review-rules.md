# Review rules

| ID | Severity | Rule |
|---|---|---|
| FB001 | High | Prefer a supported module/fileset for a recognized standard format. |
| FB002 | High | Every generated dissect must match every sample assigned to that format. |
| FB003 | High | Generate a replacement parser when the existing parser fails; do not only report the mismatch. |
| FB004 | High | Normalize placeholders and explicitly convert numeric/boolean fields. |
| FB005 | High | Detect scalar/object and cross-document type conflicts. |
| FB006 | High | Keep unrelated log formats in separate inputs/filesets or mutually exclusive conditions. |
| FB007 | High | Confirm module ingest-pipeline metadata survives Logstash output. |
| FB008 | High | Use Winlogbeat/Windows integration for native Windows Event Log when possible. |
| FB009 | Medium | Preserve original input during rollout and make parse failures observable. |
| FB010 | Medium | Do not rely on an undocumented parsing-failure tag for fallback control. |
| FB011 | Medium | Flag sample/header column-count inconsistencies. |
| FB012 | Medium | Avoid decoding arbitrary JSON into root or expanding untrusted dotted keys. |
| FB013 | Medium | Bound multiline aggregation and verify event boundaries. |
| FB014 | Low | Apply the explicit organization output/label baseline; avoid unrelated changes to credentials, monitoring, or logging settings. |
| FB015 | High | Compare all fixed Logstash settings and required labels against organization-baseline.md in every review. |
| FB016 | High | For an agreed data-stream topology, recommend root-level data_stream fields per format and matching event.dataset; verify downstream routing and templates. Preserve verified legacy index/ILM routing otherwise. |
| FB017 | High | Inspect input/global processors, modules, included files, and downstream parsing; do not apply a parser to unrelated events. |
| FB018 | High | Offer a sample-derived dissect alternative for stable text layouts when appropriate, including uploads with no existing processors; never enable it alongside verified parsing of the same payload. |
| FB019 | High | Never claim runtime parser coverage from the preliminary analyzer, fixtures, or configuration-only checks. |
| FB020 | High | Grok belongs in an ingest pipeline or Logstash filter, not a fictional native Filebeat processor. |
| FB021 | Medium | Use current samples over stored references; report source evidence and unavailable memory/files honestly. |
| FB022 | High | Flag conflicting application/environment labels or output destinations; confirm the intended profile before deployment. |
| FB023 | High | Resolve aliases using the context resolver: NONPROD uses `release/int`, PRD uses `release/prd`, and sbx uses `release/sbx` with its specific `logstash-metrics-sbx-usw1.solutions.corelogic.com:8080` US endpoint. Trace SBX routing classified as `nonprd` into its nonprod pipelines without rewriting the original `labels.environment: sbx`. Inspect only the explicit selected ref; never use master/default-branch evidence or another branch as fallback. |
| FB024 | High | Compare sample-derived field types to the matching existing mapping; recommend mapping missing fields and numeric conversion for numeric values, and flag incompatible existing types with a safe migration path. |
| FB025 | High | Trace applicable Logstash and ingest pipelines before adding Filebeat parsing; identify ownership of parsing, conversion, timestamps, and routing, and distinguish repository evidence from deployed state. |
| FB026 | Medium | Reuse supplied templates and labels, ask only for missing details one question at a time, and resolve US/AUS from organization tags; clarify deployment scope for glb. |
| FB027 | Medium | Generate the simplest complete configuration; reuse verified downstream processing, avoid unnecessary scripts, and preserve legacy routing unless a migration is explicitly agreed. |
| FB028 | High | Return complete deployable-format configuration first, a user-settings table second, and log-based suggestions third; separate application-user settings from platform-team actions and distinguish startup requirements/end-to-end blockers from verified readiness. |
| FB029 | Medium | For standard system logs without samples, generate from labels and the established OS/source using supported collection; ask only for OS/source if unknown, not mandatory test logs. |
| FB030 | High | Use the built-in IaC URL and explicit environment-selected release ref; never ask users for the IaC URL. Report authentication/missing-path failures rather than silently switching branches. |
| FB031 | Medium | Do not add an explicit timezone override when timestamps contain offsets, correct module local-time handling suffices, verified downstream timezone handling owns it, or logs have no timestamp. |

## Output topology

For direct Elasticsearch output, a module can select its ingest pipeline
normally after setup.

For Logstash output:

1. Verify module pipelines are loaded in Elasticsearch.
2. Verify Filebeat sends `[@metadata][pipeline]`.
3. Verify the Logstash Elasticsearch output uses the following only in a branch
   where `[@metadata][pipeline]` exists:

   ```logstash
   pipeline => "%{[@metadata][pipeline]}"
   ```

If any step is absent, module collection may work while parsing does not.
Recommend the missing step or provide Filebeat-side parsing when downstream
changes are outside scope.

For the standard data-stream recommendation, also follow the routing/template
prerequisites in `organization-baseline.md`. Module pipeline selection and
data-stream routing are separate requirements; neither proves the other works.
