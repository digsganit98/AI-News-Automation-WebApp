// Interactive news feed (runs in the browser): filter by group or source, search,
// time range and sort. The page passes in the items at build time.
import { useEffect, useMemo, useState } from "preact/hooks";

export interface FeedItem {
  id: string;
  source: string;
  sourceName: string;
  title: string;
  url: string;
  time: string;
  collectedAt?: string;
  excerpt: string;
  points?: number;
  comments?: number;
  upvotes?: number;
  likes?: number;
  discussionUrl?: string;
  githubRepo?: string;
  arxivUrl?: string;
}

export interface FeedSource {
  id: string;
  name: string;
  group: string;
}

interface Props {
  items: FeedItem[];
  sources: FeedSource[];
  icons: Record<string, string>;
  groups: Record<string, string>;
  buildTime: string;
  live?: boolean; // the Latest page: offers "last 3 h / 24 h" and "New" badges
}

const HOUR = 3_600_000;

function relativeTime(iso: string, now: number): string {
  if (!iso) return "";
  const diff = now - new Date(iso).getTime();
  if (diff < 60_000) return "just now";
  if (diff < HOUR) return `${Math.floor(diff / 60_000)} min ago`;
  if (diff < 24 * HOUR) return `${Math.floor(diff / HOUR)} h ago`;
  const days = Math.floor(diff / (24 * HOUR));
  return days === 1 ? "yesterday" : `${days} days ago`;
}

function signal(i: FeedItem): number {
  return (i.points ?? 0) + (i.comments ?? 0) + (i.upvotes ?? 0) * 5 + (i.likes ?? 0) / 10;
}

