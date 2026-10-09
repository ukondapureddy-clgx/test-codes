# Known log formats and parser selection

Use these references and relevant local fixtures to recognize possible formats.
Confirm every classification from the uploaded test logs. Record source file,
line range, header/format declaration, and confidence. Filenames, service names,
and old examples alone cannot establish a tokenizer. Analyze multiple layouts
independently and explicitly report unknown records.

## Category-first classification

For each sample, report both its broad category and its concrete format/producer
when evidence supports one. Categories include:

- Application: application events, errors, warnings, debug output, and exceptions.
- Operating system: service, kernel, startup/shutdown, resource, and system logs.
- Web server: HTTP access and server error logs, including IIS, Nginx, and Apache.
- Security/audit: authentication, authorization, policy, and audit events.
- Network: firewall, proxy, DNS, VPN, and network-device events.
- Database: database server, connection, query/slow-query, error, and audit logs.
- Cloud/container: cloud control-plane/service logs, Kubernetes events, and
  container stdout/stderr.

These categories can overlap: for example, a JSON application event may be
collected from a container and include an audit event. Keep category, format,
producer, and collection source distinct rather than forcing one exclusive label.
Use event content and authoritative headers/configuration as evidence. Generic
JSON, syslog envelopes, timestamps, or filenames alone do not identify a vendor
or product. When evidence is insufficient, state the supported category, mark
the format/producer as unknown or ambiguous, and request a representative sample,
format declaration, or source configuration before claiming parser coverage.

## IIS W3C access logs

Evidence:

- `#Software: Microsoft Internet Information Services`
- A `#Fields:` header containing `cs-method`, `cs-uri-stem`, `sc-status`.

Preferred parser: Filebeat `iis` module, `access` fileset. The header controls
the layout; do not assume one universal tokenizer.

Common source-to-ECS mappings:

| IIS column | Field | Type |
|---|---|---|
| `date` + `time` | `@timestamp` | date |
| `s-ip` | `destination.address` | keyword |
| `s-port` | `destination.port` | long |
| `c-ip` | `source.address` | keyword |
| `cs-method` | `http.request.method` | keyword |
| `cs-uri-stem` | `url.path` | wildcard |
| `cs-uri-query` | `url.query` | keyword |
| `cs-username` | `user.name` | keyword |
| `cs(User-Agent)` | `user_agent.original` | keyword |
| `cs(Referer)` | `http.request.referrer` | keyword |
| `sc-status` | `http.response.status_code` | long |
| `sc-substatus` | `iis.access.sub_status` | long |
| `sc-win32-status` | `iis.access.win32_status` | long |
| `time-taken` | `iis.access.time_taken` | long |

## Microsoft HTTP API / IIS HTTPERR logs

Evidence:

- `#Software: Microsoft HTTP API`
- Columns such as `c-port`, `s-reason`, and `s-queuename`.

Preferred parser: Filebeat `iis` module, `error` fileset.

Common mappings:

| HTTPERR column | Field | Type |
|---|---|---|
| `c-ip` | `source.address` | keyword |
| `c-port` | `source.port` | long |
| `s-ip` | `destination.address` | keyword |
| `s-port` | `destination.port` | long |
| `cs-version` | `http.version` | keyword |
| `cs-method` | `http.request.method` | keyword |
| `cs-uri` | `url.path` | wildcard |
| `sc-status` | `http.response.status_code` | long |
| `s-siteid` | `iis.error.site_id` | long |
| `s-reason` | `iis.error.reason_phrase` | keyword |
| `s-queuename` | `iis.error.queue_name` | keyword |

Some HTTPERR variants include `streamid` even when copied headers are
incomplete. Infer it only when all samples consistently contain the additional
column immediately before `sc-status`.

## Nginx

Evidence:

- Combined access shape: client address, timestamp in brackets, quoted request,
  status, and bytes.
- Error shape: timestamp, severity in brackets, process/thread identifiers.

Preferred parser: Filebeat `nginx` module. Also supply a Filebeat dissect
alternative for stable access layouts when the supplied samples establish the
delimiters and column order. For a custom layout, use its `log_format` declaration
when available; request it if sample columns are ambiguous. Common/combined
access text alone cannot distinguish Nginx from Apache: report that ambiguity
unless the configuration or format declaration establishes the producer.
Separate access from error logs; variable error messages may require downstream
grok instead. Account for quoted requests/referrers, missing bytes, IPv6, and
optional fields before declaring coverage.

## Apache HTTP Server

Evidence:

- Common/combined access format with bracketed timestamp and quoted request.
- Error log with bracketed timestamp/module/severity.

Preferred parser: Filebeat `apache` module.

## Syslog

For standard system-log generation without samples, use the established source:

