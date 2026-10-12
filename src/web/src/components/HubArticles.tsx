// R&D Hub (runs in the browser): the article feed, laid out like the R&D Ideas page: a control
// bar (search, table/cards switch, four filters, count and reset) above a table or a card grid.
// Uploading is quiet: a SharePoint link at the top right and a line at the bottom. A second,
// smaller route adds an article through a GitHub pull request (the pop-up below).
import { useMemo, useState } from "preact/hooks";
import {
  CLOUD_PLATFORMS, HUB_FORMATS, INDUSTRY_VERTICALS, TECH_DOMAINS, type HubCard,
} from "../lib/hubTypes";

interface Props {
  articles: HubCard[];
  sharePointUrl: string;
  uploadUrl: string;
}

const MAX_BYTES = 5 * 1024 * 1024;
const FORMAT_LABEL: Record<string, string> = { html: "HTML", pdf: "PDF" };

const DOMAIN_TONE: Record<string, string> = {
  "Agentic AI": "border-purple-300/80 bg-purple-100/80 text-purple-900 dark:border-purple-400/40 dark:bg-purple-400/15 dark:text-purple-200",
  "GenAI": "border-blue-300/80 bg-blue-100/80 text-blue-900 dark:border-blue-400/40 dark:bg-blue-400/15 dark:text-blue-200",
  "Industry Application": "border-orange-300/80 bg-orange-100/80 text-orange-900 dark:border-orange-400/40 dark:bg-orange-400/15 dark:text-orange-200",
  "Cloud AI/ML": "border-emerald-300/80 bg-emerald-100/80 text-emerald-900 dark:border-emerald-400/40 dark:bg-emerald-400/15 dark:text-emerald-200",
};
const domainTone = (d: string) =>
  `border ${DOMAIN_TONE[d] ?? "border-slate-300/80 bg-white/70 text-slate-900 dark:border-white/20 dark:bg-white/10 dark:text-slate-200"}`;

const dayText = (iso: string) => iso.slice(0, 10);

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></svg>
  );
}

