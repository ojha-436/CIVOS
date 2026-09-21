"""Point the Vobiz number at CIVOS, and check that it stayed pointed.

Connecting an operator is two API calls and one thing that is easy to get wrong.
An application registers the Answer URL; the number is then attached to that
application. Miss the second step and every call reaches Vobiz, finds no
application, and drops — with nothing in the CIVOS logs, because the request
never arrives. `--check` exists for exactly that failure: it asks Vobiz what the
number is actually pointed at rather than what we believe we configured.

Usage:
    export VOBIZ_AUTH_ID=... VOBIZ_AUTH_TOKEN=...
    export CIVOS_PUBLIC_BASE_URL=https://civos-api-....run.app

    uv run python scripts/vobiz_setup.py --check      # report, change nothing
    uv run python scripts/vobiz_setup.py --apply      # create and attach
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from urllib.parse import quote

import httpx
import typer
import yaml
from rich.console import Console
from rich.table import Table

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api.channels import vobiz  # noqa: E402

console = Console()
APP_NAME = "CIVOS_Citizen_Intake"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=f"{vobiz.API_ROOT}/Account/{vobiz.auth_id()}",
        headers={
            "X-Auth-ID": vobiz.auth_id(),
            "X-Auth-Token": vobiz.auth_token(),
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _number() -> str:
    cfg = yaml.safe_load((REPO / "adapters" / "in" / "channels.yaml").read_text())["voice"]
    return cfg["number"]


def main(
    apply: bool = typer.Option(False, "--apply", help="Create the application and attach the number"),
    check: bool = typer.Option(False, "--check", help="Report what Vobiz currently has"),
):
    if not (vobiz.auth_id() and vobiz.auth_token()):
        console.print("[red]VOBIZ_AUTH_ID and VOBIZ_AUTH_TOKEN must be set.[/red]")
        raise typer.Exit(1)
    if not vobiz.public_base():
        console.print("[red]CIVOS_PUBLIC_BASE_URL must be set — it is the URL Vobiz signs.[/red]")
        raise typer.Exit(1)
    if not (apply or check):
        console.print("Pass --check to report, or --apply to configure.")
        raise typer.Exit(1)

    answer_url = vobiz.callback_url("/channel/voice/answer")
    want = _number()
    console.rule("[bold]Vobiz[/bold]")
    console.print(f"account   [bold]{vobiz.auth_id()}[/bold]")
    console.print(f"number    [bold]{want}[/bold]")
    console.print(f"answer    [bold]{answer_url}[/bold]")
    console.print()

    with _client() as c:
        # ── the number ──────────────────────────────────────────────────────
        # Lowercase `/numbers`, not `/Number/`. Both exist; the capitalised one
        # answers 401 on this account and the lowercase one is what the Phone
        # Numbers API documents. Its payload is `items`, not `objects`.
        r = c.get("/numbers")
        if r.status_code != 200:
            console.print(f"[red]GET /numbers -> {r.status_code}[/red] {r.text[:200]}")
            raise typer.Exit(1)
        payload = r.json()
        items = payload.get("items", [])
        listed = next((n for n in items if n.get("e164") == want), None)
        # Listed is not owned. A trial account is lent a shared number that shows
        # up here as active and voice-enabled with an empty account_id, and Vobiz
        # refuses to attach an application to it.
        mine = listed if listed and vobiz._routable(listed) else None

        t = Table(show_header=True, header_style="bold")
        for col in ("number", "country", "status", "voice", "sms", "blocked"):
            t.add_column(col)
        for n in items:
            caps = n.get("capabilities") or {}
            t.add_row(
                str(n.get("e164")), str(n.get("country")), str(n.get("status")),
                "yes" if caps.get("voice") else "no",
                "yes" if caps.get("sms") else "[dim]no[/dim]",
                "[red]yes[/red]" if n.get("is_blocked") else "no",
            )
        console.print(t)

        if mine is None and listed is not None:
            console.print(
                f"[red]{want} is listed but not owned by {vobiz.auth_id()}.[/red] "
                f"account_id={listed.get('account_id')!r} is_trial_number={listed.get('is_trial_number')} "
                f"status={listed.get('status')!r}"
            )
            console.print(
                "  This is Vobiz's [bold]shared trial number[/bold]. It answers, but an application "
                "cannot be attached to it — Vobiz returns 400 access denied — so calls stop at the\n"
                "  operator. Purchase a dedicated number in the console, update\n"
                "  adapters/in/channels.yaml if it differs, and re-run --apply."
            )
        elif mine is None:
            console.print(
                f"[red]{want} is not held by account {vobiz.auth_id()}.[/red]"
            )
            if payload.get("trial_message"):
                console.print(f"  operator says: [yellow]{payload['trial_message']}[/yellow]")
            console.print(
                "  Nothing here can fix that: an application can be registered, but a number the\n"
                "  account does not own cannot be pointed anywhere. Buy or transfer the number in\n"
                "  the console, then re-run --apply. The application below is created regardless,\n"
                "  so attaching later is one step."
            )
        if payload.get("is_trial") or (mine or {}).get("is_trial_number"):
            console.print(
                "[yellow]Trial account.[/yellow] Trial numbers usually accept calls only from "
                "verified handsets — verify the phone you will demo from, in the console, before "
                "relying on it."
            )
        if (mine or {}).get("awaiting_registration"):
            console.print("[yellow]awaiting_registration is true[/yellow] — the number may not route yet.")

        # ── the application ─────────────────────────────────────────────────
        apps = c.get("/Application/").json().get("objects", [])
        app = next((a for a in apps if a.get("app_name") == APP_NAME), None)

        if app and app.get("answer_url") != answer_url:
            console.print(f"[yellow]application points elsewhere[/yellow]: {app.get('answer_url')}")
            if apply:
                r = c.post(f"/Application/{app['app_id']}/",
                           json={"answer_url": answer_url, "answer_method": "POST"})
                console.print(f"  update -> {r.status_code}")
        elif app:
            console.print(f"[green]ok[/green] application {app['app_id']} already answers at this URL")
        elif apply:
            r = c.post("/Application/", json={"app_name": APP_NAME, "answer_url": answer_url,
                                              "answer_method": "POST"})
            if r.status_code >= 400:
                console.print(f"[red]create application -> {r.status_code}[/red] {r.text[:250]}")
                raise typer.Exit(1)
            app = r.json()
            console.print(f"[green]created[/green] application {app.get('app_id')}")
        else:
            console.print("[yellow]no application yet[/yellow] — run with --apply")

        # ── attach ──────────────────────────────────────────────────────────
        # The number payload carries no application field, so there is nothing to
        # read back: attaching is the only way to know, and it is idempotent.
        if apply and app:
            enc = quote(want, safe="")
            r = c.post(f"/numbers/{enc}/application", json={"application_id": app["app_id"]})
            if r.status_code >= 400:
                console.print(f"[red]attach -> {r.status_code}[/red] {r.text[:250]}")
                raise typer.Exit(1)
            console.print(f"[green]attached[/green] {want} -> application {app['app_id']}")

    console.print()
    if mine is None:
        console.print(
            "[red]Not routable yet.[/red] The application is registered and CIVOS answers, but the "
            "operator does not hold the number, so no call can reach it."
        )
        raise typer.Exit(1)
    console.print(
        "Vobiz will now deliver calls to the answer URL. That is not proof CIVOS answers them — "
        "dial the number and watch the service logs for that."
    )


if __name__ == "__main__":
    typer.run(main)
