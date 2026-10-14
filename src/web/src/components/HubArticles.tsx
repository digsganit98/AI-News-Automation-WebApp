// R&D Hub (runs in the browser): the article feed, laid out like the R&D Ideas page: one compact
// control bar (search, table/cards switch, Upload to SharePoint, four filters and the count)
// above a table or a card grid. SharePoint is the only upload route.
import { useMemo, useState } from "preact/hooks";
import {
  CLOUD_PLATFORMS, HUB_FORMATS, INDUSTRY_VERTICALS, TECH_DOMAINS, type HubCard,
} from "../lib/hubTypes";

interface Props {
  articles: HubCard[];
  sharePointUrl: string;
}

const FORMAT_LABEL: Record<string, string> = { html: "HTML", pdf: "PDF" };

const DOMAIN_TONE: Record<string, string> = {
  "Agentic AI": "border-purple-300/80 bg-purple-100/80 text-purple-900 dark:border-purple-400/40 dark:bg-purple-400/15 dark:text-purple-200",
  "GenAI": "border-blue-300/80 bg-blue-100/80 text-blue-900 dark:border-blue-400/40 dark:bg-blue-400/15 dark:text-blue-200",
  "Industry Application": "border-orange-300/80 bg-orange-100/80 text-orange-900 dark:border-orange-400/40 dark:bg-orange-400/15 dark:text-orange-200",
  "Cloud AI/ML": "border-emerald-300/80 bg-emerald-100/80 text-emerald-900 dark:border-emerald-400/40 dark:bg-emerald-400/15 dark:text-emerald-200",
};
const domainTone = (d: string) =>
  `border ${DOMAIN_TONE[d] ?? "border-slate-300/80 bg-white/70 text-slate-900 dark:border-white/20 dark:bg-white/10 dark:text-slate-200"}`;

// Cloud and industry get their own hues so the table is not one flat grey (domain already has tones).
const toneChip = (text: string, tone: string) =>
  <span class={`inline-block whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-bold ${tone}`}>{text}</span>;
const CLOUD_TONE = "border-teal-300/80 bg-teal-100/80 text-teal-900 dark:border-teal-400/40 dark:bg-teal-400/15 dark:text-teal-200";
const INDUSTRY_TONE = "border-amber-300/80 bg-amber-100/80 text-amber-900 dark:border-amber-400/40 dark:bg-amber-400/15 dark:text-amber-200";

const dayText = (iso: string) => iso.slice(0, 10);

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></svg>
  );
}

