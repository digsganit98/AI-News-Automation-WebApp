// Latest: one shared search/filter bar above two sub-tabs.
//   Top stories           the analyst's ranked stories (filtered, first 4 shown)
//   Everything collected  news, research papers and R&D Hub articles (filtered, first 4 shown)
// A "Show X more stories" button reveals the rest of whichever tab is open.
// Inside Everything collected, a small switch picks All, News or Research papers. Research
// papers shows the Paper Trail view, which has its own search, so the shared bar hides there.
import { useEffect, useMemo, useState } from "preact/hooks";
import { FilterBar, NO_FILTER, inRange, matchesQuery } from "./feedFilters";
import { FeedCard, signal, useNow, type FeedItem, type FeedSource } from "./NewsFeed";
import PaperTrail, { type Paper } from "./PaperTrail";
import StoryCard from "./StoryCard";
import type { Story } from "../lib/siteData"; // type only

type Tab = "top" | "all";
type Kind = "all" | "news" | "papers";

interface Props {
  stories: Story[];
  categoryStyle: Record<string, string>;
  importanceLabel: Record<number, string>;
  news: FeedItem[];
  papers: Paper[];
  paperItems: FeedItem[]; // the same papers as feed rows, for the All view
  hubItems: FeedItem[];
  sources: FeedSource[];
  icons: Record<string, string>;
  buildTime: string;
  csvUrl: string;
}

const KINDS: [Kind, string][] = [["all", "All"], ["news", "News"], ["papers", "Research papers"]];
const FIRST = 4; // how many items each tab shows before "Show X more" (a 2 x 2 grid)
// Everything collected can hold hundreds of glass cards; revealing them all at once makes the
// page heavy, so each click adds a batch. The button label still shows how many are left.
const BATCH = 24;

