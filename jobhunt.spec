# PyInstaller spec for building a single-file jobhunt binary.
# Build:   pip install pyinstaller
#          pyinstaller jobhunt.spec --clean
# Outputs: dist/jobhunt (or dist/jobhunt.exe on Windows)
#
# The resulting binary bundles Python + every dependency. End users do not need
# Python installed. First launch creates ~/.local/share/jobhunt (or platform
# equivalent) automatically.

# ruff: noqa
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ["src/jobhunt/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/jobhunt/templates", "jobhunt/templates"),
        ("src/jobhunt/static", "jobhunt/static"),
        ("src/jobhunt/sources.yaml", "jobhunt"),
    ]
    + collect_data_files("uvicorn", include_py_files=False)
    + collect_data_files("apscheduler", include_py_files=False),
    hiddenimports=[
        # jobhunt scrapers (dynamically loaded via registry)
        "jobhunt.scrapers.greenhouse",
        "jobhunt.scrapers.lever",
        "jobhunt.scrapers.ashby",
        "jobhunt.scrapers.workable",
        "jobhunt.scrapers.smartrecruiters",
        "jobhunt.scrapers.recruitee",
        "jobhunt.scrapers.workday",
        "jobhunt.scrapers.remoteok",
        "jobhunt.scrapers.hackernews",
        "jobhunt.scrapers.simplifyjobs",
        "jobhunt.scrapers.arbeitnow",
        "jobhunt.scrapers.jobicy",
        "jobhunt.scrapers.himalayas",
        "jobhunt.scrapers.themuse",
        "jobhunt.scrapers.jooble",
        "jobhunt.scrapers.arbeitsagentur",
        "jobhunt.scrapers.reed",
        # jobhunt internal modules (imported by string or lazily)
        "jobhunt.main",
        "jobhunt.cli",
        "jobhunt.config",
        "jobhunt.db",
        "jobhunt.models",
        "jobhunt.filters",
        "jobhunt.refresh",
        "jobhunt.extract",
        "jobhunt.dedup",
        "jobhunt.scoring",
        "jobhunt.salary_estimator",
        "jobhunt.scheduler",
        "jobhunt.notifications",
        "jobhunt.alerts",
        "jobhunt.sources_admin",
        # uvicorn internals (needed for frozen binary)
    ]
    + collect_submodules("uvicorn")
    + [
        # multipart (file uploads)
        "multipart",
        # pydantic internals
        "pydantic",
        "pydantic_settings",
        "pydantic_core",
        # email-validator used by pydantic
        "email_validator",
        # httpx + httpcore for scraping
        "httpx",
        "httpcore",
        "h11",
        "anyio",
        "anyio._backends._asyncio",
        "sniffio",
        # sqlalchemy
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="jobhunt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
