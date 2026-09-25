"""URL cleanup, duplicate removal and the seen-list."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from digest.dataModels import RawItem
from digest.processing.cleanItems import normalize
from digest.processing.removeDuplicates import SeenStore, dedupe, inWindow
from digest.urlCleaning import canonicalKey, cleanUrl, urlId


def makeItem(url: str, title: str = "A title", source: str = "s", hoursAgo: float = 1):
    return RawItem(
        source=source,
        sourceName=source.upper(),
        title=title,
        url=url,
        publishedAt=datetime.now(UTC) - timedelta(hours=hoursAgo),
    )


def testCleanUrlDropsTrackingButKeepsTheRealLink():
    url = "http://www.Example.com/post/?utm_source=x&id=5&fbclid=abc#comments"
    assert cleanUrl(url) == "http://www.Example.com/post/?id=5"


def testSameArticleGetsSameIdWhateverTheLinkLooksLike():
    variants = [
        "https://example.com/post?b=2&a=1",
        "http://www.example.com/post/?a=1&b=2&utm_medium=email",
        "https://EXAMPLE.com/post?a=1&b=2#top",
    ]
    assert len({canonicalKey(v) for v in variants}) == 1
    assert len({urlId(v) for v in variants}) == 1


def testNonWebLinksAreLeftAlone():
    assert cleanUrl("mid:abc@mail") == "mid:abc@mail"


def testNormalizeTidiesTitles():
    [item] = normalize([makeItem("https://e.com/x?utm_campaign=1", title="  Big \n news  ")])
    assert item.title == "Big news"
    assert item.url == "https://e.com/x"


def testDedupeRemovesSeenAndRepeatedItems(tmp_path):
    seen = SeenStore(tmp_path / "seen.json")
    seen.add([makeItem("https://e.com/old")])
    items = [
        makeItem("https://e.com/old"),  # used in an earlier digest
        makeItem("https://e.com/new"),
        makeItem("https://www.e.com/new/?utm_source=hn"),  # same article, different link
        makeItem("https://e.com/new-2", title="A title!"),  # same source, near-identical title
        makeItem("https://other.com/story", title="A title", source="other"),  # other source: kept
    ]
    kept = dedupe(items, seen)
    assert [i.url for i in kept] == ["https://e.com/new", "https://other.com/story"]


def testInWindowKeepsRecentAndUndatedItems():
    old = makeItem("https://e.com/old", hoursAgo=100)
    recent = makeItem("https://e.com/recent", hoursAgo=2)
    undated = RawItem(source="s", sourceName="S", title="t", url="https://e.com/u")
    since = datetime.now(UTC) - timedelta(hours=36)
    assert inWindow([old, recent, undated], since) == [recent, undated]


def testSeenStoreSavesAndForgetsOldEntries(tmp_path):
    path = tmp_path / "state" / "seen.json"
    store = SeenStore(path)
    longAgo = datetime.now(UTC) - timedelta(days=45)
    store.add([makeItem("https://e.com/ancient")], now=longAgo)
    store.add([makeItem("https://e.com/fresh")])
    store.prune()
    store.save()

    reloaded = SeenStore(path)
    assert urlId("https://e.com/fresh") in reloaded
    assert urlId("https://e.com/ancient") not in reloaded


def testTitlesWithDifferentNumbersAreDifferentStories():
    from digest.processing.removeDuplicates import isSameTitle

    assert isSameTitle("OpenAI releases GPT-6", "OpenAI releases GPT-6!")
    assert not isSameTitle("OpenAI releases GPT-5", "OpenAI releases GPT-6")
    assert not isSameTitle(
        "Qwen 3.8 27B benchmarks", "Qwen 3.8 27B benchmarks: full report on coding"
    )
