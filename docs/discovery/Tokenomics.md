# Tokenomics — agent-hub CV Pipeline

> Last updated: 2026-05-30
> Model: claude-opus-4-5-20251101
> Source of truth for all cost analysis and unit economics

---

## 1. Pricing (verified 2026-05-30)

Source: https://anthropic.com/pricing

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| claude-opus-4.x | $5/MTok | $25/MTok | $6.25/MTok | $0.50/MTok |
| claude-sonnet-4.x | $3/MTok | $15/MTok | $3.75/MTok | $0.30/MTok |
| claude-haiku-4.5 | $1/MTok | $5/MTok | $1.25/MTok | $0.10/MTok |

**Batch processing:** 50% discount (async, 24h turnaround).

Cost formula: `(input × $5 + output × $25) / 1_000_000`

---

## 2. Prompt Caching

**What's cached:** PROFILE.md (~7119 chars ≈ 1780 tokens) — first system block with `cache_control: ephemeral`, 5-minute TTL.

**Status:** ⚠️ Was NOT working until 2026-05-30 — `betas=["prompt-caching-2024-07-31"]` header was missing. Fixed in commit `5b48762`.

**How it works across pipeline calls:**

| Call | Cache event | PROFILE.md cost |
|------|-------------|-----------------|
| Phase 1 | cache_write | 1780 × $6.25/MTok = $0.011 |
| Phase 2 | cache_read | 1780 × $0.50/MTok = $0.001 |
| Phase 3 | cache_read | 1780 × $0.50/MTok = $0.001 |
| Phase 3.5 | cache_read | 1780 × $0.50/MTok = $0.001 |
| Phase 4 | cache_read | 1780 × $0.50/MTok = $0.001 |
| **Total with cache** | | **$0.015** |
| **Total without cache** | | 5 × 1780 × $5/MTok = **$0.045** |
| **Saving** | | **~67%** on PROFILE.md |

---

## 3. Plan vs Fact — Real Runs (vacancy #47, АІ PM @ SOLAR Digital)

| Run | Date | Phases | In tok | Out tok | Plan ($) | Fact ($) | Delta | Notes |
|-----|------|--------|--------|---------|----------|----------|-------|-------|
| v1 | 2026-05-30 | analyze+generate+cover, split sessions | 34 588 | 6 837 | $0.344 | **$0.34** ✅ | $0.004 | Кэш не работал. Данные из логов Anthropic. phase1+2 в 09:48, phase3/3.5/4 в 15:39–16:07 |
| v2 | 2026-05-30 | analyze+generate+cover, одна сессия | 32 556 | 6 286 | $0.320 | **$0.32** ✅ | $0.000 | Исправленные промпты. Кэш не работал (beta header fix после прогона) |
| v3 | TBD | analyze+generate+cover | TBD | TBD | ~$0.29 est | ❓ | — | Первый прогон с рабочим кэшем |

**Total day 2026-05-30:** in=67 158, out=13 133 → fact=$0.66 (Anthropic console)

---

## 4. Детальный breakdown по фазам (из DB, vacancy #47)

| DB id | Run | Фаза | Input | Output | cost_usd |
|-------|-----|------|-------|--------|----------|
| — | v1 | phase1 | 3 244 | 2 159 | $0.068 *(из логов, не в DB)* |
| — | v1 | phase2 | 5 511 | 2 051 | $0.079 *(из логов, не в DB)* |
| 1 | v1 | phase3 | 8 147 | 923 | $0.064 |
| 2 | v1 | phase3_5 | 8 493 | 1 448 | $0.079 |
| 3 | v1 | phase4 | 9 193 | 256 | $0.052 |
| **v1 total** | | | **34 588** | **6 837** | **$0.342** |
| 4 | v2 | phase1 | 3 244 | 2 054 | $0.068 |
| 5 | v2 | phase2 | 5 550 | 1 706 | $0.070 |
| 6 | v2 | phase3 | 7 466 | 839 | $0.058 |
| 7 | v2 | phase3_5 | 7 774 | 1 448 | $0.075 |
| 8 | v2 | phase4 | 8 522 | 239 | $0.049 |
| **v2 total** | | | **32 556** | **6 286** | **$0.320** |

