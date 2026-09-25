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
/** How many days the Archive (calendar icon in the header) keeps. */
export const ARCHIVE_DAYS = 5;

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
  cloud: "Cloud & platforms",
  community: "Community",
  video: "Video",
  newsletters: "Newsletters & blogs",
  x: "X",
  webSearch: "Web search",
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
  if (slug === "search") {
    return `${open}<circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="#0071e3" stroke-width="2.6"/><path d="M15.5 15.5 21 21" stroke="#0071e3" stroke-width="2.8" stroke-linecap="round"/></svg>`;
  }
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

// ------------------------------------------------------------------ AI agent output

export interface StorySource { name: string; url: string }
export interface GoDeeper { paper?: string | null; code?: string | null; model?: string | null; demo?: string | null }

export interface Story {
  id: string;
  headline: string;
  summary: string;
  whyItMatters: string;
  category: string;
  importance: number;
  status: "new" | "followUp" | "alreadyCovered";
  followUpOf: string | null;
  cloudPlatform: string;
  industryVertical: string;
  researcher: string;
  sourceType: "Directed" | "Emergent" | "AI-assisted";
  sources: StorySource[];
  goDeeper: GoDeeper;
  createdAt: string;
}

export interface DigestFile {
  date: string;
  createdAt: string;
  digest: { headline: string; dek: string; tldr: string[]; intro: string; topStoryIds: string[] };
  opEd: { title: string; dek: string; paragraphs: string[]; basedOnStoryIds: string[] };
  sections: Record<string, string[]>;
  stories: Record<string, Story>;
  editor: { approved: boolean; issuesFound: number; revised: boolean };
  models: Record<string, number>;
}

function readDatedFiles<T>(folder: string): T[] {
  const dir = path.join(repoRoot, "data", folder);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .sort()
    .reverse()
    .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) as T);
}

/** Analyst stories from the newest `days` story files, most important first. */
export function loadTopStories(days = 2): Story[] {
  const files = readDatedFiles<{ date: string; stories: Story[] }>("stories").slice(0, days);
  return files
    .flatMap((f) => f.stories)
    .sort((a, b) => b.importance - a.importance || b.createdAt.localeCompare(a.createdAt));
}

export function loadDigests(): DigestFile[] {
  return readDatedFiles<DigestFile>("digests");
}

export const IMPORTANCE_LABEL: Record<number, string> = {
  5: "Major", 4: "Significant", 3: "Worth knowing", 2: "Niche", 1: "Minor",
};

/** Colour per tech domain (the story's category). */
export const CATEGORY_STYLE: Record<string, string> = {
  "New Model Release": "text-[#0071e3] dark:text-[#2997ff]",
  "Framework/Tooling": "text-[#1d8f4e] dark:text-[#30d158]",
  "Agentic Systems": "text-[#6d28d9] dark:text-[#bf5af2]",
  "Methodology": "text-[#0e7490] dark:text-[#64d2ff]",
  "Industry Use Case": "text-[#c2410c] dark:text-[#ff9f0a]",
  "Infrastructure/MLOps": "text-[#475569] dark:text-[#a1a1a6]",
  "Research": "text-[#8e44ad] dark:text-[#bf5af2]",
  "AGI": "text-[#be185d] dark:text-[#ff375f]",
  "Policy & Safety": "text-[#b42318] dark:text-[#ff453a]",
  "Business & Funding": "text-[#a16207] dark:text-[#ffd60a]",
};

/** Date as DD-MM-YY in the digest's timezone (the research log format). */
export function logDate(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone, day: "2-digit", month: "2-digit", year: "2-digit",
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("day")}-${get("month")}-${get("year")}`;
}

export const LOG_COLUMNS = [
  "Date", "Researcher", "Idea / Topic", "Summary", "Tech Domain", "Cloud / Platform",
  "Industry Vertical", "Source Type", "Link",
] as const;

/** One research-log row per story: the exact columns of the research strategy. */
export function logRow(s: Story): string[] {
  return [
    logDate(s.createdAt), s.researcher || "", s.headline, s.summary, s.category,
    s.cloudPlatform ?? "", s.industryVertical ?? "", s.sourceType ?? "", s.sources[0]?.url ?? "",
  ];
}

/** Stories from the newest `days` story files, newest first. */
export function loadLogStories(days = 7): Story[] {
  const files = readDatedFiles<{ date: string; stories: Story[] }>("stories").slice(0, days);
  return files.flatMap((f) => [...f.stories].reverse());
}
