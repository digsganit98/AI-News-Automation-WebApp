// Paper Trail as a research log (CSV), in the research strategy's columns, built with the site.
import { LOG_COLUMNS, PAPER_DAYS, loadPapers, paperLogRow } from "../lib/siteData";

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

export function GET() {
  const lines = [LOG_COLUMNS.join(","), ...loadPapers(PAPER_DAYS).map((p) => paperLogRow(p).map(csvCell).join(","))];
  // Byte-order mark so Excel opens the file as UTF-8.
  return new Response("﻿" + lines.join("\r\n") + "\r\n", {
    headers: { "Content-Type": "text/csv; charset=utf-8" },
  });
}
