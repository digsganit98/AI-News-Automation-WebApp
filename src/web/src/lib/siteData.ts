// Reads everything the website shows, at build time, straight from the repo:
//   data/raw/<date>.json   collected news (written by `digest collect` every 3 hours)
//   config/sources.yaml    source names, groups and logos
//   docs/images/icons/     brand logos (Simple Icons, CC0)
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import type { FeedItem, FeedSource } from "../components/NewsFeed";
import type { Paper } from "../components/PaperTrail";

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

/** The research strategy's log columns (Paper Trail's CSV download). */
export const LOG_COLUMNS = [
  "Date", "Researcher", "Idea / Topic", "Summary", "Tech Domain", "Cloud / Platform",
  "Industry Vertical", "Source Type", "Link",
] as const;

/** Stories from the newest `days` story files, newest first. */
export function loadRecentStories(days = 7): Story[] {
  const files = readDatedFiles<{ date: string; stories: Story[] }>("stories").slice(0, days);
  return files.flatMap((f) => [...f.stories].reverse());
}

// ------------------------------------------------------------------ Paper Trail
// Every paper spotted in the collected data, wherever it turned up: Hugging Face Daily
// Papers, arXiv, a Hacker News link, a web-search result or an agent story. Mentions of the
// same paper are merged by arXiv ID. Themes come from simple keyword rules (no LLM calls).

/** How many days of papers Paper Trail keeps. */
export const PAPER_DAYS = 14;

const DIRECTED_GROUPS = new Set(["labs", "research", "cloud"]);

export function sourceTypeOfGroup(group: string): string {
  if (DIRECTED_GROUPS.has(group)) return "Directed";
  return group === "webSearch" ? "AI-assisted" : "Emergent";
}

/** Research themes, checked in this order; a paper gets up to three. */
const THEME_RULES: [RegExp, string][] = [
  [/\b(agents?|agentic|multi-agent|tool[- ]use|computer[- ]use|gui|web navigation)\b/i, "Agents"],
  [/\b(reasoning|chain[- ]of[- ]thought|math\w*|theorem|planning|thinking)\b/i, "Reasoning"],
  [/\b(code|coding|programs?|programming|software engineering|swe-bench|compiler)\b/i, "Code"],
  [/\b(robot\w*|embodied|manipulation|vla|locomotion)\b/i, "Robotics & Embodied"],
  [/\b(video|world models?|3d|4d|scenes?|physical)\b/i, "Video & World Models"],
  [/\b(vision|visual|images?|multimodal|vlms?|vision-language|ocr|diffusion|pixels?)\b/i, "Multimodal & Vision"],
  [/\b(audio|speech|voice|asr|tts|music|sounds?)\b/i, "Audio & Speech"],
  [/\b(reinforcement learning|rlhf|rlvr|grpo|dpo|reward|pre-?training|post-?training|fine-tun\w*|scaling laws?)\b/i, "Training & RL"],
  [/\b(efficien\w*|quantiz\w*|distill\w*|pruning|sparse|sparsity|mixture[- ]of[- ]experts|moe|kv[- ]cache|long[- ]context|compression|speculative)\b/i, "Efficiency"],
  [/\b(safety|alignment|jailbreak\w*|red[- ]team\w*|hallucinat\w*|interpretab\w*|privacy|unlearning)\b/i, "Safety & Alignment"],
  [/\b(retrieval|rag|memory|knowledge graphs?|search engines?)\b/i, "Retrieval & Memory"],
  [/\b(medical|clinical|health\w*|biolog\w*|proteins?|chemi\w*|molecul\w*|scientific|materials|weather)\b/i, "Science & Health"],
  [/\b(benchmarks?|evaluat\w*|leaderboards?|datasets?)\b/i, "Benchmarks & Evals"],
];

