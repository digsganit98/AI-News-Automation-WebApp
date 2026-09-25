# GenAI Daily

[![CI](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/ci.yml/badge.svg)](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/ci.yml)
[![News pipeline](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/newsPipeline.yml/badge.svg)](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/newsPipeline.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**All the new things in Generative AI, in one place, written up by AI agents that check their sources.**

**🌐 Live site: <https://digsganit98.github.io/AI-News-Automation-WebApp/>**

Every 3 hours, GenAI Daily reads 30 sources (AI labs, cloud platforms, research papers, Hacker News, Reddit, YouTube, newsletters and web search). AI agents keep what's genuinely new and write it up in plain language. Every morning at 10:00 IST they also write a **daily digest** and a short **op-ed**. It runs for free on GitHub, even when your computer is off.

| At a glance | |
|---|---|
| Sources | **30**: 11 labs and research blogs, 4 cloud platforms, arXiv, Hacker News, Reddit, YouTube, 6 newsletters, web search. X is coming next. |
| Updates | Every **3 hours**; daily edition at **10:00 IST** |
| AI agents | **9**: 6 scouts, an analyst, a writer and an editor (built with LangGraph) |
| LLM calls | About **80–100 a day**, hard cap **150** (all free tiers: Groq and Google Gemini) |
| Quality | Links are checked in code, the editor checks facts against the original articles, and the test set scores **100/100** |
| Monitoring | Every LLM call and every run is traced and scored in **Langfuse** |
| Cost | **$0** |

---

## Contents

- [What you get](#what-you-get)
- [How it works](#how-it-works)
- [How we keep the AI honest](#how-we-keep-the-ai-honest)
- [Use it](#use-it)
- [Run your own copy](#run-your-own-copy)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License and credits](#license-and-credits)

## What you get

- **Latest:** every story the agents picked, ranked by importance, with a plain-English summary, "why it matters", the sources, and "Go deeper" links to the paper, code or model. Below that, everything collected, with filters and search.
- **Digest:** the daily digest and op-ed (from 10:00 IST).
- **Research log:** one row per development, with the columns *Date · Researcher · Idea / Topic · Summary · Tech Domain · Cloud / Platform · Industry Vertical · Source Type · Link*. It can be downloaded as a **CSV**.
- **Sources:** which sources worked in the last run.
- **Archive** (calendar icon, top right): the last 5 days.
- Light and dark mode, and it works on phones.

## How it works

![Architecture: 30 sources feed Python collectors on GitHub Actions. After removing duplicates, an MCP server gives 9 LangGraph agents read-only tools. Scouts run on Qwen via Groq, the analyst and editor on gpt-oss-120b via Groq, and the writer on Gemini Flash. Results are saved to the repo, published to the website every 3 hours, and traced in Langfuse.](docs/images/architecture.svg)

**Every 3 hours** a GitHub Actions job:

1. **Collects** new posts from all sources and removes anything seen before. Tutorial videos, ads and non-AI cloud news are filtered out by title.
2. **Scouts** (6 AI agents, one per source group) decide what's real news and read the full article for the most important items, using the MCP `fetchArticle` tool.
3. **The analyst** merges the same news from different sources into one story, checks it against the last 7 days, and sorts and scores it.
4. **The website** is rebuilt with the new stories.

**At 10:00 IST** it also runs:

5. **The writer**, which drafts the digest and a ~600-word op-ed.
6. **The editor**, which re-reads the original articles and fact-checks both. The writer fixes anything flagged, once.

| Agent | LLM (free tier) | Runs |
|---|---|---|
| 6 scouts: labs & research · cloud & platforms · community · video, newsletters & blogs · X · web search | Qwen 3.8 27B on Groq | every 3 h |
| Analyst | gpt-oss-120b on Groq | every 3 h |
| Writer | Gemini Flash | 10:00 IST |
| Editor | gpt-oss-120b on Groq | 10:00 IST |

If a model is busy or out of quota, the next one in [`config/agents.yaml`](config/agents.yaml) takes over. A daily budget keeps calls within the free tiers and saves 25 calls for the 10:00 edition.

**Source Type** (research log): **Directed** means official labs, research and cloud sources. **Emergent** means spotted on Hacker News, Reddit, YouTube or newsletters. **AI-assisted** means found by the web-search scout, which also covers LinkedIn, X, YC and Coimbatore news through search results.

## How we keep the AI honest

- **The AI can't invent links.** Agents refer to items by number (`i1`, `i2`…); the code attaches every URL. Any link that isn't in the collected data is removed and counted as a "hallucination catch".
- **The editor checks the original,** not a summary: it re-fetches the source article for every story the digest and op-ed use.
- **Scraped text is treated as data.** It's fenced off, so instructions hidden in a web page are ignored.
- **A test set measures it.** `uv run digest eval` runs the real agents on 20 saved cases, including tutorials to drop, fake claims, two prompt-injection traps and a planted wrong number. It scores 6 checks (keep/drop accuracy, numbers found in the source, duplicates merged, traps ignored, no invented links, editor catches the error). The current score is **100/100**.
- **Everything is visible in Langfuse:** each run, each agent and each LLM call, with tokens and errors, plus scores such as stories, failed calls, editor approval and hallucination catches.

## Use it

**Read it:** open the [live site](https://digsganit98.github.io/AI-News-Automation-WebApp/).

**Run it on your computer.** You need [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Node.js 20+](https://nodejs.org/en/download). No admin rights? Use Node's zip download and add its folder to your `PATH`.

```bash
git clone https://github.com/digsganit98/AI-News-Automation-WebApp.git
cd AI-News-Automation-WebApp
uv sync                               # install the Python pipeline
cp .env.example .env                  # then add your keys (see below)

uv run digest collect --dry-run       # collect news and print it (saves nothing)
uv run digest run --dry-run           # collect + AI agents (needs LLM keys)
uv run digest eval                    # score the agents on the test set

cd src/web && npm install && npm run dev
# open http://localhost:4321/AI-News-Automation-WebApp/
```

**Try the agents' tools in a browser (MCP Inspector):**

```bash
npx @modelcontextprotocol/inspector uv run digest mcp
```

You can also add them to Claude Desktop or Claude Code: the server command is `uv --directory <repo folder> run digest mcp`.

## Run your own copy

It takes about 15 minutes, and everything is free.

1. **Fork** this repository and keep it **public** (that makes GitHub Actions free).
2. **Actions tab:** enable workflows.
3. **Settings → Pages → Source: GitHub Actions.**
4. **Settings → Secrets and variables → Actions:** add these secrets.

   | Secret | Needed for | Get it free at |
   |---|---|---|
   | `GROQ_API_KEY` | the AI agents | <https://console.groq.com/keys> |
   | `GEMINI_API_KEY` | the writer, and fallback | <https://aistudio.google.com/apikey> |
   | `TAVILY_API_KEY` | the web-search scout | <https://tavily.com> |
   | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | monitoring (optional) | <https://cloud.langfuse.com> |
   | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | newsletters (optional) | [docs/gmailInboxSetup.md](docs/gmailInboxSetup.md) |
   | `YOUTUBE_API_KEY` | backup when YouTube's feed is down (optional) | Google Cloud Console |

5. In [`config/app.env`](config/app.env), set `SITE_URL`, `SITE_BASE_PATH` and `PROJECT_URL` to your own GitHub account and repository.
6. **Actions → News pipeline → Run workflow.** Your site goes live at `https://<you>.github.io/<repo>/`.

Anything whose key is missing is simply skipped. Without any LLM keys, for example, the site still shows everything collected.

## Configuration

| File | What's in it |
|---|---|
| [`config/app.env`](config/app.env) | Every URL and non-secret setting (committed to git) |
| [`config/sources.yaml`](config/sources.yaml) | The sources: add or pause one without code; `titleFilter` and `maxItems` keep busy feeds small |
| [`config/agents.yaml`](config/agents.yaml) | Which model each agent uses, the fallbacks, and the daily budget |
| `.env` (copy of [`.env.example`](.env.example)) | Your secrets for local runs. Never commit it. |

Priority when the same setting is in several places: environment variable or GitHub secret, then `.env`, then `config/app.env`.

**Add a source:** put its feed URL in `config/app.env`, then copy a block in `config/sources.yaml` and give it a new `id`, `group` and `icon`. Check it with `uv run digest collect --dry-run`.

## Project structure

```
config/            app.env · sources.yaml · agents.yaml
src/digest/        Python pipeline (camelCase module names)
  collectors/        one file per source type (RSS, web page, Hacker News, YouTube, Hugging Face, web search, Gmail)
  agents/            LangGraph graph, scouts, analyst, writer/editor, prompts/, LLM router and budget
  evaluation/        the grounding eval (`digest eval`)
  monitoring/        Langfuse tracing
  newsToolsServer.py MCP server with the read-only news tools
src/web/           website (Astro + Tailwind + Preact, Apple "Liquid Glass" style)
evals/             the eval test set
tests/             automated tests (no network, no LLM calls)
data/              collected news, stories and digests (public)
state/             pipeline memory: seen items, daily LLM usage
docs/              setup guides and the architecture diagram (+ editable .drawio)
.github/workflows/ newsPipeline (every 3 h) · deploySite · ci · evaluateAgents
```

## Troubleshooting

| Problem | Fix |
|---|---|
| A source shows ❌ | Other sources still run. `429` usually clears by the next run. `404` means the feed URL in `config/app.env` has changed. |
| "Skipped: no LLM API keys" | Add `GROQ_API_KEY` and/or `GEMINI_API_KEY` (in `.env` locally, or as a GitHub secret). |
| No digest today | The writer's models were busy or out of quota. The run summary and Langfuse show why, and tomorrow's run tries again. |
| Website shows 404 | Turn on Pages: **Settings → Pages → Source: GitHub Actions**. |
| `npm` not found | Install Node.js 20+ and add it to your `PATH`. |
| Scheduled runs stopped | GitHub pauses schedules after 60 days without activity. Re-enable the workflow in the Actions tab. |

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, code style and how to open a pull request.

## License and credits

[MIT](LICENSE). Developed by **Digvijay Yadav**.

Logos in the architecture diagram come from [Simple Icons](https://simpleicons.org) (CC0) and belong to their owners.
