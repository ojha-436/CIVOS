# GATE 0 — BigQuery ML/AI capability probe

**Verdict: `PROCEED_BQML`**

| | |
|---|---|
| Run at | 2026-08-14 17:41 UTC |
| Project | `civos-in` |
| BigQuery location | `asia-south1` |
| Connection | `civos-in.asia-south1.civos_vertex` |

Every capability the architecture depends on is available in this region. Proceed as specified in SPEC.md — BigQuery is the analytical spine.

## Summary

| Probe | Family | Result | Working form | Fallback if unavailable |
|---|---|---|---|---|
| `st_functions` | gis | ✅ available | `ST_CONTAINS / ST_GEOGPOINT / ST_DWITHIN` | None needed — GIS is core BigQuery |
| `embedding_inline` | embedding | ❌ unavailable | — | Vertex AI embed_content via google-genai; store ARRAY<FLOAT64> in BigQuery |
| `embedding_remote_model` | embedding | ✅ available | `CREATE MODEL REMOTE + ML.GENERATE_EMBEDDING · endpoint=gemini-embedding-001` | Vertex AI embed_content via google-genai |
| `ai_generate` | generation | ✅ available | `AI.GENERATE inline · endpoint=gemini-2.5-flash` | Call Gemini from the FastAPI layer — the dossier is one call, so this is cheap |
| `ml_generate_text` | generation | ✅ available | `CREATE MODEL REMOTE + ML.GENERATE_TEXT · endpoint=gemini-2.5-flash` | Call Gemini from the FastAPI layer |
| `vector_search` | vector | ✅ available | `VECTOR_SEARCH brute force, COSINE` | scikit-learn agglomerative clustering on embeddings pulled client-side |
| `vector_index_ddl` | vector | ⚠️ exists, needs scale | — | Brute-force VECTOR_SEARCH is fine at our corpus size; index is an optimisation |
| `arima_plus` | forecast | ✅ available | `CREATE MODEL ARIMA_PLUS + ML.FORECAST` | statsmodels ARIMA in the API layer |

**⚠️ exists, needs scale is not a failure.** The feature is present in this region; the probe table is simply too small to exercise it. Read the error before treating one of these as a blocker:

- `vector_index_ddl` — Feature exists; the probe table is below the minimum row count. Mitigation: Brute-force VECTOR_SEARCH is fine at our corpus size; index is an optimisation

## Fallback path viability (Vertex AI direct)

Probed regardless of the verdict, because a `FALLBACK_VERTEX` result is only a plan if the fallback is known to work.

| Path | Result | Detail |
|---|---|---|
| Gemini generate via `google-genai` | ✅ | gemini-2.5-flash → `OK` |
| Embeddings via `google-genai` | ✅ | gemini-embedding-001, 3072 dims |

Models visible to this project (3 listed): `gemini-2.5-flash`, `text-embedding-005`, `text-multilingual-embedding-002`

## Evidence — every attempt, with the exact error

### `st_functions` — EXIF geo path (P0-6) and district reconciliation

**PASS** · ST_CONTAINS / ST_GEOGPOINT / ST_DWITHIN · 1.1s

```sql
SELECT
                      ST_CONTAINS(
                        ST_GEOGFROMTEXT('POLYGON((72.7 18.8, 73.2 18.8, 73.2 19.3, 72.7 19.3, 72.7 18.8))'),
                        ST_GEOGPOINT(72.87, 19.07)) AS inside,
                      ST_DWITHIN(ST_GEOGPOINT(72.87, 19.07), ST_GEOGPOINT(72.88, 19.08), 5000) AS near,
                      ST_AREA(ST_GEOGFROMTEXT('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')) AS area_m2
```

Result: `{"inside": true, "near": true, "area_m2": 12364036567.076418}`

### `embedding_inline` — Is there an inline (no CREATE MODEL) embedding surface in this region?

**FAIL** · AI.GENERATE_EMBEDDING connection_id · endpoint=gemini-embedding-001 · 0.7s

```sql
SELECT ARRAY_LENGTH(embedding) AS dims
                FROM AI.GENERATE_EMBEDDING(
                  TABLE `civos-in.civos_probe.probe_text`,
                  connection_id => 'civos-in.asia-south1.civos_vertex',
                  endpoint => 'gemini-embedding-001'
                )
                LIMIT 1
```

