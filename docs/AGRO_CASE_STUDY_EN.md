# Agro Case Study — Grounded RAG Horticulture Assistant

**Project:** grounded-horticulture (doctor_gardens_ai)  
**Repository:** публичное портфолио — код + демо-данные; полный журнальный корпус не в git.
**Domain:** Apple, pear, plum — scientific articles from *Plodovodstvo i vinogradarstvo Yuga Rossii*  
**Stack:** Go orchestration · Python hybrid RAG · Telegram Mini App · browser client (API key)

---

## Problem

Gardeners and agronomists need **trustworthy, source-grounded** answers about rootstocks, slope planting, nutrition, and disease control — not generic LLM guesses. The knowledge base is large (~500 articles), Russian-language, and full of domain synonyms (СК-4 / СК 4, марссониоз / *Marssonina*).

## Solution

A production-style assistant with:

1. **Hybrid retrieval** — Chroma (multilingual-e5-small) + BM25 + RRF merge  
2. **Cross-encoder reranker** — `BAAI/bge-reranker-base` on top-32 candidates  
3. **Chunking** — 650 tokens / 80 overlap, section-aware splits, “Кратко для садовода” priority  
4. **Query expansion** — `config/agro_glossary.json` for horticulture synonyms  
5. **Grounded generation** — Go builds the prompt, calls LLM, verifies numbers against context  
6. **Multi-channel access** — Telegram `initData` or browser `X-API-Key`  
7. **RAG warmup** — models preloaded at classifier startup (~3 min once, ~6 s per question after)

## Scale (corpus)

| Metric | Value |
|--------|------:|
| Articles (apple / pear / plum) | ~344 / ~42 / ~108 |
| Indexed chunks (Chroma + BM25) | **~14,554** |
| Eval questions (apple baseline) | **45** (+ 8 pear, 10 plum, 5 demo_hr) |

## Retrieval quality (regression gate)

Automated suite: `python scripts/run_rag_eval.py --suite all`

**CI:** unit tests on every PR; full eval via manual GitHub workflow **RAG Eval** (see `docs/knowledge-base/github-ci.yml.md`).

| Suite | Questions | Target |
|-------|----------:|--------|
| apple | 45 | 100% retrieval pass |
| pear | 8 | 100% |
| plum | 10 | 100% |
| demo_hr | 5 | 100% |
| **Total** | **68** | **100%** (latest local run) |

Checks: expected substrings in retrieved context (with Russian stemming); out-of-scope questions must not hallucinate KB content.

**Latest run:** `eval/results/20260629_085246_all.json` — **68/68 passed (100%)**.

## LLM (production pilot)

- **Model:** `google/gemini-2.5-flash-lite` via OpenRouter  
- **Why:** low latency, strong multilingual quality, ~$0.10 / $0.40 per 1M tokens (vs. free-tier queues and 429 errors)

## Architecture (one diagram)

```
Browser / Telegram → Go (auth, sessions, LLM, verify)
                         ↓ POST /rag/context
                    Python (hybrid search, rerank)
                         ↓
                    Chroma + BM25 (~14.5k chunks)
```

## What this demonstrates (hiring)

- **Domain RAG at scale** — not a 5-PDF demo; real journal corpus  
- **Measurable quality** — JSONL eval suites + pass-rate tracking  
- **Production patterns** — Docker, Postgres sessions, rate limits, hybrid search  
- **Platform story** — vertical pack with sandbox `demo_hr` (clone for other domains)

## Run locally

```bash
cp .env.example .env   # LLM_API_KEY, API_KEYS, HF_TOKEN
docker compose up -d --build
python scripts/run_rag_eval.py --suite all
```

Open `http://localhost` (browser API key) or Telegram Mini App.

---

*Disclaimer: assistant output is informational; agronomic and phytosanitary decisions require local expert review and compliant product labels.*
