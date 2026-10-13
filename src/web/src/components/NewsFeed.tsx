// Interactive news feed (runs in the browser): filter by group or source, search,
// time range and sort. The page passes in the items at build time. The Latest page uses
// FeedCard directly, so one filter bar can drive both its lists.
import { useEffect, useMemo, useState } from "preact/hooks";
import { FilterBar, HOUR, NO_FILTER, inRange, matchesQuery } from "./feedFilters";

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
  kind?: "news" | "paper" | "hub"; // Latest mixes all three; a pill shows which one a row is
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
  searchHint?: string;
}

export function relativeTime(iso: string, now: number): string {
  if (!iso) return "";
  const diff = now - new Date(iso).getTime();
  if (diff < 60_000) return "just now";
  if (diff < HOUR) return `${Math.floor(diff / 60_000)} min ago`;
  if (diff < 24 * HOUR) return `${Math.floor(diff / HOUR)} h ago`;
  const days = Math.floor(diff / (24 * HOUR));
  return days === 1 ? "yesterday" : `${days} days ago`;
}

export function signal(i: FeedItem): number {
  return (i.points ?? 0) + (i.comments ?? 0) + (i.upvotes ?? 0) * 5 + (i.likes ?? 0) / 10;
}

/** The ticking "now" the feeds use for relative times and time-range filters. */
export function useNow(buildTime: string): number {
  const [now, setNow] = useState(() => new Date(buildTime).getTime());
  useEffect(() => {
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

export function FeedCard({ i, icons, now, live }: { i: FeedItem; icons: Record<string, string>; now: number; live: boolean }) {
  const isNew = live && i.collectedAt && now - new Date(i.collectedAt).getTime() < 3 * HOUR;
  return (
    <article class="card group relative flex flex-col p-4 transition duration-300 hover:-translate-y-1">
      <div class="mb-2 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <span class="glass-tile grid size-7 place-items-center !rounded-lg"
          dangerouslySetInnerHTML={{ __html: icons[i.source] ?? "" }} />
        <span class="font-semibold text-slate-700 dark:text-slate-200">{i.sourceName}</span>
        <span aria-hidden="true">·</span>
        <time dateTime={i.time} title={new Date(i.time).toLocaleString()}>{relativeTime(i.time, now)}</time>
        {i.kind === "paper" && <span class="pill border-transparent bg-[#bf5af2]/15 text-[#8944ab] dark:text-[#d9a3ff]">Paper</span>}
        {i.kind === "hub" && <span class="pill border-transparent bg-amber-400/20 text-amber-700 dark:text-amber-300">R&amp;D Hub</span>}
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
        <p class="mt-1.5 line-clamp-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{i.excerpt}</p>
      )}
      <div class="relative z-10 mt-auto flex flex-wrap items-center gap-2 pt-3 text-xs">
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
}

export default function NewsFeed({ items, sources, icons, groups, buildTime, live = false, searchHint = "Search titles and summaries…" }: Props) {
  const now = useNow(buildTime);
  const [filter, setFilter] = useState(NO_FILTER);

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
    const list = items.filter(
      (i) =>
        (!filter.group || groupOf[i.source] === filter.group) &&
        (!filter.source || i.source === filter.source) &&
        matchesQuery(`${i.title} ${i.excerpt} ${i.sourceName}`, filter.query) &&
        inRange(i.time, filter.range, now),
    );
    return filter.sort === "newest"
      ? list.sort((a, b) => b.time.localeCompare(a.time))
      : list.sort((a, b) => signal(b) - signal(a));
  }, [items, filter, now, groupOf]);

  return (
    <section aria-label="News feed">
      <div class="mb-6">
        <FilterBar value={filter} onChange={setFilter} groups={groups} presentGroups={presentGroups}
          presentSources={presentSources} searchHint={searchHint} live={live} />
      </div>

      <p class="mb-3 text-sm text-slate-500 dark:text-slate-400">
        Showing <b class="text-slate-900 dark:text-white">{visible.length}</b> of {items.length} items
      </p>

      {visible.length === 0 ? (
        <div class="card grid place-items-center gap-3 px-6 py-16 text-center">
          <p class="text-lg font-semibold">Nothing matches these filters</p>
          <button type="button" class="chip" onClick={() => setFilter({ ...NO_FILTER, sort: filter.sort })}>Clear filters</button>
        </div>
      ) : (
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((i) => <FeedCard key={i.id} i={i} icons={icons} now={now} live={live} />)}
        </div>
      )}
    </section>
  );
}
