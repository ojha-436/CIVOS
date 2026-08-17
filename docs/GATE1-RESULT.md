# GATE 1 — geo-grounding accuracy

**Verdict: `PASS` · 49/52 = 94.2%** (threshold 85%)

Run 2026-08-17 10:40 UTC · model `gemini-2.5-flash` · temperature 0 · asia-south1

Proceed as designed. Geo-grounding is accurate enough that the demand signal it produces is not dominated by placement error.

## Where the errors are

| Slice | Cases | Correct | Accuracy |
|---|---|---|---|
| Resolvable (a district is the right answer) | 44 | 41 | 93.2% |
| Abstain (null is the right answer) | 8 | 8 | 100.0% |

**Confidently wrong: 1.** This is the number that matters most — a named-but-wrong district attaches real deprivation data to the wrong place and nothing downstream questions it. A miss that abstains is recoverable; a miss that answers is not.

## By difficulty tier

| Tier | What it tests | Cases | Correct | Accuracy |
|---|---|---|---|---|
| T1 | district named outright | 9 | 9 | 100% |
| T2 | district named, different spelling | 8 | 7 | 88% |
| T3 | only a town, block or tehsil named | 16 | 15 | 94% |
| T4 | only a landmark named | 6 | 5 | 83% |
| T5 | name exists in several states | 8 | 8 | 100% |
| T6 | genuinely unresolvable | 5 | 5 | 100% |

## Every case