export default function LatestFeed({ stories, categoryStyle, importanceLabel, news, papers, paperItems, hubItems, sources, icons, buildTime, csvUrl }: Props) {
  const now = useNow(buildTime);
  const [tab, setTab] = useState<Tab>("top");
  const [kind, setKind] = useState<Kind>("all");
  const [filter, setFilter] = useState(NO_FILTER);
  // How many items each tab currently shows.
  const [shown, setShown] = useState({ top: FIRST, all: FIRST });

  // Deep links: /?view=papers (the old Paper Trail address) opens Everything > Research papers.
  useEffect(() => {
    const wanted = new URLSearchParams(location.search).get("view");
    if (wanted === "papers" || wanted === "news") { setTab("all"); setKind(wanted); }
    else if (wanted === "all") setTab("all");
  }, []);
  const pickKind = (k: Kind) => {
    setKind(k);
    try { history.replaceState(null, "", k === "all" ? location.pathname : `?view=${k}`); } catch {}
  };

  // Lookup: source name -> id (stories only carry source NAMES).
  const idByName = useMemo(() => Object.fromEntries(sources.map((s) => [s.name, s.id])), [sources]);

  const allItems = useMemo(() => [...news, ...paperItems, ...hubItems], [news, paperItems, hubItems]);

  // The filter bar only offers sources that exist somewhere in either list.
  const presentSources = useMemo(
    () => sources.filter((s) => allItems.some((i) => i.source === s.id) || stories.some((st) => st.sources.some((x) => x.name === s.name))),
    [allItems, stories, sources],
  );

  // Top stories: keep the analyst's importance ranking (the list is already sorted), so the Sort
  // control only affects Everything collected.
  const visibleStories = useMemo(
    () => stories.filter((s) => {
      const ids = s.sources.map((x) => idByName[x.name]);
      return (
        (!filter.source || ids.includes(filter.source)) &&
        matchesQuery(`${s.headline} ${s.summary} ${s.whyItMatters} ${s.sources.map((x) => x.name).join(" ")}`, filter.query) &&
        inRange(s.createdAt, filter.range, now)
      );
    }),
    [stories, filter, now, idByName],
  );

  // Everything collected: same filters, then the chosen sort.
  const matchItem = (i: FeedItem) =>
    (!filter.source || i.source === filter.source) &&
    matchesQuery(`${i.title} ${i.excerpt} ${i.sourceName}`, filter.query) &&
    inRange(i.time, filter.range, now);
  const visibleItems = useMemo(() => {
    const list = (kind === "news" ? news : allItems).filter(matchItem);
    return filter.sort === "newest"
      ? list.sort((a, b) => b.time.localeCompare(a.time))
      : list.sort((a, b) => signal(b) - signal(a));
  }, [kind, news, allItems, filter, now]);
  const filteredAllCount = useMemo(() => allItems.filter(matchItem).length, [allItems, filter, now]);
  const filteredNewsCount = useMemo(() => news.filter(matchItem).length, [news, filter, now]);

  const onFilter = (next: typeof filter) => {
    setFilter(next);
    setShown({ top: FIRST, all: FIRST }); // a new search starts from the top 3 again
  };

  const counts: Record<Kind, number> = { all: filteredAllCount, news: filteredNewsCount, papers: papers.length };
  const onPapers = tab === "all" && kind === "papers";
  const list = tab === "top" ? visibleStories : visibleItems;
  const left = Math.max(list.length - shown[tab], 0);
  const showMore = () => setShown({ ...shown, [tab]: tab === "top" ? list.length : shown[tab] + BATCH });
  const clear = () => onFilter({ ...NO_FILTER, sort: filter.sort });

  const segment = "segment";
  return (
    <div>
      {/* 1. Shared search and filters: drive both tabs. Hidden on the Paper Trail, which has its own. */}
      {!onPapers && (
        <div class="mb-4">
          <FilterBar value={filter} onChange={onFilter}
            presentSources={presentSources} searchHint="Search news, papers and articles…" live />
        </div>
      )}

      {/* 2. Sub-tabs (counts follow the filters) and, inside Everything, the All / News / Papers switch */}
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="glass-nav tabs-accent flex p-1" role="group" aria-label="Section">
          <button type="button" class={segment} aria-pressed={tab === "top"} onClick={() => setTab("top")}>
            Top stories <span class="opacity-60">{visibleStories.length}</span>
          </button>
          <button type="button" class={segment} aria-pressed={tab === "all"} onClick={() => setTab("all")}>
            Everything collected <span class="opacity-60">{filteredAllCount}</span>
          </button>
        </div>
        {tab === "top" ? (
          <p class="text-sm text-ink-muted dark:text-[#a1a1a6]">Picked, grouped and ranked by the AI agents</p>
        ) : (
          <div class="glass-nav tabs-accent flex p-1" role="group" aria-label="What to show">
            {KINDS.map(([k, label]) => (
              <button key={k} type="button" class={segment} aria-pressed={kind === k} onClick={() => pickKind(k)}>
                {label} <span class="opacity-60">{counts[k]}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 3. The list */}
      {onPapers ? (
        <>
          <p class="mb-3 text-sm text-ink-muted dark:text-[#a1a1a6]">
            Every GenAI paper from the last two weeks, from paper to code.{" "}
            <a href={csvUrl} download class="font-medium text-brand-600 hover:underline dark:text-brand-400">Download the research log (CSV)</a>
          </p>
          <PaperTrail papers={papers} icons={icons} buildTime={buildTime} />
        </>
      ) : list.length === 0 ? (
        <div class="card grid place-items-center gap-3 px-6 py-14 text-center">
          <p class="text-lg font-semibold">{tab === "top" ? "No top stories match these filters" : "Nothing collected matches these filters"}</p>
          <button type="button" class="chip" onClick={clear}>Clear filters</button>
        </div>
      ) : (
        <>
          <div class="grid gap-4 md:grid-cols-2">
            {tab === "top"
              ? visibleStories.slice(0, shown.top).map((s) => <StoryCard key={s.id} story={s} categoryStyle={categoryStyle} importanceLabel={importanceLabel} />)
              : visibleItems.slice(0, shown.all).map((i) => <FeedCard key={i.id} i={i} icons={icons} now={now} live />)}
          </div>
          {left > 0 && (
            <div class="mt-6 flex justify-center">
              <button type="button" class="chip !px-5 !py-2" onClick={showMore}>
                Show {left} more {left === 1 ? "story" : "stories"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
