// Research Radar as CSV (same rows and columns as the page), built with the site.
import { LOG_COLUMNS, loadLogEntries } from "../lib/siteData";

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

export function GET() {
  const lines = [LOG_COLUMNS.join(","), ...loadLogEntries(3).map((e) => e.row.map(csvCell).join(","))];
  // Byte-order mark so Excel opens the file as UTF-8.
  return new Response("﻿" + lines.join("\r\n") + "\r\n", {
    headers: { "Content-Type": "text/csv; charset=utf-8" },
  });
}
