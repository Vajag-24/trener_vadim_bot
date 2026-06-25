"""
ТРЕНЕР-БОТ "Режим поддержки трусов" v1.5
Калистеника-стрик: стамина (анти-перетрен), три режима дня,
колода под снаряд, submax + авто-прогрессия, боссы, ранги,
never-miss-twice, экспорт CSV.

ENV: BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY
Деплой: Railway
"""

import os, io, csv, random, asyncio, logging
from datetime import date, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, BufferedInputFile
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)

BOT_TOKEN    = os.environ["BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────────
# КОНФИГ
# ─────────────────────────────────────────────
STAMINA_MAX      = 5
SUBMAX_RATIO     = 0.55
EASY_TO_LEVEL    = 2
LEGS_FORCE_DAYS  = 3   # дней без ног → принудительная масть

# Планы по времени: sets, rest_sec, allow_heavy, label
TIME_PLANS = {
    10: (3,  45,  False, "⚡ 10 мин · 3 подх · отдых 45 сек"),
    20: (5,  90,  True,  "🕐 20 мин · 5 подх · отдых 90 сек"),
    30: (6,  150, True,  "🕕 30 мин · 6 подх · отдых 2.5 мин"),
}
DEFAULT_MINUTES = 20

def resolve_plan(minutes: int) -> dict:
    keys = sorted(TIME_PLANS)
    chosen = keys[0]
    for k in keys:
        if minutes >= k:
            chosen = k
    sets, rest, allow_heavy, label = TIME_PLANS[chosen]
    return {"minutes": chosen, "sets": sets, "rest": rest,
            "allow_heavy": allow_heavy, "label": label}

GEAR_NAMES = {
    "floor": "Пол",
    "bar":   "Турник",
    "dips":  "Брусья",
    "db":    "Гантеля 8кг",
    "band":  "Резина",
    "rope":  "Скакалка",
    "run":   "Бег",
}
DEFAULT_GEAR = "floor,bar,dips,db"

# (ключ, название, единица, масть, снаряд, описание как делать)
EXERCISES = [
    ("pullups",   "Подтягивания",               "повт", "Тяга",   "bar",
     "Вис прямым хватом, тяни себя вверх до подбородка над перекладиной, опускайся полностью."),
    ("chinups",   "Подтягивания обратным",       "повт", "Тяга",   "bar",
     "Ладони к себе, хват уже плеч. То же движение — больше работает бицепс."),
    ("rows",      "Австралийские",               "повт", "Тяга",   "bar",
     "Повисни под низкой перекладиной, тело прямое под углом, пятки на полу. Тяни грудь к перекладине."),
    ("db_row",    "Тяга гантели в наклоне",      "повт", "Тяга",   "db",
     "Наклонись, обопрись свободной рукой о колено. Тяни гантель к поясу, локоть вдоль тела."),
    ("face_pull", "Лицевые тяги",                "повт", "Тяга",   "band",
     "Резину закрепи на уровне лица. Тяни к лицу, разводя локти в стороны и сводя лопатки."),
    ("dips",      "Брусья",                      "повт", "Жим",    "dips",
     "Упор на брусьях, опускайся до ~90° в локтях, выжимай обратно. Наклон вперёд = грудь, вертикально = трицепс."),
    ("pushups",   "Отжимания",                   "повт", "Жим",    "floor",
     "Упор лёжа, тело прямое. Опускайся грудью к полу, локти ~45° к корпусу."),
    ("pike",      "Пайк-отжимания",              "повт", "Жим",    "floor",
     "Поза домик: таз вверх, руки и ноги на полу. Опускай макушку к полу — жим под плечи."),
    ("diamond",   "Алмазные отжимания",          "повт", "Жим",    "floor",
     "Ладони ромбом под грудью. Те же отжимания — акцент на трицепс."),
    ("db_press",  "Жим гантели над головой",     "повт", "Жим",    "db",
     "Стоя, гантель у плеча. Выжимай прямо вверх над головой. По очереди на каждую руку."),
    ("squats",    "Приседания",                  "повт", "Ноги",   "floor",
     "Ноги на ширине плеч. Садись, отводя таз назад, до бедра параллельно полу."),
    ("lunges",    "Выпады",                      "повт", "Ноги",   "floor",
     "Шаг вперёд, опускай заднее колено к полу, толкайся передней ногой обратно. Считай на каждую ногу."),
    ("pistol",    "Пистолетик",                  "повт", "Ноги",   "floor",
     "Присед на одной ноге, вторая вытянута вперёд. До низа и встать. Держись за опору на старте."),
    ("calf",      "Подъёмы на носки",            "повт", "Ноги",   "floor",
     "Встань на носки максимально высоко, медленно опусти пятки. Лучше на краю ступеньки."),
    ("goblet",    "Гоблет-присед",               "повт", "Ноги",   "db",
     "Держи гантель у груди двумя руками. Приседай глубоко, локти между коленей."),
    ("db_lunge",  "Выпады с гантелей",           "повт", "Ноги",   "db",
     "Обычный выпад, но с гантелей в руке. На каждую ногу."),
    ("leg_raise", "Подъёмы ног в висе",          "повт", "Кор",    "bar",
     "Вис на турнике. Поднимай прямые ноги до 90°, без раскачки. Опускай медленно."),
    ("knee_raise","Подъёмы коленей в висе",      "повт", "Кор",    "bar",
     "Вис на турнике, подтягивай согнутые колени к груди. Легче чем прямые ноги."),
    ("lsit",      "L-sit",                       "сек",  "Кор",    "floor",
     "Упор руками, подними прямые ноги в угол Г и держи. Считай секунды удержания."),
    ("plank",     "Планка",                      "сек",  "Кор",    "floor",
     "Упор на предплечьях, тело прямое от пяток до головы. Не проваливай таз."),
    ("hollow",    "Hollow hold",                 "сек",  "Кор",    "floor",
     "Лёжа на спине, прижми поясницу к полу. Оторви ноги и плечи — поза лодочки. Держи."),
    ("burpees",   "Бёрпи",                       "повт", "Кардио", "floor",
     "Присед → упор лёжа → отжимание → подпрыгни вверх. Полный цикл = 1 повтор."),
    ("climbers",  "Альпинист",                   "повт", "Кардио", "floor",
     "Упор лёжа, быстро подтягивай колени к груди поочерёдно — бег на месте в планке."),
    ("jumpsquat", "Прыжковые приседания",        "повт", "Кардио", "floor",
     "Присел → выпрыгнул вверх → мягко приземлился сразу в присед."),
    ("jacks",     "Джампинг-джеки",              "повт", "Кардио", "floor",
     "Прыжком: ноги в стороны + руки над головой, прыжком обратно. Ритмично."),
    ("hang",      "Вис на турнике",              "сек",  "Кардио", "bar",
     "Просто виси расслабленно. Растягивает плечи, декомпрессия позвоночника. Считай время."),
    ("mobility",  "Суставная разминка",          "сек",  "Кардио", "floor",
     "Круговые движения всех суставов сверху вниз: шея, плечи, таз, колени. Время в движении."),
    ("rope",      "Скакалка",                    "сек",  "Кардио", "rope",
     "Прыжки через скакалку. Считай время."),
    ("run",       "Бег",                         "сек",  "Кардио", "run",
     "Бег в комфортном темпе. Считай время."),
]

INFO = {k: {"name": n, "unit": u, "suit": s, "gear": g, "desc": d}
        for k, n, u, s, g, d in EXERCISES}

RANKS = ["🩲 Трусы", "🩳 Боксёры", "🩱 Шорты", "🤸 Трико", "🦸 Плащ"]
RANK_TH = [0, 50, 150, 350, 700]

BOSSES = [
    ("pullups", 12, "повт", "12 строгих подтягиваний"),
    ("dips",    20, "повт", "20 брусьев"),
    ("pistol",   1, "повт", "Пистолет на каждую ногу"),
    ("plank",   90, "сек",  "Планка 90 секунд"),
    ("pushups", 40, "повт", "40 отжиманий подряд"),
]

# Восстановительные упражнения (для режима 🪫)
RECOVERY_EX = {"hang", "mobility", "jacks", "climbers"}

# ─────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────

def get_player(uid: int) -> dict:
    r = sb.table("players").select("*").eq("user_id", uid).execute()
    if r.data:
        return r.data[0]
    sb.table("players").insert({"user_id": uid}).execute()
    return sb.table("players").select("*").eq("user_id", uid).execute().data[0]

def upd(uid: int, **f):
    sb.table("players").update(f).eq("user_id", uid).execute()

def get_pr(uid: int, pattern: str) -> dict:
    r = sb.table("prs").select("*").eq("user_id", uid).eq("pattern", pattern).execute()
    if r.data:
        return r.data[0]
    row = {"user_id": uid, "pattern": pattern, "pr": 0, "easy_run": 0}
    sb.table("prs").insert(row).execute()
    return row

def set_pr(uid: int, pattern: str, **f):
    sb.table("prs").update(f).eq("user_id", uid).eq("pattern", pattern).execute()

def add_xp(uid: int, amount: int):
    p = get_player(uid)
    nx = p["xp"] + amount
    upd(uid, xp=nx, rank_idx=rank_for_xp(nx))

# ─────────────────────────────────────────────
# ЛОГИКА
# ─────────────────────────────────────────────

def gear_set(p: dict) -> set:
    return set((p.get("equipment") or DEFAULT_GEAR).split(","))

def available_deck(gear: set, only_recovery: bool = False) -> dict:
    deck = {}
    for k, n, u, s, g, d in EXERCISES:
        if g not in gear:
            continue
        if only_recovery and k not in RECOVERY_EX:
            continue
        deck.setdefault(s, []).append((k, n, u))
    return deck

def submax(pr: int) -> int:
    return max(1, round(pr * SUBMAX_RATIO))

def rank_for_xp(xp: int) -> int:
    idx = 0
    for i, t in enumerate(RANK_TH):
        if xp >= t:
            idx = i
    return idx

def regen_stamina(p: dict) -> dict:
    last = date.fromisoformat(str(p["stamina_date"]))
    days = (date.today() - last).days
    if days > 0:
        ns = min(STAMINA_MAX, p["stamina"] + days)
        upd(p["user_id"], stamina=ns, stamina_date=date.today().isoformat())
        p["stamina"] = ns
    return p

def check_streak(p: dict) -> dict:
    if p["last_active"]:
        last = date.fromisoformat(str(p["last_active"]))
        gap = (date.today() - last).days
        if gap >= 2 and p["streak"] > 0:
            upd(p["user_id"], streak=0)
            p["streak"] = 0
    return p

def days_since_legs(uid: int) -> int:
    """Сколько дней прошло с последней тренировки с мастью Ноги."""
    r = sb.table("logs").select("ts").eq("user_id", uid)\
        .in_("pattern", ["squats","lunges","pistol","calf","goblet","db_lunge"])\
        .order("ts", desc=True).limit(1).execute()
    if not r.data:
        return 999
    last = date.fromisoformat(r.data[0]["ts"][:10])
    return (date.today() - last).days

def bar(cur: int, total: int, w: int = 10) -> str:
    filled = min(w, round(w * cur / total)) if total else 0
    return "▰" * filled + "▱" * (w - filled)

def return_message(gap: int) -> str:
    if gap < 14:
        return ""
    return (
        f"\n\n📅 Ты вернулся после {gap} дней.\n"
        "Сегодня одно упражнение, три подхода. Просто вспомни движение.\n"
        "Твои PR на месте — никуда не делись."
    )

# ─────────────────────────────────────────────
# БОТ
# ─────────────────────────────────────────────

dp  = Dispatcher()
bot = Bot(BOT_TOKEN)


@dp.message(Command("start"))
async def cmd_start(m: Message):
    get_player(m.from_user.id)
    await m.answer(
        "🩲 *Режим поддержки трусов*\n\n"
        "Калистеника без зала. Меньше, но постоянно.\n\n"
        "*Команды:*\n"
        "/day `[минуты]` — карта дня (10 / 20 / 30)\n"
        "/mood `high|normal|low` — режим дня\n"
        "/log `<упр> <число> [easy|hard]` — записать подход\n"
        "/done — закрыть сессию\n"
        "/skip — выходной (стрик цел)\n"
        "/stats — рекорды и прогресс\n"
        "/boss — боссы-вехи\n"
        "/history — календарь тренировок\n"
        "/gear — снаряжение · /unlock `<ключ>`\n"
        "/export — скачать CSV всех данных",
        parse_mode="Markdown")


@dp.message(Command("day"))
async def cmd_day(m: Message, command: CommandObject):
    uid = m.from_user.id
    p   = regen_stamina(check_streak(get_player(uid)))

    # парсим минуты из аргумента: /day 10 | /day 30 | /day
    raw_mins = (command.args or "").strip()
    try:
        minutes = max(5, min(60, int(raw_mins)))
    except ValueError:
        minutes = DEFAULT_MINUTES

    plan = resolve_plan(minutes)

    # сообщение о возврате после долгой паузы
    gap = 0
    if p["last_active"]:
        gap = (date.today() - date.fromisoformat(str(p["last_active"]))).days

    if p["stamina"] <= 0:
        await m.answer(
            "🪫 Стамина 0.\n\n"
            "Сегодня *отдых* — это часть плана.\n"
            "Реген +1/день. Завтра продолжим.",
            parse_mode="Markdown")
        return

    # если мало времени и тяжёлый тип недоступен — только submax/объём
    energy       = p.get("energy_today") or "normal"
    only_recovery = (energy == "low")

    gear = gear_set(p)
    deck = available_deck(gear, only_recovery=only_recovery)

    # правило ног
    force_legs = days_since_legs(uid) >= LEGS_FORCE_DAYS
    if force_legs and "Ноги" in deck:
        suit = "Ноги"
    else:
        suits = [s for s in deck if s != p.get("last_suit")] or list(deck)
        suit  = random.choice(suits)

    ex_key, ex_name, ex_unit = random.choice(deck[suit])
    ex_desc = INFO[ex_key]["desc"]
    upd(uid, last_suit=suit)

    pr = get_pr(uid, ex_key)
    if pr["pr"] == 0:
        goal_line = "Сделай чистый *максимум* — станет твоим PR."
        hint_line = f"`/log {ex_key} <число>`"
    else:
        t = submax(pr["pr"])
        goal_line = f"Цель: *{t} {ex_unit}* (~55% от PR, не до отказа)"
        hint_line = (
            f"{plan['sets']} подходов по {t}, отдых {plan['rest']} сек.\n"
            f"Закрыл легко — добавь `easy`:\n"
            f"`/log {ex_key} {t} easy`"
        )

    # предупреждение если времени мало но хочется тяжёлого
    heavy_warn = ""
    if not plan["allow_heavy"] and energy == "high":
        heavy_warn = "\n⚠️ _10 мин = только submax, без тяжёлого_"

    force_note   = "\n⚠️ _Ноги давно не работали — принудительная масть_" if force_legs else ""
    energy_note  = "\n🪫 _Режим восстановления — только лёгкое_"           if only_recovery else ""
    ret          = return_message(gap)

    await m.answer(
        f"{plan['label']}{heavy_warn}\n\n"
        f"🎴 *{suit}*{force_note}{energy_note}\n\n"
        f"*{ex_name}*\n"
        f"_{ex_desc}_\n\n"
        f"{goal_line}\n\n"
        f"{hint_line}\n\n"
        f"🔋 {p['stamina']}/{STAMINA_MAX} · 🔥 {p['streak']} дней{ret}\n\n"
        f"━━━━━━━━━━\n"
        f"Записал подходы? → /done",
        parse_mode="Markdown")


@dp.message(Command("mood"))
async def cmd_mood(m: Message, command: CommandObject):
    """Установить режим дня: /mood high | normal | low"""
    uid = m.from_user.id
    val = (command.args or "").strip().lower()
    mapping = {"high": "high", "normal": "normal", "low": "low",
               "в ударе": "high", "норм": "normal", "устал": "low"}
    if val not in mapping:
        await m.answer(
            "Укажи состояние:\n"
            "`/mood high` — ⚡ В ударе\n"
            "`/mood normal` — 😐 Норм\n"
            "`/mood low` — 🪫 Еле живой",
            parse_mode="Markdown")
        return
    energy = mapping[val]
    upd(uid, energy_today=energy)
    labels = {"high": "⚡ В ударе — полная программа", "normal": "😐 Норм — стандартный режим",
              "low":  "🪫 Еле живой — только восстановление"}
    await m.answer(f"Записал: {labels[energy]}\nТеперь жми /day")


@dp.message(Command("log"))
async def cmd_log(m: Message, command: CommandObject):
    uid  = m.from_user.id
    args = (command.args or "").split()
    if len(args) < 2:
        await m.answer("Формат: `/log <упр> <число> [easy|hard]`\nПример: `/log pullups 6 easy`",
                       parse_mode="Markdown")
        return

    key = args[0].lower()
    if key not in INFO:
        keys = ", ".join(f"`{k}`" for k in INFO)
        await m.answer(f"Не знаю упражнение `{key}`.\nДоступно:\n{keys}", parse_mode="Markdown")
        return
    try:
        reps = int(args[1])
    except ValueError:
        await m.answer("Число должно быть целым.")
        return
    effort = args[2].lower() if len(args) > 2 and args[2].lower() in ("easy", "hard") else "normal"

    name = INFO[key]["name"]
    unit = INFO[key]["unit"]
    sb.table("logs").insert({"user_id": uid, "pattern": key, "reps": reps, "effort": effort}).execute()

    pr  = get_pr(uid, key)
    msg = [f"✅ {name}: {reps} {unit} ({effort})"]

    if reps > pr["pr"]:
        set_pr(uid, key, pr=reps, easy_run=0)
        add_xp(uid, 15)
        msg.append(f"🏆 Новый PR: {reps} {unit}! (+15 xp)")
    elif effort == "easy" and reps >= submax(pr["pr"]):
        run = pr["easy_run"] + 1
        if run >= EASY_TO_LEVEL:
            set_pr(uid, key, pr=pr["pr"] + 1, easy_run=0)
            msg.append(f"📈 Прогрессия! {pr['pr']} → {pr['pr']+1} {unit}")
        else:
            set_pr(uid, key, easy_run=run)
            msg.append(f"⚡ Лёгкий {run}/{EASY_TO_LEVEL} до прогрессии")
    elif effort == "hard":
        set_pr(uid, key, easy_run=0)

    msg.append("\nГотов? → /done")
    await m.answer("\n".join(msg))


@dp.message(Command("done"))
async def cmd_done(m: Message):
    uid   = m.from_user.id
    p     = regen_stamina(check_streak(get_player(uid)))
    today = date.today().isoformat()

    if p["stamina"] <= 0:
        await m.answer("🪫 Стамина 0 — сессия не засчитана. Отдыхай.")
        return

    logs = sb.table("logs").select("id,effort").eq("user_id", uid)\
        .gte("ts", today).execute().data
    if not logs:
        await m.answer("Сначала запиши хотя бы один подход → /log")
        return

    hard = any(l["effort"] == "hard" for l in logs) or len(logs) >= 6
    cost = min(2 if hard else 1, p["stamina"])
    ns   = p["stamina"] - cost

    streak  = p["streak"] if str(p["last_active"]) == today else p["streak"] + 1
    xp_gain = 10 if hard else 5
    new_xp  = p["xp"] + xp_gain
    best    = max(p["best_streak"], streak)
    new_ri  = rank_for_xp(new_xp)

    upd(uid, stamina=ns, streak=streak, best_streak=best,
        xp=new_xp, rank_idx=new_ri, last_active=today,
        total_days=p.get("total_days", 0) + (0 if str(p["last_active"]) == today else 1),
        energy_today=None)

    out = [
        f"💪 {'Тяжёлая' if hard else 'Лёгкая'} сессия закрыта",
        f"−{cost} стамины · +{xp_gain} xp",
        f"🔥 Стрик: {streak} · 🔋 {ns}/{STAMINA_MAX}",
    ]
    if new_ri > p["rank_idx"]:
        out.append(f"\n🎖 Новый ранг: *{RANKS[new_ri]}*!")
    if ns == 0:
        out.append("\nСтамина в нуле — реген +1/день.")
    await m.answer("\n".join(out), parse_mode="Markdown")


@dp.message(Command("skip"))
async def cmd_skip(m: Message):
    uid = m.from_user.id
    p   = get_player(uid)
    upd(uid, last_active=date.today().isoformat(), energy_today=None)
    await m.answer(
        f"🛌 Выходной засчитан. Стрик цел ({p['streak']} дней).\n"
        "Один пропуск — норма. Завтра продолжаем.")


@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    uid   = m.from_user.id
    p     = regen_stamina(check_streak(get_player(uid)))
    prs   = sb.table("prs").select("*").eq("user_id", uid).execute().data
    total = sb.table("logs").select("id", count="exact").eq("user_id", uid).execute()

    lines = [
        f"*{RANKS[p['rank_idx']]}* · {p['xp']} xp",
        f"🔥 Стрик: {p['streak']} (рекорд {p['best_streak']})",
        f"📅 Всего дней: {p.get('total_days', 0)}",
        f"📒 Всего подходов: {total.count or 0}",
        f"🔋 Стамина: {p['stamina']}/{STAMINA_MAX}",
        "",
        "*Рекорды (PR → submax):*",
    ]
    found = False
    for r in sorted(prs, key=lambda x: -x["pr"]):
        if r["pr"] > 0:
            i = INFO.get(r["pattern"])
            nm = i["name"] if i else r["pattern"]
            ut = i["unit"] if i else ""
            lines.append(f"  {nm}: {r['pr']} {ut} → цель {submax(r['pr'])}")
            found = True
    if not found:
        lines.append("  Пока пусто — сделай /day.")
    await m.answer("\n".join(lines), parse_mode="Markdown")


@dp.message(Command("boss"))
async def cmd_boss(m: Message):
    uid  = m.from_user.id
    prs  = {r["pattern"]: r["pr"]
            for r in sb.table("prs").select("*").eq("user_id", uid).execute().data}
    lines = ["👹 *Боссы*\n"]
    for key, thr, unit, title in BOSSES:
        cur  = prs.get(key, 0)
        done = cur >= thr
        b    = bar(cur, thr)
        mark = "✅" if done else f"{cur}/{thr} {unit}"
        lines.append(f"{'☠️' if done else '⚔️'} {title}\n   {b} {mark}")
    await m.answer("\n".join(lines), parse_mode="Markdown")


@dp.message(Command("history"))
async def cmd_history(m: Message):
    uid  = m.from_user.id
    logs = sb.table("logs").select("ts").eq("user_id", uid)\
        .order("ts", desc=False).execute().data
    if not logs:
        await m.answer("Пока нет тренировок.")
        return

    days = sorted(set(l["ts"][:10] for l in logs))
    day_set = set(days)

    # последние 5 недель
    today = date.today()
    start = today - timedelta(weeks=5)
    lines = ["📅 *Последние 5 недель*\n"]
    week_days = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    cur = start - timedelta(days=start.weekday())
    while cur <= today:
        week = ""
        for i in range(7):
            d = cur + timedelta(days=i)
            if d > today:
                week += "░"
            elif d.isoformat() in day_set:
                week += "▓"
            else:
                week += "·"
        lines.append(f"`{cur.strftime('%d.%m')}` {week}")
        cur += timedelta(weeks=1)

    lines.append(f"\nВсего тренировочных дней: *{len(days)}*")
    lines.append(f"Первая: {days[0]} · Последняя: {days[-1]}")
    await m.answer("\n".join(lines), parse_mode="Markdown")


@dp.message(Command("gear"))
async def cmd_gear(m: Message):
    uid  = m.from_user.id
    have = gear_set(get_player(uid))
    lines = ["🎒 *Снаряжение*\n"]
    for key, nm in GEAR_NAMES.items():
        n    = sum(1 for e in EXERCISES if e[4] == key)
        mark = "✅" if key in have else "🔒"
        lines.append(f"{mark} {nm} (`{key}`) — {n} упр.")
    lines.append("\n`/unlock <ключ>` — открыть · `/lock <ключ>` — убрать")
    await m.answer("\n".join(lines), parse_mode="Markdown")


@dp.message(Command("unlock"))
async def cmd_unlock(m: Message, command: CommandObject):
    uid = m.from_user.id
    key = (command.args or "").strip().lower()
    if key not in GEAR_NAMES:
        await m.answer(f"Ключи снарядов: {', '.join(f'`{k}`' for k in GEAR_NAMES)}",
                       parse_mode="Markdown")
        return
    have = gear_set(get_player(uid))
    have.add(key)
    upd(uid, equipment=",".join(sorted(have)))
    new = [e[1] for e in EXERCISES if e[4] == key]
    await m.answer(
        f"🔓 *{GEAR_NAMES[key]}* открыт. Колода +{len(new)}:\n" +
        "\n".join(f"  • {n}" for n in new),
        parse_mode="Markdown")


@dp.message(Command("lock"))
async def cmd_lock(m: Message, command: CommandObject):
    uid  = m.from_user.id
    key  = (command.args or "").strip().lower()
    have = gear_set(get_player(uid))
    have.discard(key)
    if not have:
        have = {"floor"}
    upd(uid, equipment=",".join(sorted(have)))
    await m.answer(f"🔒 {GEAR_NAMES.get(key, key)} убран из колоды.")


@dp.message(Command("export"))
async def cmd_export(m: Message):
    uid = m.from_user.id
    await m.answer("⏳ Собираю данные...")

    # --- logs ---
    logs = sb.table("logs").select("*").eq("user_id", uid)\
        .order("ts", desc=False).execute().data

    # --- prs ---
    prs = sb.table("prs").select("*").eq("user_id", uid).execute().data

    # --- player ---
    p = get_player(uid)

    buf = io.StringIO()
    buf.write("=== LOGS ===\n")
    w = csv.writer(buf)
    w.writerow(["id","ts","pattern","exercise","reps","unit","effort"])
    for l in logs:
        i   = INFO.get(l["pattern"], {})
        nm  = i.get("name", l["pattern"])
        ut  = i.get("unit", "")
        w.writerow([l["id"], l["ts"][:16], l["pattern"], nm, l["reps"], ut, l["effort"]])

    buf.write("\n=== PERSONAL RECORDS ===\n")
    w2 = csv.writer(buf)
    w2.writerow(["pattern","exercise","pr","unit","submax"])
    for r in sorted(prs, key=lambda x: -x["pr"]):
        i  = INFO.get(r["pattern"], {})
        nm = i.get("name", r["pattern"])
        ut = i.get("unit", "")
        w2.writerow([r["pattern"], nm, r["pr"], ut, submax(r["pr"]) if r["pr"] else 0])

    buf.write("\n=== PLAYER STATE ===\n")
    w3 = csv.writer(buf)
    w3.writerow(["field", "value"])
    for k in ["stamina","streak","best_streak","xp","rank_idx","total_days","last_active","equipment"]:
        w3.writerow([k, p.get(k, "")])

    raw = buf.getvalue().encode("utf-8-sig")   # utf-8-sig = Excel открывает без кракозябр
    today = date.today().isoformat()
    fname = f"trener_export_{today}.csv"

    await m.answer_document(
        BufferedInputFile(raw, filename=fname),
        caption=f"📦 Экспорт данных · {len(logs)} подходов · {today}\n"
                "Открывай в Excel или Google Sheets."
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