const PLATFORM_RULES: [RegExp, string][] = [
  [/\b(aws|amazon|bedrock|sagemaker|agentcore)\b/i, "AWS"],
  [/\b(azure|microsoft|copilot|foundry)\b/i, "Azure"],
  [/\b(google|gemini|vertex|deepmind|gcp)\b/i, "GCP"],
  [/\b(openai|gpt-?\d|chatgpt)\b/i, "OpenAI"],
  [/\b(anthropic|claude)\b/i, "Anthropic"],
  [/\b(nvidia)\b/i, "NVIDIA"],
  [/\b(meta|llama)\b/i, "Meta"],
  [/\b(mistral)\b/i, "Mistral"],
  [/\b(qwen|alibaba)\b/i, "Alibaba"],
  [/\b(deepseek)\b/i, "DeepSeek"],
];

const VERTICAL_RULES: [RegExp, string][] = [
  [/\b(health\w*|medical|clinic\w*|radiolog\w*|drug|biolog\w*|patients?|enzyme)\b/i, "Healthcare"],
  [/\b(bank\w*|financ\w*|fraud|insur\w*|trading|payments?)\b/i, "BFSI"],
  [/\b(retail|e-?commerce|shopping)\b/i, "Retail"],
  [/\b(manufactur\w*|factory|industrial|robot\w*|supply chain)\b/i, "Manufacturing"],
  [/\b(educat\w*|students?|schools?|learning platform)\b/i, "Education"],
  [/\b(legal|law firm|lawyers?)\b/i, "Legal"],
  [/\b(game|gaming|media|video generation|music)\b/i, "Media & Entertainment"],
];

function firstMatch(rules: [RegExp, string][], text: string): string | undefined {
  return rules.find(([pattern]) => pattern.test(text))?.[1];
}

/** Up to three themes; words in the title count before words in the abstract. */
function themesOf(title: string, abstract: string): string[] {
  const hits = (text: string) => THEME_RULES.filter(([p]) => p.test(text)).map(([, t]) => t);
  const themes = [...new Set([...hits(title), ...hits(abstract)])].slice(0, 3);
  return themes.length ? themes : ["Language Models"];
}

const ARXIV_ID = /arxiv\.org\/(?:abs|pdf|html)\/(\d{4}\.\d{4,5})/i;
const PAPER_SOURCES = new Set(["hf-papers", "arxiv"]);

function fromTemplate(name: string, id: string): string | undefined {
  const t = process.env[name];
  return t ? t.replace("{id}", id) : undefined;
}

