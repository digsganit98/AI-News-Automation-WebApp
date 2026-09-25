"""New videos from a YouTube channel.

Tries the channel's public RSS feed (YOUTUBE_FEED_URL) first. That feed is sometimes
unavailable, so if it fails and YOUTUBE_API_KEY is set, the free YouTube Data API
(YOUTUBE_API_URL) is used instead: about 1 quota unit per run out of 10,000 a day.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from dateutil import parser as dateparser

from digest.collectors.collectorBase import Collector, CollectorError, excerpt, fetch, register, utc
from digest.collectors.rssFeedCollector import parseFeed
from digest.dataModels import RawItem
from digest.envSettings import env, envUrl

log = logging.getLogger(__name__)


def parseApiItems(data: dict, collector: Collector) -> list[RawItem]:
    items = []
    for entry in data.get("items", []):
        snippet = entry.get("snippet", {})
        videoId = snippet.get("resourceId", {}).get("videoId")
        if not videoId:
            continue
        published = snippet.get("publishedAt")
        items.append(
            collector.item(
                title=snippet.get("title", "").strip(),
                url=envUrl("YOUTUBE_VIDEO_URL", videoId=videoId),
                publishedAt=utc(dateparser.isoparse(published)) if published else None,
                excerpt=excerpt(snippet.get("description", "")),
                author=snippet.get("channelTitle"),
            )
        )
    return items


@register
class YouTubeCollector(Collector):
    type = "youtube"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        channelId = self.source.opt("channelId")
        if not channelId:
            raise CollectorError(f"Source '{self.source.id}' needs channelId")
        try:
            resp = await fetch(client, envUrl("YOUTUBE_FEED_URL", channelId=channelId))
            return parseFeed(resp.content, self)
        except (httpx.HTTPError, CollectorError) as exc:
            apiKey = env("YOUTUBE_API_KEY", "")
            if not apiKey:
                raise CollectorError(
                    f"YouTube RSS feed failed ({exc}); set YOUTUBE_API_KEY to use the API fallback"
                ) from exc
            log.warning("YouTube RSS failed (%s); using the Data API", exc)
            # Every channel's uploads playlist id is its channel id with "UC" swapped for "UU".
            params = {
                "part": "snippet",
                "playlistId": "UU" + channelId[2:],
                "maxResults": 10,
                "key": apiKey,
            }
            resp = await fetch(client, envUrl("YOUTUBE_API_URL"), params=params)
            return parseApiItems(resp.json(), self)
