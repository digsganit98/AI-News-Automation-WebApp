# Set up the Gmail inbox for newsletters

The digest reads newsletters (TLDR AI, The Rundown AI, Superhuman AI, AlphaSignal) from a Gmail inbox. Later, the same account sends the daily digest email.

**Use a new Gmail account just for this project, not your personal one.** The password you'll create gives access to the whole mailbox.

## 1. Create the account and an app password

1. Create a new Google account at <https://accounts.google.com/signup>, e.g. `yourname.genai.digest@gmail.com`.
2. Turn on **2-Step Verification**: <https://myaccount.google.com/security>. App passwords need it.
3. Create an **app password**: <https://myaccount.google.com/apppasswords>. Name it `genai-digest` and copy the 16-character password.
4. Make sure IMAP is on: Gmail → ⚙️ Settings → **See all settings** → **Forwarding and POP/IMAP** → **Enable IMAP** → Save.

## 2. Subscribe the inbox to the newsletters

Sign up with the new address at each one:

| Newsletter | Sign-up page |
|---|---|
| TLDR AI | <https://tldr.tech/ai> |
| The Rundown AI | <https://www.therundown.ai> |
| Superhuman AI | <https://www.superhuman.ai> |
| AlphaSignal | <https://alphasignal.ai> |

Confirm each subscription from the email it sends you.

## 3. Put newsletters under one label

In Gmail: search `from:(tldrnewsletter.com OR therundown.ai OR superhuman.ai OR alphasignal.ai)` → click the **filter icon** in the search box → **Create filter** → tick **Apply the label** → **New label** `newsletters` → **Create filter**.

The label name must match `label:` in the `newsletters` block of [`config/sources.yaml`](../config/sources.yaml).

> Sender addresses change now and then. If a newsletter stops appearing, open one of its emails, check the sender's address, and update both the Gmail filter and the `senders:` list in `config/sources.yaml`. It matches on part of the address, e.g. `tldr`.

## 4. Add the secrets

- **On GitHub:** Settings → Secrets and variables → Actions → **New repository secret**:
  - `GMAIL_ADDRESS`: the new Gmail address
  - `GMAIL_APP_PASSWORD`: the 16-character app password (spaces don't matter)
- **On your computer:** copy `.env.example` to `.env` and fill in the same two values.

## 5. Turn the source on

In [`config/sources.yaml`](../config/sources.yaml), change `enabled: false` to `enabled: true` in the `newsletters` block. Then test it:

```bash
uv run digest collect --dry-run
```

`Newsletters ✅ ok` should appear in the table once at least one newsletter has arrived.

**Privacy:** the full text of each newsletter is only used during the run, to pull out individual stories. It is never saved in the public `data/` folder. The digest shows short summaries with links back to the original.
