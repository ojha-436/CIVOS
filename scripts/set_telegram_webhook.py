"""Point the Telegram bot at the deployed CIVOS webhook.

Run once after the API is deployed, and again whenever the service URL or the
webhook secret changes. Registering a webhook implicitly stops long-polling —
the two are mutually exclusive, so `scripts/telegram_bot.py` will refuse to
fetch updates until you `--delete` this.

Usage:
    # resolve the Cloud Run URL automatically (needs gcloud + the API deployed)
    uv run python scripts/set_telegram_webhook.py

    # or give it explicitly
    uv run python scripts/set_telegram_webhook.py --url https://civos-api-xxxx.run.app

    uv run python scripts/set_telegram_webhook.py --show     # current state
    uv run python scripts/set_telegram_webhook.py --delete   # back to polling

Environment (read from .env if present):
    TELEGRAM_BOT_TOKEN        from @BotFather
    TELEGRAM_WEBHOOK_SECRET   any string; Telegram echoes it back on every
                              update and api/telegram.py rejects anything else

Neither value is ever printed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
API_ROOT = "https://api.telegram.org"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO / ".env")
    except ImportError:
        pass


def _call(token: str, method: str, params: dict | None = None) -> dict:
    url = f"{API_ROOT}/bot{token}/{method}"
    data = urllib.parse.urlencode(params or {}).encode() if params else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.load(r)


def _cloud_run_url() -> str | None:
    """Ask gcloud where civos-api lives, so the URL is never hand-copied."""
    try:
        out = subprocess.run(
            [
                "gcloud", "run", "services", "describe", "civos-api",
                "--region", "asia-south1", "--project", "civos-in",
                "--format", "value(status.url)",
            ],
            capture_output=True, text=True, timeout=60,
        )
        url = out.stdout.strip()
        return url or None
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="base URL of the deployed API, e.g. https://civos-api-x.run.app")
    ap.add_argument("--show", action="store_true", help="print current webhook state and exit")
    ap.add_argument("--delete", action="store_true", help="remove the webhook (restores polling)")
    args = ap.parse_args()

    _load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN not set (put it in .env).")

    me = _call(token, "getMe")
    if not me.get("ok"):
        sys.exit(f"token rejected by Telegram: {me}")
    username = me["result"]["username"]
    print(f"bot        : @{username}")

    if args.show:
        info = _call(token, "getWebhookInfo")["result"]
        print(f"webhook    : {info.get('url') or '(none — polling mode)'}")
        print(f"pending    : {info.get('pending_update_count', 0)}")
        if info.get("last_error_message"):
            print(f"last error : {info['last_error_message']}")
        return

    if args.delete:
        res = _call(token, "deleteWebhook", {"drop_pending_updates": "false"})
        print("deleted    :", res.get("ok"))
        return

    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not secret:
        sys.exit(
            "TELEGRAM_WEBHOOK_SECRET not set.\n"
            "Generate one:  python3 -c \"import secrets;print(secrets.token_urlsafe(32))\"\n"
            "Then add it to .env AND to the Cloud Run service, or the webhook "
            "will be registered with a secret the API does not know and every "
            "update will be rejected."
        )

    base = (args.url or _cloud_run_url() or "").rstrip("/")
    if not base:
        sys.exit("Could not resolve the API URL — pass --url explicitly.")
    if not base.startswith("https://"):
        sys.exit("Telegram requires an HTTPS webhook URL.")

    hook = f"{base}/telegram/webhook"
    res = _call(
        token,
        "setWebhook",
        {
            "url": hook,
            "secret_token": secret,
            # Only message updates are handled; asking for less means Telegram
            # sends less, and nothing silently queues up unread.
            "allowed_updates": json.dumps(["message", "edited_message"]),
            "drop_pending_updates": "true",
        },
    )
    if not res.get("ok"):
        sys.exit(f"setWebhook failed: {res}")

    print(f"webhook    : {hook}")
    print("registered : yes")

    info = _call(token, "getWebhookInfo")["result"]
    if info.get("last_error_message"):
        print(f"note       : Telegram reports a previous error — {info['last_error_message']}")
    print(f"\nVerify end to end:  open https://t.me/{username} and send 'test'")


if __name__ == "__main__":
    main()
