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
        headers={"X-Auth-ID": vobiz.auth_id(), "X-Auth-Token": vobiz.auth_token()},
        timeout=30.0,
    )


def _number() -> str:
    cfg = yaml.safe_load((REPO / "adapters" / "in" / "channels.yaml").read_text())["voice"]
    return cfg["number"]


def _digits(n: str) -> str:
    return "".join(c for c in n if c.isdigit())


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
    want = _digits(_number())
    console.rule("[bold]Vobiz[/bold]")
    console.print(f"account   [bold]{vobiz.auth_id()}[/bold]")
    console.print(f"number    [bold]{_number()}[/bold]")
    console.print(f"answer    [bold]{answer_url}[/bold]")

    with _client() as c:
        apps = c.get("/Application/").json().get("objects", [])
        app = next((a for a in apps if a.get("app_name") == APP_NAME), None)

        if app and app.get("answer_url") != answer_url:
            console.print(
                f"  [yellow]application exists but points elsewhere[/yellow]: {app.get('answer_url')}"
            )
            if apply:
                c.post(f"/Application/{app['app_id']}/", data={"answer_url": answer_url,
                                                               "answer_method": "POST"})
                console.print("  [green]updated[/green] answer_url")
        elif app:
            console.print(f"  [green]ok[/green] application {app['app_id']} already points here")
        elif apply:
            r = c.post("/Application/", data={"app_name": APP_NAME, "answer_url": answer_url,
                                              "answer_method": "POST"})
            if r.status_code >= 400:
                console.print(f"  [red]create failed {r.status_code}[/red] {r.text[:200]}")
                raise typer.Exit(1)
            app = r.json()
            console.print(f"  [green]created[/green] application {app.get('app_id')}")
        else:
            console.print("  [yellow]no application[/yellow] — run with --apply")

        nums = c.get("/Number/").json().get("objects", [])
        mine = next((n for n in nums if _digits(str(n.get("number", ""))) == want), None)
        t = Table(show_header=True, header_style="bold")
        for col in ("number", "application", "points at CIVOS"):
            t.add_column(col)
        for n in nums:
            nid = str(n.get("number"))
            attached = str(n.get("application") or "—")
            ok = bool(app) and str(app.get("app_id")) in attached
            t.add_row(nid, attached, "[green]yes[/green]" if ok else "[red]no[/red]")
        console.print(t)

        if mine is None:
            console.print(
                f"  [red]{_number()} is not on this account.[/red] Check adapters/in/channels.yaml "
                "against the console."
            )
            raise typer.Exit(1)

        already = bool(app) and str(app.get("app_id")) in str(mine.get("application") or "")
        if already:
            console.print("  [green]ok[/green] the number is attached to this application")
        elif apply and app:
            r = c.post(f"/Number/{_digits(_number())}/", data={"app_id": app["app_id"]})
            if r.status_code >= 400:
                console.print(f"  [red]attach failed {r.status_code}[/red] {r.text[:200]}")
                raise typer.Exit(1)
            console.print("  [green]attached[/green] the number to the application")
        else:
            console.print("  [yellow]not attached[/yellow] — run with --apply")

    console.print()
    console.print(
        "A green row above means Vobiz will deliver the call. It does not prove CIVOS answers it — "
        "dial the number and watch the logs for that."
    )


if __name__ == "__main__":
    typer.run(main)