// The label sits inside the dropdown ("Tech domain · All") instead of above it: one row less.
function Select({ label, value, onChange, options, all }: {
  label: string; value: string; onChange: (v: string) => void; options: readonly string[]; all: string;
}) {
  return (
    <select class="plain-field !py-1.5" aria-label={label} value={value} onChange={(e) => onChange((e.target as HTMLSelectElement).value)}>
      <option value="All">{label} · {all}</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

export default function HubArticles({ articles, sharePointUrl }: Props) {
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState("All");
  const [cloud, setCloud] = useState("All");
  const [vertical, setVertical] = useState("All");
  const [format, setFormat] = useState("All");
  const [view, setView] = useState<"table" | "cards">("table");

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return articles.filter(
      (a) =>
        (domain === "All" || a.techDomain === domain) &&
        (cloud === "All" || a.cloudPlatform === cloud) &&
        (vertical === "All" || a.industryVertical === vertical) &&
        (format === "All" || a.format === format) &&
        (!q || `${a.title} ${a.summary} ${a.author} ${a.team} ${a.tags.join(" ")}`.toLowerCase().includes(q)),
    );
  }, [articles, search, domain, cloud, vertical, format]);

  const filtering = search || domain !== "All" || cloud !== "All" || vertical !== "All" || format !== "All";
  const reset = () => { setSearch(""); setDomain("All"); setCloud("All"); setVertical("All"); setFormat("All"); };
  const chip = (text: string) => <span class="inline-block whitespace-nowrap rounded-md border border-slate-300/80 bg-white/70 px-2 py-0.5 text-[11px] font-bold text-slate-900 dark:border-white/20 dark:bg-white/10 dark:text-slate-200">{text}</span>;

  return (
    <div>
      {/* Control bar: search, view switch and upload on the first row; filters and count on the second */}
      <div class="plain-panel mb-4 flex flex-col gap-2.5 p-3.5">
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input class="plain-field flex-1" type="search" placeholder="Search articles, authors, topics…" value={search}
            onInput={(e) => setSearch((e.target as HTMLInputElement).value)} />
          <div class="flex rounded-lg border border-slate-300/80 bg-white/60 p-0.5 dark:border-white/15 dark:bg-white/10" role="group" aria-label="Layout">
            <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}
              class="rounded-md px-3 py-1 text-xs font-bold transition aria-pressed:bg-white aria-pressed:text-brand-600 aria-pressed:shadow-sm dark:aria-pressed:bg-[#2c2c2e]">Table</button>
            <button type="button" aria-pressed={view === "cards"} onClick={() => setView("cards")}
              class="rounded-md px-3 py-1 text-xs font-bold transition aria-pressed:bg-white aria-pressed:text-brand-600 aria-pressed:shadow-sm dark:aria-pressed:bg-[#2c2c2e]">Cards</button>
          </div>
          <a class="glass-button !px-4 !py-1.5" href={sharePointUrl} target="_blank" rel="noopener noreferrer" title="Opens the team's SharePoint folder">
            <UploadIcon /> Upload to SharePoint
          </a>
        </div>
        <div class="grid grid-cols-2 items-center gap-2 sm:grid-cols-[repeat(4,1fr)_auto]">
          <Select label="Tech domain" all="All" value={domain} onChange={setDomain} options={TECH_DOMAINS} />
          <Select label="Cloud / platform" all="All" value={cloud} onChange={setCloud} options={CLOUD_PLATFORMS} />
          <Select label="Industry" all="All" value={vertical} onChange={setVertical} options={INDUSTRY_VERTICALS} />
          <Select label="Format" all="All" value={format} onChange={setFormat} options={HUB_FORMATS} />
          <span class="flex items-center gap-3 whitespace-nowrap pl-1.5 text-[12.5px] font-semibold">
            <span><b class="font-bold">{visible.length}</b> of {articles.length} articles</span>
            {filtering && <button type="button" class="font-semibold text-brand-600 hover:underline dark:text-brand-400" onClick={reset}>Reset</button>}
          </span>
        </div>
      </div>

      {articles.length === 0 ? (
        <div class="plain-panel px-8 py-10 text-center">
          <p class="text-lg font-semibold">No articles yet</p>
          <p class="mt-2 text-ink-muted dark:text-[#a1a1a6]">Be the first to share what your team learned.</p>
        </div>
      ) : visible.length === 0 ? (
        <div class="plain-panel px-6 py-14 text-center"><p class="text-lg font-semibold">No matching articles</p><p class="mt-1 text-sm text-ink-muted dark:text-[#a1a1a6]">Try other filters or search words.</p></div>
      ) : view === "table" ? (
        <div class="plain-panel overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-[13px]">
              <thead class="border-b border-slate-300/70 bg-gradient-to-b from-white/70 to-white/20 text-[11px] font-bold uppercase tracking-wider text-slate-900 dark:border-white/15 dark:from-white/10 dark:to-white/0 dark:text-slate-200">
                <tr>
                  <th class="min-w-[92px] px-3.5 py-3">Date</th>
                  <th class="min-w-[180px] px-3.5 py-3">Article</th>
                  <th class="min-w-[200px] px-3.5 py-3">Summary</th>
                  <th class="min-w-[110px] px-3.5 py-3">Tech domain</th>
                  <th class="min-w-[90px] px-3.5 py-3">Cloud / platform</th>
                  <th class="min-w-[90px] px-3.5 py-3">Industry</th>
                  <th class="min-w-[70px] px-3.5 py-3">Format</th>
                  <th class="min-w-[80px] px-3.5 py-3">Open</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-300/50 dark:divide-white/10">
                {visible.map((a) => (
                  <tr key={a.id} class="transition-colors hover:bg-white/60 dark:hover:bg-white/5">
                    <td class="whitespace-nowrap px-3.5 py-3 align-top text-[12px] font-semibold">{dayText(a.publishedAt)}</td>
                    <td class="px-3.5 py-3 align-top">
                      <p class="font-bold text-slate-900 dark:text-white">{a.title}</p>
                      <p class="mt-0.5 text-[12px] font-medium text-slate-700 dark:text-slate-400">{a.author} · {a.team}</p>
                    </td>
                    <td class="px-3.5 py-3 align-top leading-relaxed text-slate-900 dark:text-slate-300">{a.summary || "—"}</td>
                    <td class="px-3.5 py-3 align-top"><span class={`inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-bold ${domainTone(a.techDomain)}`}>{a.techDomain}</span></td>
                    <td class="px-3.5 py-3 align-top">{toneChip(a.cloudPlatform, CLOUD_TONE)}</td>
                    <td class="px-3.5 py-3 align-top">{toneChip(a.industryVertical, INDUSTRY_TONE)}</td>
                    <td class="px-3.5 py-3 align-top">{chip(FORMAT_LABEL[a.format] ?? a.format)}</td>
                    <td class="px-3.5 py-3 align-top">
                      <a class="font-bold text-brand-700 hover:underline dark:text-brand-400" href={a.url} target="_blank" rel="noopener noreferrer">
                        Read ↗
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((a) => (
            <article key={a.id} class="plain-panel group relative flex flex-col p-5 transition duration-300 hover:-translate-y-0.5">
              <div class="mb-3 flex flex-wrap items-center gap-1.5">
                <span class={`rounded-md px-2 py-0.5 text-[11px] font-bold ${domainTone(a.techDomain)}`}>{a.techDomain}</span>
                {toneChip(a.cloudPlatform, CLOUD_TONE)}{toneChip(a.industryVertical, INDUSTRY_TONE)}
                <span class="ml-auto text-[12px] font-semibold">{dayText(a.publishedAt)}</span>
              </div>
              <h3 class="text-[16px] font-semibold leading-snug tracking-[-0.015em]">
                <a href={a.url} target="_blank" rel="noopener noreferrer" class="after:absolute after:inset-0 group-hover:text-brand-600 dark:group-hover:text-brand-400">{a.title}</a>
              </h3>
              <p class="mt-2 line-clamp-3 text-sm leading-relaxed text-slate-900 dark:text-slate-300">{a.summary}</p>
              <div class="mt-auto flex items-center justify-between pt-4 text-[12px]">
                <span class="text-ink-muted dark:text-[#a1a1a6]">{a.author} · {a.team}</span>
                {chip(FORMAT_LABEL[a.format] ?? a.format)}
              </div>
            </article>
          ))}
        </div>
      )}

      <p class="mt-5 text-center text-[13px] text-ink-muted dark:text-[#a1a1a6]">
        Built something worth sharing? Put it in the{" "}
        <a class="font-semibold text-brand-600 hover:underline dark:text-brand-400" href={sharePointUrl} target="_blank" rel="noopener noreferrer">team's SharePoint folder</a>{" "}
        (HTML or PDF).
      </p>
    </div>
  );
}