function Select({ label, value, onChange, options, all }: {
  label: string; value: string; onChange: (v: string) => void; options: readonly string[]; all: string;
}) {
  return (
    <label class="block">
      <span class="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-900 dark:text-slate-200">{label}</span>
      <select class="plain-field" value={value} onChange={(e) => onChange((e.target as HTMLSelectElement).value)}>
        <option value="All">{all}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function GitHubDialog({ uploadUrl, onClose }: { uploadUrl: string; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [f, setF] = useState({ title: "", team: "", author: "", tags: "", summary: "", domain: "GenAI", cloud: "Other", vertical: "Cross-industry" });
  const [copied, setCopied] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });

  const pickFile = (picked: File | undefined) => {
    setFile(null);
    setFileError("");
    if (!picked) return;
    if (!/\.(html|pdf)$/i.test(picked.name)) return setFileError("Only .html and .pdf files are accepted.");
    if (picked.size > MAX_BYTES) return setFileError("That file is over 5 MB.");
    setFile(picked);
  };

  const ready = Boolean(file && f.title.trim() && f.team.trim() && f.author.trim());
  const details = [
    `Title: ${f.title}`, `Team: ${f.team}`, `Author: ${f.author}`, `Tags: ${f.tags}`, `Summary: ${f.summary}`,
    `Domain: ${f.domain}`, `Cloud: ${f.cloud}`, `Vertical: ${f.vertical}`,
  ].join("\n");
  const next = async () => {
    try { await navigator.clipboard.writeText(details); setCopied(true); } catch {}
    window.open(uploadUrl, "_blank", "noopener");
  };
  const text = (label: string, key: keyof typeof f, placeholder = "") => (
    <label class="block text-[13px] font-semibold">
      {label}
      <input class="field mt-1 w-full font-normal" value={f[key]} placeholder={placeholder}
        onInput={(e) => set(key)((e.target as HTMLInputElement).value)} />
    </label>
  );
  const pick = (label: string, key: keyof typeof f, options: readonly string[]) => (
    <label class="block text-[13px] font-semibold">
      {label}
      <select class="field mt-1 w-full font-normal" value={f[key]} onChange={(e) => set(key)((e.target as HTMLSelectElement).value)}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
  const step = "mt-5 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-muted dark:text-[#a1a1a6]";

  return (
    <div class="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Add an article through GitHub"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="card max-h-[92vh] w-full max-w-lg overflow-y-auto p-6">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-semibold">Add an article through GitHub</h2>
          <button type="button" class="icon-button" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <p class="mt-1 text-sm text-ink-muted dark:text-[#a1a1a6]">
          Three quick steps. The file itself is added on GitHub in step 3 (it needs a free GitHub account). Published articles are public.
        </p>

        <h3 class={step}>1 · Choose your file</h3>
        <label class="mt-2 block cursor-pointer rounded-2xl border-2 border-dashed border-brand-400/60 bg-brand-500/[0.07] px-4 py-5 text-center text-sm">
          <input type="file" accept=".html,.pdf" class="sr-only" onChange={(e) => pickFile((e.target as HTMLInputElement).files?.[0])} />
          {file ? (
            <span><b>{file.name}</b> · {(file.size / 1024 / 1024).toFixed(1)} MB <span class="ml-1 text-brand-600 dark:text-brand-400">Change</span></span>
          ) : (
            <span><b class="text-brand-600 dark:text-brand-400">Choose an HTML or PDF file</b><br /><span class="text-xs text-ink-muted dark:text-[#a1a1a6]">up to 5 MB</span></span>
          )}
        </label>
        {fileError && <p class="mt-1 text-xs font-medium text-red-600 dark:text-red-400">{fileError}</p>}

        <h3 class={step}>2 · Tell us about it</h3>
        <div class="mt-2 grid gap-3">
          {text("Title", "title", "How we cut RAG latency 40%")}
          <div class="grid gap-3 sm:grid-cols-2">{text("Team", "team", "Platform Team")}{text("Author", "author", "Your name")}</div>
          <div class="grid gap-3 sm:grid-cols-3">
            {pick("Tech domain", "domain", TECH_DOMAINS)}
            {pick("Cloud / platform", "cloud", CLOUD_PLATFORMS)}
            {pick("Industry", "vertical", INDUSTRY_VERTICALS)}
          </div>
          {text("Tags (comma separated)", "tags", "RAG, latency")}
          {text("One-line summary", "summary", "What the article shows")}
        </div>

        <h3 class={step}>3 · Add it on GitHub</h3>
        <p class="mt-2 text-sm text-ink-muted dark:text-[#a1a1a6]">
          GitHub opens in a new tab. Drag <b>{file ? file.name : "your file"}</b> into the page, choose <i>Create a new branch and start a pull request</i>, then <b>paste</b> the details we copied into the description. A reviewer approves it and it appears here.
        </p>
        <button type="button" class="glass-button mt-4 disabled:cursor-not-allowed disabled:opacity-50" disabled={!ready} onClick={next}>
          Copy details &amp; open GitHub
        </button>
        {!ready && <p class="mt-2 text-xs text-ink-muted dark:text-[#a1a1a6]">Choose a file and fill in title, team and author to continue.</p>}
        {copied && <p class="mt-2 text-xs text-emerald-600 dark:text-emerald-400">Details copied to your clipboard. Paste them into the pull request description.</p>}
      </div>
    </div>
  );
}

export default function HubArticles({ articles, sharePointUrl, uploadUrl }: Props) {
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState("All");
  const [cloud, setCloud] = useState("All");
  const [vertical, setVertical] = useState("All");
  const [format, setFormat] = useState("All");
  const [view, setView] = useState<"table" | "cards">("table");
  const [github, setGithub] = useState(false);

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
      <div class="mb-5 flex flex-wrap items-center justify-end gap-3">
        <button type="button" class="text-[13px] font-medium text-ink-muted hover:underline dark:text-[#a1a1a6]" onClick={() => setGithub(true)}>
          or add through GitHub
        </button>
        <a class="glass-button !px-4 !py-2" href={sharePointUrl} target="_blank" rel="noopener noreferrer" title="Opens the team's SharePoint folder">
          <UploadIcon /> Upload to SharePoint
        </a>
      </div>

      {/* Control bar: search, view switch, four filters, count and reset */}
      <div class="plain-panel mb-5 flex flex-col gap-3 p-4">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input class="plain-field flex-1" type="search" placeholder="Search articles, authors, topics…" value={search}
            onInput={(e) => setSearch((e.target as HTMLInputElement).value)} />
          <div class="flex rounded-lg border border-slate-300/80 bg-white/60 p-0.5 dark:border-white/15 dark:bg-white/10" role="group" aria-label="Layout">
            <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}
              class="rounded-md px-3 py-1 text-xs font-bold transition aria-pressed:bg-white aria-pressed:text-brand-600 aria-pressed:shadow-sm dark:aria-pressed:bg-[#2c2c2e]">Table</button>
            <button type="button" aria-pressed={view === "cards"} onClick={() => setView("cards")}
              class="rounded-md px-3 py-1 text-xs font-bold transition aria-pressed:bg-white aria-pressed:text-brand-600 aria-pressed:shadow-sm dark:aria-pressed:bg-[#2c2c2e]">Cards</button>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Select label="Tech domain" all="All domains" value={domain} onChange={setDomain} options={TECH_DOMAINS} />
          <Select label="Cloud / platform" all="All platforms" value={cloud} onChange={setCloud} options={CLOUD_PLATFORMS} />
          <Select label="Industry vertical" all="All verticals" value={vertical} onChange={setVertical} options={INDUSTRY_VERTICALS} />
          <Select label="Format" all="All formats" value={format} onChange={setFormat} options={HUB_FORMATS} />
        </div>
        <div class="flex items-center justify-between text-[13px] font-medium">
          <span class="font-semibold">Showing <b class="font-bold">{visible.length}</b> of {articles.length} articles</span>
          {filtering && <button type="button" class="font-semibold text-brand-600 hover:underline dark:text-brand-400" onClick={reset}>Reset filters</button>}
        </div>
      </div>

      {articles.length === 0 ? (
        <div class="plain-panel px-8 py-16 text-center">
          <p class="text-lg font-semibold">No articles yet</p>
          <p class="mt-2 text-ink-muted dark:text-[#a1a1a6]">Be the first to share what your team learned.</p>
          <a class="glass-button mt-4" href={sharePointUrl} target="_blank" rel="noopener noreferrer"><UploadIcon /> Upload to SharePoint</a>
        </div>
      ) : visible.length === 0 ? (
        <div class="plain-panel px-6 py-14 text-center"><p class="text-lg font-semibold">No matching articles</p><p class="mt-1 text-sm text-ink-muted dark:text-[#a1a1a6]">Try other filters or search words.</p></div>
      ) : view === "table" ? (
        <div class="plain-panel overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-[13px]">
              <thead class="border-b border-slate-300/70 bg-gradient-to-b from-white/70 to-white/20 text-[11px] font-bold uppercase tracking-wider text-slate-900 dark:border-white/15 dark:from-white/10 dark:to-white/0 dark:text-slate-200">
                <tr>
                  <th class="min-w-[92px] px-3 py-3">Date</th>
                  <th class="min-w-[180px] px-3 py-3">Article</th>
                  <th class="min-w-[200px] px-3 py-3">Summary</th>
                  <th class="min-w-[110px] px-3 py-3">Tech domain</th>
                  <th class="min-w-[90px] px-3 py-3">Cloud / platform</th>
                  <th class="min-w-[90px] px-3 py-3">Industry</th>
                  <th class="min-w-[70px] px-3 py-3">Format</th>
                  <th class="min-w-[80px] px-3 py-3">Open</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-300/50 dark:divide-white/10">
                {visible.map((a) => (
                  <tr key={a.id} class="transition-colors hover:bg-white/60 dark:hover:bg-white/5">
                    <td class="whitespace-nowrap px-3 py-3 align-top text-[12px] font-semibold">{dayText(a.publishedAt)}</td>
                    <td class="px-3 py-3 align-top">
                      <p class="font-bold text-slate-900 dark:text-white">{a.title}</p>
                      <p class="mt-0.5 text-[12px] font-medium text-slate-700 dark:text-slate-400">{a.author} · {a.team}</p>
                    </td>
                    <td class="px-3 py-3 align-top leading-relaxed text-slate-900 dark:text-slate-300">{a.summary || "—"}</td>
                    <td class="px-3 py-3 align-top"><span class={`inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-bold ${domainTone(a.techDomain)}`}>{a.techDomain}</span></td>
                    <td class="px-3 py-3 align-top">{chip(a.cloudPlatform)}</td>
                    <td class="px-3 py-3 align-top">{chip(a.industryVertical)}</td>
                    <td class="px-3 py-3 align-top">{chip(FORMAT_LABEL[a.format] ?? a.format)}</td>
                    <td class="px-3 py-3 align-top">
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
                {chip(a.cloudPlatform)}{chip(a.industryVertical)}
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

      <p class="mt-12 text-center text-[13px] text-ink-muted dark:text-[#a1a1a6]">
        Built something worth sharing? Put it in the{" "}
        <a class="font-semibold text-brand-600 hover:underline dark:text-brand-400" href={sharePointUrl} target="_blank" rel="noopener noreferrer">team's SharePoint folder</a>{" "}
        (HTML or PDF), or{" "}
        <button type="button" class="font-semibold text-brand-600 hover:underline dark:text-brand-400" onClick={() => setGithub(true)}>add it through GitHub</button>.
      </p>

      {github && <GitHubDialog uploadUrl={uploadUrl} onClose={() => setGithub(false)} />}
    </div>
  );
}
