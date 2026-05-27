"""Entry point so `python -m jobhunt` and the PyInstaller binary both work."""

import sys

from jobhunt.cli import app

if __name__ == "__main__":
    # When double-clicked (no arguments), default to "app" mode so the server
    # starts and a browser tab opens — instead of printing help and exiting.
    if len(sys.argv) == 1:
        sys.argv.append("app")
    app()
