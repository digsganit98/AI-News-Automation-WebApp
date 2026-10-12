# GenAI Daily

[![CI](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/ci.yml/badge.svg)](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/ci.yml)
[![News pipeline](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/newsPipeline.yml/badge.svg)](https://github.com/digsganit98/AI-News-Automation-WebApp/actions/workflows/newsPipeline.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**The latest Generative AI news and research papers in one place, picked and summarised by AI agents that check their sources.**

**🌐 Live site: <https://digsganit98.github.io/AI-News-Automation-WebApp/>**

Every 3 hours, GenAI Daily reads 34 sources (AI labs, cloud and data platforms, research papers, Hacker News, Reddit, YouTube, newsletters and web search). AI agents keep what is genuinely new and write it up in plain language. News and research papers sit together on one page, and teams can share their own write-ups in the **R&D Hub**. It runs for free on GitHub, even when your computer is off.

| At a glance | |
|---|---|
| Sources | **34**, all in English: 9 AI labs, 5 research sources (arXiv, Hugging Face), 6 cloud and data platforms (AWS, Azure, Google Cloud, Databricks, Snowflake), Hacker News and Reddit, YouTube, 9 newsletters (Substack and others), web search |
| Updates | Every **3 hours** |
| AI agents | **7**: 6 scouts and 1 analyst, built with LangGraph (the X scout is switched off until an X source is added, so 6 work today) |
| LLM calls | About **60–90 a day**, hard cap **150**, all on free tiers (Groq and Google Gemini) |
| Quality | Links are checked in code, every number is checked against its source, and the test set scores **100/100** |
| Monitoring | Every LLM call and every run is traced and scored in **Langfuse** |
| Cost | **$0** |

---

## Contents

- [What you get](#what-you-get)
- [How it works](#how-it-works)
- [GitHub Actions](#github-actions)
- [How we keep the AI honest](#how-we-keep-the-ai-honest)
- [Responsible AI](#responsible-ai)
- [Use it](#use-it)
- [Email digest](#email-digest)
- [Add an article to the R&D Hub](#add-an-article-to-the-rd-hub)
- [Run your own copy](#run-your-own-copy)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License and credits](#license-and-credits)

## What you get

| Page | What it is for |
|---|---|
| **Latest** | News and research papers on one page, updated every 3 hours. It starts with **Top stories**, picked and ranked by the agents (plain-English summary, "why it matters", sources, "Go deeper" links), then everything collected. A switch picks **All**, **News** or **Research papers**, with search and filters. The research view adds a **paper of the day**, a **research pulse** chart (tap a theme to filter), a "with code" filter, links to paper, PDF, code and project, one-click **BibTeX**, and a **reading list** saved in your browser that you can export as `.bib`. The research log (*Date · Researcher · Idea / Topic · Summary · Tech Domain · Cloud / Platform · Industry Vertical · Source Type · Link*) downloads as **CSV**. |
| **R&D Hub** | The team's article feed. Search, a **Table / Cards** switch, and filters for tech domain, cloud / platform, industry vertical and format. Articles are **HTML or PDF**. Uploading is a small button at the top right, not the page. See [Add an article to the R&D Hub](#add-an-article-to-the-rd-hub). |
| **Archive** (calendar icon) | The news from the last 5 days, each day browsable and filterable. |
| **Sources** (feed icon) | A small pop-up listing the sources that worked in the latest check, grouped. Failing ones are not listed. |
| **How it works** (gear icon) | The architecture, the agents and the models they use. |

Each page has one job: news and research on Latest, team write-ups in the R&D Hub, history in the Archive. There is light and dark mode, and it works on phones.

## How it works

![Architecture: 34 sources feed Python collectors on GitHub Actions. After removing duplicates, an MCP server gives 7 LangGraph agents read-only tools. Scouts run on Qwen via Groq and the analyst on gpt-oss-120b via Groq. Results are saved to the repo, published to the website every 3 hours, and traced in Langfuse.](docs/images/architecture.svg)

Every 3 hours one GitHub Actions job does this:

1. **Collect.** New posts are fetched from all sources and anything seen before is removed. Tutorial videos, ads and non-AI cloud news are filtered out by title.
2. **Scouts** (one AI agent per source group) decide what is real news and read the full article for the most important items, using the MCP `fetchArticle` tool.
3. **Analyst** merges the same news from different sources into one story, compares it with the last 7 days, then sorts and scores it.
4. **Save and publish.** The data is committed to the repo and the website is rebuilt.

| Agent | Model (free tier) | Job |
|---|---|---|
| 6 scouts: labs & research · cloud & platforms · community · video, newsletters & blogs · X · web search | Qwen 3.8 27B on Groq | Pick the real news from each source group |
| Analyst | gpt-oss-120b on Groq | Merge, score and rank stories |

If a model is busy or out of quota, the next one in [`config/agents.yaml`](config/agents.yaml) takes over (Gemini Flash-Lite is the last fallback). Every request is sized to fit every model in its chain, including Groq's 8,000 tokens a minute, and a daily budget keeps calls within the free tiers.

**Polite to the sites it reads.** Requests to the same site take turns with a gap (2 seconds; 4 seconds for arXiv). arXiv's feed changes once a day, so it is re-checked at most every 6 hours with an "only if changed" request, and a site's `Retry-After` is honoured. Set per-site gaps with `HOST_SPACING_OVERRIDES` in `config/app.env`.

**One failure never stops the rest.** Each source, LLM call, agent and batch fails on its own. Whatever was collected is always saved and published, even if the agents crash.

**Source Type** (research log): **Directed** means official labs, research and cloud sources. **Emergent** means spotted on Hacker News, Reddit, YouTube or newsletters. **AI-assisted** means found by the web-search scout.

## GitHub Actions

There are six workflows in [`.github/workflows/`](.github/workflows/):

| Workflow | When it runs | What it does |
|---|---|---|
| **News pipeline** (`newsPipeline.yml`) | Every 3 hours, or by hand | Collects, runs the agents, saves data, republishes the site |
| **Deploy website** (`deploySite.yml`) | After each pipeline run, and when site code, data or config change on `main` | Builds the site and publishes it on GitHub Pages. It can also build a branch preview (see below) |
| **R&D Hub uploads** (`hubUploads.yml`) | When a pull request or a merge touches `hub/inbox/` | Checks an uploaded article, and after the merge publishes it |
| **CI** (`ci.yml`) | On every pull request and push to `main` | Lint, format check and tests |
| **Email digest** (`emailDigest.yml`) | By hand for now (the daily schedule is ready to switch on) | Sends each person the stories they asked for, through Gmail. See [Email digest](#email-digest) |
| **Evaluate agents** (`evaluateAgents.yml`) | By hand only | Scores the agents on the test set (about 10 LLM calls) |

The daily morning edition, its backup timer and the Daily Digest page were removed: the agents now only turn news and papers into stories.

**Preview a branch on GitHub Pages.** The live site always comes from `main`. A branch named in `PREVIEW_BRANCHES` in `deploySite.yml` is also built, with `main`'s newest data, and published at `<site address>/preview/<branch>/`, with a yellow "Preview" bar. The list is empty by default. If a deploy is refused with "branch is not allowed to deploy", add the branch under *Settings → Environments → github-pages → Deployment branches*.

## How we keep the AI honest

- **Real articles only.** From Reddit, Hacker News and web search, only items that link to a proper article, announcement or paper get through. Text-only threads, screenshots, tweets and social posts are dropped (the list of discussion sites is `notArticleHosts` in `config/sources.yaml`). The scouts also drop rumours whose only source is a forum post.
- **The AI cannot invent links.** Agents refer to items by number (`i1`, `i2`…); the code attaches every URL. Any link that is not in the collected data is removed and counted as a "hallucination catch".
- **Scraped text is treated as data.** It is fenced off, so instructions hidden in a web page are ignored.
- **A test set measures it.** `uv run digest eval` runs the real agents on 20 saved cases, including tutorials to drop, fake claims and two prompt-injection traps. It scores 5 checks: keep/drop accuracy, numbers found in the source, duplicates merged, traps ignored and no invented links.
- **Everything is visible in Langfuse.** Each run, each agent and each LLM call is traced with tokens and errors, plus scores such as stories, failed calls and hallucination catches.

## Responsible AI

GenAI Daily covers AI that advances people. These rules are enforced in code and in every AI prompt, not left to chance:

- **Content policy.** No sexual or explicit content, nothing racist, sexist, misogynistic, hateful or anti-religious, and nothing that promotes violence, weapons, terrorism or self-harm. No gossip, outrage bait or fear-mongering.
- **Checked three times.** (1) At collection, a block list (`blockedTerms` in [`config/sources.yaml`](config/sources.yaml)) drops matching items from every source before any AI or page sees them. (2) Every agent prompt includes the policy ([`contentPolicy.md`](src/digest/agents/prompts/contentPolicy.md)). (3) Before anything is saved, code checks what the AI wrote and removes any story that breaks the policy. The website applies the block list once more to everything it shows, and R&D Hub uploads go through the same check.
- **English only, in plain English.** Items in other languages are dropped at collection (`englishOnly` in `config/sources.yaml`). What the AI writes is tidied in code before saving: long dashes between clauses become proper punctuation, odd hyphens are fixed, and empty bullets are removed.
- **Only reviewed content is published.** Raw web-search results are never shown; they reach the site only as a story an AI agent reviewed.
- **Transparent.** Every story links to its original sources, and every AI call is logged in Langfuse.
- **Grounded.** The AI cannot invent links, and every number in a story is checked against its source.
- **Privacy.** No personal data is collected or stored. The site has no accounts, tracking or ads.
- **Human in charge.** The policy, block list and prompts are plain files anyone can read and change.

The block list is strict on purpose: it can also drop neutral news that uses a listed word (for example research on bias in AI). Edit the list to change that.

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
uv run digest email --dry-run         # choose and render the emails, send nothing
uv run pytest                         # run the tests (no network, no LLM calls)

cd src/web && npm install && npm run dev
# open http://localhost:4321/AI-News-Automation-WebApp/
```

**Try the agents' tools in a browser (MCP Inspector):**

```bash
npx @modelcontextprotocol/inspector uv run digest mcp
```

You can also add them to Claude Desktop or Claude Code: the server command is `uv --directory <repo folder> run digest mcp`.

## Email digest

Sends each person an email with the stories that match what they asked for. It uses the same
Gmail account as the newsletter inbox (an app password), so it costs nothing. The plan and the
next steps (an AI-written intro per person) are in [docs/emailAgentPlan.md](docs/emailAgentPlan.md).

1. **Add the secrets** `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` and `EMAIL_RECIPIENTS`. The repository is public, so addresses live only in the secret, never in a file. `EMAIL_RECIPIENTS` is a JSON list:

   ```json
   [{"name": "Priya", "email": "priya@example.com", "categories": ["Agentic Systems"],
     "clouds": ["AWS", "Cross-cloud"], "verticals": ["BFSI"], "minImportance": 3, "maxStories": 6}]
   ```

   Leave `categories`, `clouds` or `verticals` empty (or out) to get everything. Set `"enabled": false` to pause someone.
2. **Preview locally.** `uv run digest email --dry-run --preview-dir emailPreview` writes each email as an HTML file and sends nothing.
3. **Send yourself one.** `uv run digest email --to you@example.com`, or run the **Email digest** workflow with `to` set. A test mail is not counted as sent.
4. **Switch it on.** Un-comment the `schedule:` lines in `emailDigest.yml` (09:00 IST by default).

Nobody gets the same story twice: `state/emailSent.json` keeps a short salted hash per person, not the address. To stop receiving the email, reply STOP and the person is removed from `EMAIL_RECIPIENTS`.

## Add an article to the R&D Hub

An article is one **`.html` or `.pdf`** file, up to 5 MB.

**Put it in SharePoint.** The **Upload to SharePoint** button on the Hub opens the team's folder (its address is `HUB_SHAREPOINT_URL` in [`config/app.env`](config/app.env)). Files there are not copied to the website by themselves: the feed only lists articles that are in this repository, so someone adds them with the GitHub route below.

**Or add it through GitHub** (the site is static, so a file reaches it as a pull request):

1. On the R&D Hub page, click *or add through GitHub*, choose the file, fill in the details and click *Copy details & open GitHub*.
2. On the GitHub page that opens, drop in the same file and choose *Create a new branch and start a pull request*.
3. Paste the copied lines into the pull request description:
   ```
   Title: How we cut RAG latency 40%
   Team: Platform Team
   Author: Priya N.
   Tags: RAG, latency
   Summary: One or two sentences on what the article shows.
   Domain: GenAI
   Cloud: AWS
   Vertical: BFSI
   ```
4. Checks run on the pull request (file type, size, content policy) and comment with anything to fix.
5. A reviewer merges it. HTML is cleaned (scripts, embeds and outside loads removed), the article is saved, and the site is republished. It then shows in the R&D Hub and in Latest.

The code is in [`src/digest/hub/hubUploads.py`](src/digest/hub/hubUploads.py). Published articles are public, because the repository is. Files are stored in this repository (`src/web/public/hub/`); uploads are refused once that folder passes 300 MB, at which point the files should move to a separate content repository or Git LFS.

## Run your own copy

It takes about 15 minutes, and everything is free.

1. **Fork** this repository and keep it **public** (that makes GitHub Actions free).
2. **Actions tab:** enable workflows.
3. **Settings → Pages → Source: GitHub Actions.**
4. **Settings → Secrets and variables → Actions:** add these secrets.

   | Secret | Needed for | Get it free at |
   |---|---|---|
   | `GROQ_API_KEY` | the AI agents | <https://console.groq.com/keys> |
   | `GEMINI_API_KEY` | fallback model | <https://aistudio.google.com/apikey> |
   | `TAVILY_API_KEY` | the web-search scout | <https://tavily.com> |
   | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | monitoring (optional) | <https://cloud.langfuse.com> |
   | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | newsletters and the email digest (optional) | [docs/gmailInboxSetup.md](docs/gmailInboxSetup.md) |
   | `EMAIL_RECIPIENTS` | email digest (optional): who gets it and what they want | [Email digest](#email-digest) |
   | `YOUTUBE_API_KEY` | backup when YouTube's feed is down (optional) | Google Cloud Console |

5. In [`config/app.env`](config/app.env), set `SITE_URL`, `SITE_BASE_PATH`, `PROJECT_URL`, `HUB_UPLOAD_URL` and `HUB_SHAREPOINT_URL` to your own.
6. **Actions → News pipeline → Run workflow.** Your site goes live at `https://<you>.github.io/<repo>/`.

Anything whose key is missing is simply skipped. Without any LLM keys, for example, the site still shows everything collected.

## Configuration

| File | What is in it |
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
  agents/            LangGraph graph, scouts, analyst, prompts/, LLM router and budget
  evaluation/        the grounding eval (`digest eval`)
  hub/               R&D Hub upload checks and publishing
  mailer/            email digest: recipients, story selection, rendering, Gmail sending
  monitoring/        Langfuse tracing
  newsToolsServer.py MCP server with the read-only news tools
src/web/           website (Astro + Tailwind + Preact, "Liquid Glass" style)
evals/             the eval test set
tests/             automated tests (no network, no LLM calls)
data/              collected news and stories, and R&D Hub article details (public)
hub/inbox/         where a new R&D Hub article is added in a pull request (see hub/README.md)
state/             pipeline memory: seen items, daily LLM usage, feed cache
docs/              setup guides and the architecture diagram (+ editable .drawio)
.github/workflows/ newsPipeline · deploySite · hubUploads · emailDigest · ci · evaluateAgents
```

## Troubleshooting

| Problem | Fix |
|---|---|
| A source shows ❌ | Other sources still run. `429` usually clears by the next run. `404` means the feed URL in `config/app.env` has changed. |
| "Skipped: no LLM API keys" / no stories on the site | The keys in your `.env` only work on your computer. The scheduled runs need them as **GitHub secrets** too: Settings → Secrets and variables → Actions → add `GROQ_API_KEY` and `GEMINI_API_KEY`. |
| Website shows 404 | Turn on Pages: **Settings → Pages → Source: GitHub Actions**. |
| `npm` not found | Install Node.js 20+ and add it to your `PATH`. |
| Scheduled runs stopped | GitHub pauses schedules after 60 days without activity. Re-enable the workflow in the Actions tab. |
| A Hub upload check fails | Open the comment on the pull request: it lists what to fix (file type, size, missing Title / Team / Author line, or wording flagged by the content policy). |

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, code style and how to open a pull request.

## License and credits

[MIT](LICENSE). Developed by **Digvijay Yadav**.

Logos in the architecture diagram come from [Simple Icons](https://simpleicons.org) (CC0) and belong to their owners.
