// One analyst story, as a client component so the Latest page can filter and expand the list.
// Same content as the old StoryCard.astro, in the compact layout from the approved mockup:
// headline and summary are clamped to two lines each; the full text is one click away.
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
    <article class="card flex flex-col !rounded-[20px] px-4 py-3.5">
      <div class="mb-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11.5px] font-semibold">
        <span class={categoryStyle[story.category] ?? "text-ink-muted"}>{story.category}</span>
        <span class="flex items-center gap-1 text-ink-muted dark:text-[#a1a1a6]" title={`Importance ${story.importance} of 5`}>
          <span aria-hidden="true" class="tracking-[0.15em]">{"●".repeat(story.importance)}<span class="opacity-30">{"●".repeat(5 - story.importance)}</span></span>
          {importanceLabel[story.importance]}
        </span>
        {story.sourceType && <span class="text-ink-muted dark:text-[#a1a1a6]">· {story.sourceType}</span>}
        {story.status === "followUp" && <span class="pill border-amber-300/60 bg-amber-50 text-amber-700 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-300">Update</span>}
      </div>
      <h3 class="line-clamp-2 text-[15.5px] font-semibold leading-snug tracking-[-0.02em]">
        <a href={story.sources[0]?.url} target="_blank" rel="noopener" class="hover:text-brand-600 dark:hover:text-brand-400">{story.headline}</a>
      </h3>
      <p class="mt-1.5 line-clamp-2 text-[13px] leading-snug text-ink-muted dark:text-[#a1a1a6]">{story.summary}</p>
      <div class="mt-auto flex flex-wrap items-center gap-1.5 pt-2.5 text-[11.5px]">
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
