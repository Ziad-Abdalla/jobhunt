"""Entry point so `python -m jobhunt` and the PyInstaller binary both work."""

import sys

if __name__ == "__main__":
    try:
        from jobhunt.cli import app
        app()
    except Exception:
        if getattr(sys, "frozen", False):
            import traceback
            traceback.print_exc()
            input("\nPress Enter to close...")
        else:
            raise