```
400 Named argument connection_id not found in signature for call to function AI.GENERATE_EMBEDDING at [5:19]; reason: invalidQuery, location: query, message: Named argument connection_id not found in signature for call to function AI.GENERATE_EMBEDDING at [5:19]
```

**FAIL** · AI.GENERATE_EMBEDDING connection_id · endpoint=text-embedding-005 · 0.7s

```sql
SELECT ARRAY_LENGTH(embedding) AS dims
                FROM AI.GENERATE_EMBEDDING(
                  TABLE `civos-in.civos_probe.probe_text`,
                  connection_id => 'civos-in.asia-south1.civos_vertex',
                  endpoint => 'text-embedding-005'
                )
                LIMIT 1
```

```
400 Named argument connection_id not found in signature for call to function AI.GENERATE_EMBEDDING at [5:19]; reason: invalidQuery, location: query, message: Named argument connection_id not found in signature for call to function AI.GENERATE_EMBEDDING at [5:19]
```

**FAIL** · AI.GENERATE_EMBEDDING connection_id · endpoint=text-multilingual-embedding-002 · 1.0s

```sql
SELECT ARRAY_LENGTH(embedding) AS dims
                FROM AI.GENERATE_EMBEDDING(
                  TABLE `civos-in.civos_probe.probe_text`,
                  connection_id => 'civos-in.asia-south1.civos_vertex',
                  endpoint => 'text-multilingual-embedding-002'
                )
                LIMIT 1
```

```
400 Named argument connection_id not found in signature for call to function AI.GENERATE_EMBEDDING at [5:19]; reason: invalidQuery, location: query, message: Named argument connection_id not found in signature for call to function AI.GENERATE_EMBEDDING at [5:19]
```

### `embedding_remote_model` — ML.GENERATE_EMBEDDING via a REMOTE model (SPEC P0-7 assumption)

**PASS** · CREATE MODEL REMOTE + ML.GENERATE_EMBEDDING · endpoint=gemini-embedding-001 · 11.2s

```sql
CREATE OR REPLACE MODEL `civos-in.civos_probe.emb_gemini_embedding_001`
                  REMOTE WITH CONNECTION `civos-in.asia-south1.civos_vertex`
                  OPTIONS (ENDPOINT = 'gemini-embedding-001');
                SELECT ARRAY_LENGTH(ml_generate_embedding_result) AS dims
                FROM ML.GENERATE_EMBEDDING(
                  MODEL `civos-in.civos_probe.emb_gemini_embedding_001`,
                  (SELECT content FROM `civos-in.civos_probe.probe_text`)
                )
                LIMIT 1
```

Result: `{"dims": 3072}`

### `ai_generate` — Can grounded dossier text (SPEC §9) be generated inside SQL?

**FAIL** · AI.GENERATE inline · endpoint=gemini-3-flash · 1.3s

```sql
SELECT AI.GENERATE(
                  'Reply with the single word OK.',
                  connection_id => 'civos-in.asia-south1.civos_vertex',
                  endpoint => 'gemini-3-flash'
                ).result AS out
```

```
400 Unsupported endpoint: Publisher model `projects/924096812044/locations/asia-south1/publishers/google/models/gemini-3-flash` was not found or your project does not have access to it. Ensure you are using a valid model name and that the model is available in the specified region. For more information, see: https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations.; reason: invalidQuery, location: query, message: Unsupported endpoint: Publisher model `projects/924096812044/locations/asia-south1/publishers/google/models/gemini-3-flash` was not found or your project does not have access to it. Ensure you are using a valid model name and that the model is available in the specified region. For more information, see: https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations.
```

**PASS** · AI.GENERATE inline · endpoint=gemini-2.5-flash · 2.9s

```sql
SELECT AI.GENERATE(
                  'Reply with the single word OK.',
                  connection_id => 'civos-in.asia-south1.civos_vertex',
                  endpoint => 'gemini-2.5-flash'
                ).result AS out
```

Result: `{"out": "OK"}`

### `ml_generate_text` — ML.GENERATE_TEXT via a REMOTE model

**FAIL** · CREATE MODEL REMOTE + ML.GENERATE_TEXT · endpoint=gemini-3-flash · 0.9s