**Самая дорогая фаза:** Phase 3.5 (23% бюджета) — туда идёт весь контекст: JD + анализ + CV draft.

**v2 дешевле v1** ($0.32 vs $0.34) несмотря на ВСЕ 5 фаз в одной сессии — улучшенные промпты дают компактнее выходы.

---

## 5. Unit Economics — CV Processing Service

Юнит = одна обработанная вакансия (fetch → analyze → generate → cover).

| Метрика | Без кэша | С кэшем |
|---------|----------|---------|
| COGS/вакансия (LLM) | ~$0.33 | ~$0.30 |
| + infra (Docker, hosting) | ~$0.02 | ~$0.02 |
| **Total COGS** | **~$0.35** | **~$0.32** |

### Модели монетизации

| Модель | Revenue | COGS | Gross Margin |
|--------|---------|------|-------------|
| $0.99/вакансия | $0.99 | $0.35 | **65%** |
| $4.99/вакансия | $4.99 | $0.35 | **93%** |
| $9.99/мес, 20 вак | $9.99 | $7.00 | **30%** |
| $19.99/мес, 50 вак | $19.99 | $17.50 | **12%** |
| $29.99/мес, 100 вак | $29.99 | $35.00 | **-17% ❌** |

**Оптимальная модель:** pay-per-vacancy ($0.99–$4.99) или подписка с лимитом ≤ 30 вакансий/месяц.

---

## 6. DB Schema

Таблица `llm_usage`:
- `vacancy_id` FK (nullable)
- `phase` — phase1 / phase2 / phase3 / phase3_5 / phase4
- `model`, `input_tokens`, `output_tokens`
- `cache_write_tokens`, `cache_read_tokens`
- `cost_usd` — рассчитывается по `_PRICING` в `core/llm_client.py`
- `created_at`

### Ключевые SQL запросы

```sql
-- Стоимость по фазам
SELECT phase, COUNT(*), ROUND(SUM(cost_usd),4) AS total, ROUND(AVG(cost_usd),4) AS avg
FROM llm_usage GROUP BY phase;

-- Cache efficiency
SELECT
  ROUND(SUM(cache_read_tokens)*1.0 / NULLIF(SUM(input_tokens)+SUM(cache_read_tokens),0) * 100, 1)
  AS cache_hit_pct
FROM llm_usage;

-- Стоимость на вакансию
SELECT v.title, COUNT(u.id) AS calls, ROUND(SUM(u.cost_usd),4) AS total_usd
FROM llm_usage u JOIN vacancies v ON u.vacancy_id = v.id
GROUP BY v.id ORDER BY total_usd DESC;

-- Daily spend
SELECT DATE(created_at), ROUND(SUM(cost_usd),4) FROM llm_usage GROUP BY DATE(created_at);
```

---

## 7. Observations & Open Questions

- **Формула точная** — delta $0.00 на v2, $0.004 на v1 ✅
- **Кэш не работал** до 2026-05-30 (отсутствовал beta header). Ожидаемая экономия ~$0.03/прогон (~9%)
- **cache_write/cache_read в DB = 0** оба раза — SDK поля возвращают 0 даже когда кэш работает. `input_tokens` в ответе уже отражает реально заряженное (т.е. cache_read не входит в input_tokens). Нужно проверить после v3.
- **Следующий шаг:** прогнать v3 с рабочим кэшем → сравнить Fact с $0.29 планом → подтвердить или опровергнуть cache savings

---

## 8. Update Log

| Date | Change |
|------|--------|
| 2026-05-30 | Initial creation. Prices $15/$75 → исправлены на $5/$25. Кэш не работал. |
| 2026-05-30 | v1+v2 прогоны, формула верифицирована. Beta header fix. Таблица перенесена в docs/discovery/. |
