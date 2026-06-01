---
description: Run career-agent CV pipeline via Anthropic API. Mirrors /analyze flow but uses ClaudeProvider instead of Claude Code's built-in model. Accepts URL, path to JD .md file, or DB vacancy ID.
---

Run the career-agent pipeline for: $ARGUMENTS

## Ключевое отличие от /analyze

`/analyze` — Claude Code сам является LLM, без внешних API.  
`/pipeline` — Claude Code оркестрирует Python-инструменты, которые вызывают **Anthropic API** через ClaudeProvider.  
Поведение и UX — идентичны.

---

## Шаг 0 — Выбор пользователя

1. Прочитай `skill/active_user` — текущий активный пользователь.
2. Прочитай `skill/users.yaml` — список всех пользователей.
3. Покажи список и спроси: "Какой профиль использовать?" (pre-select активного).
4. Запомни: `selected_user_id`, путь к `PROFILE.md` (`skill/users/[id]/PROFILE.md`).

---

## Шаг 1 — Определи тип ввода

Из `$ARGUMENTS`:
- Начинается с `http` → **URL режим**
- Целое число → **ID режим** (переобработка из БД, пропустить fetch)
- Оканчивается на `.md` → **File режим** (пропустить fetch)

---

## Шаг 2 — Phase 1 + 2: Fetch + Analyze

Спроси: **"Запускаем fetch + analyze?"**

После подтверждения — передай флаг `--auto-confirm` (ты уже получил разрешение пользователя):

```bash
# URL режим
python scripts/e2e_test.py \
  --url "$ARGUMENTS" \
  --phase fetch,analyze \
  --user-id {selected_user_id} \
  --profile skill/users/{selected_user_id}/PROFILE.md \
  --auto-confirm

# File режим
python scripts/e2e_test.py \
  --file "$ARGUMENTS" \
  --phase fetch,analyze \
  --user-id {selected_user_id} \
  --profile skill/users/{selected_user_id}/PROFILE.md \
  --auto-confirm

# ID режим — только analyze (fetch пропущен)
python scripts/e2e_test.py \
  --id "$ARGUMENTS" \
  --phase analyze \
  --user-id {selected_user_id} \
  --profile skill/users/{selected_user_id}/PROFILE.md \
  --auto-confirm
```

После выполнения:
- Прочитай `JD_analysis.md` из папки вакансии
- Извлеки и покажи **только блок `## Quick Scan`** (заголовок + поля до следующего `##`)
- Запомни `vacancy_id` из вывода скрипта

Затем спроси: **"Генерируем CV?"**

---

## Шаг 3 — Pre-flight (один раз, перед Phase 3)

Спроси **одним сообщением**:

```
На каком языке готовить CV?
1. English — [English name из PROFILE.md]
2. [язык JD] — [кириллическое имя из PROFILE.md]
3. Оба

(Вариант 3 → два CV + два cover)
```

- Прочитай варианты имени из `PROFILE.md → ## Name variants`
- Если JD на английском — пропусти вопрос, используй английское имя

---

## Шаг 4 — Phase 3 + 3.5: Generate CV

```bash
python scripts/e2e_test.py \
  --id {vacancy_id} \
  --phase generate \
  --user-id {selected_user_id} \
  --profile skill/users/{selected_user_id}/PROFILE.md \
  --auto-confirm
```

После выполнения:
- Прочитай `[Name]_CV.md` из папки вакансии
- Показай полный текст CV пользователю

Спроси: **"Вносим правки или всё ок?"**

- Если правки → прими правки текстом, внеси в файл `[Name]_CV.md`, перегенерируй PDF:
  ```bash
  python scripts/e2e_test.py --id {vacancy_id} --phase generate --user-id {selected_user_id} --profile skill/users/{selected_user_id}/PROFILE.md --auto-confirm
  ```
- Если ок → спроси: **"Переходим к cover?"**

---

## Шаг 5 — Phase 4: Cover Letter

```bash
python scripts/e2e_test.py \
  --id {vacancy_id} \
  --phase cover \
  --user-id {selected_user_id} \
  --profile skill/users/{selected_user_id}/PROFILE.md \
  --auto-confirm
```

После выполнения:
- Прочитай `[Name]_Cover.md` из папки вакансии
- Покажи полный текст cover пользователю

Спроси: **"Вносим правки или всё ок?"**

---

## Шаг 6 — Итог

Выведи:
- `vacancy_id`
- Папка вакансии (`vacancies/{user_id}/{site}/{YYYY-MM}/{slug}/`)
- Список сгенерированных файлов
- Стоимость LLM-сессии (из вывода скрипта: `💰 Session cost`)

---

## Правила (из SKILL.md)

- **Один вопрос за раз** — никогда два вопроса в одном сообщении
- Phase 3 draft **не показывать** — показывать только после 3.5 self-review
- Blockers в Quick Scan ≠ нет → Recommendation = не подавать (предупредить пользователя)
- Язык CV = язык вакансии (не зависит от настроек пользователя)