- Linux text syslog/auth logs: prefer Filebeat's `system` module with separate
  `syslog` and `auth` filesets. Use confirmed paths or documented module defaults
  where applicable; custom paths are user settings. Do not assume distributions
  with journal-only logging have these files.
- Journal-only Linux: select version-supported journald collection; confirm
  journal access and parsing ownership instead of treating binary journals as
  text files.
- Native Windows System/Application/Security channels: recommend Winlogbeat
  (or Elastic Agent), not Filebeat text parsing. Security collection also needs
  appropriate permissions.
- If OS/source is unknown, ask a single focused OS/source question. Supplied
  labels identify routing, not the operating system or log format.

No test logs are required to propose these standard collectors. Report parser
coverage as not executed, require version/paths/permissions and module ingest
dispatch review, and never manufacture a custom Dissect without samples.

- RFC 3164 commonly starts with `Mon dd HH:mm:ss host`.
- RFC 5424 starts with `<priority>version` and an RFC3339 timestamp.
- Syslog is a transport/envelope format, not proof that the producer is a Linux
  host, firewall, database, or specific vendor. Use hostname, app/procid,
  structured data, message content, and source configuration to narrow it down.

Preferred parser: a supported `system` module/fileset for Linux system/auth
files, or the version-supported `syslog` processor with a suitable input. The
legacy `syslog` input is deprecated in newer Filebeat versions; verify support
before suggesting it. Do not use one dissect tokenizer for both RFC variants.
Offer dissect only for a stable, sample-proven application payload or layout;
RFC 5424 structured data and RFC 3164 spacing/year/timezone ambiguity require
special care. Do not classify native Windows events as Linux system logs.

## JSON application logs

Evidence: each event is a valid JSON object.

Prefer JSON input/decoding into `app`, not the document root:

```yaml
- decode_json_fields:
    fields: ["message"]
    target: app
    overwrite_keys: false
    add_error_key: true
```

Promote selected fields to ECS after verifying their types. Do not enable
arbitrary dotted-key expansion without collision analysis.

## Database logs

Database logs are identified from producer/configuration evidence or recognizable
engine-specific messages and fields, not from the word "database" in a filename.
Examples include PostgreSQL, MySQL/MariaDB, MongoDB, and Microsoft SQL Server.
Separate server/error logs from query, slow-query, connection, and audit events
when their layouts or collection paths differ. Prefer a supported Filebeat module
or Elastic integration for the identified engine and version; otherwise validate
the actual format and use JSON decoding, dissect, or downstream grok as appropriate.
Do not assume that a database module collects every event type enabled by the
database, or that a generic syslog line is a database log.

## Security, network, cloud, and container logs

- Security/audit samples may come from Linux authentication/audit sources,
  Windows Security Event Log, cloud audit services, or application audit events.
  Prefer native event collection/integrations when available; a rendered Windows
  event export is not equivalent to native event collection.
- Network samples may be firewall, proxy, DNS, VPN, or device logs. Many arrive
  inside syslog, but the syslog envelope alone cannot establish device type or
  vendor. Identify the product and version from reliable source evidence before
  selecting a vendor parser.
- Cloud logs may be exported service/control-plane or audit events. Cloud provider
  identity and schema must be supported by the payload or source configuration;
  do not infer them from generic JSON.
- Container stdout/stderr is a collection source, not necessarily a log format.
  Preserve container/orchestrator metadata and separately identify the payload
  format (for example JSON application logs, syslog, or multiline exception).
  Kubernetes events are distinct from application logs emitted by pods.

## Windows Event Log

Evidence includes `Log Name:`, `Source:`, `Event ID:`, `Computer:`, and
`Description:` or native Windows Event Log records.

Preferred collection: Winlogbeat or Elastic Agent Windows integration. Avoid
parsing human-rendered multiline exports when native event collection is
available.
For uploaded exports only, distinguish format identification from successful
native collection. Do not claim that switching to Winlogbeat parses an existing
text export. Preserve the export and explain any sample-specific parsing limits.

## CoreBatch / XLSBuilder and other application text

The baseline paths/service labels identify an application, not its log layout.
Inspect actual timestamps (including comma milliseconds or AM/PM), delimiters,
severity, logger/thread fields, and exception continuations before constructing
dissect processors. Aggregate each event first. If two layouts occur, use
separate inputs or mutually exclusive conditions and a tokenizer for each.
Do not invent columns or reuse an IIS tokenizer for application text.

## Multiline exceptions

- Java: `Exception`, `Caused by:`, and `at package.Class(...)`.
- Python: `Traceback (most recent call last):`.
- .NET: exception type/message followed by indented `at Namespace...`.

Aggregate multiline records before parsing. Bound aggregation with a timeout
and maximum line count where supported.
