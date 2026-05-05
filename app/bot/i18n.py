"""Tiny string-table i18n.

Keys are short dotted identifiers ("cancel.done", "start.hi"). EN is the
source of truth — RU is an overlay; if a key is missing in RU we fall
back to EN. If a key is missing entirely we return the key itself so a
missing translation is loud in the UI but never crashes a handler.

Strings can carry str.format placeholders ({name}, {date}, {n}).

This is intentionally not gettext — there's a single deployment, two
languages, and the project rule (CLAUDE.md) is to avoid abstractions
that don't pay for themselves yet.
"""
from __future__ import annotations

SUPPORTED: tuple[str, ...] = ("en", "ru")

EN: dict[str, str] = {
    # /start, /help, /cancel
    "start.hi": "Hi {name}! You're all set.\n\n",
    "cancel.done": "Cancelled.",
    # /lang
    "lang.help": "Use /lang en or /lang ru to switch the bot's language.",
    "lang.unknown": "Unknown language: {code}. Supported: en, ru.",
    "lang.set": "Bot language set to English.",
    # generic
    "err.send_text": "Please send text.",
    "err.send_number": "Please send a number (e.g. 7 or 7.5).",
    "err.short_text": "Please send a short text.",
    # /log flow
    "log.pick_metric": "What do you want to log?",
    "log.enter_numeric": "{label} — pick 1-10:",
    "log.enter_sleep_hours": "How many hours did you sleep? (e.g. 7.5)",
    "log.enter_text": "Send the text for {label}:",
    "log.saved_numeric": "Logged {label} = {value} for {date}.",
    "log.saved_text": "Logged {label} for {date}.",
    # /note + /thought
    "note.send": "Send your note as the next message.",
    "note.saved": "Note saved for {date}.",
    "thought.start": "CBT thought record. First, describe the situation:",
    "thought.ask_auto": "What automatic thought came up?",
    "thought.ask_distortion": (
        "Which cognitive distortion fits best?\n"
        "(catastrophising / all-or-nothing / mind-reading / personalisation / "
        "overgeneralisation / labelling / 'should' statements / fortune-telling / other)"
    ),
    "thought.ask_reframe": "Now reframe it. What's a more balanced thought?",
    "thought.saved": "Thought record saved for {date}. Nice work.",
    # /backfill
    "backfill.usage": (
        "Usage: /backfill <date> <metric> <value>\n"
        "Examples:\n"
        "  /backfill 2026-04-30 mood 6\n"
        "  /backfill yesterday sleep_hours 7.5\n"
        "  /backfill 3-days-ago note Felt tense after the call"
    ),
    "backfill.bad_date": "Couldn't parse date '{raw}': {err}",
    "backfill.bad_metric": "Unknown metric '{raw}'. Try: {choices}",
    "backfill.bad_value": "Couldn't parse numeric value '{raw}'.",
    "backfill.need_text": "{label} needs text content after the metric name.",
    "backfill.saved_numeric": "Backfilled {label} = {value} for {date}.",
    "backfill.saved_text": "Backfilled {label} for {date}.",
    # /activate (BA)
    "activate.start": "What would lift your mood, even slightly? Send one short line.",
    "activate.ask_when": "When?",
    "activate.ask_predicted": (
        "Planned for {date}. How much do you predict it will lift your mood? (1-10)"
    ),
    "activate.saved": (
        "Plan saved for {date} (predicted +{predicted}). "
        "Use /done when finished, or /skip if not."
    ),
    "plans.empty": "No open plans. /activate to add one.",
    "plans.header": "Open plans:",
    "plans.line": "• {weekday} {date} — {text}{suffix}",
    "plans.predicted_suffix": " (predicted +{predicted})",
    "done.empty": "No open plans. /activate to add one.",
    "done.pick": "Which one did you complete?",
    "done.ask_actual": "How much did it actually lift your mood? (1-10)",
    "done.saved_with_pred": "Done — predicted +{predicted}, actual +{actual}. Nice.",
    "done.saved": "Done — actual +{actual}. Nice.",
    "done.failed": "Couldn't mark done: {err}",
    "skip.empty": "No open plans to skip.",
    "skip.pick": "Which one are you skipping?",
    "skip.ask_reason": "One-line reason? (or send /cancel to skip without one)",
    "skip.saved": "Skipped. No judgement — sometimes the planning itself is the work.",
    "skip.failed": "Couldn't skip: {err}",
    # /today, /week
    "today.empty": "No entries today.",
    "today.header": "Today:",
    "today.line_numeric": "• {label}: {value}",
    "today.line_text": "• {label}: {value}",
    "week.empty": "No data in the last 7 days.",
    "week.header": "Last 7 days:",
    # /tz
    "tz.usage": "Usage: /tz <IANA timezone>, e.g. /tz Europe/Berlin",
    "tz.unknown": "Unknown timezone: {raw}. See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
    "tz.saved": "Timezone set to {tz}.",
    # /chart, /export, /therapist
    "chart.pick_period": "Pick a period:",
    "chart.empty": "No numeric data in this period.",
    "export.pick_period": "Pick a period:",
    "export.caption": "Report {start} → {end}",
    "therapist.pick_period": "Pick a period for the therapist report:",
    "therapist.caption": (
        "Therapist report {start} → {end}.\n"
        "Includes thought records, BA outcomes and notes — share with your "
        "clinician only."
    ),
    # /ask
    "ask.usage": "Ask me anything about your data, e.g. /ask How was last week?",
    "ask.thinking": "Thinking…",
    # /schedule etc.
    "sched.show": (
        "Daily summary: {daily}\n"
        "Weekly summary: {weekly}"
    ),
    "sched.daily.off": "off",
    "sched.daily.on": "on at {time} ({tz})",
    "sched.weekly.off": "off",
    "sched.weekly.on": "on {dow} {time} ({tz})",
    "sched.dailyat.usage": "Usage: /dailyat HH:MM (24-hour)",
    "sched.dailyat.bad_time": "Bad time '{raw}'. Use HH:MM, e.g. 21:00.",
    "sched.dailyat.set": "Daily summary enabled at {time} ({tz}).",
    "sched.dailyoff.set": "Daily summary disabled.",
    "sched.weeklyat.usage": "Usage: /weeklyat <mon|tue|wed|thu|fri|sat|sun> HH:MM",
    "sched.weeklyat.bad_dow": "Unknown day '{raw}'. Use mon..sun.",
    "sched.weeklyat.bad_time": "Bad time '{raw}'. Use HH:MM.",
    "sched.weeklyat.set": "Weekly summary enabled on {dow} {time} ({tz}).",
    "sched.weeklyoff.set": "Weekly summary disabled.",
    # /checkins (proactive anomaly probes)
    "checkins.show.on": (
        "Anomaly check-ins: ON. I'll send a gentle nudge if mood, sleep "
        "or anxiety look unusual. Disable with /checkins off."
    ),
    "checkins.show.off": (
        "Anomaly check-ins: OFF. Enable with /checkins on to get a "
        "gentle nudge if mood, sleep or anxiety look unusual."
    ),
    "checkins.set.on": (
        "Anomaly check-ins enabled. I'll send at most one a day, only "
        "between 08:00 and 22:00 in your timezone, and only when "
        "something looks off."
    ),
    "checkins.set.off": "Anomaly check-ins disabled.",
    "checkins.unknown": "Use /checkins, /checkins on, or /checkins off.",
    # Templates for the actual probe messages.
    "checkin.low_mood_streak": (
        "Heads up — your mood has been low for {days} days in a row "
        "({values}). Anything going on? If a thought is sticky, "
        "/thought helps work through it; /activate is good if you'd "
        "rather plan a small action."
    ),
    "checkin.sleep_crash": (
        "Sleep has been short — {values} hours over the last {days} "
        "nights. If something's keeping you up, /note it; /activate "
        "can help break the cycle."
    ),
    "checkin.anxiety_spike": (
        "Anxiety hit {value} today. /thought to work through what "
        "triggered it, or /activate to ground yourself in a small "
        "concrete action."
    ),
    # HELP_TEXT — assembled from a single block to keep formatting.
    "help.text": (
        "CBT tracker bot — log your day, ask Claude to analyse it.\n"
        "Each command below is followed by *when* to reach for it.\n\n"
        "📝 Logging\n"
        "/log — guided pick of any metric. Use when you want to log "
        "something less common (symptoms, focus, irritability) without "
        "remembering a specific command.\n"
        "/mood /sleep /energy /hunger /anxiety /stress /pain "
        "/irritability /focus — one-tap 1-10 scale. Use for fast "
        "in-the-moment captures (e.g. a sudden wave of anxiety).\n"
        "/sleephours — type sleep duration in hours (e.g. 7.5). "
        "Use right after waking to log how long you actually slept.\n"
        "/note <text> — free-form journal entry, encrypted at rest. "
        "Use when something is on your mind that doesn't fit any metric.\n"
        "/thought — guided CBT thought record (situation → automatic "
        "thought → distortion → reframe). Use when you catch a strong "
        "negative thought and want to work through it.\n"
        "/backfill <date> <metric> <value> — log for a past date. "
        "Use when you forgot to log yesterday or want to add an old entry.\n\n"
        "🌱 Behavioral activation\n"
        "/activate — plan a small mood-lifting activity and predict its "
        "lift. Use when you feel low and want a concrete step out of it.\n"
        "/plans — see open plans. Use to check what you've committed to.\n"
        "/done — mark a plan done and rate the actual lift. Use right "
        "after completing a planned activity — the predicted-vs-actual "
        "gap is the therapeutic insight.\n"
        "/skip — skip a plan with an optional reason. Use when something "
        "got in the way; no judgement.\n\n"
        "📊 Review\n"
        "/today — list today's entries. Use to see what you've logged so far.\n"
        "/week — last 7 days summary. Use for a quick weekly retrospective.\n"
        "/chart — pick a period and see a chart of numeric metrics. "
        "Use when you want to spot trends visually.\n"
        "/export — generate a multi-page PDF report (numeric only). "
        "Use for a private numeric snapshot or a personal archive.\n"
        "/therapist — richer PDF including thought records, BA outcomes, "
        "notes and other free-text. Use to share with a clinician — "
        "marked confidential, share only with people you trust.\n\n"
        "🤖 Claude\n"
        "/ask <question> — ask Claude anything about your data "
        "(e.g. 'what lifts my mood most?', 'when is my sleep worst?'). "
        "Use for analysis the bot's built-in views don't cover.\n\n"
        "⏰ Auto summaries (in your timezone)\n"
        "/schedule — show current daily / weekly auto-summary settings.\n"
        "/dailyat 21:00 — enable a daily Haiku summary at this time. "
        "Use to nudge yourself to reflect every evening.\n"
        "/dailyoff — disable the daily summary.\n"
        "/weeklyat sun 21:00 — enable a weekly Haiku summary on this "
        "day & time. Use for a Sunday-night week-in-review.\n"
        "/weeklyoff — disable the weekly summary.\n"
        "/checkins on|off — proactive nudges when mood, sleep or "
        "anxiety look unusual. Enable if you want the bot to reach "
        "out instead of waiting for your move.\n\n"
        "⚙️ Settings\n"
        "/tz <IANA> — set your timezone, e.g. /tz Europe/Berlin. "
        "Use once on first login; day boundaries depend on it.\n"
        "/lang <en|ru> — switch the bot's interface language.\n"
        "/cancel — abort the current guided step (any flow).\n"
        "/start, /help — show this list again."
    ),
}


