"""Keeps items that point to a proper article, not a discussion thread or a social post.

Community sources (Reddit, Hacker News, web search) mix real news with gossip: a Reddit
thread about a screenshot, an "Ask HN", a tweet. Sources with `articlesOnly: true` drop every
item whose link is on one of the `notArticleHosts` in sources.yaml.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from digest.dataModels import RawItem


def isOnHost(url: str, hosts: list[str]) -> bool:
    """True if the URL is on one of `hosts` or a subdomain of one (old.reddit.com, ...)."""
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in hosts)


def keepArticlesOnly(items: list[RawItem], notArticleHosts: list[str]) -> list[RawItem]:
    return [item for item in items if not isOnHost(item.url, notArticleHosts)]
