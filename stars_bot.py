# ═══════════════════════════════════════════════════════════════
#   ⭐ STARS BOT — Telegram Stars va Premium sotish boti
#   To'lov: HUMO avto to'lov | Yetkazib berish: PayStars API
#   Admin ID: 8541213007
#   pip install aiogram httpx aiosqlite python-dotenv
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging
import sys
import os
import json
import aiosqlite
import httpx

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, CopyTextButton,
)

# ── O'ZGARTIRING ─────────────────────────────────────────────
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "TOKEN_BU_YERGA")
ADMIN_ID         = int(os.environ.get("ADMIN_ID", "8541213007"))
PAYSTARS_API_URL = os.environ.get("PAYSTARS_API_URL", "https://paystars.uz/api/v1")
PAYSTARS_API_KEY = os.environ.get("PAYSTARS_API_KEY", "API_KEY_BU_YERGA")
SHOP_ID          = int(os.environ.get("SHOP_ID", "24"))
SHOP_KEY         = os.environ.get("SHOP_KEY", "SHOP_KEY_BU_YERGA")
SHOP_API         = os.environ.get("SHOP_API", "https://694bccc3c315b.myxvest1.ru/super/api.php")
DB_PATH          = os.environ.get("DB_PATH", "bot_data.db")
# ─────────────────────────────────────────────────────────────

DEFAULT_STARS_PACKAGES = [
    {"stars": 50,   "price": 15000},
    {"stars": 100,  "price": 28000},
    {"stars": 250,  "price": 65000},
    {"stars": 500,  "price": 125000},
    {"stars": 1000, "price": 240000},
    {"stars": 2500, "price": 580000},
]

