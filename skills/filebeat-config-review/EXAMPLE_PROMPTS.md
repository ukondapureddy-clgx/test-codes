# Example prompts — filebeat-config-review

Natural-language prompts that should trigger and drive this skill. It creates or
reviews Filebeat/Winlogbeat configurations, checks downstream parsing and
mappings, and returns a deployable-format configuration with clear user settings
and review prerequisites. See [SKILL.md](SKILL.md) for agent instructions.

## Prompts that trigger this skill

- "Use filebeat-config-review to generate Filebeat for my Linux syslog and auth logs."
- "Generate a Filebeat config for my Windows IIS access logs."
- "Review my Nginx Filebeat template and these access/error samples."
- "Review this filebeat.yml and preserve my labels and existing routing."
- "Check which dissect processors I can remove given downstream parsing."
- "Is anything in my config already parsed by Logstash?"
- "Why are my IIS fields not searchable in Kibana?"
- "Which mappings are missing for the fields my config produces?"
- "Are my HTTP status codes indexed as numbers?"
- "Does my module's ingest pipeline actually run through Logstash?"
- "Which Logstash pipeline does my org route to?"
- "Review my config against the organization label and output baseline."
- "Is my timestamp and timezone handling correct for these logs?"
- "Onboard a new application log path to the int environment."

Prompts with labels get further, faster:

```text
Use filebeat-config-review to generate Filebeat for my Linux system syslog
and auth logs. I have no test logs.
org: common_services_us
space: underwritting
env: sbx
application: applogs
```

```text
Use filebeat-config-review to review my Nginx Filebeat template and these
access/error samples. Preserve my labels and existing routing.
env: int
org: common_services_us
space: underwritting
application: applogs
```

## Expected inputs the skill will resolve

- `organization`, `space`, `environment`, `application` (required) — the four
  labels. The `us` / `aus` / `glb` suffix on the organization selects region, and
  the environment selects the tier and IaC release branch.
- Existing configuration or template (required for a review) — reused as-is, with
  requested Jinja style preserved.
- Representative samples or format headers (required for custom parsing) — not
  needed for standard system logs.
- Log source/OS, source paths, and stack/Filebeat version (optional) — the skill
  asks only for the OS or source if it cannot be inferred safely.

Standard system collectors can be generated without samples. Linux text logs use
the system module; journal-only logging needs supported journald collection;
native Windows event channels use Winlogbeat or Elastic Agent. Custom parsers
still need evidence. Labels alone do not establish the source OS.

## What a good result looks like

A three-section response: complete native Filebeat YAML (or Jinja on request)
with known labels and endpoints filled in, a table of settings you must add or
confirm, and suggestions tied to your actual logs and downstream configuration.
Findings cite the release branch and files checked, use the canonical statuses
such as `VERIFIED`, `UNVERIFIED`, and `NOT_EXECUTED`, separate application-user
settings from Platform/Cloud Operations actions, and never report an unexecuted
check as passed.

## Before you start

