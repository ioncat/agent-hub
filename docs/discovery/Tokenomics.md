# Tokenomics — agent-hub CV Pipeline

> Last updated: 2026-05-31 (v6)
> Current model: claude-sonnet-4-6 + Extended Thinking (budget=3k, phase1+2 only)
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
| v3 | 2026-05-30 | analyze only (2 calls) | 5 361+1731 cache | 5 347 | $0.1033 | **~$0.103** ✅ | $0.000 | sonnet-4-6 + thinking(10k). Кэш работает (cache_read phase2). Quick Scan пустой — баг code fence в промпте. |
| v4 | 2026-05-30 | analyze only (2 calls) | 5 265+1731 cache | 4 994 | $0.0977 | **~$0.098** ✅ | $0.000 | Quick Scan исправлен. Кэш работает. Анализ на русском. Качество высокое. |
| v5 | 2026-05-31 | analyze only (2 calls) | 6 559+4803 cw+2159 cr | 6 178 | $0.1226 | **~$0.123** ✅ | $0.000 | ⚠️ BROKEN RUN — Phase 2 пустой (баг: `### Quick Scan` конфликтовал с `## Quick Scan` в промпте). Оплачен, данные в Anthropic. |
| v6 | 2026-05-31 | analyze only (2 calls) | 2 879+2696 cw+5180 cr | 5 461 | $0.1022 | **~$0.102** ✅ | $0.000 | Фикс: instruction-заголовки `**[OUTPUT SECTION N]**` вместо `###`. Phase 2 полный: Quick Scan + Fit Breakdown + Adaptation Plan + Internal Analysis. Score 5.5/10. |

**Total day 2026-05-30 (v1+v2 на Opus):** in=67 158, out=13 133 → fact=$0.66 (Anthropic console)
**Total day 2026-05-31 (v5+v6 на Sonnet):** in=10 722+10 755, out=6 178+5 461 → fact=$0.22 (CSV confirmed)

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
| 9 | v3 | phase1 | 1 560 | 2 008 | $0.0413 | sonnet-4-6, cache_write=1731, thinking=30tok, elapsed=40s, budget=10k |
| 10 | v3 | phase2 | 3 801 | 3 339 | $0.0620 | sonnet-4-6, cache_read=1731, thinking=1043tok, elapsed=71s, budget=10k |
| **v3 total** | | phase1+2 only | **5 361** | **5 347** | **$0.1033** | |
| — | v5 | phase1 | 3 859 | 2 101 | $0.0617 | sonnet-4-6, broken run, cache_write=4803, phase2 prompt bug |
| — | v5 | phase2 | 6 863 | 4 077 | $0.0609 | Phase 2 output empty — `### Quick Scan` instruction header conflicted with `## Quick Scan` output template |
| **v5 total** | | phase1+2 only | **10 722** | **6 178** | **$0.1226** | ⚠️ broken, do not use as quality baseline |
| — | v6 | phase1 | 3 859 | 2 049 | ~$0.046 | cache_write=2696 (cold for phase1 prompt), budget=3k |
| — | v6 | phase2 | 6 896 | 3 412 | ~$0.056 | cache_read=5180 (warm from v5), full output: QS+FitBreakdown+AdaptPlan+Internal |
| **v6 total** | | phase1+2 only | **10 755** | **5 461** | **$0.1022** | ✅ Full new prompt structure working |

