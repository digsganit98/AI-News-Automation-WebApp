"""Collectors fetch items from sources. Importing this package registers every type."""

from digest.collectors import (  # noqa: F401  (imported to register each collector type)
    hackerNewsCollector,
    huggingFaceCollector,
    newsletterInboxCollector,
    rssFeedCollector,
    webPageCollector,
    webSearchCollector,
    youtubeCollector,
)
from digest.collectors.collectorBase import Collector, CollectorError, buildCollector

__all__ = ["Collector", "CollectorError", "buildCollector"]
