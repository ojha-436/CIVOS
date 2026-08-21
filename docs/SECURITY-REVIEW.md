# Security review — CIVOS

**Reviewed:** 21 Aug 2026 · **Revised:** 21 Aug 2026 (second pass) · **Scope:** the served surface (`api/`, `core/`,
`firestore.rules`, `Dockerfile`, `.github/workflows/deploy.yml`) and the
dependency supply chain.

Read the [Not fixed](#not-fixed--accepted-risk) and
[Not reviewed](#not-reviewed) sections before quoting this document. A review
that only lists what it fixed is marketing.

## Summary

| | Count |
|---|---|
| Findings fixed | 21 |
| Open findings (action required) | 1 |
| Accepted risks, with reasons | 5 |
| Areas not reviewed | 4 |
| Known CVEs in 66 Python packages (`pip-audit`) | **0** |
| Known CVEs in npm dependencies (`npm audit`) | **0** |
| `bandit` HIGH/MEDIUM in `api/` + `core/` | **0** |
| Security tests added | 68 (`tests/test_security.py`) |
| Total suite | **76 passing** |

Every fix below has a test, and the suite gates the deploy: `deploy` declares
`needs: [lint, test, security]`.

---

## The two that mattered

**1. Live secrets were one `docker build` from being published.** `.dockerignore`
did not exclude `.env`, and the Dockerfile ends with `COPY . .`. The real
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` would therefore be baked into
an image layer in Artifact Registry, readable by anyone with pull access —
permanently, since layers are immutable and cached. They are *already* injected
at runtime by `--set-env-vars`, so shipping them in the image bought nothing.
Fixed, plus a CI step that fails the build if `.env` ever leaves the ignore file,
plus two tests. *(The same gap was also uploading 5.9 GB of launch-film frames to
Cloud Build on every deploy.)*

**2. An unauthenticated stranger could spend the project's Gemini budget.**
`/signal` and `/dossier` each call Gemini, on a service deployed
`--allow-unauthenticated` with `CORS: *` and no rate limit, reading uploads into
memory with an unbounded `await upload.read()`. One large POST was an
out-of-memory kill of a 1 GiB instance; a loop was an open tap on the bill. Now
capped, rate-limited and pre-checked — see the honest limits in
[Not fixed](#not-fixed--accepted-risk).

---

## Open — action required (not a code change)

**Two Google API keys can bill Gemini to this project and have no application
restrictions.**

```
$ gcloud services api-keys list --project=civos-in
  "xirp"   api targets: generativelanguage.googleapis.com   (no referrer/IP restriction)
  "CIVOS"  api targets: generativelanguage.googleapis.com   (no referrer/IP restriction)
```

Nothing in this codebase uses an API key for Gemini — every call goes through
`genai.Client(vertexai=True, ...)`, which is service-account ADC
(`api/extraction.py`, `api/main.py`, `scripts/geo_ground.py`). So these are
leftovers. An unrestricted key is a bearer credential: whoever holds the string
can spend against the project until it is revoked, and unlike the service
account it is not bounded by IAM.

**Recommended:** delete both. Left for you to run rather than done here, because
deleting a cloud credential is not reversible and is outside the "codebase and
git repo" scope of this change:

```bash
gcloud services api-keys list --project=civos-in --format="value(uid,displayName)"
gcloud services api-keys delete <UID> --project=civos-in    # for each of xirp, CIVOS
```

If either is in use by something outside this repo, restrict it first
(`--allowed-referrers` or `--allowed-ips`) rather than deleting it.

---

## Fixed

Severity is impact on *this* deployment, not a generic CVSS.

### Critical

| # | Finding | Fix |
|---|---|---|
| 1 | `.env` (live bot token + webhook secret) enters the Docker build context via `COPY . .` | `.dockerignore` rewritten; CI asserts it; 2 tests |

### High

| # | Finding | Fix |
|---|---|---|
| 2 | Unbounded `await upload.read()` on `/signal` (audio, image) and `/import` — single-request OOM | `api/guards.read_capped` streams with a hard cap; `check_content_length` rejects on the declared length first |
| 3 | No rate limiting on endpoints that invoke Gemini | Sliding-window global **and** per-IP limiters in `api/guards.py` |
| 4 | Prompt injection in `/dossier`: an untyped `dict` interpolated into a line-structured prompt, so a newline forged bundle fields | `_flat()` collapses newlines and control chars — a **structural** control, not a keyword denylist; `DossierRequest` constrains every field; the prompt states bundle values are data, never instructions |
| 5 | `/telegram/status` returned `str(exc)`; httpx embeds the request URL in errors, and every Bot API URL carries the token in its path — so the endpoint could publish the bot token, which its own docstring promised it never does | Generic message; exception logged only |

### Medium

| # | Finding | Fix |
|---|---|---|
| 6 | `/signal` returned `f"Extraction failed: {exc}"` — could carry raw model output (quoting the system prompt back), the Vertex endpoint, and the project id | `safe_detail()`: log fully, return a fixed string |
| 7 | Client-supplied `content_type` forwarded verbatim to Vertex | `_safe_mime()` allowlist with fallback |
| 8 | **Live bug.** `population_affected: null` (sent for the 115 districts with no reconciled Census figure) hit `f"{None:,}"` → `TypeError` → swallowed by a bare `except` → *the exception text was returned as the dossier prose*. A crash rendered as a document. | Nullable field rendered explicitly as `NOT AVAILABLE` with an instruction not to estimate; empty completions now raise; regression test |
| 9 | Telegram `file_path` interpolated into a URL unvalidated; no download size cap | Anchored regex that rejects `..`, schemes and hosts; 20 MB cap |
| 10 | Container ran as **root** | `USER 10001`, non-login shell, `chown` |
| 11 | Base image unpinned (`python:3.12-slim` is a moving tag) | Pinned by digest (resolved and verified against the registry API), plus `apt-get upgrade` |
| 12 | `/aggregate` re-read and re-parsed a multi-MB fixture **per request** — a disk/CPU amplifier for any caller | `lru_cache` |

### Low

| # | Finding | Fix |
|---|---|---|
| 13 | Firestore profile fields had a key allowlist but no type or size limits — an authenticated user could store ~1 MiB of arbitrary text per field | `sane()` asserts `is string` and per-field size caps |
| 14 | No security response headers | `nosniff`, `DENY`, `no-referrer`, `default-src 'none'`, `no-store` |
| 15 | `CORS: *` hardcoded, credentials unstated | `CIVOS_ALLOWED_ORIGINS` env var; `allow_credentials=False` explicitly, and a comment on why the pair is dangerous |
| 16 | Unbounded free-text and query params echoed into responses/prompts | `clamp_text()` |
| 17 | `bandit` HIGH: SHA-1 (used as a filename disambiguator) | `usedforsecurity=False` — silences it honestly rather than leaving a HIGH to re-triage |

### Second pass — the accepted risks that turned out to be fixable

| # | Finding | Fix |
|---|---|---|
| 18 | **No dependency lockfile** (was the largest supply-chain gap). `uv.lock` was gitignored; the Dockerfile installed a hand-written package list that duplicated `pyproject.toml`; CI audited a fresh resolution rather than the shipped one | `uv.lock` committed. Dockerfile installs from it via `uv export --frozen … --require-hashes`, so a substituted or republished artifact **fails the build** instead of installing quietly. CI runs `uv lock --check` and audits the exported locked set. Verified end to end: 60 hash-pinned packages install and the app runs from them. 5 tests |
| 19 | **No audit logging** — for a service whose output attaches to funding requests, no record of who called what | One structured line per request: method, path, status, duration, and a **salted digest** of the caller. Deliberately excludes the query string, both bodies, and the raw address — an access log that accumulated citizen text would contradict the privacy guarantee the same service prints on its receipts. The salt defaults to a per-process random value, so digests cannot be correlated across restarts or rainbow-tabled from the IPv4 space. 2 tests |
| 20 | `/import` reported `queued: N` for records it never queued | Now reports `parseable` and `persisted: 0` with a note saying plainly that nothing was stored. For a project whose thesis is measurement integrity, an endpoint overstating its own behaviour is the wrong bug to leave in. 1 test |
| 21 | Firebase browser-key restrictions were claimed but unverified | **Verified.** Referrer-restricted to the Cloud Run, Firebase Hosting and localhost origins, and scoped by API target. The claim in commit `0b9a92b` holds |

---

## Not fixed — accepted risk

These are real. They are listed because a reader deciding whether to trust this
service needs them.

**A. There is no authentication on the API.** Deliberate: a citizen intake form
that demands a login defeats the product's central claim about reach, and
evaluators need the demo to work. Mitigation is the caps and limits above. The
proper fix is a quota layer in front — Cloud Armor, or API Gateway with per-key
quotas — plus splitting the surface so only unauthenticated *intake* stays open
and `/aggregate` and `/dossier` require a token.

**B. Rate limiting is per-instance and in-memory.** With `--max-instances 3` the
effective ceiling is 3x what is configured, and any restart resets the counters.
This bounds the blast radius of abuse; it is **not** a quota system. Shared state
(Redis / Memorystore) or an edge policy is the real answer.

**C. The per-IP limiter is spoofable.** The client address comes from
`X-Forwarded-For`, which a caller can prepend to. Per-IP limiting is therefore a
fairness measure; the **global** limiter is the one that actually bounds spend.
Documented in the code so nobody mistakes it for a security boundary.

**D. A long-lived service-account key authenticates CI.**
`github-deploy@civos-in` has one `USER_MANAGED` key created 15 Aug 2026 and never
rotated, stored as `secrets.GCP_SA_KEY`. Its roles are properly scoped (no
Owner/Editor; `run.admin`, `artifactregistry.admin`, `cloudbuild.builds.editor`,
`storage.admin`, `iam.serviceAccountUser`) though `storage.admin` is broader than
the Cloud Build staging bucket needs. Keyless **Workload Identity Federation**
removes the standing credential entirely and is the current best practice.

**E. Runtime secrets live in the Cloud Run service config.** `--set-env-vars`
makes them readable by anyone holding `run.services.get`. Secret Manager with
`--set-secrets` gives versioning, rotation and separate IAM.

---

## Not reviewed

1. **No live penetration test.** Everything here is source review plus offline
   tests. The deployed endpoints were not attacked.
2. **BigQuery IAM and dataset-level access** were not reviewed, nor whether the
   runtime service account can read more than it needs.
3. **No DDoS/WAF layer**, no abuse detection, and no alerting on the rate-limit
   counters. The counters are now logged, so an alert is possible; none is wired.
4. **Console access is not logged.** The API now emits an access line per request
   (finding 19), but the Next.js console does not, so who *read* which dossier is
   still unrecorded.

### Reviewed on the second pass, and clean

- **The Next.js console has no XSS sink.** One `dangerouslySetInnerHTML` exists,
  in `app/layout.tsx`, and it renders `THEME_INIT` — a static template literal
  with no interpolation, used to set `data-theme` before hydration. Citizen text
  and model output (`qt.original`, `prose`) render as React text children, which
  escape by default. No `innerHTML`, `eval`, `new Function` or `document.write`
  anywhere. External links carry `rel="noopener noreferrer"`.

---

## Reproducing this review

```bash
uv run pytest -q                                     # 68 tests, offline, no billing
uv run python scripts/lint_country_literals.py       # cross-border gate

uv pip freeze | sed 's/\x1b\[[0-9;]*m//g' \
  | grep -E '^[A-Za-z0-9._-]+==' > /tmp/reqs.txt
uvx --python 3.12 pip-audit -r /tmp/reqs.txt --no-deps   # dependency CVEs
uvx --python 3.12 bandit -r api core -ll                 # served surface (blocking)
uvx --python 3.12 bandit -r scripts -ll                  # build tooling (advisory)
cd console && npm audit                                  # frontend deps
```

All four run in CI as the `test` and `security` jobs, and `deploy` declares
`needs: [lint, test, security]` — so none of it can quietly stop running.

Note `bandit` reports 25 low / 23 medium findings in `scripts/`: `subprocess`
calls, `urlopen`, and f-string SQL used to build the data layer from public
sources. That job is **advisory** on purpose. Those scripts run on a developer's
machine against known URLs, never on a request path, and failing the deploy on
them would train everyone to ignore the job — which is how a real finding gets
missed.
