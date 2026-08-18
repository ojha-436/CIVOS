"""Deploy firestore.rules to the Firebase project.

Uses the Firebase Rules API with the caller's gcloud credentials, so there is no
service-account key to store and no firebase CLI dependency.

Why this exists as a script rather than a console click: the rules are the only
real protection on profile data, so they belong in version control next to the
code they protect, and deploying them has to be repeatable by anyone with project
access.

Usage:
    gcloud auth login          # once
    uv run python scripts/deploy_firestore_rules.py
    uv run python scripts/deploy_firestore_rules.py --check   # print live rules
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES = REPO / "firestore.rules"
PROJECT = "civos-in"
BASE = "https://firebaserules.googleapis.com/v1"


def token() -> str:
    out = subprocess.run(
        ["gcloud", "auth", "print-access-token"], capture_output=True, text=True
    )
    if out.returncode != 0:
        sys.exit("gcloud auth print-access-token failed — run `gcloud auth login`.")
    return out.stdout.strip()


def call(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token()}")
    req.add_header("x-goog-user-project", PROJECT)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url}\n{e.code}: {e.read().decode('utf-8', 'replace')[:500]}")


def main() -> None:
    if "--check" in sys.argv:
        rel = call("GET", f"{BASE}/projects/{PROJECT}/releases/cloud.firestore")
        rs = call("GET", f"{BASE}/{rel['rulesetName']}")
        print(rs["source"]["files"][0]["content"])
        return

    source = RULES.read_text()
    ruleset = call(
        "POST",
        f"{BASE}/projects/{PROJECT}/rulesets",
        {"source": {"files": [{"name": "firestore.rules", "content": source}]}},
    )
    name = ruleset["name"]
    print(f"ruleset created: {name}")

    release = f"projects/{PROJECT}/releases/cloud.firestore"
    try:
        call("PATCH", f"{BASE}/{release}", {"release": {"name": release, "rulesetName": name}})
        print("release updated")
    except SystemExit:
        call("POST", f"{BASE}/projects/{PROJECT}/releases",
             {"name": release, "rulesetName": name})
        print("release created")
    print("firestore.rules is live")


if __name__ == "__main__":
    main()