1. Make sure you have GitHub Copilot access (CLI or the VS Code agent).
2. Clone the repository, then copy this skill folder into your Copilot skills
   directory so that `SKILL.md` sits at the root of the skill folder. The skill
   lives in a subfolder, so do not clone the repository directly over
   `~/.copilot/skills/`:

   ```powershell
   # Windows
   git clone https://github.com/ukondapureddy-clgx/test-codes.git "$env:TEMP\test-codes"
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.copilot\skills" | Out-Null
   Copy-Item "$env:TEMP\test-codes\skills\filebeat-config-review" `
     -Destination "$env:USERPROFILE\.copilot\skills\" -Recurse -Force
   ```

   ```bash
   # macOS / Linux
   git clone https://github.com/ukondapureddy-clgx/test-codes.git /tmp/test-codes
   mkdir -p ~/.copilot/skills
   cp -R /tmp/test-codes/skills/filebeat-config-review ~/.copilot/skills/
   ```

3. Restart your Copilot client, then start a request with
   `Use filebeat-config-review` to confirm the skill loads.
4. Be signed in to GitHub with access to the private IaC repository. Without it
   the skill still generates configuration, but downstream pipeline and mapping
   findings become "could not verify" review items instead of evidence.

Node.js and Filebeat are optional. They are only needed for the local helpers
and tests described at the end of this file, not to request a configuration or
review. To update later, pull the repository again and re-copy the folder.

## Team review at a glance

The main skill is a six-step checklist:

**User details -> environment/region -> downstream checks -> configuration ->
three-section response -> safe validation.**

Detailed rules remain in linked references and are read only where applicable.
Review these essentials: correct release branch, unchanged labels, no duplicate
parsing, compatible mappings, actionable user/platform settings, and honest
validation results. The assistant checks IaC; application users do not need to
understand repository or ingest-pipeline configuration.

## What you receive

1. Complete native Filebeat YAML by default, or Jinja if requested. Known labels
   and endpoints are filled in; required unknown values use fail-fast native
   environment/keystore references. Supply those in the service environment or
   keystore before starting Filebeat.
2. A table of settings you must add/confirm (paths, TLS, versions, and timezone
   only when needed). Examples are explicitly distinguished from known values.
3. Suggestions based on supplied logs, or standard collector guidance when no
   samples exist. Include missing mappings with field names/types, parsing and
   timestamp findings, evidence, and validation results. Separate deployment
   blockers from optional improvements and application-user settings from
   Platform/Cloud Operations actions. Unexecuted checks are never called passed.

The assistant investigates IaC, ingest pipelines, Logstash dispatch, mappings,
and label registration; it does not ask application users whether these exist.
Unavailable evidence becomes an explicit platform-team review item. Missing
runtime settings go in the table instead of repeated intake questions. Only
essential source choices that cannot be inferred safely (such as OS, database
engine, or global region scope) require clarification.

Deployable format is not proof of end-to-end readiness. The skill does not
deploy, restart services, send samples, or contact live outputs without approval.
It avoids duplicate Dissect when downstream parsing already owns the fields and
unnecessary explicit timezone overrides when source/module handling suffices.

## Repository and environment selection

The [IaC repository](https://github.com/corelogic-private/platform_services_glb-elkmla-iac)
is built in. Users do not need to provide its link.

| Labels used for lookup | Tier | Branch |
|---|---|---|
| int, np, nonprod, nonprd, dev, uat | NONPROD | release/int |
| reg, dr, drg, prd, mgt | PRD | release/prd |
| sbx | NONPROD | release/sbx |

Lookup is case-insensitive; emitted labels stay unchanged. No master/default
branch or cross-branch fallback is permitted. `us` resolves US, `aus` resolves
AUS, and `glb` requires US/AUS/both scope. Sandbox uses NONPROD ingestion.
Private repository access must already be authenticated; a URL grants no access.
Missing access or branches are reported, not silently replaced.

See [repository-access.md](references/repository-access.md) for fetching and
mapping/pipeline tracing, and [US endpoints](references/us-observability-access.md)
for the user-supplied endpoint reference. Tokens are not stored.

## Local helpers and tests

Node.js is needed only for these optional helpers, not to consume generated YAML:

```powershell
node .\scripts\resolve-context.js --env sbx --org common_services_us
node .\scripts\analyze-samples.js --config .\fixtures\iis\filebeat.yml --samples .\fixtures\iis\samples.log --json
node .\tests\test-context.js
node .\tests\test-analyzer.js
```

The context helper selects repository refs/endpoints without samples or network
access. Copilot uses its output for authenticated, explicit-ref repository reads.
The sample analyzer currently supports IIS header-derived candidates and limited
Windows/exception recognition; empty output does not establish parser coverage
for Nginx, syslog, or other formats. It does not fetch IaC or execute ingest.

After filling required settings, use the installed, stack-compatible Filebeat:

```powershell
filebeat test config -c ".\filebeat.yml"
```

This checks configuration, not parser coverage. Test samples separately in an
isolated configuration with fresh `path.data` and approved outputs; inspect
module ingest results before rollout.
