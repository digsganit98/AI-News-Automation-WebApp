// One analyst story, as a client component so the Latest page can filter and expand the list.
// Same content as the old StoryCard.astro, in the approved v2 layout: coloured by category,
// headline and summary clamped to two lines each; the full text is one click away.
import type { Story } from "../lib/siteData"; // type only: erased at build, so no Node code reaches the browser

interface Props {
  story: Story;
  // Colour and label tables live in siteData.ts (server side); the page passes them in as props.
  categoryStyle: Record<string, string>;
  importanceLabel: Record<number, string>;
}

const DEEPER_LABEL: Record<string, string> = { paper: "Paper", code: "Code", model: "Model", demo: "Demo" };

export default function StoryCard({ story, categoryStyle, importanceLabel }: Props) {
  // "Go deeper" links: only the ones the agents actually found.
  const deeper = Object.entries(story.goDeeper ?? {}).filter(([, url]) => url) as [string, string][];
  return (
    // The category class (from CATEGORY_STYLE) sets the text colour, so currentColor IS the category
    // colour here: it paints the left bar, the soft tint and the label. Body text sets its own colour.
    <article class={`card relative flex flex-col overflow-hidden !rounded-[24px] py-5 pl-6 pr-5 ${categoryStyle[story.category] ?? "text-brand-600"}`}>
      <span aria-hidden="true" class="pointer-events-none absolute inset-0 opacity-[0.14]" style={{ background: "linear-gradient(135deg, currentColor, transparent 55%)" }} />
      <span aria-hidden="true" class="absolute bottom-5 left-0 top-5 w-1 rounded-r-full bg-current" />
      <div class="relative mb-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs font-semibold">
        <span class="rounded-full bg-current/15 px-2.5 py-0.5 font-bold"><span class="text-inherit">{story.category}</span></span>
        <span class="flex items-center gap-1 text-ink-muted dark:text-[#a1a1a6]" title={`Importance ${story.importance} of 5`}>
          <span aria-hidden="true" class="tracking-[0.15em]">{"●".repeat(story.importance)}<span class="opacity-30">{"●".repeat(5 - story.importance)}</span></span>
          {importanceLabel[story.importance]}
        </span>
        {story.sourceType && <span class="text-ink-muted dark:text-[#a1a1a6]">· {story.sourceType}</span>}
        {story.status === "followUp" && <span class="pill border-amber-300/60 bg-amber-50 text-amber-700 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-300">Update</span>}
      </div>
      <h3 class="relative line-clamp-2 text-[17px] font-semibold leading-snug tracking-[-0.02em] text-ink dark:text-[#f5f5f7]">
        <a href={story.sources[0]?.url} target="_blank" rel="noopener" class="hover:text-brand-600 dark:hover:text-brand-400">{story.headline}</a>
      </h3>
      <p class="relative mt-2 line-clamp-2 text-sm leading-relaxed text-ink-muted dark:text-[#a1a1a6]">{story.summary}</p>
      <div class="relative mt-auto flex flex-wrap items-center gap-1.5 pt-3.5 text-xs">
        {story.sources.map((s) => (
          <a key={s.url} href={s.url} target="_blank" rel="noopener" class="pill border-slate-200 text-ink-muted hover:border-brand-400 hover:text-brand-600 dark:border-white/15 dark:text-[#a1a1a6]">{s.name}</a>
        ))}
        {deeper.length > 0 && (
          <span class="ml-auto flex gap-3 font-semibold">
            {deeper.map(([kind, url]) => (
              <a key={kind} href={url} target="_blank" rel="noopener" class="text-brand-600 hover:underline dark:text-brand-400">{DEEPER_LABEL[kind] ?? kind} ↗</a>
            ))}
          </span>
        )}
      </div>
    </article>
  );
}
