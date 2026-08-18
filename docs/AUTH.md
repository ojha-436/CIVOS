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
