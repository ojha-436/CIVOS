# CIVOS — Explained Simply

Read this in five minutes. It is the version you should be able to say out loud without notes.

**CIVOS** = the *civic operating system*. India's instance is `CIVOS-IN`, South Africa's would be `CIVOS-ZA` — the name mirrors the code, where each country is just a folder.

---

## The one-sentence version

**CIVOS lets any citizen report what their area needs — by speaking, typing, or photographing it — then works out which districts need help most, notices which districts never speak up at all, and writes the funding proposal.**

---

## The suggestion box analogy

Imagine a suggestion box for an entire country.

Millions of notes go in. Most are handwritten in twenty different languages. Many say the same thing in different words. Nobody has time to read them, so nobody does — and the budget gets decided the way it always was.

Now notice something worse: **the box is only placed near the nice neighbourhoods.** The villages that need the most have no box, no smartphone, and nobody who knows how to file a complaint. So when someone counts the notes, those villages look like they're doing fine.

CIVOS does four things with that box:

1. **Reads every note** — spoken, typed, or photographed — in every language.
2. **Groups the duplicates** — 800 notes about the same dry borewell is *one* problem, not 800.
3. **Cross-checks against government data** on what each district actually lacks.
4. **Flags the districts with no notes at all** but terrible conditions — and says *"go ask these people, they haven't been able to reach you."*

Then it writes a proper funding proposal for the top priorities, with the evidence attached.

---

## Why three ways to report, not one

This is not "three inputs because three is better than one." Each one buys something the others can't.

| | What it's for |
|---|---|
| 🎙 **Voice** | **Access.** No reading, no writing, no form, no knowing what department owns the problem. This is the only channel that reaches the exact citizens the system is most likely to miss. |
| ⌨️ **Text** | **Scale.** Messaging apps and web forms — and importing the millions of complaints already sitting in old government systems. Without this we'd just be *adding* a new silo instead of merging the existing ones. |
| 📷 **Image** | **Evidence.** A voice note is a *claim*. A photo is *proof*. |

The photo one deserves a second look, because it does three jobs at once:

- **It corroborates.** A dossier that says *"340 distinct needs, 89 with photographic evidence"* is far stronger in front of an auditor than one that just counts complaints.
- **It knows exactly where it was taken.** Photos carry GPS data. That means no guessing which district — the hardest technical problem in the whole project just gets skipped for any signal that has a photo.
- **It can prove a fix happened.** Take a photo of the same broken culvert six months after the money was spent. That's the impact measurement nobody else will build.

And one more thing worth saying in the pitch: **a photo needs no language at all.** If someone speaks a language nothing supports, they can still point a camera at a broken handpump and be heard. That's the accessibility floor.

*(Privacy note: original photos are deleted immediately after the AI reads them. If a photo has people in it, nothing visual is kept at all — only the extracted facts. GPS is used to work out the district, then thrown away. We never store where an individual citizen was standing.)*

---

## Why this is different from what everyone else will build

Almost every team that picks this problem will build the same thing: a chatbot that takes complaints and a map with red dots showing where the complaints came from.

That looks impressive and it is quietly wrong, for one reason:

> **A map of complaints is a map of who has a phone and knows how to complain. It is not a map of need.**

If a government funds the reddest dots, it funds the loudest districts and starves the quietest ones. That is the opposite of what the problem asks for.

So CIVOS's central idea is: **silence is the most important signal in the data.**

We measure how much each district *speaks* and compare it to how much each district *lacks*. Four things can happen:

| | **Government data says conditions are OK** | **Government data says conditions are bad** |
|---|---|---|
| **Lots of complaints** | *Expectation Gap* — either your data is out of date, or the service exists but is bad | **Act Now** — everyone agrees. Fund it. |
| **Few complaints** | *Stable* — leave it alone | **Silent Need** — bad conditions, nobody speaking. **Go find out why.** |

That bottom-right box is the whole product. Nobody else will show it.

**Important:** we don't automatically send money to silent districts. That would be replacing one guess with another. We tell the government *"send someone to these districts and ask"* — we're fixing a measurement problem, not overruling citizens. Say this clearly, because a judge will absolutely ask.

**Second important thing:** having a photo makes a need score slightly higher — but only *slightly*, deliberately. If photo evidence counted for much, poor districts where nobody owns a camera would get punished twice. That would break the entire point of the product. It's the smallest weight in the formula, and if it turns out to skew results toward richer districts at all, it gets set to zero.

