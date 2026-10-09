# US Observability access

Source: [Cloud Operations / US Observability Access](https://corelogic.atlassian.net/wiki/spaces/CO/pages/118030337/US+Observability+Access).
The user supplied this page's contents on 2026-10-08; the page showed
"Updated Sep 25". This is a user-provided reference, not independently verified
live deployment state. Prefer NEW endpoints for new configurations. Refresh
against the page when accessible; when authentication prevents access, use this
reference and disclose its provenance rather than inventing a host or repeatedly
requesting an endpoint already supplied. Confirm newer conflicting evidence.

## Observability environments

| Environment | Address |
|---|---|
| US production | https://observability.solutions.corelogic.com/ |
| US non-production | https://observability-np.solutions.corelogic.com/ |

## Beats ingestion endpoints

These listeners accept Beats traffic, not HTTP. Logs and metrics use different
listeners. Filebeat and Winlogbeat are supported on the logs listeners; other
Beats may have their events dropped.

| Type | Tier | Preferred endpoint | Legacy endpoint / notes |
|---|---|---|---|
| VM logs (Filebeat / Winlogbeat) | PRD | `prd-logs-listener-us.solutions.corelogic.com:8080` | OLD: `vm-prd-logs-listener.solutions.corelogic.com:8080` |
| VM logs (Filebeat / Winlogbeat) | NONPROD | `nonprd-logs-listener-us.solutions.corelogic.com:8080` | OLD: `vm-nonprd-logs-listener.solutions.corelogic.com:8080` |
| VM logs (Filebeat / Winlogbeat) | SBX deployment | `logstash-metrics-sbx-usw1.solutions.corelogic.com:8080` | User supplied 2026-10-09; verify against the authoritative page when accessible |
| VM metrics (Metricbeat) | PRD | `prd-metrics-listener-us.solutions.corelogic.com:8080` | `vm-metrics-listener.solutions.corelogic.com:8080` marked under development; all VM metrics go to production by default |
| VM metrics (Metricbeat) | NONPROD | `nonprd-metrics-listener-us.solutions.corelogic.com:8080` | `vm-nonprd-metrics-listener.solutions.corelogic.com:8080` marked under development |
| Infosec logs (Filebeat) | PRD | `prd-logs-listener-us.solutions.corelogic.com:8091` | Infosec deployment only |
| Infosec logs | NONPROD | No endpoint listed | Do not invent one |

Use the SBX deployment endpoint above for `sbx` and the generic NONPROD logs
listener for `int`, `np`, `nonprod`, `nonprd`, `dev`, or `uat`; use PRD logs
for `reg`, `dr`, `drg`, `prd`, or `mgt`, when the organization resolves to US.
SBX repository checks use the NONPROD `release/int` branch, and SBX routing is
classified as `nonprd` without changing the original `labels.environment: sbx`. These US
Beats endpoints do not establish AUS Beats endpoints. A hostname and port do not
establish TLS or mTLS requirements; preserve existing approved TLS settings or
require the user to supply them. Never infer plaintext from port 8080.

## Firewall and external datacenters

The supplied page says GCP systems should already have access. If outbound
rules need changes, it lists both of these destinations:

| Protocol | Destination subnet | Port |
|---|---|---|
| TCP | `172.28.228.0/22` | `8080` |
| TCP | `172.28.244.0/22` | `8080` |

Verify current network requirements with Cloud Ops; do not modify firewall
rules automatically or assume these 8080 rules cover Infosec's 8091 listener.

For non-GCP sources (for example NTT), the page recommends:

```yaml
output.logstash:
  ttl: 50s
  pipelining: 0
```

The shorter TTL helps redistribute sticky connections behind load balancers
and avoids overly long-lived connections across external firewalls. Use this
50s recommendation for known non-GCP sources; otherwise retain the skill's 300s
baseline and tell the user to switch to 50s if applicable.

## APM and MCP (not Filebeat outputs)

| Service | Tier | Region | Endpoint |
|---|---|---|---|
| APM | NONPROD | US | https://apm-np.solutions.corelogic.com/ |
| APM | PRD | US | https://apm.solutions.corelogic.com/ |
| MCP | PRD | US | https://observability.solutions.corelogic.com/mcp |
| MCP | NONPROD | US | https://observability-np.solutions.corelogic.com/mcp |
| MCP | PRD | AUSE | https://observability-ause.solutions.corelogic.com/mcp |
| MCP | NONPROD | AUSE | https://observability-int-ause.solutions.corelogic.com/mcp |

Authentication tokens from the supplied page are intentionally not stored.
Use approved secret management. For access questions, the page directs users
to the `#ask-cloudops` Slack channel.