/** The paper an item is about: its arXiv ID, or its own URL for other paper pages. */
function paperKey(item: NewsItem): string | undefined {
  const arxivUrl = typeof item.extra?.arxivUrl === "string" ? item.extra.arxivUrl : "";
  const id = arxivUrl.match(ARXIV_ID)?.[1] ?? item.url.match(ARXIV_ID)?.[1];
  if (id) return id;
  const hfPrefix = (process.env.HF_PAPER_URL ?? "").split("{id}")[0];
  if (hfPrefix && item.url.startsWith(hfPrefix)) return item.url.slice(hfPrefix.length).split(/[?#/]/)[0];
  if (/openreview\.net\/(forum|pdf)\?id=/i.test(item.url) || PAPER_SOURCES.has(item.source)) return item.url;
  return undefined;
}

/** News, not papers: Latest and the Archive show news; papers have their own page. */
export function isNews(item: NewsItem): boolean {
  return paperKey(item) === undefined;
}

function cleanAbstract(text: string): string {
  // arXiv's feed starts every summary with "arXiv:2609.12345v1 Announce Type: new Abstract:".
  return text.replace(/^arXiv:\S+\s+Announce Type:\s*\S+\s*Abstract:\s*/i, "").trim();
}

export function loadPapers(days = PAPER_DAYS): Paper[] {
  const sources = loadSources();
  const groupOf = Object.fromEntries(sources.map((s) => [s.id, s.group]));
  const papers = new Map<string, Paper>();
  const groupsOf = new Map<string, Set<string>>();

  for (const day of loadDays().slice(0, days)) {
    for (const item of day.items) {
      const key = paperKey(item);
      if (!key) continue;
      const e = item.extra ?? {};
      const time = item.publishedAt ?? item.collectedAt ?? `${day.date}T00:00:00Z`;
      const isPaperSource = PAPER_SOURCES.has(item.source);
      const arxivId = /^\d{4}\.\d{4,5}$/.test(key) ? key : undefined;
      let p = papers.get(key);
      if (!p) {
        p = {
          id: key, arxivId, title: "", authors: [], abstract: "", time, upvotes: 0, points: 0,
          themes: [], spottedOn: [], links: {}, buzz: 0,
        };
        papers.set(key, p);
        groupsOf.set(key, new Set());
      }
      // The paper's own sources give the best title, authors and abstract.
      const title = item.title.replace(/\s*\[pdf\]$/i, "");
      if (!p.title || isPaperSource) p.title = title;
      if (item.author && (!p.authors.length || isPaperSource)) {
        p.authors = item.author.split(/,\s*|\s+and\s+/).map((a) => a.trim()).filter(Boolean);
      }
      const abstract = cleanAbstract(item.excerpt);
      if (abstract.length > p.abstract.length) p.abstract = abstract;
      if (time < p.time) p.time = time;
      p.upvotes = Math.max(p.upvotes, Number(e.upvotes ?? 0));
      p.points = Math.max(p.points, Number(e.points ?? 0) + Number(e.comments ?? 0));
      if (!p.spottedOn.some((s) => s.source === item.source)) {
        p.spottedOn.push({ source: item.source, name: item.sourceName, url: item.url });
      }
      groupsOf.get(key)!.add(groupOf[item.source] ?? "");
      if (typeof e.githubRepo === "string" && e.githubRepo) p.links.code = e.githubRepo;
      if (typeof e.projectPage === "string" && e.projectPage) p.links.project = e.projectPage;
      if (item.source === "hf-papers") p.links.discussion = item.url;
      else if (typeof e.discussionUrl === "string" && e.discussionUrl) p.links.discussion ??= e.discussionUrl;
    }
  }

  // The AI agents' plain-English take, when a story is about one of these papers.
  for (const story of loadRecentStories(days)) {
    const urls = [story.goDeeper?.paper, ...story.sources.map((s) => s.url)].filter(Boolean) as string[];
    for (const url of urls) {
      const key = url.match(ARXIV_ID)?.[1] ?? url;
      const p = papers.get(key);
      if (p && !p.agentNote) {
        p.agentNote = { headline: story.headline, whyItMatters: story.whyItMatters };
        if (story.goDeeper?.code) p.links.code ??= story.goDeeper.code;
      }
    }
  }

  for (const p of papers.values()) {
    if (p.arxivId) {
      p.links.abs = fromTemplate("ARXIV_ABS_URL", p.arxivId);
      p.links.pdf = fromTemplate("ARXIV_PDF_URL", p.arxivId);
    } else {
      p.links.abs = p.spottedOn[0]?.url;
    }
    p.themes = themesOf(p.title, p.abstract);
    const groups = [...groupsOf.get(p.id)!];
    p.sourceType = groups.some((g) => DIRECTED_GROUPS.has(g)) ? "Directed" : sourceTypeOfGroup(groups[0] ?? "");
    // Buzz: community upvotes, discussion, and how many places the paper turned up.
    p.buzz = p.upvotes + p.points / 2 + 15 * (p.spottedOn.length - 1) + (p.agentNote ? 20 : 0);
  }
  return [...papers.values()].filter((p) => p.title).sort((a, b) => b.time.localeCompare(a.time));
}

/** One research-log row per paper, in the strategy's exact columns. */
export function paperLogRow(p: Paper): string[] {
  const researcher = p.authors.length
    ? `${p.authors[0]}${p.authors.length > 1 ? " et al." : ""}`
    : process.env.DEFAULT_RESEARCHER ?? "";
  const text = `${p.title} ${p.abstract}`;
  const summary = p.abstract.length > 240 ? `${p.abstract.slice(0, 239)}…` : p.abstract;
  return [
    logDate(p.time), researcher, p.title, summary, p.themes.join(" · "),
    firstMatch(PLATFORM_RULES, text) ?? "Open-source", firstMatch(VERTICAL_RULES, text) ?? "Cross-industry",
    p.sourceType ?? "Directed", p.links.abs ?? "",
  ];
}
