# Contributing to GenAI Daily

Thanks for helping! This guide covers everything you need to make a change and open a pull request.

## 1. Set up

```bash
git clone https://github.com/<you>/AI-News-Automation-WebApp.git
cd AI-News-Automation-WebApp
uv sync                                  # Python pipeline + dev tools
cp .env.example .env                     # add keys only if you need live runs
cd src/web && npm install && cd ../..    # website
```

You don't need any API keys to run the tests: they use saved sample data and a fake LLM.

## 2. Make your change

- **Branch** from `main`: `git checkout -b short-description`.
- **Names:** camelCase names that say what the code does (`hackerNewsCollector.py`, `searchHackerNews()`). Classes use PascalCase; environment variables use UPPER_SNAKE.
- **No hard-coded URLs:** add them to `config/app.env` and read them with `env()` / `envUrl()`.
- **Secrets** go in `.env` (git-ignored) or GitHub secrets, never in the code or `config/`.
- **New source?** Usually just config: see "Add a source" in the README.
- **Prompt or model change?** Run `uv run digest eval` before and after, and put both scores in your pull request. Don't merge anything that lowers the score.
- **Website change?** Check both light and dark mode, and a phone-sized window.
- **Keep the README current.** If your change adds or renames a page, source, agent, model, setting or setup step, or changes a number the README quotes (sources, agents, calls a day), update `README.md` in the same pull request, in plain simple English.

## 3. Check it

```bash
uv run ruff check src tests scripts      # style
uv run ruff format src tests scripts     # formatting
uv run pytest                            # tests (fast, offline)
cd src/web && npm run build              # the website builds
```

If you changed the architecture, update the diagram in `scripts/buildArchitectureDiagram.py` and run `uv run python scripts/buildArchitectureDiagram.py`. Don't edit the `.svg` or `.drawio` files by hand.

## 4. Open a pull request

- One topic per pull request, with a clear title (e.g. "Add Cohere blog as a source").
- Say **what** changed, **why**, and **how you tested it**.
- CI runs the same checks. Please make sure they pass.

## Reporting a problem

Open an issue with what you expected, what happened, and (for pipeline problems) a link to the GitHub Actions run or the Langfuse trace.