RU: dict[str, str] = {
    "start.hi": "Привет, {name}! Всё готово.\n\n",
    "cancel.done": "Отменено.",
    "lang.help": "Используй /lang en или /lang ru, чтобы переключить язык бота.",
    "lang.unknown": "Неизвестный язык: {code}. Поддерживаются: en, ru.",
    "lang.set": "Язык бота — русский.",
    "err.send_text": "Пожалуйста, отправь текст.",
    "err.send_number": "Пожалуйста, отправь число (например, 7 или 7.5).",
    "err.short_text": "Пожалуйста, отправь короткий текст.",
    "log.pick_metric": "Что хочешь записать?",
    "log.enter_numeric": "{label} — выбери 1–10:",
    "log.enter_sleep_hours": "Сколько часов ты спала? (например, 7.5)",
    "log.enter_text": "Пришли текст для «{label}»:",
    "log.saved_numeric": "Записано: {label} = {value} за {date}.",
    "log.saved_text": "Записано: {label} за {date}.",
    "note.send": "Пришли заметку следующим сообщением.",
    "note.saved": "Заметка сохранена за {date}.",
    "thought.start": "Запись мысли (КПТ). Сначала опиши ситуацию:",
    "thought.ask_auto": "Какая автоматическая мысль появилась?",
    "thought.ask_distortion": (
        "Какое когнитивное искажение здесь подходит лучше всего?\n"
        "(катастрофизация / чёрно-белое мышление / чтение мыслей / персонализация / "
        "сверхобобщение / навешивание ярлыков / «долженствование» / предсказание / другое)"
    ),
    "thought.ask_reframe": "Теперь переформулируй. Какая мысль более сбалансирована?",
    "thought.saved": "Запись мысли сохранена за {date}. Хорошая работа.",
    "backfill.usage": (
        "Использование: /backfill <дата> <метрика> <значение>\n"
        "Примеры:\n"
        "  /backfill 2026-04-30 mood 6\n"
        "  /backfill yesterday sleep_hours 7.5\n"
        "  /backfill 3-days-ago note Было тревожно после звонка"
    ),
    "backfill.bad_date": "Не получилось распознать дату «{raw}»: {err}",
    "backfill.bad_metric": "Неизвестная метрика «{raw}». Попробуй: {choices}",
    "backfill.bad_value": "Не получилось распознать число «{raw}».",
    "backfill.need_text": "{label} требует текст после имени метрики.",
    "backfill.saved_numeric": "Внесено задним числом: {label} = {value} за {date}.",
    "backfill.saved_text": "Внесено задним числом: {label} за {date}.",
    "activate.start": "Что могло бы немного поднять настроение? Пришли одну короткую строку.",
    "activate.ask_when": "Когда?",
    "activate.ask_predicted": (
        "Запланировано на {date}. Насколько, по твоим ощущениям, "
        "это поднимет настроение? (1–10)"
    ),
    "activate.saved": (
        "План сохранён на {date} (прогноз +{predicted}). "
        "Используй /done после выполнения или /skip, если не получилось."
    ),
    "plans.empty": "Открытых планов нет. /activate — добавить.",
    "plans.header": "Открытые планы:",
    "plans.line": "• {weekday} {date} — {text}{suffix}",
    "plans.predicted_suffix": " (прогноз +{predicted})",
    "done.empty": "Открытых планов нет. /activate — добавить.",
    "done.pick": "Какой план ты выполнила?",
    "done.ask_actual": "Насколько это реально подняло настроение? (1–10)",
    "done.saved_with_pred": "Готово — прогноз +{predicted}, факт +{actual}. Умница.",
    "done.saved": "Готово — факт +{actual}. Умница.",
    "done.failed": "Не получилось отметить выполненным: {err}",
    "skip.empty": "Нет открытых планов, чтобы пропустить.",
    "skip.pick": "Какой план пропускаем?",
    "skip.ask_reason": "Причина одной строкой? (или /cancel, чтобы пропустить без причины)",
    "skip.saved": "Пропущено. Без осуждения — иногда сама попытка спланировать уже работа.",
    "skip.failed": "Не получилось пропустить: {err}",
    "today.empty": "Сегодня записей нет.",
    "today.header": "Сегодня:",
    "today.line_numeric": "• {label}: {value}",
    "today.line_text": "• {label}: {value}",
    "week.empty": "За последние 7 дней данных нет.",
    "week.header": "Последние 7 дней:",
    "tz.usage": "Использование: /tz <IANA timezone>, например /tz Europe/Berlin",
    "tz.unknown": "Неизвестная зона: {raw}. См. https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
    "tz.saved": "Часовой пояс установлен: {tz}.",
    "chart.pick_period": "Выбери период:",
    "chart.empty": "За этот период нет числовых данных.",
    "export.pick_period": "Выбери период:",
    "export.caption": "Отчёт {start} → {end}",
    "therapist.pick_period": "Выбери период для отчёта терапевту:",
    "therapist.caption": (
        "Отчёт терапевту {start} → {end}.\n"
        "Содержит записи мыслей, итоги активации и заметки — "
        "делись только с клиницистом."
    ),
    "ask.usage": "Спроси меня о твоих данных, например: /ask Как прошла неделя?",
    "ask.thinking": "Думаю…",
    "sched.show": (
        "Ежедневная сводка: {daily}\n"
        "Еженедельная сводка: {weekly}"
    ),
    "sched.daily.off": "выключена",
    "sched.daily.on": "включена в {time} ({tz})",
    "sched.weekly.off": "выключена",
    "sched.weekly.on": "включена в {dow} {time} ({tz})",
    "sched.dailyat.usage": "Использование: /dailyat HH:MM (24 часа)",
    "sched.dailyat.bad_time": "Неверное время «{raw}». Используй HH:MM, например 21:00.",
    "sched.dailyat.set": "Ежедневная сводка включена в {time} ({tz}).",
    "sched.dailyoff.set": "Ежедневная сводка выключена.",
    "sched.weeklyat.usage": "Использование: /weeklyat <mon|tue|wed|thu|fri|sat|sun> HH:MM",
    "sched.weeklyat.bad_dow": "Неизвестный день «{raw}». Используй mon..sun.",
    "sched.weeklyat.bad_time": "Неверное время «{raw}». Используй HH:MM.",
    "sched.weeklyat.set": "Еженедельная сводка включена в {dow} {time} ({tz}).",
    "sched.weeklyoff.set": "Еженедельная сводка выключена.",
    "checkins.show.on": (
        "Проверки на аномалии: ВКЛ. Я мягко напишу, если настроение, "
        "сон или тревога выглядят необычно. Выключить: /checkins off."
    ),
    "checkins.show.off": (
        "Проверки на аномалии: ВЫКЛ. Включить: /checkins on — "
        "я напишу, если что-то выглядит необычно."
    ),
    "checkins.set.on": (
        "Проверки на аномалии включены. Не чаще одного раза в сутки, "
        "только с 08:00 до 22:00 в твоём часовом поясе, и только если "
        "что-то выглядит необычно."
    ),
    "checkins.set.off": "Проверки на аномалии выключены.",
    "checkins.unknown": "Используй /checkins, /checkins on или /checkins off.",
    "checkin.low_mood_streak": (
        "Замечу аккуратно — настроение низкое уже {days} дня подряд "
        "({values}). Что-то происходит? Если мысль не отпускает, "
        "/thought поможет её разобрать; /activate — если хочется "
        "запланировать маленькое действие."
    ),
    "checkin.sleep_crash": (
        "Сон был коротким — {values} часов за последние {days} ночи. "
        "Если что-то мешает спать, /note это; /activate помогает "
        "выйти из цикла."
    ),
    "checkin.anxiety_spike": (
        "Сегодня тревога {value}. /thought поможет разобраться, что "
        "её запустило, либо /activate — чтобы заземлиться через "
        "маленькое конкретное действие."
    ),
    "help.text": (
        "Бот для самоотслеживания (КПТ) — записывай день, попроси Клода проанализировать.\n"
        "После каждой команды — *когда* её удобно использовать.\n\n"
        "📝 Записи\n"
        "/log — пошаговый выбор любой метрики. Когда хочешь записать "
        "что-то нечастое (симптомы, концентрация, раздражительность), "
        "не вспоминая конкретную команду.\n"
        "/mood /sleep /energy /hunger /anxiety /stress /pain "
        "/irritability /focus — быстрая шкала 1–10. Для мгновенных "
        "записей (например, внезапная волна тревоги).\n"
        "/sleephours — длительность сна в часах (например, 7.5). "
        "Сразу после пробуждения, чтобы записать сколько ты спала.\n"
        "/note <текст> — свободная заметка, шифруется. "
        "Когда что-то на уме, что не подходит ни под одну метрику.\n"
        "/thought — запись мысли по КПТ (ситуация → автоматическая "
        "мысль → искажение → переформулировка). Когда поймала сильную "
        "негативную мысль и хочешь её разобрать.\n"
        "/backfill <дата> <метрика> <значение> — запись задним числом. "
        "Если забыла записать вчера или хочешь добавить старую запись.\n\n"
        "🌱 Поведенческая активация\n"
        "/activate — запланировать маленькое действие и спрогнозировать "
        "его эффект. Когда настроение низкое и нужен конкретный шаг.\n"
        "/plans — открытые планы. Чтобы свериться с тем, что наметил.\n"
        "/done — отметить план выполненным и оценить реальный эффект. "
        "Сразу после выполнения — разрыв «прогноз vs факт» и есть "
        "терапевтический инсайт.\n"
        "/skip — пропустить план с опциональной причиной. Когда что-то "
        "помешало; без осуждения.\n\n"
        "📊 Обзор\n"
        "/today — записи за сегодня.\n"
        "/week — итоги последних 7 дней.\n"
        "/chart — выбрать период и увидеть график числовых метрик. "
        "Чтобы заметить тренды визуально.\n"
        "/export — многостраничный PDF-отчёт (только числа). "
        "Для личного снимка состояния или архива.\n"
        "/therapist — расширенный PDF: записи мыслей, итоги активации, "
        "заметки и тренды. Для отправки клиницисту — помечен "
        "конфиденциальным, делись только с теми, кому доверяешь.\n\n"
        "🤖 Клод\n"
        "/ask <вопрос> — спроси Клода о твоих данных "
        "(«что больше всего поднимает настроение?», «когда сон хуже всего?»). "
        "Для анализа, который встроенные команды не покрывают.\n\n"
        "⏰ Авто-сводки (в твоём часовом поясе)\n"
        "/schedule — текущие настройки ежедневной / еженедельной сводки.\n"
        "/dailyat 21:00 — включить ежедневную сводку в это время. "
        "Чтобы напоминать себе подвести итог дня.\n"
        "/dailyoff — выключить ежедневную сводку.\n"
        "/weeklyat sun 21:00 — включить еженедельную сводку в этот "
        "день и время. Например, для воскресного обзора недели.\n"
        "/weeklyoff — выключить еженедельную сводку.\n"
        "/checkins on|off — мягкие напоминания, когда настроение, сон "
        "или тревога выглядят необычно. Включи, если хочешь, чтобы "
        "бот сам обращался, а не ждал твоего хода.\n\n"
        "⚙️ Настройки\n"
        "/tz <IANA> — часовой пояс, например /tz Europe/Berlin. "
        "Один раз при первом входе; границы дня зависят от него.\n"
        "/lang <en|ru> — переключить язык интерфейса.\n"
        "/cancel — отменить текущий пошаговый ввод (в любом потоке).\n"
        "/start, /help — снова показать этот список."
    ),
}


