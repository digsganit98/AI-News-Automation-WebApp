// Paper Trail (runs in the browser): every paper we spotted, with a paper of the day, a
// "research pulse" of themes that doubles as a filter, search, a reading list kept in this
// browser, and one-click BibTeX citations. The page passes in the papers at build time.
import { useEffect, useMemo, useState } from "preact/hooks";

export interface PaperSighting {
  source: string;
  name: string;
  url: string;
}

export interface Paper {
  id: string; // arXiv ID, or the page URL for papers without one
  arxivId?: string;
  title: string;
  authors: string[];
  abstract: string;
  time: string;
  upvotes: number;
  points: number;
  themes: string[];
  spottedOn: PaperSighting[];
  links: { abs?: string; pdf?: string; code?: string; project?: string; discussion?: string };
  agentNote?: { headline: string; whyItMatters: string };
  sourceType?: string;
  buzz: number;
}

interface Props {
  papers: Paper[];
  icons: Record<string, string>;
  buildTime: string;
}

const DAY = 86_400_000;
const SAVED_KEY = "paperTrail.saved";

/** Apple system colours per theme (light / dark), as static classes Tailwind can see. */
const TONE: Record<string, { text: string; bg: string }> = {
  "Agents": { text: "text-[#8944ab] dark:text-[#bf5af2]", bg: "bg-[#8944ab] dark:bg-[#bf5af2]" },
  "Reasoning": { text: "text-[#3634a3] dark:text-[#7d7aff]", bg: "bg-[#5856d6] dark:bg-[#5e5ce6]" },
  "Code": { text: "text-[#248a3d] dark:text-[#30d158]", bg: "bg-[#34c759] dark:bg-[#30d158]" },
  "Robotics & Embodied": { text: "text-[#c93400] dark:text-[#ff9f0a]", bg: "bg-[#ff9500] dark:bg-[#ff9f0a]" },
  "Video & World Models": { text: "text-[#0071a4] dark:text-[#64d2ff]", bg: "bg-[#32ade6] dark:bg-[#64d2ff]" },
  "Multimodal & Vision": { text: "text-[#d30f45] dark:text-[#ff375f]", bg: "bg-[#ff2d55] dark:bg-[#ff375f]" },
  "Audio & Speech": { text: "text-[#b25000] dark:text-[#ffd60a]", bg: "bg-[#ffcc00] dark:bg-[#ffd60a]" },
  "Training & RL": { text: "text-[#0040dd] dark:text-[#409cff]", bg: "bg-[#007aff] dark:bg-[#0a84ff]" },
  "Efficiency": { text: "text-[#0c817b] dark:text-[#66d4cf]", bg: "bg-[#00c7be] dark:bg-[#66d4cf]" },
  "Safety & Alignment": { text: "text-[#d70015] dark:text-[#ff6961]", bg: "bg-[#ff3b30] dark:bg-[#ff453a]" },
  "Retrieval & Memory": { text: "text-[#7f6545] dark:text-[#b59469]", bg: "bg-[#a2845e] dark:bg-[#ac8e68]" },
  "Science & Health": { text: "text-[#008299] dark:text-[#5de6ff]", bg: "bg-[#30b0c7] dark:bg-[#40c8e0]" },
  "Benchmarks & Evals": { text: "text-[#6c6c70] dark:text-[#aeaeb2]", bg: "bg-[#8e8e93] dark:bg-[#98989d]" },
  "Language Models": { text: "text-[#0058b0] dark:text-[#6fb0ff]", bg: "bg-[#0071e3] dark:bg-[#2997ff]" },
};
const tone = (theme: string) => TONE[theme] ?? TONE["Language Models"];

type Range = "today" | "week" | "all";
type Sort = "trending" | "newest";

function dayLabel(iso: string, now: number): string {
  const d = new Date(iso);
  const startOf = (t: number) => new Date(new Date(t).toDateString()).getTime();
  const days = Math.round((startOf(now) - startOf(d.getTime())) / DAY);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return d.toLocaleDateString(undefined, { weekday: "long" });
  return d.toLocaleDateString(undefined, { day: "numeric", month: "long" });
}

