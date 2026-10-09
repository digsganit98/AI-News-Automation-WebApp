// R&D Hub (runs in the browser): articles written by our own teams, with search and filters.
// Uploading is deliberately quiet: a small button at the top right and a line at the bottom
// open a pop-up that explains how to add an article (a GitHub pull request).
import { useMemo, useState } from "preact/hooks";

export interface HubCard {
  id: string;
  title: string;
  summary: string;
  author: string;
  team: string;
  tags: string[];
  format: "html" | "pdf";
  url: string;
  publishedAt: string;
}

interface Props {
  articles: HubCard[];
  featuredId?: string;
  uploadUrl: string;
}

const initials = (name: string) => name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
const dayText = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function UploadButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" class="glass-button !px-4 !py-2" onClick={onClick} title="Upload an article">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></svg>
      Upload
    </button>
  );
}

function UploadDialog({ uploadUrl, onClose }: { uploadUrl: string; onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [team, setTeam] = useState("");
  const [author, setAuthor] = useState("");
  const [tags, setTags] = useState("");
  const [copied, setCopied] = useState(false);

  const details = [`Title: ${title}`, `Team: ${team}`, `Author: ${author}`, `Tags: ${tags}`].join("\n");
  const next = async () => {
    try { await navigator.clipboard.writeText(details); setCopied(true); } catch {}
    window.open(uploadUrl, "_blank", "noopener");
  };
  const input = (label: string, value: string, set: (v: string) => void, placeholder = "") => (
    <label class="block text-[13px] font-semibold">
      {label}
      <input class="field mt-1 w-full font-normal" value={value} placeholder={placeholder}
        onInput={(e) => set((e.target as HTMLInputElement).value)} />
    </label>
  );

  return (
    <div class="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Upload an article"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="card max-h-[90vh] w-full max-w-lg overflow-y-auto p-6">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-semibold">Upload an article</h2>
          <button type="button" class="icon-button" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <p class="mt-2 text-sm text-ink-muted dark:text-[#a1a1a6]">
          Share an <b>HTML</b> or <b>PDF</b> file (up to 5 MB). Fill in the details, then add the file on GitHub, which opens a pull request. Automatic checks run, a reviewer approves, and the article appears here. Published articles are public.
        </p>
        <div class="mt-4 grid gap-3">
          {input("Title", title, setTitle, "How we cut RAG latency 40%")}
          <div class="grid gap-3 sm:grid-cols-2">
            {input("Team", team, setTeam, "Platform Team")}
            {input("Author", author, setAuthor, "Your name")}
          </div>
          {input("Tags (comma separated)", tags, setTags, "RAG, latency")}
        </div>
        <button type="button" class="glass-button mt-5" onClick={next}>Copy details &amp; continue on GitHub</button>
        {copied && <p class="mt-2 text-xs text-ink-muted dark:text-[#a1a1a6]">Details copied. Paste them into the pull request description.</p>}
      </div>
    </div>
  );
}

export default function HubArticles({ articles, featuredId, uploadUrl }: Props) {
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("");
  const [format, setFormat] = useState("");
  const [tag, setTag] = useState("");
  const [uploading, setUploading] = useState(false);

  const teams = useMemo(() => [...new Set(articles.map((a) => a.team))].sort(), [articles]);
  const tags = useMemo(() => [...new Set(articles.flatMap((a) => a.tags))].sort(), [articles]);
  const featured = articles.find((a) => a.id === featuredId) ?? articles[0];

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return articles.filter(
      (a) =>
        (!team || a.team === team) &&
        (!format || a.format === format) &&
        (!tag || a.tags.includes(tag)) &&
        (!q || `${a.title} ${a.summary} ${a.author} ${a.team} ${a.tags.join(" ")}`.toLowerCase().includes(q)),
    );
  }, [articles, query, team, format, tag]);

  const filtering = Boolean(query.trim() || team || format || tag);

  return (
    <div>
      <div class="mb-6 flex justify-end">
        <UploadButton onClick={() => setUploading(true)} />
      </div>

      {articles.length === 0 ? (
        <div class="card px-8 py-16 text-center">
          <p class="text-lg font-semibold">No articles yet</p>
          <p class="mt-2 text-ink-muted dark:text-[#a1a1a6]">Be the first to share what your team learned.</p>
          <div class="mt-4"><UploadButton onClick={() => setUploading(true)} /></div>
        </div>
      ) : (
        <>
          {featured && !filtering && (
            <section class="mb-12" aria-label="Pick of the week">
              <article class="card relative flex flex-col p-6 sm:p-8">
                <p class="eyebrow !text-brand-600 dark:!text-brand-400">✦ Pick of the week</p>
                <h2 class="mt-3 text-2xl font-semibold leading-[1.15] tracking-[-0.03em] sm:text-[32px]">
                  <a href={featured.url} target="_blank" rel="noopener" class="hover:text-brand-600 dark:hover:text-brand-400">{featured.title}</a>
                </h2>
                <p class="mt-2 text-sm text-ink-muted dark:text-[#a1a1a6]">{featured.author} · {featured.team} · {featured.format.toUpperCase()}</p>
                <p class="mt-4 max-w-3xl text-[15px] leading-relaxed text-slate-700 dark:text-slate-300">{featured.summary}</p>
                <div class="mt-5 flex flex-wrap items-center gap-2">
                  <a class="glass-button !py-2" href={featured.url} target="_blank" rel="noopener">Read article</a>
                  {featured.tags.map((t) => <span class="pill border-slate-200 text-ink-muted dark:border-white/15 dark:text-[#a1a1a6]">{t}</span>)}
                </div>
              </article>
            </section>
          )}

          <div class="mb-5 flex flex-wrap items-end justify-between gap-2">
            <h2 class="text-3xl font-semibold">All articles</h2>
            <p class="text-sm text-ink-muted dark:text-[#a1a1a6]">{visible.length} of {articles.length}, newest first</p>
          </div>
          <div class="card mb-4 flex flex-col gap-3 p-4">
            <div class="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
              <input class="field w-full" type="search" placeholder="Search articles, authors, teams…" value={query}
                onInput={(e) => setQuery((e.target as HTMLInputElement).value)} />
              <select class="field" aria-label="Team" value={team} onChange={(e) => setTeam((e.target as HTMLSelectElement).value)}>
                <option value="">All teams</option>
                {teams.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <select class="field" aria-label="Format" value={format} onChange={(e) => setFormat((e.target as HTMLSelectElement).value)}>
                <option value="">Any format</option><option value="html">HTML</option><option value="pdf">PDF</option>
              </select>
            </div>
            {tags.length > 0 && (
              <div class="flex flex-wrap gap-2">
                <button type="button" class="chip" aria-pressed={tag === ""} onClick={() => setTag("")}>All topics</button>
                {tags.map((t) => <button key={t} type="button" class="chip" aria-pressed={tag === t} onClick={() => setTag(tag === t ? "" : t)}>{t}</button>)}
              </div>
            )}
          </div>

          {visible.length === 0 ? (
            <div class="card px-6 py-14 text-center"><p class="text-lg font-semibold">Nothing matches these filters</p></div>
          ) : (
            <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((a) => (
                <article key={a.id} class="card group relative flex flex-col p-5 transition duration-300 hover:-translate-y-1">
                  <div class="mb-3 flex flex-wrap items-center gap-2 text-xs">
                    <span class="pill border-transparent bg-amber-400/20 text-amber-700 dark:text-amber-300">{a.team}</span>
                    <span class="pill border-slate-200 text-ink-muted dark:border-white/15 dark:text-[#a1a1a6]">{a.format.toUpperCase()}</span>
                    <span class="text-ink-muted dark:text-[#a1a1a6]">· {dayText(a.publishedAt)}</span>
                  </div>
                  <h3 class="text-[17px] font-semibold leading-snug tracking-[-0.02em]">
                    <a href={a.url} target="_blank" rel="noopener" class="after:absolute after:inset-0 group-hover:text-brand-600 dark:group-hover:text-brand-400">{a.title}</a>
                  </h3>
                  <p class="mt-2 line-clamp-3 text-sm leading-relaxed text-ink-muted dark:text-[#a1a1a6]">{a.summary}</p>
                  <div class="mt-auto flex items-center gap-2 pt-4 text-[13px]">
                    <span class="glass-tile grid size-7 place-items-center !rounded-full text-[11px] font-bold">{initials(a.author)}</span>
                    <span>{a.author}</span>
                    <span class="ml-auto text-xs font-medium text-brand-600 dark:text-brand-400">{a.tags[0]}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      <p class="mt-12 text-center text-[13px] text-ink-muted dark:text-[#a1a1a6]">
        Built something worth sharing?{" "}
        <button type="button" class="font-semibold text-brand-600 hover:underline dark:text-brand-400" onClick={() => setUploading(true)}>Upload an article</button>{" "}
        (HTML or PDF).
      </p>

      {uploading && <UploadDialog uploadUrl={uploadUrl} onClose={() => setUploading(false)} />}
    </div>
  );
}
