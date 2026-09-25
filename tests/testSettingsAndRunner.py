"""Settings, config loading, the parallel runner and the article fetcher's safety checks."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import readFixture

from digest.envSettings import MissingSettingError, env, envUrl
from digest.runCollectors import collectSources
from digest.sourcesConfig import Config, SourceConfig, loadConfig
from digest.tools.fetchArticle import UnsafeUrlError, checkUrlIsPublic


def testEnvUrlFillsPlaceholders(monkeypatch):
    monkeypatch.setenv("TEST_ITEM_URL", "https://site.test/item?id={id}")
    assert envUrl("TEST_ITEM_URL", id="42") == "https://site.test/item?id=42"


def testMissingSettingGivesClearError():
    with pytest.raises(MissingSettingError, match="NOT_A_REAL_SETTING"):
        env("NOT_A_REAL_SETTING")


def testSourcesYamlGetsEveryUrlFromEnv():
    config = loadConfig()
    for source in config.enabledSources:
        assert "${" not in (source.url or ""), f"{source.id} has an unfilled URL"
    ids = [s.id for s in config.sources]
    assert len(ids) == len(set(ids)), "source ids must be unique"


def testRealEnvironmentOverridesAppEnv(monkeypatch):
    monkeypatch.setenv("OPENAI_FEED_URL", "https://override.test/feed")
    config = loadConfig()
    assert next(s for s in config.sources if s.id == "openai").url == "https://override.test/feed"


@respx.mock
async def testOneBrokenSourceDoesNotStopTheOthers():
    respx.get("https://good.test/feed").mock(
        return_value=httpx.Response(200, content=readFixture("openaiFeed.xml"))
    )
    respx.get("https://broken.test/feed").mock(return_value=httpx.Response(404))
    config = Config(
        sources=[
            SourceConfig(id="good", name="Good", type="rss", url="https://good.test/feed"),
            SourceConfig(id="broken", name="Broken", type="rss", url="https://broken.test/feed"),
        ]
    )
    # Look back far enough to include the fixture's dated entries.
    result = await collectSources(config, hours=24 * 365 * 5)

    health = {h.source: h for h in result.health}
    assert health["good"].ok and health["good"].items == 2
    assert not health["broken"].ok and "404" in health["broken"].error
    assert {i.source for i in result.items} == {"good"}
    assert result.items[0].url == "https://openai.com/index/new-reasoning-model/"  # utm removed


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "http://localhost/admin", "http://127.0.0.1:8080", "http://10.0.0.5/"],
)
async def testFetchArticleRefusesNonPublicUrls(url):
    with pytest.raises(UnsafeUrlError):
        await checkUrlIsPublic(url)