function authorLine(authors: string[], max = 3): string {
  if (authors.length <= max) return authors.join(", ");
  return `${authors.slice(0, max).join(", ")} +${authors.length - max}`;
}

function bibtex(p: Paper): string {
  const year = p.time.slice(0, 4);
  const surname = (p.authors[0] ?? "").split(/\s+/).pop()?.toLowerCase().replace(/[^a-z]/g, "") || "anon";
  const word = p.title.toLowerCase().match(/[a-z]{4,}/)?.[0] ?? "paper";
  const safe = (s: string) => s.replace(/[{}]/g, "");
  const lines = [`@misc{${surname}${year}${word},`, `  title = {${safe(p.title)}},`];
  if (p.authors.length) lines.push(`  author = {${p.authors.map(safe).join(" and ")}},`);
  lines.push(`  year = {${year}},`);
  if (p.arxivId) lines.push(`  eprint = {${p.arxivId}},`, "  archivePrefix = {arXiv},");
  lines.push(`  url = {${p.links.abs ?? p.spottedOn[0]?.url ?? ""}}`, "}");
  return lines.join("\n");
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function readSaved(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]"));
  } catch {
    return new Set();
  }
}

// ------------------------------------------------------------------ small icons (SF Symbols-like)

const BookmarkIcon = ({ filled }: { filled: boolean }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill={filled ? "currentColor" : "none"} stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 3.5h11a1 1 0 0 1 1 1v16l-6.5-4.2-6.5 4.2v-16a1 1 0 0 1 1-1z" /></svg>
);
const QuoteIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M9.6 6C6.5 7.4 4.5 10 4.5 13.4c0 2.5 1.5 4.1 3.4 4.1 1.7 0 2.9-1.2 2.9-2.8s-1.1-2.7-2.6-2.7c-.3 0-.6 0-.8.1.4-1.6 1.7-3 3.4-3.9zm8.5 0c-3.1 1.4-5.1 4-5.1 7.4 0 2.5 1.5 4.1 3.4 4.1 1.7 0 2.9-1.2 2.9-2.8s-1.1-2.7-2.6-2.7c-.3 0-.6 0-.8.1.4-1.6 1.7-3 3.4-3.9z" /></svg>
);
const SparkIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z" /></svg>
);
const ArrowIcon = () => (
  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8" /></svg>
);

// ------------------------------------------------------------------ pieces

function Upvotes({ n }: { n: number }) {
  if (!n) return null;
  return (
    <span class="inline-flex items-center gap-1 rounded-full bg-[#ff9500]/12 px-2 py-0.5 text-[11px] font-semibold text-[#c93400] dark:bg-[#ff9f0a]/15 dark:text-[#ff9f0a]" title={`${n} upvotes on Hugging Face`}>
      ▲ {n}
    </span>
  );
}

function Sightings({ p, icons }: { p: Paper; icons: Record<string, string> }) {
  return (
    <span class="flex items-center -space-x-1.5" title={`Spotted on ${p.spottedOn.map((s) => s.name).join(", ")}`}>
      {p.spottedOn.map((s) => (
        <a key={s.source} href={s.url} target="_blank" rel="noopener" aria-label={s.name}
          class="glass-tile grid size-6 place-items-center !rounded-full ring-2 ring-white/70 dark:ring-black/40"
          dangerouslySetInnerHTML={{ __html: (icons[s.source] ?? "").replace(/width="\d+" height="\d+"/, 'width="13" height="13"') }} />
      ))}
    </span>
  );
}

function Links({ p }: { p: Paper }) {
  const items: [string, string | undefined][] = [
    ["Paper", p.links.abs], ["PDF", p.links.pdf], ["Code", p.links.code],
    ["Project", p.links.project], ["Discuss", p.links.discussion],
  ];
  return (
    <div class="flex flex-wrap gap-1.5">
      {items.filter(([, url]) => url).map(([label, url]) => (
        <a key={label} class="link-capsule" href={url} target="_blank" rel="noopener">{label}</a>
      ))}
    </div>
  );
}

