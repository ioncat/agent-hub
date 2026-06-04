# /analyze — Career Agent Pipeline

Single entry point for the local CV pipeline.
Handles mode selection, user selection, and pipeline start in one command.

---

## Step 0 — Profile + Mode confirm (always first)

**Every `/analyze` run begins here** — before inbox, before everything.

Read `skill/active_user` → ID → `skill/users.yaml` → name + slug. Display:

```
👤 Alex Bondarenko (alex)
  [1] Локально — Claude Code (без Anthropic API)
  [2] API — Anthropic Claude (с расходом токенов)
  [3] Другой профиль → /analyze -u [id|slug]
```

- **[1]** → `MODE = local`, proceed to inbox check with this profile
- **[2]** → `MODE = api`, proceed to inbox check with this profile
- **[3]** → show user list (same as `-l`), stop — user re-runs with `-u`
- Selected mode applies to **all phases and all inbox files** in this invocation
- Display selected mode in all subsequent status lines: `[Локально]` or `[API]`
- **Skip Step 0 for:** `-l` (list users), `-inbox` (list inbox only) — read-only, no pipeline

---

## Flags

| Flag | Alias | Behavior |
|------|-------|----------|
| *(no args)* | | **Mode** → inbox → active user → load → start |
| `-n` | `-now` | Same as no args (explicit) |
| `-u [id\|slug]` | `-user [id\|slug]` | **Mode** → switch user → inbox → load → start |
| `-v [id]` | `-vacancy [id]` | **Mode** → load vacancy by DB id → continue pipeline → skip inbox |
| `-l` | `-list` | Show user list → stop (no pipeline, no mode ask) |
| `-pdf [name?]` | | Regenerate PDFs → stop (no pipeline, no mode ask) |
| `-inbox` | | Show inbox contents only → stop (no pipeline, no mode ask) |

---

## `-l` / `-list` — Show user list

Read `skill/active_user`, `skill/users.yaml`, scan `skill/users/` directory.

Display:

```
👥 Career Agent — пользователи

  ID    Name               Slug      Profile
  1     Alex Bondarenko    alex      ✅        ← активный
  2     Maria Beleshko     maria     ✅

/analyze -u [id|slug]   — переключить и начать
/analyze                — начать с активным
```

Profile status: `✅` if `skill/users/[id]/PROFILE.md` exists and non-empty. `⚠️ missing` if not.
Unregistered folders (on disk, not in yaml): show as `(unregistered)` — cannot switch until added to `users.yaml`.

Stop after display. Do not start pipeline.

---

## `-u` / `-user` — Switch user then start

Read `skill/users.yaml`. Match argument against `id` or `slug`.

**Not found:**
```
❌ Пользователь "[arg]" не найден.
Запусти /analyze -l для списка.
```
Stop.

**Found — switch:**
Write new ID to `skill/active_user` (overwrite, one line, no trailing spaces).

```
✅ Переключено: [name] ([slug])
```

Then proceed to **Load & Start** below.

---

## No args / `-n` / `-now` — Use active user

Run **Step 0** (profile + mode confirm) above — active user already known.

After mode selected → proceed to **Inbox check** → **Load & Start**.

---

## Load & Start

1. Check profile: `skill/users/[id]/PROFILE.md` — must exist and be non-empty (not just placeholder comment block).

   If missing or placeholder:
   ```
   ⚠️ Профиль не заполнен: skill/users/[id]/PROFILE.md
   Заполни профиль и повтори команду.
   ```
   Stop.

2. Load `skill/SKILL.md` — pipeline rules and orchestration.
3. Read `skill/users/[id]/PROFILE.md` into context — candidate profile.

4. Display:
   ```
   ✅ [name] — профиль загружен.
   Загружай вакансию: вставь текст JD или дай URL.
   ```

5. Follow pipeline rules from `skill/SKILL.md` exactly.

---

## `-v [id]` / `-vacancy [id]` — Resume pipeline for existing vacancy

Look up vacancy in DB. Display **both blocks in one message** — no round-trip for mode confirmation.

```bash
python scripts/vacancy_track.py get --id [id]
```

**Not found:**
```
❌ Вакансия #[id] не найдена в DB.
Запусти /analyze для обработки новой вакансии.
```
Stop.

---

### Combined single-message display

Show **Block 1** (profile/mode — informational) and **Block 2** (vacancy actions — working) in one response.

**Numbering:**
- Block 1 items: **1–10** (change profile or mode)
- Block 2 items: **11–20** (pipeline actions for this vacancy)

Answer 1–10 → routes to Block 1. Answer 11–20 → routes to Block 2. Never ambiguous.

**Example output:**

```
👤 Alex Bondarenko (alex) · Локально

  [1] Сменить режим → API
  [2] Сменить профиль

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Вакансия #75 [Локально]

Product Manager (CRM) — JustMarkets Tech
https://djinni.co/jobs/829358-product-manager-srm
Создана: 2026-06-03

Выполнено:
  ✅ Phase 1+2 — анализ (fit 7/10, rec: apply)
  ✅ Phase 3+3.5 — CV (Alex Bondarenko, en, 0 правок)
  ✅ Phase 4 — cover (en)

Что делаем?
  [11] Повторить Phase 4 — новый cover
  [12] Повторить Phase 3+3.5 — новый CV
  [13] Повторить Phase 1+2 — новый анализ
  [14] Заново с нуля — Phase 1+2 → 3+3.5 → 4
```

---

### Block 1 — Profile/Mode (items 1–10)

Always exactly:
- `[1]` Сменить режим → [other mode] (if current = Локально → show API; if API → show Локально)
- `[2]` Сменить профиль

