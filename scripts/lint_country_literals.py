"""Fail the build if a country literal reaches core/.

SPEC P0-14 claims a second country is a config directory rather than a code
change. This script is the evidence for that claim, which is why it runs in CI
rather than being a Day-8 tidy-up: a claim nobody checks is a slide, and
cross-border applicability is 20% of the score.

Why not `grep -riE '\\b(india|IN)\\b' core/`, as the plan first suggested: `IN` is
a SQL keyword and `in` is an English preposition, so that pattern matches almost
every line of Python ever written. This scans string literals, identifiers and
comments separately instead, and distinguishes a *violation* (a literal in code)
from a *smell* (a country named in prose).

Usage:
    uv run python scripts/lint_country_literals.py            # lint core/
    uv run python scripts/lint_country_literals.py --path api # lint somewhere else
    uv run python scripts/lint_country_literals.py --strict   # comments fail too
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

import typer
import yaml
from rich.console import Console

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config" / "country_literals.yaml"
console = Console()


@dataclass
class Finding:
    path: Path
    line: int
    term: str
    where: str  # "code" | "prose"
    excerpt: str

    @property
    def is_violation(self) -> bool:
        return self.where == "code"


def load_terms() -> tuple[list[str], list[str], set[str]]:
    cfg = yaml.safe_load(CONFIG.read_text())
    iso = [str(c) for c in cfg.get("iso_codes") or []]
    words: list[str] = []
    for key in ("names", "admin_terms", "schemes", "datasets", "misc"):
        words.extend(str(w) for w in (cfg.get(key) or []))
    exemptions = {str(e) for e in (cfg.get("exemptions") or [])}
    return iso, words, exemptions


def build_word_pattern(words: list[str]) -> re.Pattern[str]:
    # Longest first so "South Africa" wins over a hypothetical "Africa".
    alts = sorted((re.escape(w) for w in words), key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(alts) + r")(?!\w)", re.IGNORECASE)


def scan_file(path: Path, iso: list[str], word_re: re.Pattern[str]) -> list[Finding]:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    findings: list[Finding] = []

    def excerpt(lineno: int) -> str:
        return lines[lineno - 1].strip()[:120] if 0 < lineno <= len(lines) else ""

    # -- docstrings are prose; every other string is code -------------------
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:
        console.print(f"[red]{path}: could not parse — {exc}[/red]")
        return findings

    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstring_nodes.add(id(first.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            where = "prose" if id(node) in docstring_nodes else "code"
            text = node.value
            if where == "code" and text in iso:
                findings.append(Finding(path, node.lineno, text, "code", excerpt(node.lineno)))
            for m in word_re.finditer(text):
                findings.append(Finding(path, node.lineno, m.group(1), where, excerpt(node.lineno)))
        elif isinstance(node, ast.Name):
            for m in word_re.finditer(node.id):
                findings.append(Finding(path, node.lineno, m.group(1), "code", excerpt(node.lineno)))

    # -- comments are prose --------------------------------------------------
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                for m in word_re.finditer(tok.string):
                    findings.append(Finding(path, tok.start[0], m.group(1), "prose", tok.line.strip()[:120]))
    except tokenize.TokenError:
        pass

    return findings


def main(
    path: str = typer.Option("core", "--path", help="Directory to lint, relative to the repo root"),
    strict: bool = typer.Option(False, "--strict", help="Treat prose mentions as failures too"),
) -> None:
    iso, words, exemptions = load_terms()
    word_re = build_word_pattern(words)

    target = REPO / path
    if not target.exists():
        console.print(f"[red]No such path: {target}[/red]")
        raise typer.Exit(code=2)

    files = [p for p in sorted(target.rglob("*.py")) if str(p.relative_to(REPO)) not in exemptions]
    findings: list[Finding] = []
    for f in files:
        findings.extend(scan_file(f, iso, word_re))

    violations = [f for f in findings if f.is_violation]
    prose = [f for f in findings if not f.is_violation]

    console.print(f"Scanned [bold]{len(files)}[/bold] file(s) under [bold]{path}/[/bold]")

    for f in violations:
        rel = f.path.relative_to(REPO)
        console.print(f"[red]VIOLATION[/red] {rel}:{f.line} — country literal [bold]{f.term}[/bold] in code")
        console.print(f"          {f.excerpt}")

    for f in prose:
        rel = f.path.relative_to(REPO)
        label = "[red]VIOLATION[/red]" if strict else "[yellow]note[/yellow]"
        console.print(f"{label} {rel}:{f.line} — [bold]{f.term}[/bold] named in prose")

    failed = violations if not strict else findings
    if failed:
        console.print(f"\n[red]FAIL[/red] — {len(failed)} country literal(s) in {path}/. "
                      "Move them to adapters/<iso>/.")
        raise typer.Exit(code=1)

    console.print(f"\n[green]PASS[/green] — no country literals in {path}/. "
                  f"({len(prose)} prose mention(s), not failing)")


if __name__ == "__main__":
    typer.run(main)
