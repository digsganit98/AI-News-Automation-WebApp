// Reads everything the website shows, at build time, straight from the repo:
//   data/raw/<date>.json   collected news (written by `digest collect` every 3 hours)
//   config/sources.yaml    source names, groups and logos
//   docs/images/icons/     brand logos (Simple Icons, CC0)
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import type { FeedItem, FeedSource } from "../components/NewsFeed";

export const repoRoot = path.resolve(process.env.DIGEST_ROOT ?? path.join(process.cwd(), "..", ".."));
export const timeZone = process.env.DIGEST_TIMEZONE ?? "Asia/Kolkata";
export const projectUrl = process.env.PROJECT_URL ?? "";

export interface NewsItem {
  id: string;
  source: string;
  sourceName: string;
  title: string;
  url: string;
  publishedAt: string | null;
  collectedAt?: string;
  excerpt: string;
  author: string | null;
  extra: Record<string, unknown>;
}

export interface SourceHealth {
  source: string;
  sourceName: string;
  ok: boolean;
  items: number;
  error: string | null;
  checkedAt: string;
}

export interface CollectionRun {
  runAt: string;
  newItems: number;
  health: SourceHealth[];
}

export interface DayFile {
  date: string;
  updatedAt: string;
  runs: CollectionRun[];
  items: NewsItem[];
}

export interface SourceInfo {
  id: string;
  name: string;
  type: string;
  group: string;
  icon: string;
  enabled: boolean;
}

export const GROUPS: Record<string, string> = {
  labs: "AI labs",
  research: "Research & open models",
  community: "Community",
  video: "Video",
  newsletters: "Newsletters",
  x: "X",
};

export function loadSources(): SourceInfo[] {
  const raw = YAML.parse(fs.readFileSync(path.join(repoRoot, "config", "sources.yaml"), "utf8"));
  return (raw.sources as Record<string, unknown>[]).map((s) => ({
    id: String(s.id),
    name: String(s.name),
    type: String(s.type),
    group: String(s.group ?? "community"),
    icon: String(s.icon ?? ""),
    enabled: s.enabled !== false,
  }));
}

export function loadDays(): DayFile[] {
  const dir = path.join(repoRoot, "data", "raw");
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .sort()
    .reverse()
    .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) as DayFile);
}

export function itemTime(item: NewsItem): string {
  return item.publishedAt ?? item.collectedAt ?? "";
}

export function sortNewestFirst(items: NewsItem[]): NewsItem[] {
  return [...items].sort((a, b) => itemTime(b).localeCompare(itemTime(a)));
}

/** A number for "most discussed" sorting: HN points, paper upvotes, model likes... */
export function signal(item: NewsItem): number {
  const e = item.extra ?? {};
  return Number(e.points ?? 0) + Number(e.comments ?? 0) + Number(e.upvotes ?? 0) * 5 + Number(e.likes ?? 0) / 10;
}

export function formatDay(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
}

export function todayInDigestZone(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

/** Join the site's base path (e.g. /AI-News-Automation-WebApp) with a page path. */
export function href(page: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}/${page.replace(/^\//, "")}`;
}

// ------------------------------------------------------------------ logos

const colours: Record<string, string> = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "docs", "images", "icons", "colours.json"), "utf8"),
);

function isVeryDark(hex: string): boolean {
  const n = parseInt(hex, 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 60;
}

/** Inline SVG markup for a brand logo. Near-black logos follow the text colour (dark mode). */
export function iconSvg(slug: string, size = 20): string {
  const open = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">`;
  if (slug === "microsoft") {
    return `${open}<rect x="1" y="1" width="10.5" height="10.5" fill="#F25022"/><rect x="12.5" y="1" width="10.5" height="10.5" fill="#7FBA00"/><rect x="1" y="12.5" width="10.5" height="10.5" fill="#00A4EF"/><rect x="12.5" y="12.5" width="10.5" height="10.5" fill="#FFB900"/></svg>`;
  }
  const file = path.join(repoRoot, "docs", "images", "icons", `${slug}.svg`);
  if (!slug || !fs.existsSync(file)) {
    return `${open}<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
  }
  const d = fs.readFileSync(file, "utf8").match(/<path d="([^"]+)"/)?.[1] ?? "";
  const hex = colours[slug] ?? "000000";
  const fill = isVeryDark(hex) ? "currentColor" : `#${hex}`;
  return `${open}<path fill="${fill}" d="${d}"/></svg>`;
}

export function iconMap(sources: SourceInfo[]): Record<string, string> {
  return Object.fromEntries(sources.map((s) => [s.id, iconSvg(s.icon)]));
}

// ------------------------------------------------------------------ feed props


export function toFeedItem(item: NewsItem): FeedItem {
  const e = item.extra ?? {};
  const num = (v: unknown) => (typeof v === "number" && v > 0 ? v : undefined);
  const str = (v: unknown) => (typeof v === "string" && v ? v : undefined);
  const excerpt = item.excerpt.length > 280 ? `${item.excerpt.slice(0, 279)}…` : item.excerpt;
  return {
    id: item.id,
    source: item.source,
    sourceName: item.sourceName,
    title: item.title,
    url: item.url,
    time: itemTime(item),
    collectedAt: item.collectedAt,
    excerpt,
    points: num(e.points),
    comments: num(e.comments),
    upvotes: num(e.upvotes),
    likes: num(e.likes),
    discussionUrl: str(e.discussionUrl),
    githubRepo: str(e.githubRepo),
    arxivUrl: str(e.arxivUrl),
  };
}

export function toFeedSources(sources: SourceInfo[]): FeedSource[] {
  return sources.map(({ id, name, group }) => ({ id, name, group }));
}
