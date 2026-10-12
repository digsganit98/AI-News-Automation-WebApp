// R&D Hub: the article shape and the filter options. No Node imports, so the browser
// component (HubArticles.tsx) and the build-time loader (siteData.ts) can both use it.
// The columns follow the research log: Date · Researcher · Topic · Summary · Tech Domain ·
// Cloud / Platform · Industry Vertical · Source Type · Link.

export const HUB_FORMATS = ["html", "pdf"] as const;
export type HubFormat = (typeof HUB_FORMATS)[number];

export const TECH_DOMAINS = ["Agentic AI", "GenAI", "Cloud AI/ML", "Industry Application", "Other"] as const;
export const CLOUD_PLATFORMS = ["AWS", "Azure", "GCP", "OpenAI", "Anthropic", "Open-source", "Cross-cloud", "Other"] as const;
export const INDUSTRY_VERTICALS = ["BFSI", "Healthcare", "Retail", "Manufacturing", "Cross-industry", "Other"] as const;

/** One article as the R&D Hub page shows it. */
export interface HubCard {
  id: string;
  title: string;
  summary: string;
  author: string;
  team: string;
  tags: string[];
  format: HubFormat;
  techDomain: string;
  cloudPlatform: string;
  industryVertical: string;
  url: string;
  publishedAt: string;
}
