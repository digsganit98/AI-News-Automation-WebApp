// Shared filter bar (search, source, time range, sort) used by the Latest page
// and the day pages. The filter state lives in the parent, so one bar can drive several lists
// (on Latest: the Top stories list and the Everything collected list).
import type { FeedSource } from "./NewsFeed";

// One hour in MILLISECONDS: 60 minutes x 60 seconds x 1000 ms = 3,600,000.
// Why milliseconds: JavaScript's Date.now() and new Date(iso).getTime() both return
// milliseconds, so every time maths below (cutoffs, "3 h ago") must use the same unit.
// This is not new: the original NewsFeed.tsx declared it as `const HOUR = 3_600_000` and used
// it for relativeTime(), the "Last 3 / 24 hours" cutoff and the "New" badge (3 * HOUR).
// It now lives here so NewsFeed.tsx and this file share ONE definition instead of two copies.
export const HOUR = 60 * 60 * 1000;

export type Range = "all" | "3" | "24"; // "3" and "24" are hours, the same values as the <option>s below
export type Sort = "newest" | "discussed";

export interface FilterState {
  source: string; // a source id; "" means all sources
  query: string; // free-text search
  range: Range;
  sort: Sort;
}

// The "nothing filtered" state: the starting point and what "Clear filters" returns to.
export const NO_FILTER: FilterState = { source: "", query: "", range: "all", sort: "newest" };

/** True when `iso` falls inside the chosen range ("all" keeps everything). `now` is in ms. */
export const inRange = (iso: string, range: Range, now: number) =>
  range === "all" || new Date(iso).getTime() >= now - Number(range) * HOUR;

/** Case-insensitive "contains" search; an empty query matches everything. */
export const matchesQuery = (text: string, query: string) => {
  const q = query.trim().toLowerCase();
  return !q || text.toLowerCase().includes(q);
};

interface BarProps {
  value: FilterState;
  onChange: (next: FilterState) => void;
  presentSources: FeedSource[]; // only the sources that actually have items
  searchHint?: string;
  live?: boolean; // the Latest page also offers the "last 3 / 24 hours" range
}

export function FilterBar({ value, onChange, presentSources, searchHint = "Search titles and summaries…", live = false }: BarProps) {
  // Change one field and keep the rest, so each control only has to say what it changed.
  const set = (patch: Partial<FilterState>) => onChange({ ...value, ...patch });
  // One clean row (approved v2 mockup): the group chips were removed, so only search + dropdowns.
  return (
    <div class="card flex flex-col gap-2 !rounded-[24px] p-3.5">
      <div class="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
        <label class="relative">
          <span class="sr-only">Search</span>
          <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
          <input class="field w-full !py-2 pl-9" type="search" placeholder={searchHint}
            value={value.query} onInput={(e) => set({ query: (e.target as HTMLInputElement).value })} />
        </label>
        <select class="field !py-2" aria-label="Source" value={value.source}
          onChange={(e) => set({ source: (e.target as HTMLSelectElement).value })}>
          <option value="">All sources</option>
          {presentSources
            .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        {live && (
          <select class="field !py-2" aria-label="Time range" value={value.range}
            onChange={(e) => set({ range: (e.target as HTMLSelectElement).value as Range })}>
            <option value="all">Any time</option>
            <option value="3">Last 3 hours</option>
            <option value="24">Last 24 hours</option>
          </select>
        )}
        <select class="field !py-2" aria-label="Sort" value={value.sort}
          onChange={(e) => set({ sort: (e.target as HTMLSelectElement).value as Sort })}>
          <option value="newest">Newest first</option>
          <option value="discussed">Most discussed</option>
        </select>
      </div>
    </div>
  );
}
