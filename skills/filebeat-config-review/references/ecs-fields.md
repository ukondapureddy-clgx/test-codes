# ECS field and type guidance

Use these stable types when producing recommendations.

| Field | Type or expectation |
|---|---|
| `@timestamp` | date |
| `message` | text/match_only_text |
| `event.original` | preserved original event |
| `event.duration` | long, nanoseconds |
| `event.dataset` | constant_keyword/keyword |
| `data_stream.type` | constant_keyword; `logs` for this skill's log feeds |
| `data_stream.dataset` | constant_keyword; same value as `event.dataset` |
| `data_stream.namespace` | constant_keyword; environment-appropriate; use `prd` only for PRD |
| `labels.organization` | keyword; `data_portals_us` baseline |
| `labels.environment` | keyword; preserve the configured environment value |
| `labels.space` | keyword; `corebatch` baseline |
| `labels.application` | keyword; `cb-app` baseline |
| `log.level` | keyword |
| `service.name` | keyword |
| `source.address` | keyword |
| `source.ip` | ip |
| `source.port` | long |
| `destination.address` | keyword |
| `destination.ip` | ip |
| `destination.port` | long |
| `http.request.method` | keyword |
| `http.version` | keyword |
| `http.response.status_code` | long |
| `http.response.body.bytes` | long |
| `url.path` | wildcard/keyword |
| `url.query` | keyword |
| `user.name` | keyword |
| `user_agent.original` | keyword/wildcard |
| `error.message` | text/match_only_text |
| `error.stack_trace` | wildcard |
| `trace.id` | keyword |
| `transaction.id` | keyword |

## Conflict checks

Report at least:

- String versus number, boolean, date, or IP.
- Scalar versus object, such as `host: "x"` and `host.name: "x"`.
- Array versus scalar/object.
- Dotted-key expansion collisions.
- Custom values written to ECS container objects such as `host`, `event`,
  `agent`, `cloud`, `log`, `source`, or `destination`.
- Dynamic object keys derived from IDs, URLs, user input, or timestamps.
- `-`, empty string, `N/A`, or units written into numeric fields.
- Mixed timestamp formats.
- JSON/XML decoded directly into root without a controlled schema.
- Scalar values at `data_stream` or `labels` conflicting with the required objects.
- Dataset/namespace values that vary within a stream's constant_keyword mapping
  or disagree with downstream routing and `event.dataset`.

Normalize missing placeholders before conversion. Dissect produces strings, so
all numeric and boolean output requires explicit conversion unless a downstream
ingest pipeline owns that conversion. Cross-check recommendations against the
environment- and region-matched component/index template in
`platform_services_glb-elkmla-iac`; report whether each field is present and its
current mapped type. A sample value that is semantically numeric must not be
left as a string just because dissect returns strings (for example,
`http.response.status_code: 200` should be numeric `long`, not `"200"`). If an
existing mapping has a conflicting type, distinguish a proposed template fix
for future indices from migration of existing indices; Elasticsearch does not
support changing an existing field's type in place.