export default function NewsFeed({ items, sources, icons, groups, buildTime, live = false }: Props) {
  const [now, setNow] = useState(() => new Date(buildTime).getTime());
  const [group, setGroup] = useState<string | null>(null);
  const [source, setSource] = useState("");
  const [query, setQuery] = useState("");
  const [range, setRange] = useState<"all" | "3" | "24">("all");
  const [sort, setSort] = useState<"newest" | "discussed">("newest");

  useEffect(() => {
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const groupOf = useMemo(() => Object.fromEntries(sources.map((s) => [s.id, s.group])), [sources]);
  const presentGroups = useMemo(
    () => Object.keys(groups).filter((g) => items.some((i) => groupOf[i.source] === g)),
    [items, groups, groupOf],
  );
  const presentSources = useMemo(
    () => sources.filter((s) => items.some((i) => i.source === s.id)),
    [items, sources],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const cutoff = range === "all" ? 0 : now - Number(range) * HOUR;
    const list = items.filter(
      (i) =>
        (!group || groupOf[i.source] === group) &&
        (!source || i.source === source) &&
        (!q || `${i.title} ${i.excerpt} ${i.sourceName}`.toLowerCase().includes(q)) &&
        (!cutoff || new Date(i.time).getTime() >= cutoff),
    );
    return sort === "newest"
      ? list.sort((a, b) => b.time.localeCompare(a.time))
      : list.sort((a, b) => signal(b) - signal(a));
  }, [items, group, source, query, range, sort, now, groupOf]);

  const reset = () => {
    setGroup(null); setSource(""); setQuery(""); setRange("all");
  };

  return (
    <section aria-label="News feed">
      <div class="card mb-6 flex flex-col gap-3 p-4">
        <div class="flex flex-wrap items-center gap-2">
          <button type="button" class="chip" aria-pressed={group === null} onClick={() => setGroup(null)}>
            All
          </button>
          {presentGroups.map((g) => (
            <button type="button" key={g} class="chip" aria-pressed={group === g}
              onClick={() => { setGroup(group === g ? null : g); setSource(""); }}>
              {groups[g]}
            </button>
          ))}
        </div>
        <div class="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
          <label class="relative">
            <span class="sr-only">Search</span>
            <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
            <input class="field w-full pl-9" type="search" placeholder="Search titles and summaries…"
              value={query} onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
          </label>
          <select class="field" aria-label="Source" value={source}
            onChange={(e) => setSource((e.target as HTMLSelectElement).value)}>
            <option value="">All sources</option>
            {presentSources
              .filter((s) => !group || s.group === group)
              .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {live && (
            <select class="field" aria-label="Time range" value={range}
              onChange={(e) => setRange((e.target as HTMLSelectElement).value as typeof range)}>
              <option value="all">Any time</option>
              <option value="3">Last 3 hours</option>
              <option value="24">Last 24 hours</option>
            </select>
          )}
          <select class="field" aria-label="Sort" value={sort}
            onChange={(e) => setSort((e.target as HTMLSelectElement).value as typeof sort)}>
            <option value="newest">Newest first</option>
            <option value="discussed">Most discussed</option>
          </select>
        </div>
      </div>

      <p class="mb-3 text-sm text-slate-500 dark:text-slate-400">
        Showing <b class="text-slate-900 dark:text-white">{visible.length}</b> of {items.length} items
      </p>

      {visible.length === 0 ? (
        <div class="card grid place-items-center gap-3 px-6 py-16 text-center">
          <p class="text-lg font-semibold">Nothing matches these filters</p>
          <button type="button" class="chip" onClick={reset}>Clear filters</button>
        </div>
      ) : (
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((i) => {
            const isNew = live && i.collectedAt && now - new Date(i.collectedAt).getTime() < 3 * HOUR;
            return (
              <article key={i.id} class="card group relative flex flex-col p-5 transition duration-300 hover:-translate-y-1">
                <div class="mb-3 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <span class="glass-tile grid size-7 place-items-center !rounded-lg"
                    dangerouslySetInnerHTML={{ __html: icons[i.source] ?? "" }} />
                  <span class="font-semibold text-slate-700 dark:text-slate-200">{i.sourceName}</span>
                  <span aria-hidden="true">·</span>
                  <time dateTime={i.time} title={new Date(i.time).toLocaleString()}>{relativeTime(i.time, now)}</time>
                  {isNew && (
                    <span class="pill ml-auto border-emerald-300/60 bg-emerald-50 text-emerald-700 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-300">New</span>
                  )}
                </div>
                <h3 class="text-[16px] font-semibold leading-snug tracking-[-0.015em]">
                  <a href={i.url} target="_blank" rel="noopener" class="after:absolute after:inset-0 group-hover:text-brand-600 dark:group-hover:text-brand-400">
                    {i.title}
                  </a>
                </h3>
                {i.excerpt && (
                  <p class="mt-2 line-clamp-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{i.excerpt}</p>
                )}
                <div class="relative z-10 mt-auto flex flex-wrap items-center gap-2 pt-4 text-xs">
                  {i.points ? <span class="pill border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-400/30 dark:bg-orange-400/10 dark:text-orange-300">▲ {i.points}</span> : null}
                  {i.comments ? <span class="pill border-slate-200 text-slate-600 dark:border-white/10 dark:text-slate-300">{i.comments} comments</span> : null}
                  {i.upvotes ? <span class="pill border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-300">▲ {i.upvotes} upvotes</span> : null}
                  {i.likes ? <span class="pill border-pink-200 bg-pink-50 text-pink-700 dark:border-pink-400/30 dark:bg-pink-400/10 dark:text-pink-300">♥ {i.likes.toLocaleString()}</span> : null}
                  <span class="ml-auto flex gap-3 font-medium">
                    {i.arxivUrl && <a class="text-brand-600 hover:underline dark:text-brand-400" href={i.arxivUrl} target="_blank" rel="noopener">Paper</a>}
                    {i.githubRepo && <a class="text-brand-600 hover:underline dark:text-brand-400" href={i.githubRepo} target="_blank" rel="noopener">Code</a>}
                    {i.discussionUrl && i.discussionUrl !== i.url && <a class="text-brand-600 hover:underline dark:text-brand-400" href={i.discussionUrl} target="_blank" rel="noopener">Discussion</a>}
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
