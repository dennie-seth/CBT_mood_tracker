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
        "Which thinking trap fits best? Tap one — or “Other” to write your own.\n\n"
        "• Catastrophising — expecting the worst\n"
        "• All-or-nothing — perfect or a total failure\n"
        "• Mind reading — “they think I'm…”\n"
        "• Fortune telling — “it will go badly”\n"
        "• Personalisation — “it's my fault”\n"
        "• Overgeneralisation — “this always happens”\n"
        "• Labelling — “I'm useless”\n"
        "• “Should” statements — rigid rules for yourself\n"
        "• Emotional reasoning — “I feel it, so it's true”\n"
        "• Discounting the positive — “that doesn't count”"
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
        "Planned for {date}. How much do you expect it to help your mood?\n"
        "1 = not at all, 10 = a lot.{hint}"
    ),
    "activate.saved": (
        "Plan saved for {date} (you expect it to help {predicted}/10). "
        "Use /done when finished, or /skip if not."
    ),
    "plans.empty": "No open plans. /activate to add one.",
    "plans.header": "Open plans:",
    "plans.line": "• {weekday} {date} — {text}{suffix}",
    "plans.predicted_suffix": " (expected {predicted}/10)",
    "done.empty": "No open plans. /activate to add one.",
    "done.pick": "Which one did you complete?",
    "done.ask_actual": "How much did it actually help your mood?\n1 = not at all, 10 = a lot.",
    "done.saved_with_pred": "Done — you expected {predicted}/10, it helped {actual}/10. Nice.",
    "done.saved": "Done — it helped {actual}/10. Nice.",
    "done.failed": "Couldn't mark done: {err}",
    "skip.empty": "No open plans to skip.",
    "skip.pick": "Which one are you skipping?",
    "skip.ask_reason": "One-line reason? (or send /cancel to skip without one)",
    "skip.saved": "Skipped. No judgement — sometimes the planning itself is the work.",
    # /migraine — attack card
    "migraines.header": "Migraines, {start} → {end}",
    "migraines.empty": "No migraine attacks logged between {start} and {end}.",
    "migraines.bad_period": "Use /migraines 7d, 30d, 90d or all.",
    "migraines.attacks": "Attacks: {n} · headache days: {days}",
    "migraines.open": " ({n} still open)",
    "migraines.duration": "Typical length: {avg} (longest {longest})",
    "migraines.peak": "Average worst: {avg}/10 (max {max}/10)",
    "migraines.aura": "Aura: in {n} of {total}",
    "migraines.symptoms": "Common symptoms: {items}",
    "migraines.triggers": "Possible triggers: {items}",
    "migraines.meds_header": "Medication:",
    "migraines.med_line": "• {name} — {n}×",
    "migraines.med_relief": " · helped {relief}/10 on average",
    "migraines.med_days": "Acute medication logged on {n} of the last 30 days.",
    "migraines.med_flag": (
        "Taking acute medication this often can itself make headaches more "
        "frequent — it's worth mentioning to your doctor."
    ),
    "migraine.label": "Migraine",
    "migraine.reminder": (
        "Checking in gently — is this attack still going? "
        "If it's over, tap “It's over”."
    ),
    "migraine.btn.mute": "🔕 Don't remind me",
    "migraine.ask_intensity": (
        "Sorry you're dealing with this. How strong is it right now? (1-10)\n"
        "It's saved as starting now — you can change the start time after."
    ),
    "migraine.ask_start": (
        "When did it start? Tap, or type a time: 14:30, yesterday 22:00, 06.10 18:30."
    ),
    "migraine.ask_end": (
        "When did it end? Tap, or type a time: 18:45, yesterday 23:10, 06.10 07:30."
    ),
    "migraine.bad_time": (
        "Couldn't read that. Try 14:30, yesterday 22:00 or 06.10 18:30 — "
        "or tap a button above."
    ),
    "migraine.ask_peak": "How bad is it at its worst so far? (1-10)",
    "migraine.ask_peak_end": "How bad did it get at its worst? (1-10)",
    "migraine.ask_aura": "Did you have an aura (visual or other warning signs)?",
    "migraine.ask_symptoms": "Anything else with it? Tap all that apply, then Done.",
    "migraine.ask_triggers": (
        "What might have played a part? Tap all that apply, or write your own. "
        "A guess is fine."
    ),
    "migraine.ask_trigger_text": "Write it in a few words:",
    "migraine.ask_med": "What did you take? Tap a recent one, or type what and how much.",
    "migraine.ask_end_med": (
        "Did you take anything for it? Tap a recent one, type what and how much, "
        "or tap “Didn't take anything”."
    ),
    "migraine.ask_relief": "How much did it help? (1 = not at all, 10 = completely)",
    "migraine.ask_delete": "Delete this attack? This can't be undone.",
    "migraine.deleted": "Deleted.",
    "migraine.saved_note": "✓ Saved",
    "migraine.stale_button": "That button is from an earlier step — use the latest message.",
    "migraine.sym.nausea": "Nausea",
    "migraine.sym.light": "Light sensitivity",
    "migraine.sym.sound": "Sound sensitivity",
    "migraine.sym.one_sided": "One-sided pain",
    "migraine.trg.sleep": "Poor sleep",
    "migraine.trg.stress": "Stress",
    "migraine.trg.skipped_meal": "Skipped meal",
    "migraine.trg.dehydration": "Not enough water",
    "migraine.trg.alcohol": "Alcohol",
    "migraine.trg.screens": "Screens",
    "migraine.trg.weather": "Weather",
    "migraine.trg.cycle": "Menstrual cycle",
    "migraine.card.title_open": "🤕 Migraine — ongoing",
    "migraine.card.title_ended": "Migraine — ended",
    "migraine.card.started_ago": "Started: {when} ({ago} ago)",
    "migraine.card.started": "Started: {when}",
    "migraine.card.ended": "Ended: {when} · lasted {duration}",
    "migraine.card.ended_unknown": "Ended: time not recorded",
    "migraine.card.intensity": "Intensity: {start}/10 at start · worst {peak}/10",
    "migraine.card.aura": "Aura: {value}",
    "migraine.card.symptoms": "Symptoms: {value}",
    "migraine.card.triggers": "Possible triggers: {value}",
    "migraine.card.medication": "Medication: {value}",
    "migraine.card.relief": " · helped {relief}/10",
    "migraine.card.none": "—",
    "migraine.card.yes": "yes",
    "migraine.card.no": "no",
    "migraine.card.stale": "⚠️ Open for {duration}. Did you forget to close it?",
    "migraine.card.closed_footer": "Rest well. You can still change anything below.",
    "migraine.when.yesterday": "yesterday {time}",
    "migraine.summary": "{span} ({duration}), peak {peak}",
    "migraine.summary_open": "since {start}, ongoing, peak so far {peak}",
    "migraine.summary_unknown_end": "from {start}, end not recorded, peak {peak}",
    "migraine.summary_med": "; {med}",
    "migraine.summary_relief": " → helped {relief}/10",
    "migraine.duration_min": "{m}m",
    "migraine.duration": "{h}h {m}m",
    "migraine.duration_days": "{d}d {h}h",
    "migraine.btn.start_time": "🕑 Start time",
    "migraine.btn.end_time": "🕑 End time",
    "migraine.btn.worse": "📈 It's worse",
    "migraine.btn.peak": "📈 Worst",
    "migraine.btn.aura": "Aura",
    "migraine.btn.symptoms": "Symptoms",
    "migraine.btn.medication": "💊 Medication",
    "migraine.btn.relief": "Did it help?",
    "migraine.btn.triggers": "Triggers",
    "migraine.btn.over": "✅ It's over",
    "migraine.btn.forgot_end": "Don't remember when it ended",
    "migraine.btn.delete": "🗑 Delete",
    "migraine.btn.delete_yes": "Yes, delete",
    "migraine.btn.back": "« Back",
    "migraine.btn.new": "➕ New attack",
    "migraine.btn.edit_last": "✏️ Edit last attack",
    "migraine.btn.now": "Now",
    "migraine.btn.ago": "{h}h ago",
    "migraine.btn.yes": "Yes",
    "migraine.btn.no": "No",
    "migraine.btn.done": "Done",
    "migraine.btn.no_med": "Didn't take anything",
    "migraine.btn.own_trigger": "✏️ Write my own",
    "migraine.btn.clear": "Clear",
    "migraine.err.not_found": "I can't find that attack any more — it may have been deleted.",
    "migraine.err.not_migraine": "That button doesn't belong to a migraine entry.",
    "migraine.err.already_ended": "That attack is already closed.",
    "migraine.err.not_ended": "That attack is still open — close it first.",
    "migraine.err.end_before_start": "The end can't be before the start. Try another time.",
    "migraine.err.in_future": "That time is in the future. Try another time.",
    "migraine.err.bad_scale": "Please pick a value from 1 to 10.",
    "migraine.err.unknown_symptom": "That option isn't available any more — please try again.",
    "migraine.err.unknown_trigger": "That option isn't available any more — please try again.",
    "migraine.err.relief_without_medication": (
        "Add the medication first, then rate how much it helped."
    ),
    "migraine.err.generic": "Something went wrong saving that. Please try again.",
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
    # Prediction calibration hints (/activate)
    "activate.hint_more_specific": (
        "\n\n💡 When you did this before ({n}×), it helped about {delta} points "
        "more than you expected."
    ),
    "activate.hint_more_overall": (
        "\n\n💡 So far, planned activities helped you about {delta} points more "
        "than you expected ({n} plans). Low mood tends to underestimate them."
    ),
    "activate.hint_less_specific": (
        "\n\n💡 When you did this before ({n}×), it helped about {delta} points "
        "less than you expected."
    ),
    "activate.hint_less_overall": (
        "\n\n💡 So far, planned activities helped about {delta} points less than "
        "you expected ({n} plans) — small, easy ones still count."
    ),
    # Distortion buttons
    "dist.catastrophising": "Catastrophising",
    "dist.all_or_nothing": "All-or-nothing",
    "dist.mind_reading": "Mind reading",
    "dist.fortune_telling": "Fortune telling",
    "dist.personalisation": "Personalisation",
    "dist.overgeneralisation": "Overgeneralisation",
    "dist.labelling": "Labelling",
    "dist.shoulds": "“Should” statements",
    "dist.emotional_reasoning": "Emotional reasoning",
    "dist.discounting_positive": "Discounting the positive",
    "dist.other": "✏️ Other — I'll write it",
    "thought.type_distortion": "Write it in your own words:",
    # /day card
    "day.q.mood": "How's your mood today?\n1 = very low, 10 = very good",
    "day.q.energy": "How much energy did you have today?\n1 = drained, 10 = full of energy",
    "day.q.anxiety": "How anxious did you feel today?\n1 = calm, 10 = very anxious",
    "day.q.sleep_quality": "How well did you sleep last night?\n1 = very poorly, 10 = very well",
    "day.btn.skip": "Skip",
    "day.done": "Day logged: {items}. Thank you for checking in.",
    "day.done_empty": "Nothing logged — that's okay.",
    "stale.button": "That button is from an earlier step — use the latest message.",
    # /recent
    "recent.header": "Recent entries — tap one to change or delete it:",
    "recent.empty": "Nothing logged in the last 30 days.",
    "recent.pick_value": "{label} — pick the corrected value:",
    "recent.ask_text": "Send the corrected text:",
    "recent.ask_delete": "Delete this entry? This can't be undone.",
    "recent.deleted": "Deleted.",
    "recent.saved": "✓ Saved",
    "recent.not_found": "I can't find that entry any more.",
    "recent.btn.value": "✏️ Change value",
    "recent.btn.text": "✏️ Edit text",
    "recent.btn.delete": "🗑 Delete",
    "recent.btn.delete_yes": "Yes, delete",
    "recent.btn.back": "« Back",
    "recent.btn.card": "🤕 Open attack card",
    "cmd.day": "Rate my day: mood, energy, anxiety, sleep",
    "cmd.recent": "Fix or delete recent entries",
    # /hide, /tidy, /pause
    "hide.confirm": (
        "This removes the last 48 hours of this chat from your screen "
        "(Telegram doesn't let bots delete older messages). Your saved entries "
        "stay — /today and /recent still show them."
    ),
    "hide.btn.yes": "🧹 Clear chat",
    "hide.btn.no": "Cancel",
    "hide.done": "Cleared. Your entries are still saved.",
    "hide.cancelled": "Okay, nothing removed.",
    "tidy.on": (
        "Auto-tidy is on: notes and thought records disappear from this chat "
        "5 minutes after saving. They stay saved. /tidy off to stop."
    ),
    "tidy.off": "Auto-tidy is off.",
    "tidy.status_on": "Auto-tidy is on. /tidy off to stop.",
    "tidy.status_off": (
        "Auto-tidy is off. /tidy on makes notes and thought records disappear "
        "from the chat 5 minutes after saving (they stay saved)."
    ),
    "pause.ask": (
        "Pause every message the bot sends on its own — summaries, check-ins, "
        "migraine reminders? Everything else keeps working."
    ),
    "pause.btn.1": "1 day",
    "pause.btn.3": "3 days",
    "pause.btn.7": "1 week",
    "pause.btn.resume": "▶ Resume now",
    "pause.set": "Paused until {until}. Take care of yourself.",
    "pause.resumed": "Resumed — the bot's own messages are back on.",
    "pause.status": "Paused until {until}.",
    "pause.bad_args": "Use /pause 1d … /pause 14d, or /pause off.",
    "cmd.hide": "Clear this chat (entries stay saved)",
    "cmd.pause": "Quiet mode: pause the bot's own messages",
    # Hard moments
    "support.header": "Things that helped you before:",
    "support.offer": "Want to slow down for a minute?",
    "support.btn.breathe": "🫁 Breathe with me",
    "support.btn.ground": "🖐 5-4-3-2-1 grounding",
    "breathe.choose": "Pick one — each takes about a minute.",
    "breathe.title": "🫁 Box breathing · round {round}/{total}",
    "breathe.in": "Breathe in through your nose… 4",
    "breathe.hold_in": "Hold gently… 4",
    "breathe.out": "Breathe out slowly… 4",
    "breathe.hold_out": "Rest… 4",
    "breathe.btn.stop": "■ Stop",
    "breathe.done": "Well done. Notice how your body feels now.",
    "breathe.stopped": "Stopped. Come back any time with /breathe.",
    "breathe.btn.log_anxiety": "😰 Log anxiety now",
    "ground.5": "👀 Look around and name 5 things you can see.",
    "ground.4": "✋ Notice 4 things you can touch or feel.",
    "ground.3": "👂 Listen for 3 things you can hear.",
    "ground.2": "👃 Notice 2 things you can smell.",
    "ground.1": "👅 Notice 1 thing you can taste.",
    "ground.btn.next": "Done ✓",
    "ground.done": "You're here, now. Take one slow breath.",
    "cmd.breathe": "Breathing or grounding exercise",
    # Command menu (Telegram "/" list)
    "cmd.mood": "Log mood 1-10",
    "cmd.anxiety": "Log anxiety 1-10",
    "cmd.migraine": "Migraine attack — start, update or close",
    "cmd.note": "Write a private note",
    "cmd.thought": "CBT thought record",
    "cmd.today": "What I've logged today",
    "cmd.week": "Last 7 days",
    "cmd.ask": "Ask Claude about my data",
    "cmd.log": "Log any metric",
    "cmd.activate": "Plan a small mood-lifting activity",
    "cmd.done": "Mark a planned activity done",
    "cmd.chart": "Chart my metrics",
    "cmd.migraines": "Migraine summary",
    "cmd.therapist": "PDF report for my therapist",
    "cmd.home": "Show or hide shortcut buttons",
    "cmd.lang": "Language: /lang en or /lang ru",
    "cmd.help": "All commands and when to use them",
    "cmd.cancel": "Cancel the current step",
    # Short metric names (buttons, one-line confirmations)
    "short.mood": "Mood",
    "short.energy": "Energy",
    "short.hunger": "Appetite",
    "short.anxiety": "Anxiety",
    "short.stress": "Stress",
    "short.irritability": "Irritability",
    "short.focus": "Focus",
    "short.pain": "Pain",
    "short.sleep_quality": "Sleep",
    "short.sleep_hours": "Slept (h)",
    # Home keyboard
    "home.note": "📝 Note",
    "home.migraine": "🤕 Migraine",
    "home.today": "📅 Today",
    "home.ask": "💬 Ask",
    "home.shown": "Shortcuts are below the text field. /home off hides them.",
    "home.hidden": "Shortcuts hidden. /home brings them back.",
    "home.ask_question": "What would you like to ask about your data?",
    # Plain text sent outside a command
    "plain.offer": "What should I do with this?",
    "plain.btn.note": "📝 Save as note",
    "plain.btn.thought": "🧠 Thought record",
    "plain.btn.ask": "💬 Ask Claude",
    "plain.btn.nothing": "✖ Nothing",
    "plain.dismissed": "Okay — not saved.",
    "plain.expired": "That text isn't available any more — please send it again.",
    # One-message logging + confirmation buttons
    "quick.saved": "Logged {items} for {date}.",
    "entry.btn.undo": "↩ Undo",
    "entry.btn.note": "📝 Add a note",
    "entry.btn.thought": "🧠 Thought record",
    "entry.undone": "Undone — removed.",
    "entry.undo_failed": "Couldn't undo — it may already be removed.",
    "entry.note_prompt": "What's behind it? Send a note.",
    # HELP_TEXT — assembled from a single block to keep formatting.
    "help.text": (
        "CBT tracker bot — log your day, ask Claude to analyse it.\n"
        "Each command below is followed by *when* to reach for it.\n\n"
        "📝 Logging\n"
        "Tip: just type “mood 6 anxiety 7 slept 6.5” to log several at once, "
        "or send any text and pick what to do with it.\n"
        "/home — shortcut buttons under the text field (your most-used "
        "metrics, note, migraine, today, ask). Use to log with one tap; "
        "/home off hides them.\n"
        "/day — rate your day in a few taps (mood, energy, anxiety, sleep). "
        "Use in the evening to check in without typing.\n"
        "/recent — your latest entries with fix / delete buttons. Use when "
        "you tapped the wrong number or want to correct a note.\n"
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
        "Use when you forgot to log yesterday or want to add an old entry.\n"
        "/migraine — one tap saves an attack; the card it shows has "
        "optional buttons for start time, aura, symptoms, medication, "
        "triggers and \"It's over\", and you can change any of them later. "
        "Use when an attack starts — or afterwards to log one that already "
        "passed (times like 'yesterday 22:00' work).\n"
        "/migraines [7d|30d|90d|all] — attacks, headache days, typical length, "
        "triggers and which medication helps. Use before a doctor's "
        "appointment or to see whether things are changing.\n\n"
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
        "🫁 Hard moments\n"
        "/breathe — box breathing or 5-4-3-2-1 grounding, all taps, no typing. "
        "Use when anxiety spikes or a migraine makes reading hard. After a very "
        "hard reading the bot also shows what helped you before.\n\n"
        "🔒 Privacy & quiet\n"
        "/hide — clear the last 48 hours of this chat from your screen; entries "
        "stay saved. Use when someone else might see your phone.\n"
        "/tidy on|off — notes and thought records disappear from the chat 5 "
        "minutes after saving. Use if you'd rather not leave them on screen.\n"
        "/pause [1d…14d|off] — quiet mode: no summaries, check-ins or reminders "
        "until it ends. Use on days when any notification is too much.\n\n"
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
        "Какая ловушка мышления подходит лучше? Нажми — или «Другое», чтобы написать своё.\n\n"
        "• Катастрофизация — ожидание худшего\n"
        "• Чёрно-белое мышление — либо идеально, либо провал\n"
        "• Чтение мыслей — «они думают, что я…»\n"
        "• Предсказание — «всё пойдёт плохо»\n"
        "• Персонализация — «это из-за меня»\n"
        "• Сверхобобщение — «так всегда»\n"
        "• Навешивание ярлыков — «я ни на что не гожусь»\n"
        "• «Долженствование» — жёсткие правила к себе\n"
        "• Эмоциональное обоснование — «чувствую, значит, правда»\n"
        "• Обесценивание хорошего — «это не считается»"
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
        "Запланировано на {date}. Насколько, по-твоему, это поможет настроению?\n"
        "1 — совсем нет, 10 — очень.{hint}"
    ),
    "activate.saved": (
        "План сохранён на {date} (ожидаешь, что поможет на {predicted}/10). "
        "Используй /done после выполнения или /skip, если не получилось."
    ),
    "plans.empty": "Открытых планов нет. /activate — добавить.",
    "plans.header": "Открытые планы:",
    "plans.line": "• {weekday} {date} — {text}{suffix}",
    "plans.predicted_suffix": " (ожидание {predicted}/10)",
    "done.empty": "Открытых планов нет. /activate — добавить.",
    "done.pick": "Какой план ты выполнила?",
    "done.ask_actual": "Насколько это на самом деле помогло настроению?\n1 — совсем нет, 10 — очень.",
    "done.saved_with_pred": "Готово — ожидала {predicted}/10, помогло на {actual}/10. Умница.",
    "done.saved": "Готово — помогло на {actual}/10. Умница.",
    "done.failed": "Не получилось отметить выполненным: {err}",
    "skip.empty": "Нет открытых планов, чтобы пропустить.",
    "skip.pick": "Какой план пропускаем?",
    "skip.ask_reason": "Причина одной строкой? (или /cancel, чтобы пропустить без причины)",
    "skip.saved": "Пропущено. Без осуждения — иногда сама попытка спланировать уже работа.",
    "migraines.header": "Мигрени, {start} → {end}",
    "migraines.empty": "Между {start} и {end} приступов мигрени не записано.",
    "migraines.bad_period": "Используй /migraines 7d, 30d, 90d или all.",
    "migraines.attacks": "Приступов: {n} · дней с головной болью: {days}",
    "migraines.open": " (ещё открыто: {n})",
    "migraines.duration": "Обычная длительность: {avg} (самый долгий {longest})",
    "migraines.peak": "Средний максимум: {avg}/10 (наибольший {max}/10)",
    "migraines.aura": "Аура: в {n} из {total}",
    "migraines.symptoms": "Частые симптомы: {items}",
    "migraines.triggers": "Возможные триггеры: {items}",
    "migraines.meds_header": "Лекарства:",
    "migraines.med_line": "• {name} — {n}×",
    "migraines.med_relief": " · в среднем помогло на {relief}/10",
    "migraines.med_days": "Обезболивающие записаны в {n} из последних 30 дней.",
    "migraines.med_flag": (
        "Если принимать обезболивающие так часто, головные боли сами могут "
        "становиться чаще — об этом стоит рассказать врачу."
    ),
    "migraine.label": "Мигрень",
    "migraine.reminder": (
        "Тихо напоминаю — приступ ещё идёт? "
        "Если прошёл, нажми «Прошёл»."
    ),
    "migraine.btn.mute": "🔕 Не напоминать",
    "migraine.ask_intensity": (
        "Сочувствую. Насколько сильно болит сейчас? (1–10)\n"
        "Начало запишется как «сейчас» — время можно поменять потом."
    ),
    "migraine.ask_start": (
        "Когда начался? Нажми кнопку или напиши время: 14:30, вчера 22:00, 06.10 18:30."
    ),
    "migraine.ask_end": (
        "Когда закончился? Нажми кнопку или напиши время: 18:45, вчера 23:10, 06.10 07:30."
    ),
    "migraine.bad_time": (
        "Не получилось разобрать. Попробуй 14:30, вчера 22:00 или 06.10 18:30 — "
        "или нажми кнопку выше."
    ),
    "migraine.ask_peak": "Насколько сильно сейчас в самый тяжёлый момент? (1–10)",
    "migraine.ask_peak_end": "Насколько сильно было в самый тяжёлый момент? (1–10)",
    "migraine.ask_aura": "Была аура (зрительные или другие предвестники)?",
    "migraine.ask_symptoms": "Что-то ещё сопровождает? Отметь всё подходящее и нажми «Готово».",
    "migraine.ask_triggers": (
        "Что могло повлиять? Отметь всё подходящее или напиши своё. "
        "Догадки — тоже нормально."
    ),
    "migraine.ask_trigger_text": "Напиши в паре слов:",
    "migraine.ask_med": "Что ты приняла? Выбери из недавних или напиши что и сколько.",
    "migraine.ask_end_med": (
        "Ты что-нибудь принимала? Выбери из недавних, напиши что и сколько "
        "или нажми «Ничего не принимала»."
    ),
    "migraine.ask_relief": "Насколько это помогло? (1 — совсем нет, 10 — полностью)",
    "migraine.ask_delete": "Удалить этот приступ? Отменить будет нельзя.",
    "migraine.deleted": "Удалено.",
    "migraine.saved_note": "✓ Сохранено",
    "migraine.stale_button": "Эта кнопка из прошлого шага — используй последнее сообщение.",
    "migraine.sym.nausea": "Тошнота",
    "migraine.sym.light": "Светобоязнь",
    "migraine.sym.sound": "Звукобоязнь",
    "migraine.sym.one_sided": "Боль с одной стороны",
    "migraine.trg.sleep": "Плохой сон",
    "migraine.trg.stress": "Стресс",
    "migraine.trg.skipped_meal": "Пропуск еды",
    "migraine.trg.dehydration": "Мало воды",
    "migraine.trg.alcohol": "Алкоголь",
    "migraine.trg.screens": "Экраны",
    "migraine.trg.weather": "Погода",
    "migraine.trg.cycle": "Менструальный цикл",
    "migraine.card.title_open": "🤕 Мигрень — идёт",
    "migraine.card.title_ended": "Мигрень — закончилась",
    "migraine.card.started_ago": "Начало: {when} ({ago} назад)",
    "migraine.card.started": "Начало: {when}",
    "migraine.card.ended": "Конец: {when} · длилась {duration}",
    "migraine.card.ended_unknown": "Конец: время не записано",
    "migraine.card.intensity": "Сила: {start}/10 в начале · максимум {peak}/10",
    "migraine.card.aura": "Аура: {value}",
    "migraine.card.symptoms": "Симптомы: {value}",
    "migraine.card.triggers": "Возможные триггеры: {value}",
    "migraine.card.medication": "Лекарство: {value}",
    "migraine.card.relief": " · помогло на {relief}/10",
    "migraine.card.none": "—",
    "migraine.card.yes": "да",
    "migraine.card.no": "нет",
    "migraine.card.stale": "⚠️ Открыт уже {duration}. Может, ты забыла его закрыть?",
    "migraine.card.closed_footer": "Отдыхай. Ниже можно поменять что угодно.",
    "migraine.when.yesterday": "вчера {time}",
    "migraine.summary": "{span} ({duration}), пик {peak}",
    "migraine.summary_open": "с {start}, идёт, пик пока {peak}",
    "migraine.summary_unknown_end": "с {start}, конец не записан, пик {peak}",
    "migraine.summary_med": "; {med}",
    "migraine.summary_relief": " → помогло на {relief}/10",
    "migraine.duration_min": "{m} мин",
    "migraine.duration": "{h} ч {m} мин",
    "migraine.duration_days": "{d} д {h} ч",
    "migraine.btn.start_time": "🕑 Начало",
    "migraine.btn.end_time": "🕑 Конец",
    "migraine.btn.worse": "📈 Стало хуже",
    "migraine.btn.peak": "📈 Максимум",
    "migraine.btn.aura": "Аура",
    "migraine.btn.symptoms": "Симптомы",
    "migraine.btn.medication": "💊 Лекарство",
    "migraine.btn.relief": "Помогло?",
    "migraine.btn.triggers": "Триггеры",
    "migraine.btn.over": "✅ Прошёл",
    "migraine.btn.forgot_end": "Не помню, когда закончился",
    "migraine.btn.delete": "🗑 Удалить",
    "migraine.btn.delete_yes": "Да, удалить",
    "migraine.btn.back": "« Назад",
    "migraine.btn.new": "➕ Новый приступ",
    "migraine.btn.edit_last": "✏️ Изменить последний приступ",
    "migraine.btn.now": "Сейчас",
    "migraine.btn.ago": "{h} ч назад",
    "migraine.btn.yes": "Да",
    "migraine.btn.no": "Нет",
    "migraine.btn.done": "Готово",
    "migraine.btn.no_med": "Ничего не принимала",
    "migraine.btn.own_trigger": "✏️ Написать своё",
    "migraine.btn.clear": "Очистить",
    "migraine.err.not_found": "Не могу найти этот приступ — возможно, он удалён.",
    "migraine.err.not_migraine": "Эта кнопка не относится к записи о мигрени.",
    "migraine.err.already_ended": "Этот приступ уже закрыт.",
    "migraine.err.not_ended": "Этот приступ ещё открыт — сначала закрой его.",
    "migraine.err.end_before_start": "Конец не может быть раньше начала. Попробуй другое время.",
    "migraine.err.in_future": "Это время ещё не наступило. Попробуй другое.",
    "migraine.err.bad_scale": "Выбери значение от 1 до 10.",
    "migraine.err.unknown_symptom": "Этот вариант больше недоступен — попробуй ещё раз.",
    "migraine.err.unknown_trigger": "Этот вариант больше недоступен — попробуй ещё раз.",
    "migraine.err.relief_without_medication": (
        "Сначала добавь лекарство, потом оцени, насколько помогло."
    ),
    "migraine.err.generic": "Что-то пошло не так при сохранении. Попробуй ещё раз.",
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
    "activate.hint_more_specific": (
        "\n\n💡 Когда ты делала это раньше ({n}×), это помогало примерно на {delta} "
        "больше, чем ты ожидала."
    ),
    "activate.hint_more_overall": (
        "\n\n💡 Пока что запланированные дела помогали тебе примерно на {delta} больше, "
        "чем ты ожидала ({n} планов). В плохом настроении их эффект часто недооценивают."
    ),
    "activate.hint_less_specific": (
        "\n\n💡 Когда ты делала это раньше ({n}×), это помогало примерно на {delta} "
        "меньше, чем ты ожидала."
    ),
    "activate.hint_less_overall": (
        "\n\n💡 Пока что запланированные дела помогали примерно на {delta} меньше, "
        "чем ты ожидала ({n} планов) — маленькие и лёгкие тоже считаются."
    ),
    "dist.catastrophising": "Катастрофизация",
    "dist.all_or_nothing": "Чёрно-белое мышление",
    "dist.mind_reading": "Чтение мыслей",
    "dist.fortune_telling": "Предсказание",
    "dist.personalisation": "Персонализация",
    "dist.overgeneralisation": "Сверхобобщение",
    "dist.labelling": "Навешивание ярлыков",
    "dist.shoulds": "«Долженствование»",
    "dist.emotional_reasoning": "Эмоциональное обоснование",
    "dist.discounting_positive": "Обесценивание хорошего",
    "dist.other": "✏️ Другое — напишу сама",
    "thought.type_distortion": "Напиши своими словами:",
    "day.q.mood": "Как настроение сегодня?\n1 — очень плохое, 10 — очень хорошее",
    "day.q.energy": "Сколько было энергии сегодня?\n1 — совсем без сил, 10 — полна сил",
    "day.q.anxiety": "Насколько тревожно было сегодня?\n1 — спокойно, 10 — очень тревожно",
    "day.q.sleep_quality": "Как ты спала этой ночью?\n1 — очень плохо, 10 — очень хорошо",
    "day.btn.skip": "Пропустить",
    "day.done": "День записан: {items}. Спасибо, что отметилась.",
    "day.done_empty": "Ничего не записано — это нормально.",
    "stale.button": "Эта кнопка из прошлого шага — используй последнее сообщение.",
    "recent.header": "Последние записи — нажми, чтобы изменить или удалить:",
    "recent.empty": "За последние 30 дней записей нет.",
    "recent.pick_value": "{label} — выбери исправленное значение:",
    "recent.ask_text": "Пришли исправленный текст:",
    "recent.ask_delete": "Удалить эту запись? Отменить будет нельзя.",
    "recent.deleted": "Удалено.",
    "recent.saved": "✓ Сохранено",
    "recent.not_found": "Не могу найти эту запись.",
    "recent.btn.value": "✏️ Изменить значение",
    "recent.btn.text": "✏️ Изменить текст",
    "recent.btn.delete": "🗑 Удалить",
    "recent.btn.delete_yes": "Да, удалить",
    "recent.btn.back": "« Назад",
    "recent.btn.card": "🤕 Открыть карточку приступа",
    "cmd.day": "Оценить день: настроение, энергия, тревога, сон",
    "cmd.recent": "Исправить или удалить недавние записи",
    "hide.confirm": (
        "Это уберёт с экрана последние 48 часов этого чата (более старые "
        "сообщения Telegram удалять ботам не даёт). Записи останутся — /today "
        "и /recent их покажут."
    ),
    "hide.btn.yes": "🧹 Очистить чат",
    "hide.btn.no": "Отмена",
    "hide.done": "Очищено. Записи сохранены.",
    "hide.cancelled": "Хорошо, ничего не удаляю.",
    "tidy.on": (
        "Автоочистка включена: заметки и записи мыслей исчезают из чата через "
        "5 минут после сохранения. Сами записи остаются. /tidy off — выключить."
    ),
    "tidy.off": "Автоочистка выключена.",
    "tidy.status_on": "Автоочистка включена. /tidy off — выключить.",
    "tidy.status_off": (
        "Автоочистка выключена. /tidy on — заметки и записи мыслей будут "
        "исчезать из чата через 5 минут после сохранения (сами записи остаются)."
    ),
    "pause.ask": (
        "Поставить на паузу всё, что бот присылает сам — сводки, проверки, "
        "напоминания о мигрени? Остальное продолжит работать."
    ),
    "pause.btn.1": "1 день",
    "pause.btn.3": "3 дня",
    "pause.btn.7": "1 неделю",
    "pause.btn.resume": "▶ Возобновить",
    "pause.set": "Пауза до {until}. Береги себя.",
    "pause.resumed": "Возобновлено — бот снова пишет сам.",
    "pause.status": "Пауза до {until}.",
    "pause.bad_args": "Используй /pause 1d … /pause 14d или /pause off.",
    "cmd.hide": "Очистить этот чат (записи сохранятся)",
    "cmd.pause": "Тихий режим: пауза для сообщений бота",
    "support.header": "Что помогало тебе раньше:",
    "support.offer": "Хочешь немного замедлиться?",
    "support.btn.breathe": "🫁 Подышать вместе",
    "support.btn.ground": "🖐 Заземление 5-4-3-2-1",
    "breathe.choose": "Выбери — каждое занимает около минуты.",
    "breathe.title": "🫁 Квадратное дыхание · круг {round}/{total}",
    "breathe.in": "Вдох через нос… 4",
    "breathe.hold_in": "Мягко задержи… 4",
    "breathe.out": "Медленный выдох… 4",
    "breathe.hold_out": "Пауза… 4",
    "breathe.btn.stop": "■ Стоп",
    "breathe.done": "Хорошо. Заметь, как сейчас чувствует себя тело.",
    "breathe.stopped": "Остановлено. Возвращайся в любой момент: /breathe.",
    "breathe.btn.log_anxiety": "😰 Записать тревогу",
    "ground.5": "👀 Оглянись и назови 5 вещей, которые видишь.",
    "ground.4": "✋ Заметь 4 вещи, которых можешь коснуться или почувствовать.",
    "ground.3": "👂 Прислушайся к 3 звукам.",
    "ground.2": "👃 Заметь 2 запаха.",
    "ground.1": "👅 Заметь 1 вкус.",
    "ground.btn.next": "Готово ✓",
    "ground.done": "Ты здесь и сейчас. Сделай один медленный вдох.",
    "cmd.breathe": "Дыхание или заземление",
    "cmd.mood": "Записать настроение 1–10",
    "cmd.anxiety": "Записать тревогу 1–10",
    "cmd.migraine": "Приступ мигрени — начать, дополнить, закрыть",
    "cmd.note": "Личная заметка",
    "cmd.thought": "Запись мысли (КПТ)",
    "cmd.today": "Что я записала сегодня",
    "cmd.week": "Последние 7 дней",
    "cmd.ask": "Спросить Клода о моих данных",
    "cmd.log": "Записать любую метрику",
    "cmd.activate": "Запланировать маленькое приятное дело",
    "cmd.done": "Отметить план выполненным",
    "cmd.chart": "График моих метрик",
    "cmd.migraines": "Сводка по мигреням",
    "cmd.therapist": "PDF-отчёт для терапевта",
    "cmd.home": "Показать или скрыть кнопки-ярлыки",
    "cmd.lang": "Язык: /lang en или /lang ru",
    "cmd.help": "Все команды и когда их использовать",
    "cmd.cancel": "Отменить текущий шаг",
    "short.mood": "Настроение",
    "short.energy": "Энергия",
    "short.hunger": "Аппетит",
    "short.anxiety": "Тревога",
    "short.stress": "Стресс",
    "short.irritability": "Раздражительность",
    "short.focus": "Концентрация",
    "short.pain": "Боль",
    "short.sleep_quality": "Сон",
    "short.sleep_hours": "Сон (ч)",
    "home.note": "📝 Заметка",
    "home.migraine": "🤕 Мигрень",
    "home.today": "📅 Сегодня",
    "home.ask": "💬 Спросить",
    "home.shown": "Ярлыки — под полем ввода. /home off их скрывает.",
    "home.hidden": "Ярлыки скрыты. /home вернёт их.",
    "home.ask_question": "Что ты хочешь узнать о своих данных?",
    "plain.offer": "Что с этим сделать?",
    "plain.btn.note": "📝 Сохранить заметку",
    "plain.btn.thought": "🧠 Запись мысли",
    "plain.btn.ask": "💬 Спросить Клода",
    "plain.btn.nothing": "✖ Ничего",
    "plain.dismissed": "Хорошо — не сохраняю.",
    "plain.expired": "Этот текст больше недоступен — пришли его ещё раз.",
    "quick.saved": "Записано: {items} за {date}.",
    "entry.btn.undo": "↩ Отменить",
    "entry.btn.note": "📝 Добавить заметку",
    "entry.btn.thought": "🧠 Запись мысли",
    "entry.undone": "Отменено — запись удалена.",
    "entry.undo_failed": "Не получилось отменить — возможно, запись уже удалена.",
    "entry.note_prompt": "Что за этим стоит? Пришли заметку.",
    "help.text": (
        "Бот для самоотслеживания (КПТ) — записывай день, попроси Клода проанализировать.\n"
        "После каждой команды — *когда* её удобно использовать.\n\n"
        "📝 Записи\n"
        "Подсказка: просто напиши «настроение 6 тревога 7 спала 6.5», чтобы "
        "записать сразу несколько, или пришли любой текст и выбери, что с ним сделать.\n"
        "/home — кнопки-ярлыки под полем ввода (частые метрики, заметка, "
        "мигрень, сегодня, вопрос). Чтобы записывать в одно касание; "
        "/home off их скрывает.\n"
        "/day — оценить день в несколько касаний (настроение, энергия, тревога, сон). "
        "Вечером, чтобы отметиться без набора текста.\n"
        "/recent — последние записи с кнопками исправить / удалить. Когда "
        "нажала не ту цифру или хочешь поправить заметку.\n"
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
        "Если забыла записать вчера или хочешь добавить старую запись.\n"
        "/migraine — одно нажатие сохраняет приступ; в карточке есть "
        "необязательные кнопки: начало, аура, симптомы, лекарство, "
        "триггеры и «Прошёл», и всё можно поменять позже. Когда приступ "
        "начался — или уже после, чтобы записать прошедший (подойдёт "
        "время вроде «вчера 22:00»).\n"
        "/migraines [7d|30d|90d|all] — приступы, дни с болью, обычная "
        "длительность, триггеры и какое лекарство помогает. Перед визитом "
        "к врачу или чтобы увидеть, меняется ли что-то.\n\n"
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
        "🫁 Трудные моменты\n"
        "/breathe — квадратное дыхание или заземление 5-4-3-2-1, только касания. "
        "Когда накрывает тревога или из-за мигрени трудно читать. После очень "
        "тяжёлой оценки бот также покажет, что помогало тебе раньше.\n\n"
        "🔒 Приватность и тишина\n"
        "/hide — убрать с экрана последние 48 часов чата; записи сохранятся. "
        "Когда кто-то может увидеть твой телефон.\n"
        "/tidy on|off — заметки и записи мыслей исчезают из чата через 5 минут "
        "после сохранения. Если не хочешь оставлять их на экране.\n"
        "/pause [1d…14d|off] — тихий режим: без сводок, проверок и напоминаний, "
        "пока не закончится. В дни, когда любое уведомление — слишком.\n\n"
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
    "migraine": "Мигрень, пик (1–10)",
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