> v3 input breakdown (estimated, len//4): profile=1779, prompt_phase1=702 / prompt_phase2=927, user_phase1=512 / user_phase2=1812
> v6 platform totals (non_cache+cache_write+cache_read): phase1=3859, phase2=6896. Console: non_cache=2879, cache_write=2696, cache_read=5180

**Самая дорогая фаза:** Phase 3.5 (23% бюджета v2) — туда идёт весь контекст: JD + анализ + CV draft.

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

Таблица `llm_usage` (актуальная схема, v3+):
- `vacancy_id` FK (nullable)
- `phase` — phase1 / phase2 / phase3 / phase3_5 / phase4
- `model`
- **Input breakdown (estimated, len//4 ±10%):** `profile_tokens`, `prompt_tokens`, `user_tokens`
- **API totals (exact):** `input_tokens`, `output_tokens`, `cache_write_tokens`, `cache_read_tokens`
- **Extended Thinking:** `budget_tokens` (requested), `thinking_tokens` (estimated from block text)
- **Timing:** `elapsed_ms`
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

## 7. Заметка о параметре `budget_tokens` и его связи с `max_tokens`

> ⚠️ Рекомендационная заметка. Поведение моделей может измениться непредсказуемо. Основана на наблюдениях 2026-05-30, не на официальной документации.

**Что такое `budget_tokens`:**
Верхний лимит на количество thinking токенов. Модель не превысит этот порог. Но сколько реально использовать — решает сама.

**Связь с `max_tokens`:**
В нашей реализации `max_tokens` автоматически поднимается до `budget_tokens + 4096` (требование API — max_tokens должен превышать budget_tokens). Это влияет на максимально возможный размер всего ответа (thinking + текст).

**Влияет ли бюджет на поведение модели:**
По наблюдениям — предположительно да. Большой бюджет (10k) может сигнализировать модели "думай глубже". Маленький бюджет (3k) — "будь лаконичнее в рассуждениях". Но это не задокументировано и может быть просто артефактом наблюдений.

**Влияет ли бюджет на стоимость:**
Нет — напрямую. Биллинг по фактически использованным thinking токенам, а не по бюджету. Если используется 1043 из 10000 — платишь за 1043.

**Зачем тогда снижать бюджет:**
Защитный потолок. Если однажды на сложной вакансии модель решит думать 8000 токенов — лимит остановит. При budget=3k и фактическом использовании ~1043 — запас 3× достаточен, неожиданных трат нет.

**Наши значения:**
- phase1: фактически ~30 thinking токенов из 10k → снижено до 3k
- phase2: фактически ~1043 thinking токенов из 10k → снижено до 3k
- Запас при budget=3k: phase1 = 100×, phase2 = 3×

---

## 8. Observations & Open Questions

- **Формула точная** — delta $0.00 на v2, $0.004 на v1 ✅
- **Кэш работает в v3** ✅ — cache_read=1731 на phase2, SDK 0.105.2 (betas параметр убран, prompt caching теперь GA)
- **Кэш экономит на phase2:** 1731 × ($3.00−$0.30)/MTok = **$0.005** за вызов
- **Extended Thinking утилизация:** phase1=30/10000=0.3%, phase2=1043/10000=10.4% → budget=10k избыточен. Оптимум: 2000–3000
- **Thinking tokens в output_tokens** — billing по output rate ($15/MTok Sonnet). output=5347 vs v2=3760 → ~1587 доп. токенов = thinking
- **v3 дешевле v2 при лучшем качестве:** $0.1033 за 2 фазы vs $0.138 на Opus → **25% экономия** при смене на sonnet-4-6 + thinking
- **Latency:** phase1=40s, phase2=71s — thinking увеличивает время (vs ~15–35s без thinking). Приемлемо для batch.
- **✅ Формула `_calc_cost()` правильная** — thinking токены биллятся как output ($15/MTok). Первый CSV для v3 показал $0.04 из-за **billing lag** (данные не успели появиться). Второй CSV (после v4) подтверждает: v3≈$0.103, v4≈$0.098 — совпадает с нашим расчётом.
- **v3+v4 дешевле v2 при лучшем качестве:** ~$0.10 за 2 analysis фазы (vs $0.138 Opus v2) — **28% экономия** при смене на sonnet-4-6 + thinking.
- **Данные из консоли (sonnet-4-6, все вызовы):** v3 phase1=3291in/2008out, phase2=5532in/3339out; v4 phase1=3291in/1932out. CSV total: input_no_cache=$0.03, cache_write=$0.01, cache_read=$0.00, output=$0.16.
- **Quick Scan баг v3:** code fence в промпте сбивает модель → пустой блок. Фикс: убрать ``` из примера в phase2_fit.md
- **Phase 2 структурный баг v5:** `### Quick Scan` как instruction-заголовок в промпте конфликтовал с output `## Quick Scan`. Модель писала контент под `###`, оставляла `##` пустым. Фикс: все instruction-заголовки → `**[OUTPUT SECTION N — Name]**`.
- **Cache cascade v5→v6:** v5 кэширует phase1 prompt (cache_write=4803), v6 читает его (cache_read=5180). cache_read v6 в 2.4× выше чем v5. Промпт-кэш работает корректно между прогонами.
- **v6 output меньше v5 при полном выводе:** out=5461 vs v5=6178 — несмотря на то что v6 генерирует всё 4 секции Phase 2. v5 генерировал только Phase 1 (broken Phase 2). Вывод: Phase 2 full output ≈ 3412 output tokens.
- **2026-05-31 CSV total $0.22** = v5($0.1226) + v6($0.1022). Формула точна ✅

---

## 8. Update Log

| Date | Change |
|------|--------|
| 2026-05-30 | Initial creation. Prices $15/$75 → исправлены на $5/$25. Кэш не работал. |
| 2026-05-30 | v1+v2 прогоны, формула верифицирована. Beta header fix. Таблица перенесена в docs/discovery/. |
| 2026-05-30 | v3: смена на sonnet-4-6, Extended Thinking (budget=10k), кэш подтверждён. DB schema расширена (profile/prompt/user/budget/thinking/elapsed). Старый .claude/memory/token-tracking.md удалён. |
| 2026-05-30 | v4: исправлен Quick Scan (code fence убран из промпта). Billing lag в первом CSV подтверждён — формула _calc_cost() верна, thinking токены биллятся как output. |
| 2026-05-31 | v5 (broken): новые Phase 2 промпты, но `### Quick Scan` конфликт → Phase 2 пустой. v6: фикс instruction-заголовков, полный вывод Phase 2 (4 секции). Score 5.5/10. CSV $0.22 = v5+v6 ✅ |
