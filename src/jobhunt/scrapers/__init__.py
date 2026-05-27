from .arbeitnow import ArbeitnowScraper
from .ashby import AshbyScraper
from .base import BaseScraper, RawJob
from .greenhouse import GreenhouseScraper
from .hackernews import HackerNewsScraper
from .himalayas import HimalayasScraper
from .jobicy import JobicyScraper
from .lever import LeverScraper
from .recruitee import RecruiteeScraper
from .remoteok import RemoteOKScraper
from .simplifyjobs import SimplifyJobsScraper
from .smartrecruiters import SmartRecruitersScraper
from .themuse import TheMuseScraper
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
    "simplifyjobs": SimplifyJobsScraper,
    "arbeitnow": ArbeitnowScraper,
    "jobicy": JobicyScraper,
    "himalayas": HimalayasScraper,
    "themuse": TheMuseScraper,
}

__all__ = [
    "ArbeitnowScraper",
    "AshbyScraper",
    "BaseScraper",
    "GreenhouseScraper",
    "HackerNewsScraper",
    "HimalayasScraper",
    "JobicyScraper",
    "LeverScraper",
    "RawJob",
    "RecruiteeScraper",
    "RemoteOKScraper",
    "SCRAPER_REGISTRY",
    "SimplifyJobsScraper",
    "SmartRecruitersScraper",
    "TheMuseScraper",
    "WorkableScraper",
    "WorkdayScraper",
]
