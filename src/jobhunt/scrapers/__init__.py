from .ashby import AshbyScraper
from .base import BaseScraper, RawJob
from .greenhouse import GreenhouseScraper
from .hackernews import HackerNewsScraper
from .lever import LeverScraper
from .recruitee import RecruiteeScraper
from .remoteok import RemoteOKScraper
from .smartrecruiters import SmartRecruitersScraper
from .workable import WorkableScraper
from .workday import WorkdayScraper

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "greenhouse": GreenhouseScraper,
    "lever": LeverScraper,
    "ashby": AshbyScraper,
    "workable": WorkableScraper,
    "smartrecruiters": SmartRecruitersScraper,
    "recruitee": RecruiteeScraper,
    "workday": WorkdayScraper,
    "remoteok": RemoteOKScraper,
    "hackernews": HackerNewsScraper,
}

__all__ = [
    "AshbyScraper",
    "BaseScraper",
    "GreenhouseScraper",
    "HackerNewsScraper",
    "LeverScraper",
    "RawJob",
    "RecruiteeScraper",
    "RemoteOKScraper",
    "SCRAPER_REGISTRY",
    "SmartRecruitersScraper",
    "WorkableScraper",
    "WorkdayScraper",
]
