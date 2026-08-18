# Authentication — what is gated, and the cost of gating it

**Added 18 Aug 2026.** Firebase Authentication with email/password and Google SSO,
plus a profile stored in Firestore.

## What requires an account

| Surface | Account required | Why |
|---|---|---|
| `/` landing | No | Public |
| `/login`, `/profile` | — | The account itself |
| **`/console`** | **Yes** | Shows district-level funding priorities. No real deployment would leave this open. |
| **`/report`** web intake | **Yes** | Product decision, 18 Aug 2026 |
| **Telegram `@Civos_in_bot`** | **No** | Telegram is the identity layer; CIVOS holds no account for the citizen |

## The cost, stated plainly

CIVOS argues that the poorest and least-connected citizens cannot navigate a
grievance process, and that **every barrier between a citizen and a report excludes
exactly the people the product exists to reach**. A login is such a barrier. Gating
the web intake form is therefore a real cost, not a neutral hardening step, and the
repository should say so rather than let the decision look free.

**What keeps the argument standing is the Telegram channel.** `@Civos_in_bot` takes
voice notes, text and photographs from any citizen with **no CIVOS account at all**,
in any language, with the same single Gemini extraction call behind it. The Tier-D
accessibility floor — *"a citizen whose language nothing supports can still
photograph a broken handpump and be heard"* — now runs through the messaging channel
rather than the web form.

Every place that previously claimed the web form needed no account was corrected on
the same day: the landing hero, the voice-modality card, Telegram step 01, the QR
card, and the intake page itself, which now links citizens to the Telegram route if
they would rather not sign in.

## What actually protects data

Two different mechanisms, and only one of them is security:

- **`console/components/RequireAuth.tsx`** is a client-side route guard. It controls
  the **UI**. It is not security — anyone can call Firestore directly using the
  public web config.
- **`firestore.rules`** is the real control. Each `profiles/{uid}` document is
  readable and writable only by the account that owns it, the writable key set is
  allow-listed, deletion is denied because the UI never offers it, and every other
  path is denied outright.

Verified: an unauthenticated read of `profiles/anything` returns
`403 PERMISSION_DENIED`.

Citizen signals deliberately do **not** live in Firestore. SPEC §11 keeps them in
the warehouse with k-anonymity applied inside it, so no client can route around the
suppression.

Deploy the rules with:

```bash
uv run python scripts/deploy_firestore_rules.py          # deploy
uv run python scripts/deploy_firestore_rules.py --check  # read back what is live
```

## On the Firebase config being committed

`console/lib/firebase.ts` contains the project's web config, including `apiKey`.
**This is intended to be public.** It ships inside every client bundle by
necessity, and it is a project identifier rather than a credential — what protects
the data is Auth plus the rules above, not the obscurity of those strings. Google
documents this explicitly.

Contrast with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET`, which are real
credentials and live only in `.env` (gitignored) and in GitHub Actions secrets.

### GitHub flagged it, and the flag was reasonable

On 18 Aug 2026 GitHub secret scanning opened *Google API Key #1* against
`console/lib/firebase.ts`. The alert is a pattern match on `AIza…`: a server key,
a Maps key and a Firebase web key are indistinguishable to a regex, so all three
are flagged, and `Validity: Unknown` means GitHub could not verify what this one
does.

**"Public by design" is only true if the key is actually restricted**, so that
was checked rather than assumed. It was already API-restricted to Firebase
services, and — this is the part that mattered — `aiplatform` and
`generativelanguage` **are** enabled on `civos-in` for the dossier generator. An
unrestricted key would have let anyone bill Gemini calls to the project. A direct
call confirmed the restriction holds:

```
GET generativelanguage.../models?key=…   ->  403 PERMISSION_DENIED
```

Two gaps were real and are now closed:

- **HTTP referrer restriction** — the key is limited to the two Cloud Run hosts,
  the two Firebase hosts, and localhost. Probed after the change:

  | Caller | Result |
  |---|---|
  | no referrer (an attacker's `curl` default) | `403 Requests from referer <empty> are blocked.` |
  | `https://evil.example.com/` | `403 … are blocked.` |
  | the real Cloud Run host | allowed |

  Referrer restrictions are a speed bump, not a control — a `Referer` header is
  trivially forged. They raise the cost of casual abuse; the Firestore rules are
  what actually protect data.

- **Signup quota** — capped at 200/day. Anyone holding the key can call
  Identity Toolkit and create accounts; the cap bounds junk-account and quota
  abuse. 200 is far above any judging panel and far below a spam run. Email
  enumeration protection is also on.

The alert was closed as **won't fix**, not *revoked* and not *false positive*.
Revoked would be false — the key is live and must stay live. False positive
would also be false — it genuinely is a Google API key. Won't fix is the only
honest classification, and the resolution comment records the reasoning.

Applying the restriction has one operational trap worth writing down. `gcloud
services api-keys update` **replaces** the entire restrictions block, so passing
`--allowed-referrers` without re-passing every `--api-target` silently *widens*
the key to all APIs. Worse, under zsh an unquoted `$VAR` holding 27 flags is not
word-split, so gcloud accepted the whole string as a single service name and the
key was left with one bogus target — which blocked `identitytoolkit` and took
live sign-in down until it was restored. Write the flags out literally:

```bash
gcloud services api-keys update <KEY_UID> --project=civos-in \
  --allowed-referrers="https://…/*,http://localhost:3000/*" \
  --api-target=service=identitytoolkit.googleapis.com \
  --api-target=service=securetoken.googleapis.com \
  …one line per service, all 27…
```

Then re-verify sign-in end to end; API key changes take up to five minutes to
propagate. Both the restriction and the quota are reversible in one command.

Every value is overridable by `NEXT_PUBLIC_FIREBASE_*` environment variables, so a
second deployment — a different ministry, a different country instance — points at
its own project without a code change.

## Setup, and the one step that needs a human

Everything below was done programmatically against project `civos-in`:

```
gcloud services enable firebase.googleapis.com identitytoolkit.googleapis.com \
                       firestore.googleapis.com firebaserules.googleapis.com
POST firebase.googleapis.com/v1beta1/projects/civos-in:addFirebase
POST firebase.googleapis.com/v1beta1/projects/civos-in/webApps
POST identitytoolkit.googleapis.com/v2/projects/civos-in/identityPlatform:initializeAuth
PATCH .../config?updateMask=signIn.email            # email/password ON
PATCH .../config?updateMask=authorizedDomains        # + Cloud Run hosts, localhost
gcloud firestore databases create --location=asia-south1
uv run python scripts/deploy_firestore_rules.py
```

**Google SSO needs one manual toggle.** Enabling the Google provider requires an
OAuth 2.0 client, which only the Firebase console can auto-create — there is no
public API for it. Until it is enabled, the *Continue with Google* button returns
`auth/operation-not-allowed`, and the UI says so in plain words rather than failing
silently:

> *Google sign-in is not enabled on this project yet. Use email and password, or
> enable the Google provider in Firebase Authentication.*

To enable: **Firebase console → Authentication → Sign-in method → Google → Enable →
Save.** Nothing in the code changes.

## Profile fields

Stored at `profiles/{uid}`. All optional — an empty profile still has full access,
because a mandatory form is the same barrier objected to above.

| Field | Purpose |
|---|---|
| `fullName` | Display name, also mirrored to the Firebase Auth profile |
| `role` | District officer, state, central ministry, analyst, civil society, evaluator |
| `organisation` | Department or ministry |
| `state`, `district` | Jurisdiction, from the **same** government district list the citizen intake uses, so a profile cannot name a district the rest of the product does not know |
| `phone` | Optional contact |
