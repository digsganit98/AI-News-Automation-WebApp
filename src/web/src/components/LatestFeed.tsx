// Latest: news and research papers in one place. A segmented switch picks All, News or
// Research papers. All and News use the news feed (papers appear in All with a "Paper" pill);
// Research papers shows the Paper Trail view (paper of the day, research pulse, reading list).
import { useEffect, useState } from "preact/hooks";
import NewsFeed, { type FeedItem, type FeedSource } from "./NewsFeed";
import PaperTrail, { type Paper } from "./PaperTrail";

type View = "all" | "news" | "papers";

interface Props {
  news: FeedItem[];
  papers: Paper[];
  paperItems: FeedItem[]; // the same papers as feed rows, for the All view
  hubItems: FeedItem[];
  sources: FeedSource[];
  icons: Record<string, string>;
  groups: Record<string, string>;
  buildTime: string;
  csvUrl: string;
}

const VIEWS: [View, string][] = [["all", "All"], ["news", "News"], ["papers", "Research papers"]];

export default function LatestFeed({ news, papers, paperItems, hubItems, sources, icons, groups, buildTime, csvUrl }: Props) {
  const [view, setView] = useState<View>("all");

  // Deep links: /?view=papers (the old Paper Trail address redirects here).
  useEffect(() => {
    const wanted = new URLSearchParams(location.search).get("view");
    if (wanted === "news" || wanted === "papers" || wanted === "all") setView(wanted);
  }, []);
  const pick = (v: View) => {
    setView(v);
    try { history.replaceState(null, "", v === "all" ? location.pathname : `?view=${v}`); } catch {}
  };

  const counts: Record<View, number> = { all: news.length + paperItems.length + hubItems.length, news: news.length, papers: papers.length };
  const allItems = [...news, ...paperItems, ...hubItems];

  return (
    <div>
      <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 class="text-3xl font-semibold">{view === "papers" ? "Research papers" : view === "news" ? "Latest news" : "Everything collected"}</h2>
          <p class="mt-1 text-sm text-ink-muted dark:text-[#a1a1a6]">
            {view === "papers" ? "Every GenAI paper from the last two weeks, from paper to code." : "News and research papers, in one place."}
            {view === "papers" && <> <a href={csvUrl} download class="font-medium text-brand-600 hover:underline dark:text-brand-400">Download the research log (CSV)</a></>}
          </p>
        </div>
        <div class="glass-nav flex p-1" role="group" aria-label="What to show">
          {VIEWS.map(([v, label]) => (
            <button key={v} type="button" class="segment" aria-pressed={view === v} onClick={() => pick(v)}>
              {label} <span class="opacity-60">{counts[v]}</span>
            </button>
          ))}
        </div>
      </div>

      {view === "papers" ? (
        <PaperTrail papers={papers} icons={icons} buildTime={buildTime} />
      ) : (
        <NewsFeed
          key={view}
          items={view === "all" ? allItems : news}
          sources={sources}
          icons={icons}
          groups={groups}
          buildTime={buildTime}
          live
          searchHint={view === "all" ? "Search news, papers and articles…" : "Search titles and summaries…"}
        />
      )}
    </div>
  );
}