---

## The second big idea: the output isn't a dashboard

Here's a question worth sitting with: what does a district officer do with a heatmap?

Nothing. They can't attach a heatmap to a funding request. They get audited.

So CIVOS's output is not a chart. It is a **project dossier** — a one-page document that says:

- This district needs this, in this sector
- Here are 340 distinct citizen needs behind it, from 1,200 requests, in 7 languages
- Here are three things citizens actually said, in their own words *and* in English
- **Here are four photographs of the problem**
- Government data confirms it: 61% of households here have no piped water *(source: NFHS-5, 2021)*
- Roughly 48,000 people affected
- It'll cost roughly this much
- **And it can be funded under Jal Jeevan Mission** — here's the eligibility

That last line is the one that matters. A recommendation with no funding route is a wish. A recommendation attached to money that already exists is something a government can start next month.

Every number in that dossier links back to its source. Nothing is invented by the AI — it can only write from evidence we retrieved and handed it.

---

## The three loops

**1. LISTEN** — A citizen speaks, types, or photographs, in their own language, on a web page or Telegram. **One single Gemini call** handles all three — audio, text and images go into the same request — and returns structured data: which sector, how severe, which district, and for photos what the object is and what state it's in. It handles mixed languages in one sentence, the way people actually talk. We also import existing complaint data from old government systems.

**2. DECIDE** — All of it lands in BigQuery. Duplicate complaints get merged into distinct needs (and duplicate *photos* get caught too, so nobody can inflate their district by resubmitting the same picture). Real government deprivation data gets joined in. The participation correction runs. Districts get scored and sorted into the four boxes above. A forecast predicts where demand is heading. Then Gemini writes the dossier.

**3. VERIFY** — After a project is funded, do the complaints stop? Does the photo of the same handpump look different? The problem statement specifically says nobody can measure impact, and almost every team will ignore that sentence.

---

## Why it works in other countries

Because the country is a **folder**, not code.

`adapters/in/` holds India's districts, languages, data sources and government schemes. Add `adapters/za/` with South Africa's and the exact same system runs on South African data in Zulu. Nothing in the core is rewritten — there's even an automated check that fails the build if anyone hardcodes "India" into the core.

In the demo you click a dropdown, switch from `CIVOS-IN` to `CIVOS-ZA`, and the whole thing re-runs on real foreign data. That single click is worth 20% of the score, because "will this work in my country?" is the only question a foreign evaluator actually cares about.

---

## What you're actually building in 8 days

| | |
|---|---|
| A multimodal widget on a web page | mic + camera + text box, no app install |
| A Telegram bot | voice notes, text, and photos — proves the "messaging app" requirement |
| **One** Gemini call | any mix of speech, text and image → structured data, any language |
| A pile of SQL in BigQuery | dedup, scoring, forecasting |
| One web console | map, four boxes, drilldown, dossier |
| Two config folders | India + one more country |
| Real government data | five sectors, ~700 districts |
| ~3,000 generated citizen requests | clearly labelled as synthetic, because we have no real access — and the generator itself becomes part of the public good, so any ministry can trial the platform before they have data |
| ~150 **real** openly-licensed photographs | these are not generated. Vision accuracy proved on fake images would prove nothing |

That's it. Everything else is deliberately cut. The full list of what we are *not* building — and the order things get dropped if time runs out — is in [plan.md](plan.md).

---

## The 30-second pitch

> Governments don't lack citizen feedback. They're drowning in it. What they lack is a way to turn it into a funding decision they can defend.
>
> CIVOS takes citizen requests by voice, text or photo in any language, merges duplicates into real distinct needs, checks them against official deprivation data, and produces a costed project proposal tied to an existing government scheme — with every claim citable and, where a citizen sent a picture, visually corroborated.
>
> And it does one thing no complaint dashboard does: it corrects for the fact that the poorest districts complain the least. It finds the districts with the worst conditions and no voice, and tells the government to go listen to them.
>
> The country is a config folder. It runs on India today and on any BRICS nation tomorrow.

---

**Next reads:** [SPEC.md](SPEC.md) for the full specification · [plan.md](plan.md) for the day-by-day build plan · [memory.md](memory.md) for the decision log
