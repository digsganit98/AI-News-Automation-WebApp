import { useMemo, useState } from "preact/hooks";
import type { RndIdea } from "../lib/rndTypes";
import {
  TECH_DOMAINS,
  CLOUD_PLATFORMS,
  INDUSTRY_VERTICALS,
  SOURCE_TYPES,
} from "../lib/rndTypes";

interface Props {
  initialIdeas: RndIdea[];
}

export default function RndIdeaHub({ initialIdeas }: Props) {
  const [search, setSearch] = useState("");
  const [selectedDomain, setSelectedDomain] = useState<string>("All");
  const [selectedCloud, setSelectedCloud] = useState<string>("All");
  const [selectedVertical, setSelectedVertical] = useState<string>("All");
  const [selectedSourceType, setSelectedSourceType] = useState<string>("All");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");

  const filteredIdeas = useMemo(() => {
    const q = search.toLowerCase().trim();
    return initialIdeas.filter((item) => {
      if (selectedDomain !== "All" && item.techDomain !== selectedDomain) return false;
      if (selectedCloud !== "All" && item.cloudPlatform !== selectedCloud) return false;
      if (selectedVertical !== "All" && item.industryVertical !== selectedVertical) return false;
      if (selectedSourceType !== "All" && item.sourceType !== selectedSourceType) return false;

      if (!q) return true;
      const haystack = `${item.topic} ${item.summary} ${item.link}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [initialIdeas, search, selectedDomain, selectedCloud, selectedVertical, selectedSourceType]);

  const domainBadge = (d: string) => {
    switch (d) {
      case "Agentic AI":
        return "bg-purple-100 text-purple-900 border-purple-300";
      case "GenAI":
        return "bg-blue-100 text-[#1a00d9] border-blue-300";
      case "Industry Application":
        return "bg-orange-100 text-[#c25000] border-orange-300";
      case "Cloud AI/ML":
        return "bg-emerald-100 text-emerald-900 border-emerald-300";
      default:
        return "bg-slate-100 text-slate-900 border-slate-300";
    }
  };

  return (
    <div class="space-y-4">
      {/* Control Bar: Search & Filters */}
      <div class="rounded-xl border border-slate-300 bg-white p-3 sm:p-4 shadow-xs">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Search Box */}
          <div class="relative flex-1">
            <svg
              class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-600"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search ideas, topics, summary..."
              value={search}
              onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
              class="w-full rounded-lg border border-slate-400 bg-white py-1.5 pl-9 pr-3 text-xs font-medium text-slate-900 placeholder-slate-500 focus:border-[#1a00d9] focus:outline-none"
            />
          </div>

          {/* View Toggle */}
          <div class="flex rounded-lg border border-slate-300 bg-slate-100 p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("table")}
              class={`rounded-md px-3 py-1 text-xs font-bold transition ${
                viewMode === "table"
                  ? "bg-white text-[#1a00d9] shadow-xs"
                  : "text-slate-800 hover:text-slate-900"
              }`}
            >
              Table
            </button>
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              class={`rounded-md px-3 py-1 text-xs font-bold transition ${
                viewMode === "grid"
                  ? "bg-white text-[#1a00d9] shadow-xs"
                  : "text-slate-800 hover:text-slate-900"
              }`}
            >
              Cards
            </button>
          </div>
        </div>

        {/* 4 Dropdown Filters */}
        <div class="mt-3 grid grid-cols-2 gap-2 border-t border-slate-200 pt-3 sm:grid-cols-4">
          <div>
            <label class="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-900">
              Tech Domain
            </label>
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain((e.target as HTMLSelectElement).value)}
              class="w-full rounded-md border border-slate-300 bg-white py-1.5 pl-2 pr-6 text-xs font-semibold text-slate-900 focus:border-[#1a00d9] focus:outline-none"
            >
              <option value="All">All Domains</option>
              {TECH_DOMAINS.map((td) => (
                <option value={td}>{td}</option>
              ))}
            </select>
          </div>

          <div>
            <label class="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-900">
              Cloud / Platform
            </label>
            <select
              value={selectedCloud}
              onChange={(e) => setSelectedCloud((e.target as HTMLSelectElement).value)}
              class="w-full rounded-md border border-slate-300 bg-white py-1.5 pl-2 pr-6 text-xs font-semibold text-slate-900 focus:border-[#1a00d9] focus:outline-none"
            >
              <option value="All">All Platforms</option>
              {CLOUD_PLATFORMS.map((cp) => (
                <option value={cp}>{cp}</option>
              ))}
            </select>
          </div>

          <div>
            <label class="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-900">
              Industry Vertical
            </label>
            <select
              value={selectedVertical}
              onChange={(e) => setSelectedVertical((e.target as HTMLSelectElement).value)}
              class="w-full rounded-md border border-slate-300 bg-white py-1.5 pl-2 pr-6 text-xs font-semibold text-slate-900 focus:border-[#1a00d9] focus:outline-none"
            >
              <option value="All">All Verticals</option>
              {INDUSTRY_VERTICALS.map((iv) => (
                <option value={iv}>{iv}</option>
              ))}
            </select>
          </div>

          <div>
            <label class="mb-1 block text-[11px] font-bold uppercase tracking-wider text-slate-900">
              Source Type
            </label>
            <select
              value={selectedSourceType}
              onChange={(e) => setSelectedSourceType((e.target as HTMLSelectElement).value)}
              class="w-full rounded-md border border-slate-300 bg-white py-1.5 pl-2 pr-6 text-xs font-semibold text-slate-900 focus:border-[#1a00d9] focus:outline-none"
            >
              <option value="All">All Source Types</option>
              {SOURCE_TYPES.map((st) => (
                <option value={st}>{st}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Counter & Reset */}
        <div class="mt-2.5 flex items-center justify-between text-xs font-semibold text-slate-800">
          <span>
            Showing <strong class="text-slate-950 font-bold">{filteredIdeas.length}</strong> of {initialIdeas.length} ideas
          </span>
          {(selectedDomain !== "All" ||
            selectedCloud !== "All" ||
            selectedVertical !== "All" ||
            selectedSourceType !== "All" ||
            search) && (
            <button
              type="button"
              onClick={() => {
                setSelectedDomain("All");
                setSelectedCloud("All");
                setSelectedVertical("All");
                setSelectedSourceType("All");
                setSearch("");
              }}
              class="font-bold text-[#1a00d9] hover:underline"
            >
              Reset filters
            </button>
          )}
        </div>
      </div>

      {/* Main Table or Card View */}
      {filteredIdeas.length === 0 ? (
        <div class="rounded-xl border border-slate-300 bg-white p-10 text-center">
          <p class="text-base font-bold text-slate-900">No matching ideas found</p>
          <p class="mt-1 text-xs text-slate-700">Try adjusting your filters or search terms.</p>
        </div>
      ) : viewMode === "table" ? (
        /* TABLE VIEW - Strictly 7 columns */
        <div class="overflow-hidden rounded-xl border border-slate-300 bg-white shadow-xs">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="border-b border-slate-300 bg-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-900">
                <tr>
                  <th scope="col" class="min-w-[105px] px-4 py-3">
                    Date
                  </th>
                  <th scope="col" class="min-w-[200px] px-4 py-3">
                    Idea / Topic
                  </th>
                  <th scope="col" class="min-w-[320px] px-4 py-3">
                    Summary
                  </th>
                  <th scope="col" class="min-w-[130px] px-4 py-3">
                    Tech Domain
                  </th>
                  <th scope="col" class="min-w-[120px] px-4 py-3">
                    Cloud / Platform
                  </th>
                  <th scope="col" class="min-w-[120px] px-4 py-3">
                    Industry Vertical
                  </th>
                  <th scope="col" class="min-w-[140px] px-4 py-3">
                    Source Type
                  </th>
                  <th scope="col" class="min-w-[140px] px-4 py-3">
                    Link
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-200">
                {filteredIdeas.map((idea) => {
                  const isHttp = idea.link && /^https?:\/\//i.test(idea.link);
                  return (
                    <tr
                      key={idea.id}
                      class="hover:bg-slate-50 transition-colors"
                    >
                      {/* Date */}
                      <td class="px-4 py-3 align-top whitespace-nowrap font-bold text-slate-800 text-[11px]">
                        {idea.date || "—"}
                      </td>

                      {/* 1. Idea / Topic */}
                      <td class="px-4 py-3 align-top font-bold text-slate-900">
                        {idea.topic}
                      </td>

                      {/* 2. Summary */}
                      <td class="px-4 py-3 align-top leading-relaxed text-slate-900 font-normal">
                        {idea.summary}
                      </td>

                      {/* 3. Tech Domain */}
                      <td class="px-4 py-3 align-top whitespace-nowrap">
                        <span
                          class={`inline-block rounded-md border px-2 py-0.5 text-[11px] font-bold ${domainBadge(
                            idea.techDomain
                          )}`}
                        >
                          {idea.techDomain}
                        </span>
                      </td>

                      {/* 4. Cloud / Platform */}
                      <td class="px-4 py-3 align-top whitespace-nowrap">
                        <span class="inline-block rounded-md border border-slate-300 bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-900">
                          {idea.cloudPlatform}
                        </span>
                      </td>

                      {/* 5. Industry Vertical */}
                      <td class="px-4 py-3 align-top whitespace-nowrap">
                        <span class="inline-block rounded-md border border-slate-300 bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-900">
                          {idea.industryVertical}
                        </span>
                      </td>

                      {/* 6. Source Type */}
                      <td class="px-4 py-3 align-top text-xs font-medium text-slate-800">
                        {idea.sourceType}
                      </td>

                      {/* 7. Link */}
                      <td class="px-4 py-3 align-top">
                        {isHttp ? (
                          <a
                            href={idea.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="inline-flex max-w-[160px] items-center gap-1 truncate font-bold text-[#1a00d9] hover:underline"
                            title={idea.link}
                          >
                            <span>{idea.link.replace(/^https?:\/\/(www\.)?/, "")}</span>
                            <svg class="size-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        ) : (
                          <span class="text-slate-600 font-medium">{idea.link || "—"}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* CARD VIEW */
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filteredIdeas.map((idea) => {
            const isHttp = idea.link && /^https?:\/\//i.test(idea.link);
            return (
              <div
                key={idea.id}
                class="flex flex-col rounded-xl border border-slate-300 bg-white p-4 shadow-xs transition hover:border-slate-400"
              >
                <div class="mb-2 flex flex-wrap items-center gap-1.5">
                  <span
                    class={`rounded-md border px-2 py-0.5 text-[10px] font-bold ${domainBadge(
                      idea.techDomain
                    )}`}
                  >
                    {idea.techDomain}
                  </span>
                  {idea.cloudPlatform && (
                    <span class="rounded-md border border-slate-300 bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-900">
                      {idea.cloudPlatform}
                    </span>
                  )}
                  {idea.industryVertical && (
                    <span class="rounded-md border border-slate-300 bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-900">
                      {idea.industryVertical}
                    </span>
                  )}
                  {idea.date && (
                    <span class="ml-auto text-[11px] font-bold text-slate-800">
                      {idea.date}
                    </span>
                  )}
                </div>

                <h3 class="text-sm font-bold text-slate-900">
                  {idea.topic}
                </h3>

                <p class="mt-2 line-clamp-3 text-xs leading-relaxed text-slate-900">
                  {idea.summary}
                </p>

                <div class="mt-auto flex items-center justify-between border-t border-slate-200 pt-3 text-xs font-semibold mt-3">
                  <span class="text-slate-700">{idea.sourceType}</span>
                  {isHttp ? (
                    <a
                      href={idea.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="font-bold text-[#1a00d9] hover:underline"
                    >
                      Open ↗
                    </a>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

