"""Entry point so `python -m jobhunt` and the PyInstaller binary both work."""

from jobhunt.cli import app

if __name__ == "__main__":
    app()