```sql
CREATE OR REPLACE MODEL `civos-in.civos_probe.gen_gemini_3_flash`
                  REMOTE WITH CONNECTION `civos-in.asia-south1.civos_vertex`
                  OPTIONS (ENDPOINT = 'gemini-3-flash');
                SELECT ml_generate_text_llm_result AS out
                FROM ML.GENERATE_TEXT(
                  MODEL `civos-in.civos_probe.gen_gemini_3_flash`,
                  (SELECT 'Reply with the single word OK.' AS prompt),
                  STRUCT(TRUE AS flatten_json_output)
                )
```

```
400 GET https://bigquery.googleapis.com/bigquery/v2/projects/civos-in/queries/1509885f-bc10-403c-9db0-a6c56181b406?maxResults=0&location=asia-south1&prettyPrint=false: Query error: Not found: Publisher model `projects/civos-in/locations/asia-south1/publishers/google/models/gemini-3-flash` was not found or your project does not have access to it. Ensure you are using a valid model name and that the model is available in the specified region. For more information, see: https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations. at [2:17]
```

**PASS** · CREATE MODEL REMOTE + ML.GENERATE_TEXT · endpoint=gemini-2.5-flash · 7.9s

```sql
CREATE OR REPLACE MODEL `civos-in.civos_probe.gen_gemini_2_5_flash`
                  REMOTE WITH CONNECTION `civos-in.asia-south1.civos_vertex`
                  OPTIONS (ENDPOINT = 'gemini-2.5-flash');
                SELECT ml_generate_text_llm_result AS out
                FROM ML.GENERATE_TEXT(
                  MODEL `civos-in.civos_probe.gen_gemini_2_5_flash`,
                  (SELECT 'Reply with the single word OK.' AS prompt),
                  STRUCT(TRUE AS flatten_json_output)
                )
```

Result: `{"out": "OK"}`

### `vector_search` — Dedup → distinct needs (P0-7): the Signals-vs-Needs number

**PASS** · VECTOR_SEARCH brute force, COSINE · 0.9s

```sql
SELECT base.id AS match_id, distance
                    FROM VECTOR_SEARCH(
                      TABLE `civos-in.civos_probe.probe_vec`, 'emb',
                      (SELECT [1.0, 0.0, 0.0, 0.0] AS emb),
                      top_k => 2,
                      distance_type => 'COSINE')
                    ORDER BY distance
```

Result: `{"match_id": "a", "distance": 0.0}`

### `vector_index_ddl` — Will a vector index be available at 3,000-signal scale?

**SUPPORTED_NEEDS_SCALE** · CREATE VECTOR INDEX IVF/COSINE · 1.8s

> Feature exists; the probe table is below the minimum row count.

```sql
CREATE OR REPLACE VECTOR INDEX probe_idx
                    ON `civos-in.civos_probe.probe_vec`(emb)
                    OPTIONS (index_type = 'IVF', distance_type = 'COSINE')
```

```
400 GET https://bigquery.googleapis.com/bigquery/v2/projects/civos-in/queries/465e2ee5-bc64-4891-82a7-7824e34f81dd?maxResults=0&location=asia-south1&prettyPrint=false: Total rows 5 is smaller than min allowed 5000 for CREATE VECTOR INDEX query with the IVF index type. Please use VECTOR_SEARCH table-valued function directly to perform the similarity search.
```

### `arima_plus` — 90-day demand forecast (P1-1) in ~10 lines of SQL

**PASS** · CREATE MODEL ARIMA_PLUS + ML.FORECAST · 6.5s

```sql
CREATE OR REPLACE MODEL `civos-in.civos_probe.probe_arima`
                      OPTIONS (
                        model_type = 'ARIMA_PLUS',
                        time_series_timestamp_col = 'ts',
                        time_series_data_col = 'value',
                        horizon = 30,
                        auto_arima = TRUE
                      ) AS
                    SELECT ts, value FROM `civos-in.civos_probe.probe_series`;
                    SELECT forecast_timestamp, forecast_value
                    FROM ML.FORECAST(MODEL `civos-in.civos_probe.probe_arima`,
                                     STRUCT(30 AS horizon, 0.8 AS confidence_level))
                    LIMIT 1
```

Result: `{"forecast_timestamp": "2026-03-02 00:00:00+00:00", "forecast_value": 31.96154102083473}`