interface ActionProps {
  p: Paper;
  saved: boolean;
  onSave: (p: Paper) => void;
  onCite: (p: Paper) => void;
}

function Actions({ p, saved, onSave, onCite }: ActionProps) {
  return (
    <div class="flex items-center">
      <button type="button" class="icon-button" onClick={() => onCite(p)} aria-label="Copy BibTeX citation" title="Copy BibTeX citation">
        <QuoteIcon />
      </button>
      <button type="button" class={`icon-button ${saved ? "!text-brand-600 dark:!text-brand-400" : ""}`} onClick={() => onSave(p)}
        aria-pressed={saved} aria-label={saved ? "Remove from reading list" : "Save to reading list"} title={saved ? "Saved to your reading list" : "Save to reading list"}>
        <BookmarkIcon filled={saved} />
      </button>
    </div>
  );
}

function ThemeTags({ themes, onPick }: { themes: string[]; onPick: (t: string) => void }) {
  return (
    <div class="flex flex-wrap gap-x-3 gap-y-1">
      {themes.map((t) => (
        <button key={t} type="button" onClick={() => onPick(t)}
          class={`inline-flex items-center gap-1.5 text-xs font-semibold hover:underline ${tone(t).text}`}>
          <span class={`size-1.5 rounded-full ${tone(t).bg}`} />{t}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ the page

export default function PaperTrail({ papers, icons, buildTime }: Props) {
  const [now, setNow] = useState(() => new Date(buildTime).getTime());
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState<string | null>(null);
  const [range, setRange] = useState<Range>("all");
  const [sort, setSort] = useState<Sort>("trending");
  const [codeOnly, setCodeOnly] = useState(false);
  const [savedOnly, setSavedOnly] = useState(false);
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState("");

  useEffect(() => {
    setNow(Date.now());
    setSaved(readSaved());
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 2200);
    return () => clearTimeout(timer);
  }, [toast]);

  // Newest paper time, so "today" means the latest collection even on an old build.
  const latest = useMemo(() => Math.max(now - DAY, ...papers.map((p) => new Date(p.time).getTime())), [papers, now]);
  const inRange = useMemo(() => {
    const cutoff = range === "today" ? latest - 1.5 * DAY : range === "week" ? latest - 7 * DAY : 0;
    return papers.filter((p) => new Date(p.time).getTime() >= cutoff);
  }, [papers, range, latest]);

  // Paper of the day: the most talked-about paper from the latest ~36 hours.
  const spotlight = useMemo(() => {
    const recent = papers.filter((p) => new Date(p.time).getTime() >= latest - 1.5 * DAY);
    return [...(recent.length ? recent : papers)].sort((a, b) => b.buzz - a.buzz)[0];
  }, [papers, latest]);

  const pulse = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of inRange) for (const t of p.themes) counts.set(t, (counts.get(t) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [inRange]);
  const pulseMax = pulse[0]?.[1] ?? 1;

  const filtering = Boolean(query.trim() || theme || codeOnly || savedOnly);
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = inRange.filter(
      (p) =>
        (filtering || p.id !== spotlight?.id) &&
        (!theme || p.themes.includes(theme)) &&
        (!codeOnly || p.links.code) &&
        (!savedOnly || saved.has(p.id)) &&
        (!q || `${p.title} ${p.abstract} ${p.authors.join(" ")}`.toLowerCase().includes(q)),
    );
    return sort === "newest"
      ? list.sort((a, b) => b.time.localeCompare(a.time) || b.buzz - a.buzz)
      : list.sort((a, b) => b.buzz - a.buzz);
  }, [inRange, theme, codeOnly, savedOnly, saved, query, sort, filtering, spotlight]);

  const toggleSave = (p: Paper) => {
    const next = new Set(saved);
    const adding = !next.has(p.id);
    adding ? next.add(p.id) : next.delete(p.id);
    setSaved(next);
    try { localStorage.setItem(SAVED_KEY, JSON.stringify([...next])); } catch {}
    setToast(adding ? "Saved to your reading list" : "Removed from your reading list");
  };
  const cite = async (p: Paper) => setToast((await copyText(bibtex(p))) ? "BibTeX copied" : "Couldn't copy: your browser blocked it");
  const exportList = () => {
    const list = papers.filter((p) => saved.has(p.id));
    const blob = new Blob([list.map(bibtex).join("\n\n") + "\n"], { type: "application/x-bibtex" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "paper-trail-reading-list.bib" });
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const toggleOpen = (id: string) => {
    const next = new Set(open);
    next.has(id) ? next.delete(id) : next.add(id);
    setOpen(next);
  };
  const reset = () => { setQuery(""); setTheme(null); setCodeOnly(false); setSavedOnly(false); setRange("all"); };

  // Group by day when sorted by date, like Mail and Photos do.
  const groups = useMemo(() => {
    if (sort !== "newest") return [["", visible]] as [string, Paper[]][];
    const out: [string, Paper[]][] = [];
    for (const p of visible) {
      const label = dayLabel(p.time, now);
      if (out.at(-1)?.[0] === label) out.at(-1)![1].push(p);
      else out.push([label, [p]]);
    }
    return out;
  }, [visible, sort, now]);

  return (
    <div>
      {/* ---------------------------------------------------------- paper of the day + pulse */}
      <div class="grid gap-5 lg:grid-cols-[1.65fr_1fr]">
        {spotlight && (
          <article class="card relative flex flex-col overflow-hidden p-6 sm:p-8" aria-label="Paper of the day">
            <div class={`pointer-events-none absolute -right-20 -top-24 size-72 rounded-full opacity-25 blur-3xl ${tone(spotlight.themes[0]).bg}`} />
            <div class="relative flex flex-1 flex-col">
              <div class="flex items-center justify-between gap-3">
                <p class="eyebrow flex items-center gap-1.5 !text-[12px] !text-brand-600 dark:!text-brand-400"><SparkIcon /> Paper of the day</p>
                <div class="flex items-center gap-2"><Upvotes n={spotlight.upvotes} /><Sightings p={spotlight} icons={icons} /></div>
              </div>
              <h2 class="mt-4 text-2xl font-semibold leading-[1.15] tracking-[-0.03em] sm:text-[32px]">
                <a href={spotlight.links.abs} target="_blank" rel="noopener" class="hover:text-brand-600 dark:hover:text-brand-400">{spotlight.title}</a>
              </h2>
              {spotlight.authors.length > 0 && (
                <p class="mt-2 text-sm text-ink-muted dark:text-[#a1a1a6]">{authorLine(spotlight.authors, 4)}</p>
              )}
              <p class="mt-4 line-clamp-4 text-[15px] lg:line-clamp-6 leading-relaxed text-slate-700 dark:text-slate-300">
                {spotlight.agentNote?.whyItMatters || spotlight.abstract}
              </p>
              <div class="mt-4"><ThemeTags themes={spotlight.themes} onPick={setTheme} /></div>
              <div class="mt-6 flex flex-wrap items-center gap-2 lg:mt-auto lg:pt-6">
                <a class="glass-button !py-2" href={spotlight.links.abs} target="_blank" rel="noopener">Read the paper <ArrowIcon /></a>
                {spotlight.links.code && <a class="link-capsule !px-3.5 !py-2 !text-[13px]" href={spotlight.links.code} target="_blank" rel="noopener">Code</a>}
                {spotlight.links.pdf && <a class="link-capsule !px-3.5 !py-2 !text-[13px]" href={spotlight.links.pdf} target="_blank" rel="noopener">PDF</a>}
                <span class="ml-auto"><Actions p={spotlight} saved={saved.has(spotlight.id)} onSave={toggleSave} onCite={cite} /></span>
              </div>
            </div>
          </article>
        )}

        <section class="card flex flex-col p-6" aria-label="Research pulse">
          <p class="eyebrow !text-[12px]">Research pulse</p>
          <p class="mt-1 text-[15px] font-semibold tracking-[-0.02em]">What researchers are working on</p>
          <ul class="mt-4 flex flex-1 flex-col gap-1">
            {pulse.map(([t, n]) => (
              <li key={t}>
                <button type="button" onClick={() => setTheme(theme === t ? null : t)} aria-pressed={theme === t}
                  class={`group grid w-full grid-cols-[8.5rem_1fr_1.75rem] items-center gap-3 rounded-xl px-2 py-1.5 text-left text-[13px] transition hover:bg-black/[0.035] dark:hover:bg-white/[0.06] ${theme === t ? "bg-black/[0.05] dark:bg-white/[0.09]" : ""} ${theme && theme !== t ? "opacity-45" : ""}`}>
                  <span class="truncate font-medium">{t}</span>
                  <span class="h-1.5 overflow-hidden rounded-full bg-black/[0.06] dark:bg-white/10">
                    <span class={`block h-full rounded-full ${tone(t).bg} transition-[width] duration-500`} style={{ width: `${Math.max(6, (n / pulseMax) * 100)}%` }} />
                  </span>
                  <span class="text-right tabular-nums text-ink-muted dark:text-[#a1a1a6]">{n}</span>
                </button>
              </li>
            ))}
          </ul>
          <p class="mt-3 text-xs text-ink-muted dark:text-[#a1a1a6]">Tap a theme to filter the papers below.</p>
        </section>
      </div>

      {/* ---------------------------------------------------------- controls */}
      <div class="sticky top-[76px] z-20 mt-10 md:top-[72px]">
        <div class="card flex flex-col gap-3 !rounded-[22px] p-3 sm:flex-row sm:items-center">
          <label class="relative flex-1">
            <span class="sr-only">Search papers</span>
            <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
            <input class="field w-full !rounded-full pl-9" type="search" placeholder="Search titles, abstracts, authors"
              value={query} onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <div class="glass-nav flex p-1" role="group" aria-label="Time range">
              {([["today", "Today"], ["week", "This week"], ["all", "All"]] as [Range, string][]).map(([v, label]) => (
                <button key={v} type="button" class="segment" aria-pressed={range === v} onClick={() => setRange(v)}>{label}</button>
              ))}
            </div>
            <div class="glass-nav flex p-1" role="group" aria-label="Sort">
              {([["trending", "Trending"], ["newest", "Newest"]] as [Sort, string][]).map(([v, label]) => (
                <button key={v} type="button" class="segment" aria-pressed={sort === v} onClick={() => setSort(v)}>{label}</button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-2">
        <button type="button" class="chip !py-1 !text-[13px]" aria-pressed={codeOnly} onClick={() => setCodeOnly(!codeOnly)}>With code</button>
        <button type="button" class="chip !py-1 !text-[13px]" aria-pressed={savedOnly} onClick={() => setSavedOnly(!savedOnly)}>
          Reading list{saved.size ? ` · ${saved.size}` : ""}
        </button>
        {theme && (
          <button type="button" class="chip !py-1 !text-[13px]" aria-pressed="true" onClick={() => setTheme(null)} aria-label={`Remove filter ${theme}`}>
            {theme} <span aria-hidden="true" class="ml-1 opacity-80">✕</span>
          </button>
        )}
        {saved.size > 0 && (
          <button type="button" class="ml-auto text-[13px] font-medium text-brand-600 hover:underline dark:text-brand-400" onClick={exportList}>
            Export reading list (.bib)
          </button>
        )}
        <p class={`text-[13px] text-ink-muted dark:text-[#a1a1a6] ${saved.size > 0 ? "" : "ml-auto"}`}>
          <b class="font-semibold text-ink dark:text-white">{visible.length + (filtering || !spotlight ? 0 : 1)}</b> of {papers.length} papers
        </p>
      </div>

      {/* ---------------------------------------------------------- papers */}
      {visible.length === 0 ? (
        <div class="card mt-6 grid place-items-center gap-3 px-6 py-16 text-center">
          <p class="text-lg font-semibold">{savedOnly && saved.size === 0 ? "Your reading list is empty" : "No papers match"}</p>
          <p class="max-w-sm text-sm text-ink-muted dark:text-[#a1a1a6]">
            {savedOnly && saved.size === 0 ? "Tap the bookmark on any paper to keep it here. It stays in this browser." : "Try a wider time range or clear the filters."}
          </p>
          <button type="button" class="chip" onClick={reset}>Clear filters</button>
        </div>
      ) : (
        groups.map(([label, list]) => (
          <section key={label || "all"} class="mt-6">
            {label && <h3 class="mb-3 ml-1 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-muted dark:text-[#a1a1a6]">{label}</h3>}
            <div class="grid gap-4 md:grid-cols-2">
              {list.map((p) => {
                const expanded = open.has(p.id);
                return (
                  <article key={p.id} class="card flex flex-col p-5 sm:p-6">
                    <div class="flex items-center gap-2 text-xs text-ink-muted dark:text-[#a1a1a6]">
                      <span class={`size-2 rounded-full ${tone(p.themes[0]).bg}`} />
                      <span class={`font-semibold ${tone(p.themes[0]).text}`}>{p.themes[0]}</span>
                      <span aria-hidden="true">·</span>
                      <time dateTime={p.time}>{dayLabel(p.time, now)}</time>
                      <span class="ml-auto flex items-center gap-2"><Upvotes n={p.upvotes} /><Sightings p={p} icons={icons} /></span>
                    </div>
                    <h4 class="mt-3 text-[17px] font-semibold leading-snug tracking-[-0.02em]">
                      <a href={p.links.abs} target="_blank" rel="noopener" class="hover:text-brand-600 dark:hover:text-brand-400">{p.title}</a>
                    </h4>
                    {p.authors.length > 0 && <p class="mt-1 truncate text-[13px] text-ink-muted dark:text-[#a1a1a6]">{authorLine(p.authors)}</p>}
                    {p.agentNote && (
                      <p class="mt-3 flex gap-2 rounded-2xl bg-brand-500/[0.07] px-3 py-2 text-[13px] leading-snug text-slate-700 dark:bg-brand-400/10 dark:text-slate-200">
                        <span class="mt-0.5 shrink-0 text-brand-600 dark:text-brand-400"><SparkIcon /></span>
                        <span><b class="font-semibold">Why it matters:</b> {p.agentNote.whyItMatters}</span>
                      </p>
                    )}
                    {p.abstract && (
                      <div class="mt-3">
                        <p id={`abs-${p.id}`} class={`text-sm leading-relaxed text-slate-600 dark:text-slate-400 ${expanded ? "" : "line-clamp-3"}`}>{p.abstract}</p>
                        <button type="button" class="mt-1 text-[13px] font-medium text-brand-600 hover:underline dark:text-brand-400"
                          aria-expanded={expanded} aria-controls={`abs-${p.id}`} onClick={() => toggleOpen(p.id)}>
                          {expanded ? "Less" : "More"}
                        </button>
                      </div>
                    )}
                    {p.themes.length > 1 && <div class="mt-3"><ThemeTags themes={p.themes.slice(1)} onPick={setTheme} /></div>}
                    <div class="mt-auto flex items-center justify-between gap-2 pt-4">
                      <Links p={p} />
                      <Actions p={p} saved={saved.has(p.id)} onSave={toggleSave} onCite={cite} />
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ))
      )}

      {/* ---------------------------------------------------------- toast */}
      <div role="status" aria-live="polite"
        class={`glass-nav pointer-events-none fixed bottom-6 left-1/2 z-40 -translate-x-1/2 px-4 py-2 text-[13px] font-medium transition duration-300 ${toast ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"}`}>
        {toast}
      </div>
    </div>
  );
}
