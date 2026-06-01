# Local Execution Mode — Claude Code Skill

**Что:** полный CV-pipeline прямо в Claude Code desktop. Никакого Telegram, никакого бота, никакой инфраструктуры.  
**Как:** slash-команда `/analyze` → Claude Code IS the agent — читает профиль, прогоняет фазы, пишет файлы.  
**Для кого:** разработчик / сам кандидат — быстрый разбор вакансии без поднятия docker compose.

---

## Запуск

```bash
# В Claude Code — просто написать:
/analyze

# Или триггер через естественный язык:
# "проанализируй вакансию", "сделай CV", "разбор вакансии", "job fit"
```

---

## Команды

| Команда | Действие |
|---------|---------|
| `/analyze` | загрузить активного пользователя → начать |
| `/analyze -u [id\|slug]` | переключить пользователя → начать |
| `/analyze -l` | показать список пользователей → остановиться |

---

## Как это работает (пошагово)

1. `/analyze` → Claude Code читает `skill/active_user` → берёт ID → загружает `skill/users/[id]/PROFILE.md`
2. Пользователь вставляет URL или текст JD
3. **Phase 1 + 2** запускаются автоматически — без подтверждения
   - Результат сохраняется в `JD_analysis.md`
   - В чат выводится только **Quick Scan** блок
   - Вопрос: _«Генерируем CV?»_
4. После подтверждения — **pre-flight** (язык CV + вариант имени, один вопрос)
5. **Phase 3** — черновик CV (не показывается пользователю)
6. **Phase 3.5** — self-review → показать пользователю → правки → сохранить `[Name]_CV.md` → сгенерировать PDF
7. Вопрос: _«Переходим к cover?»_
8. **Phase 4** — cover letter → правки → сохранить `[Name]_Cover.md`

**Правило: один вопрос за раз. Никогда два вопроса в одном сообщении.**

---

## Структура файлов

Папка вакансии: `vacancies/[Company — Role]/`

```
vacancies/
└── Acme Corp — Product Manager/
    ├── JD.md                  ← JD (из URL или вставлен вручную)
    ├── JD_analysis.md         ← Phase 1 + 2 + 3.5 self-review
    ├── [Name]_CV.md           ← английское CV
    ├── [Name]_CV_UA.md        ← украинское CV (если запрошено)
    ├── [Name]_CV.pdf          ← PDF
    ├── [Name]_Cover.md        ← cover (английский)
    └── [Name]_Cover_UA.md     ← cover (украинский, если запрошено)
```

---

## Профиль пользователя

```
skill/
├── active_user          ← ID активного пользователя (одна строка)
├── users.yaml           ← список пользователей {id, slug, name, profile_path}
└── users/
    └── [id]/
        └── PROFILE.md   ← опыт, навыки, настройки (language, skill_type, name variants)
```

Переключить пользователя: `/analyze -u kosar` или `/analyze -u 1`

---

## Язык CV и имя

- **Язык CV** = язык вакансии (English JD → English CV). Не зависит от настроек пользователя.
- **Имя** = берётся из `PROFILE.md → ## Name variants`. Если JD не на английском — спросить вариант.
- Если JD не на английском: предложить три варианта — English / JD-язык / Оба.

---

## PDF-генерация

**Сейчас** (до EPIC-14 на локальной машине):
```bash
CAREER_AGENT_FONTS=fonts/ python ../callback-cv/cv_to_pdf.py vacancies/[folder]/[Name]_CV.md
```

**После EPIC-14** (`services/pdf` запущен):
```bash
# Claude Code делает это автоматически — POST markdown → http://localhost:8002/render → PDF bytes
docker compose up pdf-service -d
```

---

## Промпты

Все фазы роутятся через `skill_type` из `PROFILE.md → ## Settings`:

| Фаза | Файл |
|------|------|
| Phase 1 | `prompts/[skill_type]/phase1_analysis.md` |
| Phase 2 | `prompts/[skill_type]/phase2_fit.md` |
| Phase 3 | `prompts/[skill_type]/phase3_cv_draft.md` |
| Phase 3.5 | `prompts/[skill_type]/phase3_5_review.md` |
| Phase 4 | `prompts/[skill_type]/phase4_cover.md` |

Доступные `skill_type`: `pm` (активен), `generic` (в разработке).

---

## Отличие от Telegram-бота

