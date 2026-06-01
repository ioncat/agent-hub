---
description: Run career-agent CV pipeline. Accepts vacancy URL, path to JD .md file, or DB vacancy ID.
---

Run the career-agent pipeline for: $ARGUMENTS

## Steps

1. **Определи тип ввода** по `$ARGUMENTS`:
   - Начинается с `http` → URL вакансии
   - Целое число → `vacancy_id` в БД (переобработка существующей)
   - Заканчивается на `.md` или содержит `/` → путь к файлу JD

2. **Выбери фазы** — спроси пользователя если не указано явно (default: все фазы):
   - `fetch` — скачать JD (только для URL; пропускается для file/id)
   - `analyze` — анализ вакансии
   - `generate` — генерация CV (включает self-review 3.5)
   - `cover` — cover letter

3. **Запусти скрипт** подходящей командой:

   ```bash
   # Режим URL
   python scripts/e2e_test.py --url "$ARGUMENTS" --phase fetch,analyze,generate,cover

   # Режим файла
   python scripts/e2e_test.py --file "$ARGUMENTS" --phase analyze,generate,cover

   # Режим ID (переобработка)
   python scripts/e2e_test.py --id "$ARGUMENTS" --phase analyze,generate,cover
   ```

4. **Показывай результат** каждой фазы по мере выполнения.

5. **После каждой фазы** спроси подтверждение перед следующей (если не запущен в batch-режиме).

6. **В конце** выведи итоги: vacancy_id, пути к файлам, стоимость LLM-сессии.

## Заметки

- Для `--file`: скрипт читает JD из файла, вставляет в БД с `url=file://<path>`, пропускает fetch
- Для `--id`: скрипт находит вакансию по ID, пропускает fetch, запускает указанные фазы
- `AGENT_MODE=testing` в `.env` → запрашивает подтверждение перед каждым Claude API вызовом
- kmp-service должен быть доступен на `KMP_BASE_URL` (только для режима URL + fetch)
