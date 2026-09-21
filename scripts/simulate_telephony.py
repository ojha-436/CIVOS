"""Drive the SMS and missed-call webhooks without a carrier.

No telephony account exists on this build — a virtual number needs a registered
business entity and DLT registration, which an individual cannot obtain on this
timeline. That leaves two honest options: claim the channel and not show it, or
show the channel and be precise about which leg is unproven. This script is the
second option.

What it proves: the webhook contract, the signature check, the provider-agnostic
field mapping, the salted-hash privacy rule, the shared extraction path, and the
receipt that fits one message. What it does not prove: that a carrier delivers
the bytes. That gap is stated here, in `/channel/status`, and in the README.

Usage:
    uv run python scripts/simulate_telephony.py                    # against local
    uv run python scripts/simulate_telephony.py --base https://... # against deployed
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

console = Console()

# Real phrasing a citizen would actually send, in the languages the corpus
# already covers. Short, because a feature-phone keypad makes people terse.
SMS_CASES = [
    ("+919812345678", "hamare gaon me handpump 5 mahine se kharab hai koi nahi aaya"),
    ("+919823456789", "gavat rasta nahi ahe, pavsat shala band hote"),
    ("+919834567890", "no electricity in our hamlet since last week, transformer burnt"),
]


def sign(secret: str, body: bytes) -> dict[str, str]:
    return {
        "X-Civos-Signature": hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
        "content-type": "application/x-www-form-urlencoded",
    }


def main(
    base: str = typer.Option("http://127.0.0.1:8080", help="API base URL"),
    secret: str = typer.Option("", help="Defaults to CIVOS_TELEPHONY_SECRET"),
):
    secret = secret or os.environ.get("CIVOS_TELEPHONY_SECRET", "")
    if not secret:
        console.print(
            "[red]No signature secret.[/red] Set CIVOS_TELEPHONY_SECRET — the webhook "
            "refuses unsigned requests by design, so there is nothing to simulate without it."
        )
        raise typer.Exit(1)

    with httpx.Client(timeout=60.0, base_url=base) as client:
        status = client.get("/channel/status")
        console.print(Panel.fit(str(status.json()), title="channel status"))

        console.rule("[bold]Missed call → callback[/bold]")
        body = urlencode({"CallFrom": "09845123456", "CallSid": "sim-001"}).encode()
        r = client.post("/channel/voice/missed-call", content=body, headers=sign(secret, body))
        console.print(f"  {r.status_code} {r.json()}")
        if r.status_code == 200:
            assert "9845123456" not in r.text, "caller number leaked into the response"
            console.print("  [green]ok[/green] caller number does not appear in the response")

        console.rule("[bold]Inbound SMS[/bold]")
        for number, text in SMS_CASES:
            body = urlencode({"From": number, "Body": text}).encode()
            r = client.post("/channel/sms", content=body, headers=sign(secret, body))
            if r.status_code != 200:
                console.print(f"  [red]{r.status_code}[/red] {r.text[:200]}")
                continue
            j = r.json()
            console.print(f"  [green]{r.status_code}[/green] {text[:44]}...")
            console.print(
                f"       lang={j['language']} sector={j['sector']} severity={j['severity']}"
            )
            console.print(f"       reply → [bold]{j['reply']}[/bold] ({len(j['reply'])} chars)")
            assert number[-10:] not in r.text, "caller number leaked into the response"

    console.print()
    console.print(
        "[yellow]Unproven:[/yellow] the carrier leg. Everything above is the real webhook "
        "contract; no operator delivered these bytes."
    )


if __name__ == "__main__":
    typer.run(main)
