# Pipeline Evolution — agent-hub CV Analysis

> Хронология изменений pipeline: модели, промпты, API-паттерны.
> Каждая версия = конкретные изменения + уроки. Source of truth: `docs/discovery/Tokenomics.md`.

---

## v1 — Baseline (2026-05-30)

**Модель:** claude-opus-4-5  
**Кэш:** не работал (beta header отсутствовал)  
**Промпты:** первые версии из callback-cv, частично адаптированные  
**Cost:** $0.34 (analyze+generate+cover)

**Что работало:** базовый pipeline end-to-end  
**Что не работало:** кэш, язык вывода (иногда украинский), Quick Scan структура неустойчивая

---

## v2 — Prompt fixes (2026-05-30)

**Модель:** claude-opus-4-5  
**Кэш:** не работал (beta header fix вышел уже после прогона)  
**Изменения:** исправленные промпты, лучшая структура секций  
**Cost:** $0.32 (analyze+generate+cover) — дешевле v1 несмотря на все 5 фаз в одной сессии

**Урок:** компактные выходы → ниже стоимость. Качество промпта влияет на стоимость напрямую.

---

## v3 — Sonnet + Thinking + Cache (2026-05-30)

**Модель:** claude-sonnet-4-6  
**Кэш:** исправлен — убран `betas=["prompt-caching-2024-07-31"]` (SDK 0.105.2, caching теперь GA)  
**Extended Thinking:** включён, budget=10k (впоследствии снижен до 3k)  
**DB:** расширена таблица `llm_usage` — 6 новых колонок (profile/prompt/user/budget/thinking/elapsed)  
**Cost:** $0.1033 (только phase1+2) vs $0.138 Opus → **25% экономия**

**Баги:**
- Quick Scan пустой: code fence ` ``` ` в примере phase2_fit.md сбивала модель — выдавала пустой блок вместо контента

**API уроки:**
- `betas` параметр удалён из SDK 0.105.2, кэш работает без него
- Extended Thinking: billing по фактически использованным thinking tokens, не по budget
- `max_tokens` должен превышать `budget_tokens` (auto-raise: `max(max_tok, budget_tokens + 4096)`)
- `response.content` содержит `thinking` блоки + `text` блоки — нужно явно фильтровать

---

## v4 — Quick Scan fix + Language enforcement (2026-05-30)

**Модель:** claude-sonnet-4-6  
**Изменения:**
- Убраны code fences из примера Quick Scan в phase2_fit.md
- Language rule перемещён непосредственно перед Output Format (было вверху файла)
- Консолидирован `**Output rules:**` блок с языком, тоном и обязательными секциями
- `budget_tokens` снижен 10k → 3k (фактическое использование: phase1≈30tok, phase2≈1043tok)
**Cost:** $0.0977 (only phase1+2)

**Промпт-урок:** правило языка работает надёжнее если стоит непосредственно перед Output Format, не в начале файла.

**Prompt engineering observations:**
- Модель следует правилам лучше когда они рядом с местом применения
- Code fence в примере = модель думает что пример — это шаблон для вывода → пустой блок
- Consolidating related rules (language + tone + sections) в один блок снижает drift

---

## v5 — Phase 2 redesign (BROKEN) (2026-05-31)

**Модель:** claude-sonnet-4-6  
**Изменения в Phase 2 prompt (major rewrite):**
- Три отдельных потока: Key Barriers (кандидат) / Hidden Risks (контекст) / Warnings (процесс)
- 3-way Verdict: подавать / подавать с адаптацией / не подавать
- Математический scoring: baseline 5.0, дельты (+2.0/-1.5/-1.0 etc.), cap 9.5
- Обязательная Fit Breakdown таблица (✅/⚠️/❌, строгие правила)
- Условный Adaptation Plan (≥4 → reframe advice; <4 → причины не подавать)
- Internal Analysis секция (не в Telegram, только в файле)
- Archetype delta: и в Barrier, и в Adaptation Plan

**Баг:** `### Quick Scan` как instruction-заголовок конфликтовал с output `## Quick Scan`.  
Модель писала весь контент под `###`, оставляла `##` пустым.  
Phase 2 body в файле = 4 строки вместо ~150.  
**Cost:** $0.1226 (оплачен, данные в Anthropic, не переиспользуются)

**Промпт-урок:** заголовки секций в инструкции НЕ ДОЛЖНЫ совпадать по тексту и уровню с заголовками output-шаблона. Модель путается какой `##` писать контент.

---

## v6 — Fixed structure, full Phase 2 (2026-05-31)

**Модель:** claude-sonnet-4-6  
**Фикс:** все instruction-секции переименованы в `**[OUTPUT SECTION N — Name]**` вместо `### Name`.  
Output-шаблоны сохранили свои `## ` заголовки.