| | Claude Code skill | Telegram bot |
|--|------------------|-------------|
| Триггер | `/analyze` или фраза | RSS / команда в Telegram |
| Профиль | `skill/users/[id]/PROFILE.md` | DB (после EPIC-17) |
| Запись в DB | ❌ нет | ✅ да |
| PDF | subprocess / HTTP (EPIC-14) | CVAdapter → HTTP |
| Мультипользователь | `users.yaml` + `active_user` | DB `users` table |
| Когда использовать | быстрый разбор, без инфраструктуры | полный prod-pipeline |

---

## Связанные документы

- Epic: [`docs/delivery/Epics/EPIC-19-local-execution.md`](delivery/Epics/EPIC-19-local-execution.md)
- Онбординг (источник профиля): [`docs/delivery/Epics/EPIC-17-onboarding.md`](delivery/Epics/EPIC-17-onboarding.md)
- Skill types: [`skill/SKILL_TYPES.md`](../skill/SKILL_TYPES.md) _(gitignored — локальный файл)_

---

---

## Диаграммы

### Pipeline flow

```mermaid
flowchart TD
    User(["👤 Claude Code\n/analyze"])
    User --> Load["Загрузить профиль\nskill/active_user → PROFILE.md"]

    Load --> P1

    subgraph P1["⬜ Phase 1 + 2 — Analyze JD"]
        direction LR
        F1["phase1_analysis\n+ phase2_fit"] -->|"JD text + PROFILE"| Claude1["Claude API\nprompts/[skill_type]/"]
        Claude1 -->|"fit score\narchetypes / gaps"| F1
        F1 --> A1[/"JD_analysis.md\n→ Quick Scan в чат"/]
    end

    P1 --> Confirm1{"Генерируем CV?"}
    Confirm1 -->|нет| Stop(["🛑 Стоп"])
    Confirm1 -->|да| Preflight["Pre-flight:\nязык CV + вариант имени"]

    Preflight --> P3

    subgraph P3["⬜ Phase 3 — CV Draft"]
        direction LR
        F3["phase3_cv_draft"] -->|"JD + PROFILE\n+ анализ + язык"| Claude2["Claude API"]
        Claude2 -->|"черновик CV\n(не показывать)"| F3
    end

    P3 --> P35

    subgraph P35["⬜ Phase 3.5 — Self-Review"]
        direction LR
        F35["phase3_5_review"] -->|"черновик + анализ"| Claude3["Claude API"]
        Claude3 -->|"рецензия + правки"| F35
        F35 --> A35[/"[Name]_CV.md\n→ PDF\n→ показать пользователю"/]
    end

    A35 --> Confirm2{"Правки или ок?"}
    Confirm2 -->|правки| P35
    Confirm2 -->|ок| Confirm3{"Переходим к cover?"}
    Confirm3 -->|нет| Done1(["✅ CV готов"])

    Confirm3 -->|да| P4

    subgraph P4["⬜ Phase 4 — Cover Letter"]
        direction LR
        F4["phase4_cover"] -->|"JD + CV + анализ"| Claude4["Claude API"]
        Claude4 -->|cover letter| F4
        F4 --> A4[/"[Name]_Cover.md\n→ показать пользователю"/]
    end

    A4 --> Confirm4{"Правки или ок?"}
    Confirm4 -->|правки| P4
    Confirm4 -->|ок| Done2(["✅ CV + Cover готовы"])
```

### Component map

```mermaid
graph TD
    CC["👤 Claude Code Desktop\n/analyze command"]
    SKILL["skill/SKILL.md\nорхестрация"]
    PROFILE["skill/users/[id]/PROFILE.md\nпрофиль кандидата"]
    Prompts["prompts/[skill_type]/\nphase1..4"]
    Claude["Claude API"]
    FS["vacancies/[Company — Role]/\nJD.md, CV.md, Cover.md, PDF"]
    PDF_local["subprocess\ncv_to_pdf.py\n(до EPIC-14)"]
    PDF_svc["services/pdf :8002\n(после EPIC-14)"]

    CC --> SKILL
    SKILL --> PROFILE
    SKILL --> Prompts
    Prompts --> Claude
    Claude --> SKILL
    SKILL --> FS
    SKILL --> PDF_local
    SKILL --> PDF_svc
```

### Источник профиля (переход)

| Этап | Источник |
|------|---------|
| Сейчас (pre-EPIC-17) | `skill/users/[id]/PROFILE.md` — filesystem |
| После EPIC-17 | DB `users.profile_md` — запись при онбординге |
| Переход | `AgentDeps` проверяет DB → если нет, читает файл |
