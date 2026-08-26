from .arbeitnow import ArbeitnowScraper
from .arbeitsagentur import ArbeitsagenturScraper
from .ashby import AshbyScraper
from .base import BaseScraper, RawJob
from .careerjet import CareerjetScraper
from .fourdayweek import FourDayWeekScraper
from .greenhouse import GreenhouseScraper
from .hackernews import HackerNewsScraper
from .himalayas import HimalayasScraper
from .jobicy import JobicyScraper
from .jooble import JoobleScraper
from .jsearch import JSearchScraper
from .lever import LeverScraper
from .pythonjobs import PythonJobsScraper
from .recruitee import RecruiteeScraper
from .reddit import RedditScraper
from .reed import ReedScraper
from .remoteok import RemoteOKScraper
from .remotive import RemotiveScraper
from .simplifyjobs import SimplifyJobsScraper
from .smartrecruiters import SmartRecruitersScraper
from .themuse import TheMuseScraper
from .weworkremotely import WeWorkRemotelyScraper
from .workable import WorkableScraper
from .workday import WorkdayScraper
from .workingnomads import WorkingNomadsScraper
from .wuzzuf import WuzzufScraper

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
    # Expansion 2026-07 — Egypt + worldwide-remote, all free/no-auth.
    "wuzzuf": WuzzufScraper,
    "remotive": RemotiveScraper,
    "workingnomads": WorkingNomadsScraper,
    "weworkremotely": WeWorkRemotelyScraper,
    "pythonjobs": PythonJobsScraper,
    # P8 — BYO-key indirect Egypt/MENA + remote (off by default, no key).
    "jsearch": JSearchScraper,
    # 2026-07-21 — freelance/contract lane via subreddit hiring threads.
    "reddit": RedditScraper,
    # 2026-07-21 — BYO-affid Egypt/MENA aggregator (off by default, no key).
    "careerjet": CareerjetScraper,
    # 2026-08-26 — remote + 4-day-week board; carries hires_worldwide.
    "4dayweek": FourDayWeekScraper,
}

__all__ = [
    "ArbeitnowScraper",
    "ArbeitsagenturScraper",
    "AshbyScraper",
    "BaseScraper",
    "CareerjetScraper",
    "FourDayWeekScraper",
    "GreenhouseScraper",
    "HackerNewsScraper",
    "HimalayasScraper",
    "JSearchScraper",
    "JobicyScraper",
    "JoobleScraper",
    "LeverScraper",
    "PythonJobsScraper",
    "RawJob",
    "RecruiteeScraper",
    "RedditScraper",
    "ReedScraper",
    "RemoteOKScraper",
    "RemotiveScraper",
    "SCRAPER_REGISTRY",
    "SimplifyJobsScraper",
    "SmartRecruitersScraper",
    "TheMuseScraper",
    "WeWorkRemotelyScraper",
    "WorkableScraper",
    "WorkdayScraper",
    "WorkingNomadsScraper",
    "WuzzufScraper",
]
