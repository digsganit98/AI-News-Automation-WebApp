"""Paths and environment settings.

Every URL and setting is read from the environment. At startup two files are loaded into
`os.environ` without overwriting variables that are already set:

1. `.env`             - secrets and local overrides (not in git)
2. `config/app.env`   - all URLs and non-secret defaults (in git)

So a real environment variable (e.g. a GitHub Actions secret) wins over `.env`,
which wins over `config/app.env`.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(os.environ.get("DIGEST_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR = REPO_ROOT / "config"

_loaded = False


class MissingSettingError(RuntimeError):
    pass


def loadEnv() -> None:
    global _loaded
    if _loaded:
        return
    load_dotenv(REPO_ROOT / ".env", override=False)
    load_dotenv(CONFIG_DIR / "app.env", override=False)
    _loaded = True


def env(name: str, default: str | None = None) -> str:
    """Read a setting. Raises a clear error if it is missing and has no default."""
    loadEnv()
    value = os.environ.get(name, default)
    if value is None or value == "":
        if default is not None:
            return default
        raise MissingSettingError(
            f"Setting '{name}' is not set. Add it to config/app.env (URLs and non-secrets) "
            "or .env / a GitHub secret (passwords and keys)."
        )
    return value


def envUrl(name: str, **params: str) -> str:
    """Read a URL setting and fill in its {placeholders}, e.g. envUrl("HN_ITEM_URL", id="1")."""
    template = env(name)
    return template.format(**params) if params else template
