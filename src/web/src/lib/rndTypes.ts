// Shared client/server types and dropdown options for Ganit R&D Idea Radar
// Populated purely from AI crawling & summarization of news, papers & releases

export interface RndIdea {
  id: string;
  topic: string;
  summary: string;
  techDomain: string;
  cloudPlatform: string;
  industryVertical: string;
  sourceType: string;
  link: string;
  date?: string;
  buildEffort?: "Low" | "Medium" | "High";
  decision?: "Build" | "Prototype" | "Benchmark" | "Experiment" | "Article-only" | "Shelved" | "Pending";
  category?: string;
  researcher?: string;
}

export const CATEGORIES = [
  "New OCR",
  "New STT",
  "New TTS",
  "New Models",
  "New Repos",
  "BFSI Solutions",
  "New Skills",
] as const;

export const TECH_DOMAINS = [
  "Agentic AI",
  "GenAI",
  "Cloud AI/ML",
  "Industry Application",
  "Other",
] as const;

export const CLOUD_PLATFORMS = [
  "AWS",
  "Azure",
  "GCP",
  "OpenAI",
  "Anthropic",
  "Open-source",
  "Cross-cloud",
  "Other",
] as const;

export const INDUSTRY_VERTICALS = [
  "BFSI",
  "Healthcare",
  "Retail",
  "Manufacturing",
  "Cross-industry",
  "Other",
] as const;

export const SOURCE_TYPES = [
  "Directed (Radar/Topics page)",
  "Emergent (Signal)",
  "AI-assisted (Claude/MCP)",
] as const;

export const BUILD_EFFORTS = [
  "High",
  "Medium",
  "Low",
] as const;

export const DECISIONS = [
  "Build",
  "Prototype",
  "Benchmark",
  "Experiment",
  "Article-only",
  "Pending",
] as const;
