# Environment-selected repository access

Built-in repository:
[corelogic-private/platform_services_glb-elkmla-iac](https://github.com/corelogic-private/platform_services_glb-elkmla-iac)
(Terraform / Ansible specific configuration for generic ECE usage).
Do not ask the user for this URL.

| Environment aliases (case-insensitive lookup) | Tier | Required branch |
|---|---|---|
| int, np, nonprod, nonprd, dev, uat, sbx | NONPROD | release/int |
| reg, dr, drg, prd, mgt | PRD | release/prd |

Preserve original labels in generated configuration. Unknown environments fail
resolution and require clarification. No master/default-branch access and no
fallback to another release branch.

## Resolve, then fetch

```powershell
node .\scripts\resolve-context.js --env sbx --org common_services_us
```

The helper outputs repository owner/name/URL, tier, branch, explicit Git ref,
region candidates, and the known US logs endpoint. For SBX, it also reports the
`nonprd` Logstash routing classification while preserving `labels.environment`
as supplied. SBX uses the same NONPROD US logs listener as `int` and other
NONPROD environments. It does not download private
data, authenticate, validate labels against dictionaries, or prove deployment
state. It works without test logs. `glb` returns US and AUS candidates; confirm
scope unless already supplied. AUS endpoint is unknown, never a US fallback.

Use authenticated GitHub tools to fetch with the returned ref, for example:

```text
owner: corelogic-private
repo: platform_services_glb-elkmla-iac
path: clgx-obs-configuration/terraform
ref: refs/heads/release/int
```

Always pass `ref` to every directory/file read. Alternatively, resolve the
selected release ref to a commit SHA and pin all reads to that SHA. Record the
branch and SHA when available. Branchless code search is only for discovering
candidate paths; refetch each candidate on the selected ref before using it.
Do not use master or implicit default-branch content, even for missing files.

1. List the selected ref's directories; discover deployment paths by region
   and environment rather than assuming aliases correspond to folder names.
2. Trace `index_templates.tf`, `componenttemplates.tf`, and regional
   `spaces.csv` entries to applicable mapping/settings components.
3. Trace enabled Logstash inputs, label dictionaries, pipeline links, outputs,
   and referenced Elasticsearch ingest pipelines. Check enablement/migration
   configuration: a stored pipeline file does not establish an active pipeline.
4. Resolve the endpoint separately from the repository branch using
   [us-observability-access.md](us-observability-access.md). Do not assume the
   endpoint proves that a Logstash pipeline is enabled or establishes the
   downstream Elasticsearch topology.
5. If authentication, a branch, or runtime files are unavailable, report exactly
   what could not be checked. Keep generation possible with explicit review
   blockers and assign access/deployment verification to Platform/Cloud
   Operations. Never ask application users for the known IaC URL, repository
   files, or confirmation that pipelines/mappings exist; never claim downstream
   parsing is verified without evidence.

The sample analyzer remains a local, sample-only candidate tool. Use this
resolver before repository reads; do not embed unauthenticated network fetching
or credentials into the analyzer.