**Результат:**
- Quick Scan заполнен полностью
- Score 5.5/10 — критичный, реалистичный (не завышен)
- Key Barriers: 3 конкретных (AI только pet-projects, архетип-дельта, no-code gap)
- Hidden Risks: 3 контекстных сигнала компании/роли
- Fit Breakdown: 10 строк, строгий ✅/⚠️/❌
- Adaptation Plan: 5 конкретных reframe-действий, архетип-коррекция первой

**Cost:** $0.1022 (phase1+2) — кэш cache_read=5180 (2.4× выше v5 за счёт cache cascade)

**Cache cascade:** v5 записал phase1 prompt в кэш (cache_write=4803). v6 прочитал его (cache_read=5180). Экономия на v6 за счёт v5's cache write.

---

## Промпт-инжиниринг: накопленные уроки

| Урок | Что произошло | Фикс |
|------|--------------|------|
| Правило языка в начале файла не работает | Модель игнорировала Russian rule при длинных промптах | Переместить rule непосредственно перед Output Format |
| Code fence в примере = пустой вывод | Модель воспринимала ``` как шаблон для своего вывода | Убрать fences из примеров в промпте |
| `### Name` заголовок = конфликт с `## Name` в output | Модель пишет контент под instruction-заголовок, игнорирует output-заголовок | Instruction секции: `**[OUTPUT SECTION N — Name]**` |
| Pet-projects без явного правила = ✅ | Модель ставила ✅ за GitHub репозитории | Явное правило: `Pet-projects are NEVER ✅` |
| Scoring без guidance = "галлюцинации оптимизма" | 7/10 вместо реалистичного 5.5/10 | Числовые дельты: baseline 5.0, +2.0/-1.5 etc. |
| Смешивание warnings типов | Candidate gaps попадали в Warnings вместо Key Barriers | Три раздельных поля + `⚠️ CRITICAL` с примерами что не класть |

---

## API: накопленные уроки

| Урок | Версия |
|------|--------|
| `betas=["prompt-caching-2024-07-31"]` устарел — SDK 0.105.2+ кэш работает без него | v3 |
| Thinking tokens биллятся как output tokens ($15/MTok Sonnet) — не "бесплатно" | v3 |
| `budget_tokens` — потолок, не заказ. Фактическое использование: phase1≈30/3000, phase2≈1043/3000 | v3-v4 |
| `max_tokens` должен > `budget_tokens`. Auto-raise: `max(max_tok, budget_tokens + 4096)` | v3 |
| Billing lag в Anthropic CSV: первый экспорт может показывать неполные данные | v3 |
| `response.content` = `[ThinkingBlock, TextBlock]`. Нужно явно фильтровать по `block.type == "text"` | v3 |
| Prompt caching cascade: cache_write одного прогона = cache_read следующего в течение 5 минут | v5→v6 |
| Platform "Input Tokens" = non_cache + cache_write + cache_read (не только non-cached input) | v6 |

---

## Эволюция Phase 2 output структуры

```
v1-v2 (Opus):
  → Fit Dimensions table
  → Detailed Assessment (matches/gaps/transferable/objections)
  → Summary
  → Quick Scan (Category/Who/Fit/Blockers/Warnings/Recommendation)

v3-v4 (Sonnet, initial):
  → Fit Dimensions table
  → Detailed Assessment
  → Summary
  → Quick Scan (same fields, но Russian rule зафиксирован)

v5 (broken):
  → [OUTPUT SECTION 1] Quick Scan (new: 3-way Verdict, Key Barriers, Hidden Risks)
  → [OUTPUT SECTION 2] Fit Breakdown (новое: mandatory ✅/⚠️/❌ table)
  → [OUTPUT SECTION 3] Adaptation Plan (новое: conditional, archetype-aware)
  → [OUTPUT SECTION 4] Internal Analysis (старые секции под капот)
  BROKEN: Phase 2 body пустой из-за ### vs ## конфликта

v6 (working):
  → ## Quick Scan (5 полей: Category/Who/Score/Verdict/KeyBarriers/HiddenRisks/Warnings)
  → ## Fit Breakdown (10 строк, строгий ✅/⚠️/❌)
  → ## Adaptation Plan (5 действий, archetype delta first)
  → ## Internal Analysis (Fit Dimensions + Detailed Assessment + Summary)
```

---

## Связанные файлы

- `docs/discovery/Tokenomics.md` — cost breakdown по всем runs
- `prompts/phase1_analysis.md` — Phase 1 текущая версия
- `prompts/phase2_fit.md` — Phase 2 текущая версия (v6 структура)
- `prompts/phase3_cv_draft.md` — Phase 3 + Adaptation Plan implementation
- `prompts/phase3_5_review.md` — Phase 3.5 + Phase 2 Implementation Check
- `callback-cv/skill/PROFILE.md` — профиль кандидата + Archetype & Role Positioning