If user picks `[1]` → toggle MODE, re-display both blocks with updated mode header.
If user picks `[2]` → show user list inline (same as `-l`), ask to re-run with `-u`.

**In most cases user ignores Block 1** — profile and mode are already correct.

---

### Block 2 — Vacancy actions (items 11–20)

**Phase status rules:**
- `p2` in analysis_json → ✅ Phase 1+2 done (show fit_score + recommendation)
- `p3` in analysis_json → ✅ Phase 3+3.5 done (show name_variant + cv_language + changes_count)
- `p4` in analysis_json → ✅ Phase 4 done (show cover_language)
- Missing key → ❌ that phase not done

**Menu ordering:**
- `[11]` = first ❌ phase (if any). If none → `[11]` = Повторить Phase 4
- Remaining phases in reverse pipeline order
- Last item always = "Заново с нуля — Phase 1+2 → 3+3.5 → 4"

**After user selects — proceed directly to that phase:**
- Phase 1+2 → run Phase 1+2 (re-read JD.md; re-save JD_analysis.md)
- Phase 3+3.5 → ask name/language pre-flight → run Phase 3+3.5
- Phase 4 → run Phase 4
- "Заново с нуля" → Phase 1+2 silent → Quick Scan → "Генерируем CV?" → normal pipeline

**JD source for re-runs:**
- `[vacancy_folder]/JD.md` if exists
- Otherwise `JD_analysis.md` for context reconstruction
- If neither → ask user to paste JD

**Inbox check skipped entirely** when `-v` is used.

---

## `-pdf [name?]` — Regenerate all PDFs for a vacancy

Converts every eligible `.md` file in a vacancy folder to PDF.
**Eligible files:** `JD_analysis.md` + `*_CV.md` + `*_CV_UA.md` (covers excluded).

### No argument — show vacancy list

Scan `vacancies/` directory. List folders that contain at least one eligible `.md` file:

```
📄 Выбери вакансию для генерации PDF:

  1. AlphaNova — Junior Publishing Manager
       JD_analysis.md  →  JD_analysis.pdf
  2. Stripe — Product Manager
       JD_analysis.md  →  JD_analysis.pdf
       Alex_CV.md      →  Alex_CV.pdf

Введи номер или часть названия.
```

Wait for input. Then proceed.

### With argument — match vacancy folder

Match argument (partial, case-insensitive) against folder names in `vacancies/`.

**No match:**
```
❌ Вакансия "[arg]" не найдена. Запусти /analyze -pdf для списка.
```

**Multiple matches:** show filtered list, ask to clarify.

**One match — regenerate:**

For each eligible `.md` in the folder, run:
```bash
CAREER_AGENT_FONTS=fonts/ python ../callback-cv/cv_to_pdf.py vacancies/[user_id]/[Company — Role]/[file].md
```

Report result:
```
📄 AlphaNova — Junior Publishing Manager

  ✅ JD_analysis.pdf
  ✅ Alex_CV.pdf
  ❌ Maria_CV.pdf — ошибка: [message]
```

Stop after report. Do not start pipeline.

---

## Inbox — Manual Vacancy Drop

**Folder:** `vacancies/inbox_manual/`
Checked automatically on every `/analyze` run (before loading profile).

### `-inbox` — Show inbox contents only

```
📥 Inbox — vacancies/inbox_manual/ (N файлів):

  1. stripe-pm.md
  2. djinni-job.txt

/analyze      — обробити з активним профілем
/analyze -u   — обробити з іншим профілем
```

Stop after display.

### Auto-check on `/analyze` (no args, `-n`, `-u`)

Runs **after Step 0** (profile + mode already confirmed).

1. Scan `vacancies/inbox_manual/` — `.md` and `.txt` files only (skip `processed/`, `.gitkeep`)
2. **No files** → skip, proceed to normal load & start
3. **Files found** → dedup check per file (see `skill/SKILL.md` → Sequential/Batch Mode for detail):
   - Extract `Source: http...` from first 3 lines → grep against `vacancies/inbox/{user_id}/*/JD.md`
   - Already seen → Sequential: ask skip/reprocess · Batch: skip silently, mark `♻️ уже обработана`
4. Show inbox menu:

```
📥 Найдено N вакансий в inbox [Локально]:

  1. Role — Company
  2. Role — Company
  ...

Что делаем?
  [1]  — обработать конкретную вакансию (через любой разделитель укажи номер: "1", "1,3", "1 3")
  [2]  — обработать все (batch)
  [3]  — пропустить inbox, начать с новой вакансией
```

4. If multiple users → ask profile (skip if active user already selected via `-u`):
   *(mode already selected in Step 0 — do not ask again)*

```
Для какого профиля?
  [1] Alex Bondarenko (alex) ← активный
  [2] Maria Beleshko (maria)
```

6. **Choose processing mode** based on selected count:
   - **1–2 vacancies** → Sequential mode (process one by one, full analysis shown per vacancy)
   - **3+ vacancies** → Batch mode (Phase 1+2 silent for all → consolidated table → ask to proceed)

   See `skill/SKILL.md` → "Batch Mode" and "Sequential Mode" for full step-by-step.

7. After all processed → "Продолжить с новой вакансией или завершить?"

**File naming tip:** name file `Company — Role.md` → used as vacancy folder name directly.

---

## Adding a New User

1. Create `skill/users/[id]/PROFILE.md` — fill with candidate profile.
2. Add entry to `skill/users.yaml`:
   ```yaml
   - id: "003"
     name: "Full Name"
     slug: "shortname"
   ```
3. Run `/analyze -u shortname` to switch and start.

IDs are sequential integers as strings (`1`, `2`, ...). Match DB `user_id` directly.
