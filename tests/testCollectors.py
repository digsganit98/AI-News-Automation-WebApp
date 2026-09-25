"""Each collector's parser, run against saved copies of real responses."""

from __future__ import annotations

from datetime import UTC, datetime

from conftest import makeCollector, readFixture

from digest.collectors.hackerNewsCollector import keywordPattern, parseHits
from digest.collectors.huggingFaceCollector import parseDailyPapers, parseTrendingModels
from digest.collectors.newsletterInboxCollector import parseNewsletter
from digest.collectors.rssFeedCollector import parseFeed
from digest.collectors.webPageCollector import parseListing, parseListingDate
from digest.collectors.youtubeCollector import parseApiItems


def testRssFeedReadsTitleLinkDateAndPlainTextExcerpt():
    items = parseFeed(readFixture("openaiFeed.xml"), makeCollector("rss"))

    assert [i.title for i in items] == [
        "Introducing a new reasoning model",
        "An older announcement",
    ]  # the entry without a title is skipped
    first = items[0]
    assert first.publishedAt == datetime(2026, 9, 24, 17, 0, tzinfo=UTC)
    assert first.excerpt == "Our newest model thinks before it answers."
    assert first.sourceName == "Test rss"


def testAnthropicPageParsesCardsOnceEach():
    collector = makeCollector(
        "webPage",
        selectors={"item": 'a[href^="/news/"]', "title": '[class*="__title"]', "date": "time"},
    )
    html = readFixture("anthropicNews.html").decode()
    items = parseListing(html, "https://www.anthropic.com/news", collector)

    assert [i.url for i in items] == [
        "https://www.anthropic.com/news/claude-discovers-novel-enzyme-system",
        "https://www.anthropic.com/news/accenture-embedded-evaluation",
    ]
    assert items[0].title == "Claude discovers a novel enzyme system with CRISPR-like repeats"


def testDateWithoutTimeCountsAsEndOfDay():
    assert parseListingDate("Sep 23, 2026") == datetime(2026, 9, 23, 23, 59, 59, tzinfo=UTC)
    assert parseListingDate("2026-09-23T08:15:00Z") == datetime(2026, 9, 23, 8, 15, tzinfo=UTC)
    assert parseListingDate("not a date") is None


def testHackerNewsKeepsOnlyAiStoriesAndLinksDiscussion():
    hits = [
        {
            "objectID": "1",
            "title": "New LLM beats GPT on math",
            "url": "https://x.dev/a",
            "created_at_i": 1790000000,
            "points": 300,
            "num_comments": 120,
            "author": "pg",
        },
        {
            "objectID": "2",
            "title": "Show HN: My sourdough starter",
            "url": "https://bread.dev",
            "created_at_i": 1790000000,
            "points": 500,
            "num_comments": 10,
        },
        {"objectID": "3", "title": "Ask HN: Is AI overhyped?", "created_at_i": 1790000000},
        {"objectID": "4", "title": "The FAIR use of data", "created_at_i": 1790000000},
    ]
    items = parseHits(hits, keywordPattern(["AI", "LLM"]), makeCollector("hackerNews"))

    assert [i.title for i in items] == ["New LLM beats GPT on math", "Ask HN: Is AI overhyped?"]
    assert items[0].extra["points"] == 300
    assert items[1].url == "https://news.ycombinator.com/item?id=3"  # text post -> HN page


def testYoutubeApiFallbackParsesVideos():
    data = {
        "items": [
            {
                "snippet": {
                    "title": " GPT-6 explained ",
                    "publishedAt": "2026-09-24T12:00:00Z",
                    "description": "Everything new.",
                    "channelTitle": "AI Explained",
                    "resourceId": {"videoId": "abc123"},
                }
            }
        ]
    }
    [item] = parseApiItems(data, makeCollector("youtube", channelId="UCx"))

    assert item.title == "GPT-6 explained"
    assert item.url == "https://www.youtube.com/watch?v=abc123"
    assert item.publishedAt == datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def testHuggingFacePapersRespectMinimumUpvotes():
    data = [
        {
            "paper": {
                "id": "2609.00001",
                "title": "Popular paper",
                "upvotes": 40,
                "summary": "S",
                "githubRepo": "https://github.com/a/b",
                "submittedOnDailyAt": "2026-09-24T00:00:00Z",
            }
        },
        {"paper": {"id": "2609.00002", "title": "Unnoticed paper", "upvotes": 2}},
    ]
    [item] = parseDailyPapers(data, 10, makeCollector("huggingFacePapers"))

    assert item.url == "https://huggingface.co/papers/2609.00001"
    assert item.extra["arxivUrl"] == "https://arxiv.org/abs/2609.00001"
    assert item.extra["githubRepo"] == "https://github.com/a/b"


def testHuggingFaceTrendingModels():
    data = [{"id": "org/model-7b", "author": "org", "likes": 900, "trendingScore": 800}]
    [item] = parseTrendingModels(data, makeCollector("huggingFaceTrendingModels"))

    assert item.url == "https://huggingface.co/org/model-7b"
    assert item.extra["trendingScore"] == 800


def testNewsletterEmailKeepsTextAndLinksPrivate():
    collector = makeCollector("newsletterInbox")
    item = parseNewsletter(readFixture("newsletterEmail.eml"), {"tldr": "TLDR AI"}, collector)

    assert item is not None
    assert item.title == "New open model tops leaderboard 🚀"
    assert item.url == "https://tldr.tech/ai/2026-09-25"  # the "View Online" link
    assert item.author == "TLDR AI"
    assert any(
        link["url"].startswith("https://example.com/open-model") for link in item.extra["_links"]
    )
    # Private fields never reach public data files.
    assert "_bodyText" not in item.public()["extra"]
    assert item.public()["extra"] == {"newsletter": "TLDR AI"}


def testNewsletterFromUnknownSenderIsIgnored():
    collector = makeCollector("newsletterInbox")
    assert parseNewsletter(readFixture("newsletterEmail.eml"), {"rundown": "x"}, collector) is None
