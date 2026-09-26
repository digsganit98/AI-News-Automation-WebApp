"""Articles only: Reddit posts become the article they link to; threads and social posts go."""

from __future__ import annotations

import httpx
import respx
from conftest import makeCollector

from digest.collectors.rssFeedCollector import parseFeed
from digest.processing.articleFilter import isOnHost, keepArticlesOnly
from digest.runCollectors import collectSources
from digest.sourcesConfig import Config, Settings, SourceConfig

HOSTS = ["reddit.com", "redd.it", "news.ycombinator.com", "x.com"]


def redditEntry(title: str, postId: str, linkHref: str, body: str = "") -> str:
    thread = f"https://www.reddit.com/r/LocalLLaMA/comments/{postId}/post/"
    summary = (
        f"{body} submitted by <a href='https://www.reddit.com/user/someone'>/u/someone</a> to "
        f"<a href='https://www.reddit.com/r/LocalLLaMA/'>r/LocalLLaMA</a> <br/> "
        f"<span><a href='{linkHref}'>[link]</a></span> "
        f"<span><a href='{thread}'>[comments]</a></span>"
    )
    return (
        f"<entry><title>{title}</title><link href='{thread}'/>"
        f"<updated>2026-09-26T08:00:00+00:00</updated>"
        f"<content type='html'><![CDATA[{summary}]]></content></entry>"
    )


def redditFeed(*entries: str) -> str:
    return f"<feed xmlns='http://www.w3.org/2005/Atom'><title>r</title>{''.join(entries)}</feed>"


FEED = redditFeed(
    redditEntry("Qwen 4 released", "a1", "https://qwenlm.github.io/blog/qwen4/"),
    redditEntry(
        "GPT-6 got 62.7% on a benchmark!!",
        "b2",
        "https://www.reddit.com/r/LocalLLaMA/comments/b2/post/",  # text-only thread
        body="I finally got to follow up on a RemindMe comment.",
    ),
    redditEntry("Look at this chart", "c3", "https://i.redd.it/chart.png"),
    redditEntry("Lab CEO says AGI soon", "d4", "https://x.com/someone/status/1"),
)


def testRedditPostPointsAtTheArticleItLinksTo():
    reddit = makeCollector("rss", url="https://reddit.test/feed", useLinkedArticle=True)
    first = parseFeed(FEED, reddit)[0]

    assert first.url == "https://qwenlm.github.io/blog/qwen4/"
    assert first.extra["discussionUrl"].startswith("https://www.reddit.com/r/LocalLLaMA/")
    assert "submitted by" not in first.excerpt


def testThreadsScreenshotsAndTweetsAreDropped():
    reddit = makeCollector("rss", url="https://reddit.test/feed", useLinkedArticle=True)
    kept = keepArticlesOnly(parseFeed(FEED, reddit), HOSTS)
    assert [i.title for i in kept] == ["Qwen 4 released"]


def testHostMatchingCoversSubdomains():
    assert isOnHost("https://old.reddit.com/r/x", HOSTS)
    assert isOnHost("https://i.redd.it/chart.png", HOSTS)
    assert not isOnHost("https://notreddit.com/a", HOSTS)
    assert not isOnHost("https://openai.com/index/x", HOSTS)


@respx.mock
async def testArticlesOnlyAppliesPerSource():
    """Only sources with `articlesOnly` are filtered; a YouTube feed, say, is left alone."""
    respx.get("https://reddit.test/feed").mock(return_value=httpx.Response(200, text=FEED))
    respx.get("https://other.test/feed").mock(return_value=httpx.Response(200, text=FEED))
    config = Config(
        settings=Settings(notArticleHosts=HOSTS),
        sources=[
            SourceConfig(
                id="reddit",
                name="Reddit",
                type="rss",
                url="https://reddit.test/feed",
                useLinkedArticle=True,
                articlesOnly=True,
            ),
            SourceConfig(id="other", name="Other", type="rss", url="https://other.test/feed"),
        ],
    )
    result = await collectSources(config, hours=24 * 365 * 5)

    counts = {h.source: h.items for h in result.health}
    assert counts == {"reddit": 1, "other": 4}


def testEditionLeavesOutStoriesBackedOnlyByThreads(monkeypatch):
    from datetime import UTC, datetime

    from digest.agents import runAgents
    from digest.agents.agentModels import Story

    def story(sid: str, *urls: str) -> Story:
        return Story(
            id=sid,
            createdAt=datetime.now(UTC).isoformat(),
            headline=sid,
            summary="S.",
            category="Research",
            importance=3,
            sources=[{"name": "x", "url": u} for u in urls],
        )

    monkeypatch.setattr(runAgents, "storiesForEdition", lambda: [])
    stories = [
        story("gossip", "https://www.reddit.com/r/singularity/comments/1/x/"),
        story("tweet", "https://x.com/someone/status/1"),
        story("article", "https://openai.com/index/new-model"),
        story("threadAndArticle", "https://www.reddit.com/r/a/1", "https://example.com/news"),
    ]
    kept = {s.id for s in runAgents.mergeForEdition(stories)}
    assert kept == {"article", "threadAndArticle"}
