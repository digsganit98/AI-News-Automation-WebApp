# Email agent: plan

Status: on branch `digvijay_work_branch`.

| Phase | State |
|---|---|
| 1. Selection and rendering (no LLM) | **Implemented, not yet run or tested** |
| 2. Gmail sending, sent log, workflow | **Implemented, not yet run or tested** |
| 3. Mailer LLM agent (personal intro) | Not started |
| 4. Daily schedule | Prepared in `emailDigest.yml` (commented out) |

Decisions taken: Gmail SMTP with the existing app password; recipients in the `EMAIL_RECIPIENTS`
secret; one email a day; filters are category, cloud, vertical and minimum importance.

## Goal

An 8th agent that sends each person an email with the stories they care about, written for them.
It must keep the project's rules: $0, runs on GitHub Actions, grounded (no invented links),
content policy enforced in code, plain-English docs.

## What already exists that we reuse

| Need | Already in the repo |
|---|---|
| Content to send | `data/stories/<date>.json`: headline, summary, whyItMatters, category, importance, cloudPlatform, industryVertical, sources, goDeeper |
| Personalisation fields | `category` (Tech Domain), `cloudPlatform`, `industryVertical`, `importance`, `sourceType` |
| Agent pattern | LangGraph agents with model fallback chains in `config/agents.yaml`, `llmRouter.py`, `llmBudget.py` (150 calls/day cap) |
| Grounding | LLM refers to items by ref, code attaches URLs (`scoutAgent.py`, `analystAgent.py`) |
| Content policy | `contentSafety.py` `guardOutput`, `contentPolicy.md` prompt |
| Gmail credentials | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` already used for IMAP newsletter reading |
| CLI, tracing, eval | `cli.py`, Langfuse `traceRun`, `evals/groundingSet.json` |
| Settings | `envSettings.py`, all URLs in `config/app.env` |

## Design

```
data/stories/*.json ──┐
                      ├─► select (code) ─► compose (LLM agent) ─► check (code) ─► send (SMTP) ─► log
recipients (private) ─┘    per-person        intro + order          links, policy,     Gmail          state/emailSent.json
                           filter            only                   numbers            app password   (no addresses)
```

1. **Select (code, no LLM).** For each recipient, take stories from the window (e.g. since their
   last email), keep those matching their preferences (categories, clouds, verticals, minimum
   importance), rank by importance, cap at N. Skip the email if nothing matches.
2. **Compose (LLM agent, "Mailer").** Gets only the selected stories as numbered refs. Returns a
   short personal intro, a one-line "why this one is for you" per story, and the order, all by
   ref. It writes no URLs and no new facts; headline and summary text come from the stories
   already verified by the analyst.
3. **Check (code).** Drop unknown refs, run `guardOutput`-style policy check and `tidyOutcome`
   style tidy on the intro, fall back to a plain template if the LLM output is unusable.
4. **Render.** HTML (inline CSS, mobile friendly, light/dark safe) plus a plain-text part.
5. **Send.** SMTP over TLS, one message per person (no CC), `List-Unsubscribe` header.
6. **Log.** `state/emailSent.json` stores a hash of each address and the story ids sent, so
   nobody gets the same story twice and a rerun does not resend.

LLM cost: people with the same preferences share one compose call (group by preference
signature), so it is a handful of calls a day, inside the 150 cap. A reserve is held back so
the news agents are never starved.

## Key decision: where do recipients live?

The repo is **public**. Email addresses must never be committed.

| Option | $0 | Effort | Notes |
|---|---|---|---|
| **A. GitHub secret `EMAIL_RECIPIENTS` (JSON)** | yes | low | Recommended to start. Edit in repo settings. Fine for a team of a few dozen. |
| B. Private repo with `recipients.yaml` | yes | medium | Workflow checks it out with a token. Easier to edit and review. |
| C. Google Sheet (published as CSV with a secret URL) | yes | medium | Non-developers can edit. |
| D. Sign-up form on the site | needs a backend | high | Breaks the static, no-server design. Not now. |

Recipient shape (never in git):

```json
[
  {
    "name": "Priya",
    "email": "priya@example.com",
    "frequency": "daily",
    "categories": ["Agentic Systems", "Infrastructure/MLOps"],
    "clouds": ["AWS", "Cross-cloud"],
    "verticals": ["BFSI"],
    "minImportance": 3,
    "maxStories": 6
  }
]
```

## Key decision: how do we send?

| Option | $0 | Notes |
|---|---|---|
| **Gmail SMTP + app password** | yes | Recommended. Same account already configured. About 500 recipients a day, enough for a team. Sends from the dedicated Gmail address. |
| Brevo or Resend free tier | yes | Better deliverability and unsubscribe handling, needs a new account and a verified domain. Switch later if the list grows. |

## Unsubscribe

The site is static, so there is no one-click server endpoint. For now: `List-Unsubscribe:
<mailto:...>` header plus a footer line "Reply STOP to unsubscribe", handled by removing the
person from the recipient list. Revisit if we move to Brevo or Resend.

## Files to add

| File | Purpose |
|---|---|
| `src/digest/email/__init__.py` | package |
| `src/digest/email/recipients.py` | load and validate recipients from the secret / private source |
| `src/digest/email/selectStories.py` | preference filter and ranking (pure code, easy to test) |
| `src/digest/email/mailerAgent.py` | LLM compose step, ref-based, with fallback chain |
| `src/digest/email/renderEmail.py` | HTML and text templates |
| `src/digest/email/sendEmail.py` | SMTP sender, dry-run mode |
| `src/digest/email/sentLog.py` | `state/emailSent.json` read and write |
| `src/digest/agents/prompts/mailer.md` | prompt (includes `contentPolicy.md`) |
| `config/agents.yaml` | add `models.mailer` and `maxOutputTokens.mailer` |
| `config/app.env` | `SMTP_HOST`, `SMTP_PORT`, `EMAIL_SUBJECT_PREFIX`, `EMAIL_MAX_STORIES` |
| `.github/workflows/emailDigest.yml` | scheduled send, `workflow_dispatch` with `dryRun` and `to` |
| `tests/testEmail*.py` | selection, grounding, policy, render, no-resend |
| `README.md` | update in the same change (agent count becomes 8, new workflow, new secret) |

CLI: `uv run digest email --dry-run --preview-dir out/` writes the HTML for each recipient and
sends nothing. `uv run digest email --to you@example.com` sends one real test mail.

## Phases

1. **Selection and rendering, no LLM, no sending.** Recipients loader, filter, HTML/text
   template, `--dry-run` preview, tests. Deliverable: preview files from real `data/stories`.
2. **Sending.** SMTP sender, sent log, one test mail to yourself, `emailDigest.yml` run by hand.
3. **Mailer agent.** Personal intro and "for you" lines, grounding and policy checks, eval
   cases added to `evals/groundingSet.json`, Langfuse scores (`emailsSent`, `emailsSkipped`).
4. **Schedule and docs.** Daily cron, README section, secrets list, troubleshooting.

## Risks

- **Public repo leak:** addresses only in secrets or a private source; sent log stores hashes.
- **Gmail limits or blocking:** low volume, one message per person; fall back to Brevo.
- **Free LLM quota:** grouped calls, reserve held back, plain-template fallback so mail still goes.
- **Spam filters:** plain-text part, no tracking pixels, honest subject, unsubscribe header.
- **Content policy:** same three layers apply, the final check runs on the email text too.

## Open questions

1. Where should recipients live (A, B or C above)?
2. How often: one daily email (suggested 09:00 IST) or also an instant alert for importance 5?
3. Send from the existing Gmail account, or set up Brevo or Resend now?
4. Which preferences matter first: category, cloud, vertical, importance, or a free-text "interests" line?
