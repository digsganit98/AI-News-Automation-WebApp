// The research log as CSV (same columns as the Research log page), built with the site.
import { LOG_COLUMNS, loadLogStories, logRow } from "../lib/siteData";

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

export function GET() {
  const lines = [LOG_COLUMNS.join(","), ...loadLogStories(7).map((s) => logRow(s).map(csvCell).join(","))];
  // Byte-order mark so Excel opens the file as UTF-8.
  return new Response("﻿" + lines.join("\r\n") + "\r\n", {
    headers: { "Content-Type": "text/csv; charset=utf-8" },
  });
}
