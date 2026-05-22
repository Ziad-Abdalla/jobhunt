# Installing jobhunt

jobhunt is a local-first app. Everything runs on your machine, the SQLite DB
lives in `./data/jobhunt.db`, and no data leaves your computer.

Requires **Python 3.11+**.

## Quickstart with `uv` (Linux / macOS / WSL)

[`uv`](https://docs.astral.sh/uv/) is the fastest path.

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt.git
cd jobhunt
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

jobhunt scrape           # first scrape (a few minutes)
jobhunt serve            # open http://127.0.0.1:8765
```

If you don't have `uv` yet:

```bash
pip install --user uv
```

Or use the bundled helper, which checks your Python version and sets up the
venv for you:

```bash
./scripts/install.sh           # assumes uv is installed
./scripts/install.sh --with-uv # also installs uv via pip --user
```

## Quickstart with plain `pip` (any OS)

```bash
git clone https://github.com/Abdalla2004-collab/Jobhunt.git
cd jobhunt
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

jobhunt scrape
jobhunt serve
```

Windows users can run the bundled PowerShell installer:

```powershell
.\scripts\install.ps1
```

## Docker quickstart

The Docker image binds to `127.0.0.1` on the host so the service is reachable
from your browser but not from the network. The SQLite DB lives in `./data/`
on the host (mounted into the container), so it survives rebuilds.

```bash
docker compose up --build -d
```

Open <http://127.0.0.1:8765>.

To stop:

```bash
docker compose down
```

The compose file sets `JOBHUNT_REFRESH_INTERVAL_MINUTES=360`, so the container
re-scrapes every 6 hours automatically.

## Optional features

### CV matching

Embeds your CV locally with `sentence-transformers` and ranks jobs by
semantic similarity to the job descriptions. Everything runs on your machine.
Adds roughly 500MB of dependencies.

```bash
pip install -e ".[match]"
```

### LinkedIn (opt-in, not recommended)

> **Warning:** scraping LinkedIn violates their Terms of Service and can get
> your account restricted or permanently banned. The default sources
> (Greenhouse, Lever, Ashby, RemoteOK, Hacker News) are deliberately chosen
> because they welcome polite scraping. Use this extra at your own risk.

```bash
pip install -e ".[linkedin]"
```

## Self-update (auto-refresh)

jobhunt has an in-process scheduler. Setting

```
JOBHUNT_REFRESH_INTERVAL_MINUTES=360
```

(or any positive integer) makes the server re-run the full scrape on that
interval while `jobhunt serve` is running. No cron, no launchd, no Task
Scheduler. The default `docker-compose.yml` sets this to 360 (6 hours).

To disable, leave it unset or set it to `0`.

## Where things live

| Path                              | What                                  |
|-----------------------------------|---------------------------------------|
| `./data/jobhunt.db`               | SQLite database (gitignored)          |
| `./src/jobhunt/sources.yaml`      | Default scrape sources                |
| `./src/jobhunt/local_sources.yaml`| Your overrides (gitignored)           |
| `./.env`                          | Optional config overrides             |

See the top-level `README.md` for filters, CLI commands, and the full feature
tour.