DEFAULT_PREMIUM_PACKAGES = [
    {"months": 1,  "label": "1 oy",  "price": 85000},
    {"months": 3,  "label": "3 oy",  "price": 240000},
    {"months": 6,  "label": "6 oy",  "price": 450000},
    {"months": 12, "label": "12 oy", "price": 850000},
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#   DATABASE
# ═══════════════════════════════════════════════════════════════

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, order_id INTEGER,
                type TEXT, amount INTEGER, price REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS forced_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT, channel_title TEXT, channel_link TEXT
            )
        """)
        await db.commit()
    defaults = {
        "stars_packages":   json.dumps(DEFAULT_STARS_PACKAGES),
        "premium_packages": json.dumps(DEFAULT_PREMIUM_PACKAGES),
        "stars_enabled":    "1",
        "premium_enabled":  "1",
        "welcome_text":     "Assalomu alaykum! ⭐ Stars va 💎 Telegram Premium xarid qilish uchun quyidagi bo'limni tanlang.",
    }
    async with aiosqlite.connect(DB_PATH) as db:
        for k, v in defaults.items():
            await db.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (k, v))
        await db.commit()


async def get_setting(key, default=None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else default


async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        await db.commit()


async def get_stars_packages():
    raw = await get_setting("stars_packages")
    return json.loads(raw) if raw else DEFAULT_STARS_PACKAGES


async def set_stars_packages(pkgs):
    await set_setting("stars_packages", json.dumps(pkgs))


async def get_premium_packages():
    raw = await get_setting("premium_packages")
    return json.loads(raw) if raw else DEFAULT_PREMIUM_PACKAGES


async def get_forced_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id,channel_id,channel_title,channel_link FROM forced_channels") as c:
            rows = await c.fetchall()
            return [{"id": r[0], "channel_id": r[1], "title": r[2], "link": r[3]} for r in rows]


async def add_forced_channel(channel_id, title, link):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO forced_channels (channel_id,channel_title,channel_link) VALUES (?,?,?)",
                         (channel_id, title, link))
        await db.commit()


async def remove_forced_channel(row_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM forced_channels WHERE id=?", (row_id,))
        await db.commit()


async def create_order(user_id, order_id, order_type, amount, price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO orders (user_id,order_id,type,amount,price) VALUES (?,?,?,?,?)",
                         (user_id, order_id, order_type, amount, price))
        await db.commit()


async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id,user_id,order_id,type,amount,price,status FROM orders WHERE order_id=?",
            (order_id,)
        ) as c:
            row = await c.fetchone()
            if row:
                return {"id": row[0], "user_id": row[1], "order_id": row[2],
                        "type": row[3], "amount": row[4], "price": row[5], "status": row[6]}
            return None


async def update_order_status(order_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='paid'") as c:
            paid = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'") as c:
            pending = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(price) FROM orders WHERE status='paid'") as c:
            revenue = (await c.fetchone())[0] or 0
        return {"paid": paid, "pending": pending, "revenue": revenue}


# ═══════════════════════════════════════════════════════════════
#   PAYMENT SERVICES
# ═══════════════════════════════════════════════════════════════

async def humo_create(user_id, amount):
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            res = await client.post(
                f"{SHOP_API}?action=create_order",
                json={"shop_id": SHOP_ID, "shop_key": SHOP_KEY,
                      "amount": float(amount), "user_id": str(user_id)}
            )
            return res.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def humo_check(order_id):
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            res = await client.get(SHOP_API, params={
                "action": "check", "order_id": order_id,
                "shop_id": SHOP_ID, "shop_key": SHOP_KEY,
            })
            return res.json().get("data")
    except Exception:
        return None


async def paystars_send_stars(telegram_id, stars):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{PAYSTARS_API_URL}/stars/send",
                headers={"Authorization": f"Bearer {PAYSTARS_API_KEY}"},
                json={"telegram_id": telegram_id, "amount": stars}
            )
            return res.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


async def paystars_send_premium(telegram_id, months):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{PAYSTARS_API_URL}/premium/send",
                headers={"Authorization": f"Bearer {PAYSTARS_API_KEY}"},
                json={"telegram_id": telegram_id, "months": months}
            )
            return res.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


async def paystars_balance():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{PAYSTARS_API_URL}/balance",
                headers={"Authorization": f"Bearer {PAYSTARS_API_KEY}"}
            )
            return res.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
#   HELPERS
# ═══════════════════════════════════════════════════════════════

def fmt(n):
    try: return f"{int(float(n)):,}".replace(",", " ")
    except: return str(n)


async def check_subscriptions(bot, user_id):
    channels = await get_forced_channels()
    not_sub = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked", "banned"):
                not_sub.append(ch)
        except Exception:
            not_sub.append(ch)
    return not_sub


# ═══════════════════════════════════════════════════════════════
#   KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def kb_main(stars_on=True, premium_on=True):
    rows = []
    if stars_on:   rows.append([KeyboardButton(text="⭐ Telegram Stars sotib olish")])
    if premium_on: rows.append([KeyboardButton(text="💎 Telegram Premium sotib olish")])
    rows.append([KeyboardButton(text="📦 Mening buyurtmalarim")])
    rows.append([KeyboardButton(text="ℹ️ Yordam")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def kb_admin():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="⭐ Stars narxlarini o'zgartirish"),
         KeyboardButton(text="💎 Premium narxlarini o'zgartirish")],
        [KeyboardButton(text="📢 Majburiy obuna"),
         KeyboardButton(text="⚙️ Bot sozlamalari")],
        [KeyboardButton(text="💰 PayStars balansi")],
        [KeyboardButton(text="🔙 Asosiy menyu")],
    ], resize_keyboard=True)


def kb_stars(packages):
    rows = []
    for i, p in enumerate(packages):
        rows.append([InlineKeyboardButton(
            text=f"⭐ {p['stars']} Stars — {fmt(p['price'])} so'm",
            callback_data=f"stars_buy:{i}")])
    rows.append([InlineKeyboardButton(text="✏️ O'zim yozaman (miqdorni)", callback_data="stars_custom")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_premium(packages):
    rows = []
    for i, p in enumerate(packages):
        rows.append([InlineKeyboardButton(
            text=f"💎 {p['label']} — {fmt(p['price'])} so'm",
            callback_data=f"premium_buy:{i}")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_payment(order_id, card, amount):
    card_copy = card.replace(" ", "")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📋 {card}",
                              copy_text=CopyTextButton(text=card_copy))],
        [InlineKeyboardButton(text=f"💰 {fmt(amount)} so'm",
                              copy_text=CopyTextButton(text=str(amount)))],
        [InlineKeyboardButton(text="✅ To'lov qildim",
                              callback_data=f"check_pay:{order_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish",
                              callback_data=f"cancel_pay:{order_id}")],
    ])


def kb_channels(channels):
    rows = [[InlineKeyboardButton(text=f"📢 {ch['title']}", url=ch["link"])]
            for ch in channels]
    rows.append([InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_stars(packages):
    rows = [[InlineKeyboardButton(
        text=f"⭐ {p['stars']} → {fmt(p['price'])} so'm",
        callback_data=f"edit_stars:{i}")] for i, p in enumerate(packages)]
    rows.append([InlineKeyboardButton(text="➕ Yangi paket qo'shish", callback_data="add_stars_pkg")])
    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_premium(packages):
    rows = [[InlineKeyboardButton(
        text=f"💎 {p['label']} → {fmt(p['price'])} so'm",
        callback_data=f"edit_premium:{i}")] for i, p in enumerate(packages)]
    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_channels(channels):
    rows = [[InlineKeyboardButton(text=f"❌ {ch['title']}", callback_data=f"del_channel:{ch['id']}")]
            for ch in channels]
    rows.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")])
    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══════════════════════════════════════════════════════════════
#   FSM STATES
# ═══════════════════════════════════════════════════════════════

class ShopSt(StatesGroup):
    stars_custom    = State()
    stars_pay       = State()
    premium_pay     = State()


class AdminSt(StatesGroup):
    edit_stars_price    = State()
    edit_premium_price  = State()
    add_stars_stars     = State()
    add_stars_price     = State()
    add_ch_id           = State()
    add_ch_title        = State()
    add_ch_link         = State()
    edit_welcome        = State()


# ═══════════════════════════════════════════════════════════════
#   ROUTERS
# ═══════════════════════════════════════════════════════════════

r_common = Router()
r_admin  = Router()
r_start  = Router()
r_shop   = Router()


# ─── /cancel (istalgan holatda ishlaydi) ─────────────────────
@r_common.message(Command("cancel"))
@r_common.message(StateFilter("*"), F.text.casefold() == "bekor")
async def cmd_cancel(msg: Message, state: FSMContext):
    cur = await state.get_state()
    await state.clear()
    if cur is None:
        await msg.answer("Bekor qilinadigan narsa yo'q. /start bosing.")
    else:
        await msg.answer("❌ Bekor qilindi. /start bosing.")


# ─── /start ──────────────────────────────────────────────────
@r_start.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uid = msg.from_user.id
    if uid == ADMIN_ID:
        await msg.answer("👋 Xush kelibsiz, Admin!\n\nAdmin panelga: /admin",
                         reply_markup=kb_main())
        return
    not_sub = await check_subscriptions(bot, uid)
    if not_sub:
        await msg.answer("⚠️ <b>Botdan foydalanish uchun kanallarga obuna bo'ling:</b>",
                         reply_markup=kb_channels(not_sub), parse_mode="HTML")
        return
    welcome = await get_setting("welcome_text", "Xush kelibsiz!")
    stars_on = (await get_setting("stars_enabled", "1")) == "1"
    premium_on = (await get_setting("premium_enabled", "1")) == "1"
    await msg.answer(f"👋 {welcome}", reply_markup=kb_main(stars_on, premium_on), parse_mode="HTML")


@r_start.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery, bot: Bot):
    not_sub = await check_subscriptions(bot, call.from_user.id)
    if not_sub:
        await call.answer("⚠️ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        welcome = await get_setting("welcome_text", "Xush kelibsiz!")
        stars_on = (await get_setting("stars_enabled", "1")) == "1"
        premium_on = (await get_setting("premium_enabled", "1")) == "1"
        await call.message.answer(f"✅ Rahmat!\n\n👋 {welcome}",
                                   reply_markup=kb_main(stars_on, premium_on), parse_mode="HTML")


@r_start.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()


@r_start.message(F.text == "ℹ️ Yordam")
async def help_msg(msg: Message):
    await msg.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "Bu bot orqali Telegram Stars va Premium sotib olasiz.\n\n"
        "💳 <b>To'lov:</b> HUMO karta orqali avtomatik\n"
        "⭐ <b>Stars:</b> Hisob raqamingizga tushadi\n"
        "💎 <b>Premium:</b> Avtomatik faollashtiriladi",
        parse_mode="HTML"
    )


# ─── Stars xarid ─────────────────────────────────────────────
@r_shop.message(F.text == "⭐ Telegram Stars sotib olish")
async def stars_menu(msg: Message, bot: Bot):
    not_sub = await check_subscriptions(bot, msg.from_user.id)
    if not_sub:
        await msg.answer("⚠️ Avval kanallarga obuna bo'ling:", reply_markup=kb_channels(not_sub))
        return
    if (await get_setting("stars_enabled", "1")) != "1":
        await msg.answer("⭐ Stars xizmati vaqtincha to'xtatilgan.")
        return
    pkgs = await get_stars_packages()
    await msg.answer("⭐ <b>Telegram Stars</b>\n\nPaket tanlang:",
                     reply_markup=kb_stars(pkgs), parse_mode="HTML")


@r_shop.callback_query(F.data.startswith("stars_buy:"))
async def stars_buy(call: CallbackQuery, state: FSMContext, bot: Bot):
    not_sub = await check_subscriptions(bot, call.from_user.id)
    if not_sub:
        await call.message.answer("⚠️ Avval kanallarga obuna bo'ling:", reply_markup=kb_channels(not_sub))
        await call.answer()
        return
    idx = int(call.data.split(":")[1])
    pkgs = await get_stars_packages()
    if idx >= len(pkgs):
        await call.answer("Paket topilmadi!", show_alert=True)
        return
    p = pkgs[idx]
    await _start_stars_pay(call.message, call.from_user.id, p["stars"], p["price"], state)
    await call.answer()


@r_shop.callback_query(F.data == "stars_custom")
async def stars_custom(call: CallbackQuery, state: FSMContext):
    await state.set_state(ShopSt.stars_custom)
    await call.message.answer(
        "✏️ Nechta Stars xohlaysiz?\n\n"
        "<i>Minimal: 10 | Maksimal: 100 000</i>\n\nBekor qilish: /cancel",
        parse_mode="HTML"
    )
    await call.answer()


@r_shop.message(ShopSt.stars_custom)
async def stars_custom_input(msg: Message, state: FSMContext):
    raw = msg.text.strip().replace(" ", "")
    if not raw.isdigit() or not (10 <= int(raw) <= 100000):
        await msg.answer("⚠️ 10 dan 100 000 gacha raqam kiriting.")
        return
    stars = int(raw)
    pkgs = await get_stars_packages()
    pps = (pkgs[0]["price"] / pkgs[0]["stars"]) if pkgs else 280
    price = int(stars * pps)
    await _start_stars_pay(msg, msg.from_user.id, stars, price, state)


async def _start_stars_pay(msg_obj, uid, stars, price, state):
    wait = await msg_obj.answer("⏳ To'lov yaratilmoqda...")
    res = await humo_create(uid, price)
    if not res or not res.get("ok"):
        err = res.get("error", "Server xatosi") if res else "Javob yo'q"
        await wait.edit_text(f"❌ <b>Xato:</b> {err}", parse_mode="HTML")
        await state.clear()
        return
    d = res["data"]
    oid = d["order_id"]
    fp  = int(d["amount"])
    card = d["card_number"]
    await create_order(uid, oid, "stars", stars, fp)
    await state.set_state(ShopSt.stars_pay)
    await state.update_data(order_id=oid, stars=stars)
    extra = (f"\n\n⚠️ Farqlash uchun <b>+{d['extra_sum']} so'm</b> qo'shildi."
             if d.get("extra_sum", 0) > 0 else "")
    await wait.edit_text(
        f"⭐ <b>Stars xarid</b>\n\n"
        f"📦 Miqdor: <b>{stars} Stars</b>\n"
        f"💰 To'lov: <b>{fmt(fp)} so'm</b>\n"
        f"🏦 Karta: <code>{card}</code>\n\n"
        f"📋 <b>Ko'rsatma:</b>\n"
        f"1️⃣ Karta raqamini nusxa oling\n"
        f"2️⃣ Aniq summani o'tkazing\n"
        f"3️⃣ «✅ To'lov qildim» bosing\n\n"
        f"⏳ Muddat: <b>10 daqiqa</b>{extra}",
        reply_markup=kb_payment(oid, card, fp),
        parse_mode="HTML"
    )


# ─── Premium xarid ───────────────────────────────────────────
@r_shop.message(F.text == "💎 Telegram Premium sotib olish")
async def premium_menu(msg: Message, bot: Bot):
    not_sub = await check_subscriptions(bot, msg.from_user.id)
    if not_sub:
        await msg.answer("⚠️ Avval kanallarga obuna bo'ling:", reply_markup=kb_channels(not_sub))
        return
    if (await get_setting("premium_enabled", "1")) != "1":
        await msg.answer("💎 Premium xizmati vaqtincha to'xtatilgan.")
        return
    pkgs = await get_premium_packages()
    await msg.answer("💎 <b>Telegram Premium</b>\n\nMuddatni tanlang:",
                     reply_markup=kb_premium(pkgs), parse_mode="HTML")


@r_shop.callback_query(F.data.startswith("premium_buy:"))
async def premium_buy(call: CallbackQuery, state: FSMContext, bot: Bot):
    not_sub = await check_subscriptions(bot, call.from_user.id)
    if not_sub:
        await call.message.answer("⚠️ Avval kanallarga obuna bo'ling:", reply_markup=kb_channels(not_sub))
        await call.answer()
        return
    idx = int(call.data.split(":")[1])
    pkgs = await get_premium_packages()
    if idx >= len(pkgs):
        await call.answer("Paket topilmadi!", show_alert=True)
        return
    p = pkgs[idx]
    wait = await call.message.answer("⏳ To'lov yaratilmoqda...")
    res = await humo_create(call.from_user.id, p["price"])
    if not res or not res.get("ok"):
        err = res.get("error", "Server xatosi") if res else "Javob yo'q"
        await wait.edit_text(f"❌ <b>Xato:</b> {err}", parse_mode="HTML")
        await call.answer()
        return
    d = res["data"]
    oid = d["order_id"]
    fp  = int(d["amount"])
    card = d["card_number"]
    await create_order(call.from_user.id, oid, "premium", p["months"], fp)
    await state.set_state(ShopSt.premium_pay)
    await state.update_data(order_id=oid, months=p["months"])
    await wait.edit_text(
        f"💎 <b>Premium xarid</b>\n\n"
        f"📦 Muddat: <b>{p['label']}</b>\n"
        f"💰 To'lov: <b>{fmt(fp)} so'm</b>\n"
        f"🏦 Karta: <code>{card}</code>\n\n"
        f"📋 <b>Ko'rsatma:</b>\n"
        f"1️⃣ Karta raqamini nusxa oling\n"
        f"2️⃣ Aniq summani o'tkazing\n"
        f"3️⃣ «✅ To'lov qildim» bosing\n\n"
        f"⏳ Muddat: <b>10 daqiqa</b>",
        reply_markup=kb_payment(oid, card, fp),
        parse_mode="HTML"
    )
    await call.answer()


# ─── To'lovni tekshirish ─────────────────────────────────────
@r_shop.callback_query(F.data.startswith("check_pay:"))
async def check_pay(call: CallbackQuery, state: FSMContext):
    oid = int(call.data.split(":")[1])
    d = await humo_check(oid)
    if not d:
        await call.answer("⚠️ Server javob bermadi. Qaytadan bosing.", show_alert=True)
        return
    status = d.get("status", "")
    secs   = int(d.get("seconds_left", 0))

    if status == "paid":
        order = await get_order(oid)
        if not order:
            await call.answer("Buyurtma topilmadi!", show_alert=True)
            return
        await update_order_status(oid, "paid")
        await call.message.edit_text("⏳ To'lov tasdiqlandi! Mahsulot yuborilmoqda...")
        if order["type"] == "stars":
            res = await paystars_send_stars(call.from_user.id, order["amount"])
            if res.get("success") or res.get("ok"):
                await call.message.edit_text(
                    f"✅ <b>Muvaffaqiyatli!</b>\n\n"
                    f"⭐ <b>{order['amount']} Telegram Stars</b> hisobingizga yuborildi!\n"
                    f"🧾 Buyurtma: <code>#{oid}</code>", parse_mode="HTML")
            else:
                await call.message.edit_text(
                    f"✅ To'lov qabul qilindi!\n⭐ {order['amount']} Stars tez orada yuboriladi.\n🧾 #{oid}")
        elif order["type"] == "premium":
            res = await paystars_send_premium(call.from_user.id, order["amount"])
            if res.get("success") or res.get("ok"):
                await call.message.edit_text(
                    f"✅ <b>Muvaffaqiyatli!</b>\n\n"
                    f"💎 <b>Telegram Premium ({order['amount']} oy)</b> faollashtirildi!\n"
                    f"🧾 Buyurtma: <code>#{oid}</code>", parse_mode="HTML")
            else:
                await call.message.edit_text(
                    f"✅ To'lov qabul qilindi!\n💎 Premium tez orada faollashtiriladi.\n🧾 #{oid}")
        await state.clear()

    elif status in ("expired", "cancelled") or secs <= 0:
        await update_order_status(oid, "expired")
        await call.answer("⏰ Muddat tugadi. Qaytadan urinib ko'ring.", show_alert=True)
        await call.message.edit_text("⏰ <b>To'lov muddati tugadi.</b>\n\nQaytadan urinib ko'ring.",
                                     parse_mode="HTML", reply_markup=None)
        await state.clear()
    else:
        m = secs // 60; s = secs % 60
        t = f"{m} daqiqa {s} soniya" if m else f"{s} soniya"
        await call.answer(f"⏳ Hali tasdiqlanmadi. ~{t} qoldi.", show_alert=True)


@r_shop.callback_query(F.data.startswith("cancel_pay:"))
async def cancel_pay(call: CallbackQuery, state: FSMContext):
    oid = int(call.data.split(":")[1])
    await update_order_status(oid, "cancelled")
    await state.clear()
    await call.message.edit_text("❌ To'lov bekor qilindi.")


@r_shop.message(F.text == "📦 Mening buyurtmalarim")
async def my_orders(msg: Message):
    await msg.answer("📦 Muammo bo'lsa admin bilan bog'laning yoki /start bosing.")


# ─── Admin panel ─────────────────────────────────────────────
@r_admin.message(Command("admin"))
async def admin_panel(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("⛔ Ruxsat yo'q.")
        return
    await state.clear()
    await msg.answer("🔐 <b>Admin Panel</b>", reply_markup=kb_admin(), parse_mode="HTML")


@r_admin.message(F.text == "🔙 Asosiy menyu")
async def admin_to_main(msg: Message, state: FSMContext):
    await state.clear()
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("Asosiy menyu:", reply_markup=kb_main())


@r_admin.message(F.text == "📊 Statistika")
async def admin_stats(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    s = await get_stats()
    await msg.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{s['paid']}</b>\n"
        f"⏳ Kutilayotgan: <b>{s['pending']}</b>\n"
        f"💰 Daromad: <b>{fmt(s['revenue'])} so'm</b>",
        parse_mode="HTML"
    )


@r_admin.message(F.text == "⭐ Stars narxlarini o'zgartirish")
async def admin_stars_menu(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    pkgs = await get_stars_packages()
    await msg.answer("⭐ <b>Stars paketlari:</b>",
                     reply_markup=kb_admin_stars(pkgs), parse_mode="HTML")


@r_admin.callback_query(F.data.startswith("edit_stars:"))
async def edit_stars(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    idx = int(call.data.split(":")[1])
    pkgs = await get_stars_packages()
    await state.set_state(AdminSt.edit_stars_price)
    await state.update_data(idx=idx)
    await call.message.answer(
        f"⭐ <b>{pkgs[idx]['stars']} Stars</b> — hozirgi: <b>{fmt(pkgs[idx]['price'])} so'm</b>\n\nYangi narx (so'm):",
        parse_mode="HTML")
    await call.answer()


@r_admin.message(AdminSt.edit_stars_price)
async def save_stars_price(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    raw = msg.text.strip().replace(" ", "")
    if not raw.isdigit(): await msg.answer("Faqat raqam!"); return
    data = await state.get_data()
    pkgs = await get_stars_packages()
    pkgs[data["idx"]]["price"] = int(raw)
    await set_stars_packages(pkgs)
    await state.clear()
    await msg.answer(f"✅ Narx yangilandi!", reply_markup=kb_admin_stars(pkgs))


@r_admin.callback_query(F.data == "add_stars_pkg")
async def add_stars_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    await state.set_state(AdminSt.add_stars_stars)
    await call.message.answer("⭐ Yangi paket uchun nechta Stars?")
    await call.answer()


@r_admin.message(AdminSt.add_stars_stars)
async def add_stars_stars_input(msg: Message, state: FSMContext):
    raw = msg.text.strip().replace(" ", "")
    if not raw.isdigit(): await msg.answer("Faqat raqam!"); return
    await state.update_data(new_stars=int(raw))
    await state.set_state(AdminSt.add_stars_price)
    await msg.answer(f"💰 {raw} Stars uchun narx (so'm)?")


@r_admin.message(AdminSt.add_stars_price)
async def add_stars_price_input(msg: Message, state: FSMContext):
    raw = msg.text.strip().replace(" ", "")
    if not raw.isdigit(): await msg.answer("Faqat raqam!"); return
    data = await state.get_data()
    pkgs = await get_stars_packages()
    pkgs.append({"stars": data["new_stars"], "price": int(raw)})
    pkgs.sort(key=lambda x: x["stars"])
    await set_stars_packages(pkgs)
    await state.clear()
    await msg.answer(f"✅ Yangi paket qo'shildi!", reply_markup=kb_admin_stars(pkgs))


@r_admin.message(F.text == "💎 Premium narxlarini o'zgartirish")
async def admin_premium_menu(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    pkgs = await get_premium_packages()
    await msg.answer("💎 <b>Premium paketlari:</b>",
                     reply_markup=kb_admin_premium(pkgs), parse_mode="HTML")


@r_admin.callback_query(F.data.startswith("edit_premium:"))
async def edit_premium(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    idx = int(call.data.split(":")[1])
    pkgs = await get_premium_packages()
    await state.set_state(AdminSt.edit_premium_price)
    await state.update_data(idx=idx)
    await call.message.answer(
        f"💎 <b>{pkgs[idx]['label']}</b> — hozirgi: <b>{fmt(pkgs[idx]['price'])} so'm</b>\n\nYangi narx (so'm):",
        parse_mode="HTML")
    await call.answer()


@r_admin.message(AdminSt.edit_premium_price)
async def save_premium_price(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    raw = msg.text.strip().replace(" ", "")
    if not raw.isdigit(): await msg.answer("Faqat raqam!"); return
    data = await state.get_data()
    pkgs = await get_premium_packages()
    pkgs[data["idx"]]["price"] = int(raw)
    await set_setting("premium_packages", json.dumps(pkgs))
    await state.clear()
    await msg.answer(f"✅ Narx yangilandi!", reply_markup=kb_admin_premium(pkgs))


@r_admin.message(F.text == "📢 Majburiy obuna")
async def admin_channels_menu(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    channels = await get_forced_channels()
    text = "📢 <b>Majburiy obuna kanallari</b>\n\n"
    text += "\n".join(f"• {ch['title']} (<code>{ch['channel_id']}</code>)" for ch in channels) if channels else "Kanal yo'q."
    await msg.answer(text, reply_markup=kb_admin_channels(channels), parse_mode="HTML")


@r_admin.callback_query(F.data == "add_channel")
async def add_channel_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    await state.set_state(AdminSt.add_ch_id)
    await call.message.answer(
        "📢 Kanal ID sini kiriting\n(masalan: <code>-1001234567890</code>)\n\n"
        "Botni kanalingizga admin qilib qo'shing!", parse_mode="HTML")
    await call.answer()


@r_admin.message(AdminSt.add_ch_id)
async def add_ch_id(msg: Message, state: FSMContext):
    await state.update_data(ch_id=msg.text.strip())
    await state.set_state(AdminSt.add_ch_title)
    await msg.answer("Kanal nomini kiriting:")


@r_admin.message(AdminSt.add_ch_title)
async def add_ch_title(msg: Message, state: FSMContext):
    await state.update_data(ch_title=msg.text.strip())
    await state.set_state(AdminSt.add_ch_link)
    await msg.answer("Kanal havolasini kiriting (https://t.me/...):")


@r_admin.message(AdminSt.add_ch_link)
async def add_ch_link(msg: Message, state: FSMContext):
    data = await state.get_data()
    await add_forced_channel(data["ch_id"], data["ch_title"], msg.text.strip())
    channels = await get_forced_channels()
    await state.clear()
    await msg.answer(f"✅ Kanal qo'shildi: <b>{data['ch_title']}</b>",
                     reply_markup=kb_admin_channels(channels), parse_mode="HTML")


@r_admin.callback_query(F.data.startswith("del_channel:"))
async def del_channel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    await remove_forced_channel(int(call.data.split(":")[1]))
    channels = await get_forced_channels()
    await call.message.edit_reply_markup(reply_markup=kb_admin_channels(channels))
    await call.answer("✅ O'chirildi.")


@r_admin.message(F.text == "⚙️ Bot sozlamalari")
async def bot_settings(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    stars_on = (await get_setting("stars_enabled", "1")) == "1"
    premium_on = (await get_setting("premium_enabled", "1")) == "1"
    welcome = await get_setting("welcome_text", "Xush kelibsiz!")
    sts = "✅ Yoqiq" if stars_on else "❌ O'chiq"
    pts = "✅ Yoqiq" if premium_on else "❌ O'chiq"
    await msg.answer(
        f"⚙️ <b>Bot sozlamalari</b>\n\n⭐ Stars: {sts}\n💎 Premium: {pts}\n\n"
        f"📝 Xush kelish matni:\n<i>{welcome}</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Stars: {sts}", callback_data="toggle_stars")],
            [InlineKeyboardButton(text=f"💎 Premium: {pts}", callback_data="toggle_premium")],
            [InlineKeyboardButton(text="✏️ Xush kelish xabarini o'zgartirish", callback_data="edit_welcome")],
        ]),
        parse_mode="HTML"
    )


@r_admin.callback_query(F.data == "toggle_stars")
async def toggle_stars(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    cur = await get_setting("stars_enabled", "1")
    new = "0" if cur == "1" else "1"
    await set_setting("stars_enabled", new)
    await call.answer(f"Stars {'yoqildi ✅' if new == '1' else 'o\\'chirildi ❌'}", show_alert=True)
    await call.message.delete()


@r_admin.callback_query(F.data == "toggle_premium")
async def toggle_premium(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    cur = await get_setting("premium_enabled", "1")
    new = "0" if cur == "1" else "1"
    await set_setting("premium_enabled", new)
    await call.answer(f"Premium {'yoqildi ✅' if new == '1' else 'o\\'chirildi ❌'}", show_alert=True)
    await call.message.delete()


@r_admin.callback_query(F.data == "edit_welcome")
async def edit_welcome_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: await call.answer("Ruxsat yo'q!"); return
    await state.set_state(AdminSt.edit_welcome)
    await call.message.answer("✏️ Yangi xush kelish xabarini kiriting:")
    await call.answer()


@r_admin.message(AdminSt.edit_welcome)
async def save_welcome(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await set_setting("welcome_text", msg.text.strip())
    await state.clear()
    await msg.answer("✅ Xush kelish matni yangilandi!")


@r_admin.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer()


@r_admin.message(F.text == "💰 PayStars balansi")
async def paystars_bal(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    res = await paystars_balance()
    if res.get("success") or res.get("balance") is not None:
        bal = res.get("balance", res.get("data", {}).get("balance", "N/A"))
        await msg.answer(f"💰 <b>PayStars balansi:</b> <code>{bal}</code>", parse_mode="HTML")
    else:
        await msg.answer(f"❌ Xato: {res.get('error', 'Noma\\'lum')}")


# ═══════════════════════════════════════════════════════════════
#   O'Z-O'ZINI UYG'OTISH (SELF-PING) — har 90 soniyada
# ═══════════════════════════════════════════════════════════════

from aiohttp import web

SELF_PORT = int(os.environ.get("BOT_PORT", 5000))


async def _health(request):
    return web.Response(text="OK")


async def run_webserver():
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", SELF_PORT).start()
    logger.info(f"Web server port {SELF_PORT} da ishga tushdi.")


async def self_ping():
    await asyncio.sleep(30)
    url = f"http://localhost:{SELF_PORT}/health"
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                logger.info(f"Self-ping OK ({r.status_code})")
        except Exception as e:
            logger.warning(f"Self-ping xato: {e}")
        await asyncio.sleep(90)


# ═══════════════════════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    logger.info("Bot ishga tushmoqda...")
    await init_db()
    logger.info("DB tayyor.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp  = Dispatcher(storage=MemoryStorage())

    dp.include_router(r_common)
    dp.include_router(r_admin)
    dp.include_router(r_start)
    dp.include_router(r_shop)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling boshlandi. Bot tayyor! @SpellyStars_Bot")

    try:
        await asyncio.gather(
            dp.start_polling(bot, skip_updates=True,
                             allowed_updates=dp.resolve_used_update_types()),
            run_webserver(),
            self_ping(),
        )
    finally:
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
