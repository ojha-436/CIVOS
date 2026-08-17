"""Shared India administrative naming — ISO codes, slugs, district code assignment.

Country-specific by definition, so this lives in scripts/ alongside the other
adapter-adjacent tooling and never in core/. `scripts/lint_country_literals.py`
would fail the build if any of it drifted inward.

It exists because two scripts need the same table and a second copy would
eventually disagree with the first: `build_boundaries.py` assigns district codes
when the boundary set is built, and `generate_console_fixtures.py` needs the same
rules for any boundary file that arrives without codes already attached.

The name table is deliberately permissive about spelling. Census-derived sources
disagree with each other constantly — "Odisha" vs "Orissa", "&" vs "and",
"Arunanchal" (a real typo in the upstream DataMeet shapefile) vs "Arunachal" — and
every one of those is a legitimate name for the same subdivision. Accepting the
variants is correct; guessing at an unrecognised one is not.
"""

from __future__ import annotations

import re
import unicodedata

# ISO 3166-2:IN subdivision codes, keyed by every spelling the project's sources
# actually emit. Multiple keys mapping to one code is intended.
ISO_3166_2_IN: dict[str, str] = {
    # -- canonical ----------------------------------------------------------
    "Andaman and Nicobar": "AN",
    "Andhra Pradesh": "AP",
    "Arunachal Pradesh": "AR",
    "Assam": "AS",
    "Bihar": "BR",
    "Chandigarh": "CH",
    "Chhattisgarh": "CT",
    "Dadra and Nagar Haveli": "DH",
    "Daman and Diu": "DH",
    "Delhi": "DL",
    "Goa": "GA",
    "Gujarat": "GJ",
    "Haryana": "HR",
    "Himachal Pradesh": "HP",
    "Jammu and Kashmir": "JK",
    "Jharkhand": "JH",
    "Karnataka": "KA",
    "Kerala": "KL",
    "Ladakh": "LA",
    "Lakshadweep": "LD",
    "Madhya Pradesh": "MP",
    "Maharashtra": "MH",
    "Manipur": "MN",
    "Meghalaya": "ML",
    "Mizoram": "MZ",
    "Nagaland": "NL",
    "Orissa": "OR",
    "Puducherry": "PY",
    "Punjab": "PB",
    "Rajasthan": "RJ",
    "Sikkim": "SK",
    "Tamil Nadu": "TN",
    "Telangana": "TG",
    "Tripura": "TR",
    "Uttar Pradesh": "UP",
    "Uttaranchal": "UT",
    "West Bengal": "WB",
    # -- variants emitted by the DataMeet Census-2011 shapefile -------------
    # Kept mapping to the SAME codes as their canonical spellings, so district
    # codes stay stable across a change of boundary source.
    "Andaman & Nicobar Island": "AN",
    "Arunanchal Pradesh": "AR",          # upstream typo, preserved as an alias
    "Dadara & Nagar Havelli": "DH",
    "Daman & Diu": "DH",
    "Jammu & Kashmir": "JK",
    "NCT of Delhi": "DL",
    "Odisha": "OR",                      # same subdivision as "Orissa"
    "Uttarakhand": "UT",                 # same subdivision as "Uttaranchal"
}


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def state_abbr(state: str) -> str:
    """ISO 3166-2:IN subdivision code. Fails loudly rather than guessing.

    A heuristic fallback is what produced the Maharashtra/Manipur collision, so an
    unrecognised state is an error to fix in the table above, not something to
    paper over with initials.
    """
    try:
        return ISO_3166_2_IN[state.strip()]
    except KeyError:
        raise SystemExit(
            f"No ISO 3166-2 code for state {state!r}. Add it to ISO_3166_2_IN in "
            "scripts/india_admin.py rather than letting a heuristic invent one."
        ) from None


def district_code(state: str, district: str, seen: set[str] | None = None) -> str:
    """`IN-<ISO subdivision>-<slug>`, de-duplicated.

    Human-readable on purpose — the code is shown in the console drilldown and in
    dossiers, where `IN-OR-dhenkanal` tells a reader something and a census
    integer does not. Census codes travel alongside it in the boundary properties
    rather than replacing it.
    """
    code = f"IN-{state_abbr(state)}-{slug(district)}"
    if seen is None:
        return code
    base, n = code, 2
    while code in seen:
        code = f"{base}-{n}"
        n += 1
    seen.add(code)
    return code
