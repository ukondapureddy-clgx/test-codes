#!/usr/bin/env node

const fs = require("fs");

const IIS_ACCESS_MAP = {
  date: "iis.access.date",
  time: "iis.access.time",
  "s-ip": "destination.address",
  "cs-method": "http.request.method",
  "cs-uri-stem": "url.path",
  "cs-uri-query": "url.query",
  "s-port": "destination.port",
  "cs-username": "user.name",
  "c-ip": "source.address",
  "cs(User-Agent)": "user_agent.original",
  "cs(Referer)": "http.request.referrer",
  "sc-status": "http.response.status_code",
  "sc-substatus": "iis.access.sub_status",
  "sc-win32-status": "iis.access.win32_status",
  "time-taken": "iis.access.time_taken",
};

const HTTPERR_MAP = {
  date: "iis.error.date",
  time: "iis.error.time",
  "c-ip": "source.address",
  "c-port": "source.port",
  "s-ip": "destination.address",
  "s-port": "destination.port",
  "cs-version": "http.version",
  "cs-method": "http.request.method",
  "cs-uri": "url.path",
  streamid: "iis.error.stream_id",
  "sc-status": "http.response.status_code",
  "s-siteid": "iis.error.site_id",
  "s-reason": "iis.error.reason_phrase",
  "s-queuename": "iis.error.queue_name",
};

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--json") {
      options.json = true;
    } else if (argument === "--config" || argument === "--samples" || argument === "--output") {
      options[argument.slice(2)] = argv[++index];
    } else {
      throw new Error(`Unknown argument: ${argument}`);
    }
  }
  if (!options.samples) {
    throw new Error("--samples is required");
  }
  return options;
}

function sectionKind(software) {
  if (software.includes("Internet Information Services")) return "iis_access";
  if (software.includes("Microsoft HTTP API")) return "iis_http_error";
  return "unknown_header_format";
}

function extractSections(text) {
  const sections = [];
  let current = null;
  text.split(/\r?\n/).forEach((raw, offset) => {
    const line = raw.trim();
    if (line.startsWith("#Software:")) {
      current = {
        software: line.slice(line.indexOf(":") + 1).trim(),
        fields: [],
        rows: [],
      };
      sections.push(current);
    } else if (current && line.startsWith("#Fields:")) {
      current.fields = line.slice(line.indexOf(":") + 1).trim().split(/\s+/);
    } else if (
      current &&
      line &&
      !line.startsWith("#") &&
      /^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+/.test(line)
    ) {
      current.rows.push({ line: offset + 1, tokens: line.split(/\s+/) });
    }
  });
  return sections;
}

function distinctSorted(values) {
  return [...new Set(values)].sort((left, right) => left - right);
}

function adjustedFields(section) {
  const fields = [...section.fields];
  const warnings = [];
  const counts = distinctSorted(section.rows.map((row) => row.tokens.length));

  if (counts.length === 0) {
    return { fields, warnings: ["No data rows found after the header."] };
  }
  if (counts.length > 1) {
    warnings.push(`Rows have inconsistent token counts: ${JSON.stringify(counts)}.`);
  }
  if (counts.length === 1 && counts[0] === fields.length) {
    return { fields, warnings };
  }
  if (
    sectionKind(section.software) === "iis_http_error" &&
    counts.length === 1 &&
    counts[0] === fields.length + 1 &&
    fields.includes("sc-status")
  ) {
    fields.splice(fields.indexOf("sc-status"), 0, "streamid");
    warnings.push(
      "Rows contain one more value than #Fields; inferred streamid immediately before sc-status from all supplied rows.",
    );
    return { fields, warnings };
  }
  warnings.push(
    `#Fields declares ${fields.length} columns, but row counts are ${JSON.stringify(counts)}; no safe automatic adjustment is available.`,
  );
  return { fields, warnings };
}

