from .arbeitnow import ArbeitnowScraper
from .arbeitsagentur import ArbeitsagenturScraper
from .ashby import AshbyScraper
from .base import BaseScraper, RawJob
from .findajob import FindAJobScraper
from .greenhouse import GreenhouseScraper
from .hackernews import HackerNewsScraper
from .himalayas import HimalayasScraper
from .jobicy import JobicyScraper
from .jooble import JoobleScraper
from .lever import LeverScraper
from .recruitee import RecruiteeScraper
from .reed import ReedScraper
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
    "jooble": JoobleScraper,
    "arbeitsagentur": ArbeitsagenturScraper,
    "reed": ReedScraper,
    "findajob": FindAJobScraper,
}

__all__ = [
    "ArbeitnowScraper",
    "ArbeitsagenturScraper",
    "AshbyScraper",
    "BaseScraper",
    "FindAJobScraper",
    "GreenhouseScraper",
    "HackerNewsScraper",
    "HimalayasScraper",
    "JobicyScraper",
    "JoobleScraper",
    "LeverScraper",
    "RawJob",
    "RecruiteeScraper",
    "ReedScraper",
    "RemoteOKScraper",
    "SCRAPER_REGISTRY",
    "SimplifyJobsScraper",
    "SmartRecruitersScraper",
    "TheMuseScraper",
    "WorkableScraper",
    "WorkdayScraper",
]