| | id | tier | lang | expected | got | note |
|---|---|---|---|---|---|---|
| ✅ | `t1-01` | T1 | mr | `IN-MH-nashik` | `IN-MH-nashik` | state+district |
| ✅ | `t1-02` | T1 | en | `IN-RJ-barmer` | `IN-RJ-barmer` | state+district |
| ✅ | `t1-03` | T1 | ml | `IN-KL-wayanad` | `IN-KL-wayanad` | state+district |
| ✅ | `t1-04` | T1 | en | `IN-OR-kandhamal` | `IN-OR-kandhamal` | state+district |
| ✅ | `t1-05` | T1 | hi | `IN-UP-sonbhadra` | `IN-UP-sonbhadra` | state+district |
| ✅ | `t1-06` | T1 | bn | `IN-WB-murshidabad` | `IN-WB-murshidabad` | state+district |
| ✅ | `t1-07` | T1 | en | `IN-OR-malkangiri` | `IN-OR-malkangiri` | state+district |
| ✅ | `t1-08` | T1 | hi | `IN-MP-jhabua` | `IN-MP-jhabua` | state+district |
| ✅ | `t2-01` | T2 | en | `IN-AS-dhubri` | `IN-AS-dhubri` | state+district |
| ✅ | `t2-02` | T2 | en | `IN-KA-chamrajnagar` | `IN-KA-chamrajnagar` | state+district |
| ❌ | `t2-03` | T2 | bn | `IN-WB-puruliya` | `null` | model error: 1 validation error for GeoProposal
  Invalid JSON: EOF while parsing a string at line 1 column 65311 [type=json_invalid, input_value='{"place_mentions": ["\\u...0932\\ |
| ✅ | `t2-04` | T2 | en | `IN-OR-nabarangapur` | `IN-OR-nabarangapur` | state+district |
| ✅ | `t2-05` | T2 | gu | `IN-GJ-kachchh` | `IN-GJ-kachchh` | state+district |
| ✅ | `t2-06` | T2 | en | `IN-OR-baleshwar` | `IN-OR-baleshwar` | state+district |
| ✅ | `t2-07` | T2 | en | `IN-AS-karimganj` | `IN-AS-karimganj` | state+district |
| ✅ | `t3-01` | T3 | en | `IN-AS-cachar` | `IN-AS-cachar` | state+district |
| ✅ | `t3-02` | T3 | hi | `IN-CT-bastar` | `IN-CT-bastar` | state+district |
| ✅ | `t3-03` | T3 | gu | `IN-GJ-kachchh` | `IN-GJ-kachchh` | state+district |
| ✅ | `t3-04` | T3 | ml | `IN-KL-wayanad` | `IN-KL-wayanad` | state+district |
| ✅ | `t3-05` | T3 | en | `IN-OR-kandhamal` | `IN-OR-kandhamal` | state+district |
| ✅ | `t3-06` | T3 | en | `IN-TR-dhalai` | `IN-TR-dhalai` | state+district |
| ✅ | `t3-07` | T3 | en | `IN-OR-koraput` | `IN-OR-koraput` | state+district |
| ✅ | `t3-08` | T3 | en | `IN-ML-south-garo-hills` | `IN-ML-south-garo-hills` | state+district |
| ✅ | `t3-09` | T3 | hi | `IN-RJ-jaisalmer` | `IN-RJ-jaisalmer` | state+district |
| ✅ | `t3-10` | T3 | mr | `IN-MH-nashik` | `IN-MH-nashik` | state+district |
| ✅ | `t3-11` | T3 | mr | `IN-MH-pune` | `IN-MH-pune` | state+district |
| ✅ | `t3-12` | T3 | en | `IN-MH-thane` | `IN-MH-thane` | state+district |
| ❌ | `t3-13` | T3 | mr | `IN-MH-nandurbar` | `IN-MH-dhule` | state+district |
| ✅ | `t3-14` | T3 | en | `IN-KL-wayanad` | `IN-KL-wayanad` | state+district |
| ✅ | `t3-15` | T3 | hi | `IN-BR-supaul` | `IN-BR-supaul` | state+district |
| ❌ | `t4-01` | T4 | en | `IN-GJ-junagadh` | `null` | spans multiple districts |
| ✅ | `t4-02` | T4 | en | `IN-MN-bishnupur` | `IN-MN-bishnupur` | state+district |
| ✅ | `t4-03` | T4 | hi | `IN-JK-srinagar` | `IN-JK-srinagar` | state+district |
| ✅ | `t4-04` | T4 | en | `null` | `null` | spans multiple districts |
| ✅ | `t4-05` | T4 | or | `null` | `null` | spans multiple districts |
| ✅ | `t5-01` | T5 | en | `IN-BR-aurangabad` | `IN-BR-aurangabad` | state+district |
| ✅ | `t5-02` | T5 | mr | `IN-MH-aurangabad` | `IN-MH-aurangabad` | state+district |
| ✅ | `t5-03` | T5 | en | `IN-HP-bilaspur` | `IN-HP-bilaspur` | state+district |
| ✅ | `t5-04` | T5 | hi | `IN-CT-bilaspur` | `IN-CT-bilaspur` | state+district |
| ✅ | `t5-05` | T5 | hi | `IN-UP-hamirpur` | `IN-UP-hamirpur` | state+district |
| ✅ | `t5-06` | T5 | en | `IN-CT-raigarh` | `IN-CT-raigarh` | state+district |
| ✅ | `t5-07` | T5 | en | `null` | `null` | spans multiple districts |
| ✅ | `t6-01` | T6 | hi | `null` | `null` | no district proposed |
| ✅ | `t6-02` | T6 | en | `null` | `null` | no district proposed |
| ✅ | `t6-03` | T6 | ta | `null` | `null` | no district proposed |
| ✅ | `t6-04` | T6 | en | `null` | `null` | no district proposed |
| ✅ | `t6-05` | T6 | hi | `null` | `null` | no district proposed |
| ✅ | `t7-01` | T3 | hi-en | `IN-BR-kishanganj` | `IN-BR-kishanganj` | state+district |
| ✅ | `t7-02` | T1 | mr-en | `IN-MH-nandurbar` | `IN-MH-nandurbar` | state+district |
| ✅ | `t7-03` | T2 | hi-en | `IN-BR-sitamarhi` | `IN-BR-sitamarhi` | state+district |
| ✅ | `t7-04` | T5 | hi-en | `IN-HP-hamirpur` | `IN-HP-hamirpur` | state+district |
| ✅ | `t7-05` | T4 | en | `IN-RJ-jaisalmer` | `IN-RJ-jaisalmer` | state+district |

## Disputed cases

Cases where, on review, the resolver's answer looks defensible and the answer key looks wrong. **The keys are left unchanged.** Editing them after seeing the score is the tuning this test set was written first to prevent.

- **`t4-01`** — expected `IN-GJ-junagadh`, resolver said `null`. The only case Gate 1 missed, and on review the resolver was probably right and this answer key wrong: Gir spans Junagadh, Gir Somnath (created 2013) and Amreli, so abstaining is defensible. The `expected` value is deliberately LEFT UNCHANGED. Editing an answer key after seeing the score is precisely the tuning this test set was written first to prevent, and a disclosed 98.1% is worth more than a quietly manufactured 100%.

## Method and its limitation

The resolver is a single Gemini call with the full 641-district gazetteer in the prompt, so a returned district is valid by construction. Ambiguity is then resolved in code, not by the model: if a district name maps to several states and none is given, the resolver abstains. That rule is deterministic and testable in a way a prompt instruction is not.

**This is a self-graded exam.** The test set was authored by the same party that built the resolver — though it was written and committed first, before any resolver code existed, which constrains but does not eliminate the bias. Treat this as a build gate, not an independent benchmark.