function sanitize(value) {
  return value.replace(/[^a-zA-Z0-9_]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase();
}

function tokenizerFor(kind, fields) {
  const mapping = kind === "iis_access" ? IIS_ACCESS_MAP : HTTPERR_MAP;
  const unknown = fields.filter((name) => !mapping[name]);
  const tokenizer = fields
    .map((name) => `%{${mapping[name] || `app.${sanitize(name)}`}}`)
    .join(" ");
  return { tokenizer, unknown };
}

function currentDissects(config) {
  const tokenizers = [];
  const pattern = /tokenizer:\s*["']([^"']+)["']/g;
  for (const match of config.matchAll(pattern)) {
    tokenizers.push({
      fields: [...match[1].matchAll(/%\{[^}]*\}/g)].length,
      tokenizer: match[1],
    });
  }
  return tokenizers;
}

function detectOtherFormats(text) {
  const formats = [];
  if (/^Log Name:\s+/m.test(text) && /^Event ID:\s+/m.test(text)) {
    formats.push("windows_application_event");
  }
  if (text.includes("Traceback (most recent call last):")) {
    formats.push("python_exception");
  }
  if (/^\s+at\s+[\w.$]+\(/m.test(text)) {
    formats.push("java_or_dotnet_exception");
  }
  return formats;
}

function analyze(config, samples) {
  const detectedSections = extractSections(samples).map((section) => {
    const kind = sectionKind(section.software);
    const adjusted = adjustedFields(section);
    const generated = tokenizerFor(kind, adjusted.fields);
    return {
      format: kind,
      software: section.software,
      header_field_count: section.fields.length,
      effective_field_count: adjusted.fields.length,
      row_token_counts: distinctSorted(section.rows.map((row) => row.tokens.length)),
      sample_rows: section.rows.length,
      tokenizer: generated.tokenizer,
      unknown_columns: generated.unknown,
      warnings: adjusted.warnings,
    };
  });
  return {
    existing_dissects: currentDissects(config),
    detected_sections: detectedSections,
    other_formats: detectOtherFormats(samples),
  };
}

function markdownReport(result) {
  const lines = [
    "# Filebeat sample analysis",
    "",
    `Existing quoted dissect tokenizers found: ${result.existing_dissects.length}`,
  ];
  result.existing_dissects.forEach((item, index) => {
    lines.push(`- Existing tokenizer ${index + 1}: ${item.fields} fields`);
  });
  result.detected_sections.forEach((section) => {
    lines.push(
      "",
      `## ${section.format}`,
      "",
      `- Software: \`${section.software}\``,
      `- Header fields: ${section.header_field_count}`,
      `- Effective fields: ${section.effective_field_count}`,
      `- Row token counts: ${JSON.stringify(section.row_token_counts)}`,
      `- Sample rows: ${section.sample_rows}`,
      "",
      "Candidate tokenizer:",
      "",
      "```yaml",
      `tokenizer: "${section.tokenizer}"`,
      "```",
    );
    section.warnings.forEach((warning) => lines.push(`- Warning: ${warning}`));
    if (section.unknown_columns.length > 0) {
      lines.push(
        `- Unmapped columns placed under \`app.*\`: ${section.unknown_columns.join(", ")}`,
      );
    }
  });
  if (result.other_formats.length > 0) {
    lines.push("", "## Other detected formats", "");
    result.other_formats.forEach((format) => lines.push(`- ${format}`));
  }
  return `${lines.join("\n")}\n`;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const config = options.config ? fs.readFileSync(options.config, "utf8") : "";
  const samples = fs.readFileSync(options.samples, "utf8");
  const result = analyze(config, samples);
  const output = options.json
    ? `${JSON.stringify(result, null, 2)}\n`
    : markdownReport(result);
  if (options.output) {
    fs.writeFileSync(options.output, output, "utf8");
  } else {
    process.stdout.write(output);
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`filebeat-config-review: ${error.message}\n`);
  process.exitCode = 1;
}