# Russian translations of MetricType labels (METRIC_LABELS in domain).
# Defined here (not in domain) so the domain layer stays language-agnostic.
_METRIC_LABELS_RU: dict[str, str] = {
    "sleep_hours": "Длительность сна (часов)",
    "sleep_quality": "Качество сна (1–10)",
    "mood": "Настроение (1–10)",
    "energy": "Энергия (1–10)",
    "hunger": "Голод / аппетит (1–10)",
    "anxiety": "Тревога (1–10)",
    "stress": "Стресс (1–10)",
    "irritability": "Раздражительность (1–10)",
    "focus": "Концентрация (1–10)",
    "pain": "Боль (1–10)",
    "symptom": "Телесный симптом",
    "thought_record": "Запись мысли",
    "activity": "Активность",
    "activity_plan": "План активации",
    "substance": "Вещество / лекарство",
    "trigger": "Триггер",
    "coping": "Стратегия совладания",
    "note": "Заметка",
}


def metric_label(metric, lang: str) -> str:
    """Return the localized label for a `MetricType`.

    Imported lazily to avoid a domain ↔ bot import cycle.
    """
    from app.domain.enums import METRIC_LABELS, MetricType  # noqa: PLC0415
    if isinstance(metric, str):
        metric = MetricType(metric)
    if lang == "ru":
        return _METRIC_LABELS_RU.get(metric.value, METRIC_LABELS[metric])
    return METRIC_LABELS[metric]


def detect_language(language_code: str | None) -> str:
    """Pick a supported language from a Telegram `language_code`.

    Telegram sends BCP-47-ish tags ('en', 'en-US', 'ru', 'ru-RU').
    We only care about the primary subtag.
    """
    if not language_code:
        return "en"
    primary = language_code.split("-", 1)[0].lower()
    return "ru" if primary == "ru" else "en"


def t(lang: str, key: str, **fmt: object) -> str:
    """Look up `key` in the table for `lang`, falling back to EN, then to
    the key itself. Applies `str.format(**fmt)` on the result.
    """
    table = RU if lang == "ru" else EN
    raw = table.get(key) or EN.get(key) or key
    if fmt:
        try:
            return raw.format(**fmt)
        except (KeyError, IndexError):
            return raw
    return raw
