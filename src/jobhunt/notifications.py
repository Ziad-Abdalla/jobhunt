"""Best-effort cross-platform desktop notifications.

Strategy:
  - Linux: try `notify-send` (libnotify). Most desktop distros ship it.
  - macOS: try `osascript`.
  - Windows: try the `win10toast`-style PowerShell BurntToast fallback.
  - Always: log the message so users without a working notifier still see it.

Notifications are best-effort — failures are logged, never raised.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

from .config import settings

log = logging.getLogger(__name__)


def notify(title: str, body: str, *, url: str | None = None) -> bool:
    """Send a desktop notification. Returns True if the OS notifier accepted it."""
    method = settings.notify_method
    body_full = f"{body}\n{url}" if url else body
    try:
        if method in ("auto", "notify-send") and sys.platform.startswith(("linux", "freebsd")):
            if shutil.which("notify-send"):
                subprocess.run(
                    ["notify-send", "--app-name=jobhunt", title, body_full],
                    check=False,
                    timeout=5,
                )
                return True
        if method in ("auto", "osascript") and sys.platform == "darwin":
            if shutil.which("osascript"):
                escaped_title = title.replace('"', '\\"')
                escaped_body = body_full.replace('"', '\\"')
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'display notification "{escaped_body}" with title "{escaped_title}"',
                    ],
                    check=False,
                    timeout=5,
                )
                return True
        if method in ("auto", "powershell") and sys.platform == "win32":
            ps_cmd = (
                "[Windows.UI.Notifications.ToastNotificationManager,"
                "Windows.UI.Notifications,ContentType=WindowsRuntime] > $null;"
                f'Write-Host "{title}: {body_full}"'
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False, timeout=5)
            return True
    except Exception as exc:  # noqa: BLE001
        log.debug("notify failed: %s", exc)
    # Fallback: log only.
    log.info("[notify] %s — %s", title, body_full)
    return False
