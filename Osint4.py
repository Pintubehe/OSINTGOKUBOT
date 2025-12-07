# GOKU OSINT BOT 
# Created by @Gokkuuu
# Free to use with proper credits

import os
import json
import time
import random
import string
import logging
import requests
from typing import Union, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, Message
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext

# ---------------- CONFIG ----------------
BOT_TOKEN = "8489974226:AAFEPkUViZSfSYn1uZcuWRffTvjtcempYOA"
BOT_USERNAME = "Gokuuu_osinytt_bot"        
BUY_CREDITS_USERNAME = "gokuuuu_1" 
ADMIN_IDS = [8333354105]  # Your admin ID

# Core settings
REFERRAL_BONUS = 2
INITIAL_CREDITS = 2
SEARCH_COST = 1
BACKUP_COOLDOWN = 300
DAILY_BONUS_AMOUNT = 2
DAILY_SECONDS = 86400
GENERATED_CODE_LENGTH = 8

# Data files
USERS_FILE = "users.json"
CODES_FILE = "redeem_codes.json"
BACKUP_META = "backup_meta.json"

# Your APIs
PHONE_IN_API = "https://meowmeow.rf.gd/gand/mobile.php?num={num}"  # India Phone
PHONE_PK_API = "https://pakistan-info-api-five.vercel.app/api/seller/?mobile={num}&key=GOKU"  # Pakistan Phone
AADHAAR_API = "https://addartofamily.vercel.app/fetch?aadhaar={aadhaar}"  # Aadhaar Info
CNIC_API = "https://cnic-info.gauravcyber0.workers.dev/?cnic={cnic}"  # CNIC Info
RC_API = "https://vvvin-ng.vercel.app/lookup?rc={rc}"  # Vehicle RC Info
IFSC_API = "https://ifsc.razorpay.com/{ifsc}"  # IFSC Info
FF_UID_API = "https://anku-ffapi.vercel.app/ff?uid={uid}"  # Free Fire UID Info
PINCODE_API = "https://api.postalpincode.in/pincode/{pincode}"  # Pincode Info
BIN_API = "https://data.handyapi.com/bin/{bin}"  # BIN Info

# Maintenance message
MAINTENANCE_TEXT = "⚙️ This feature is under maintenance. Credits not deducted."

# ---------------- logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("goku-osint-bot")

# ---------------- helpers for JSON files ----------------
def read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"read_json error {path}: {e}")
        return {}

def write_json(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"write_json error {path}: {e}")

def ensure_files_exist():
    for fn in [USERS_FILE, CODES_FILE, BACKUP_META]:
        if not os.path.exists(fn):
            write_json(fn, {})

# ---------------- misc helpers ----------------
def gen_code(length: int = GENERATED_CODE_LENGTH) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))

def http_get(url: str, timeout: int = 12) -> Optional[requests.Response]:
    headers = {"User-Agent": "GOKU-OSINT-BOT/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.debug(f"http_get error for {url}: {e}")
        return None

# ---------------- user data helpers ----------------
def ensure_user(uid: str) -> dict:
    users = read_json(USERS_FILE)
    if uid not in users:
        users[uid] = {
            "credits": INITIAL_CREDITS,
            "referrals": 0,
            "banned": False,
            "referred_by": None,
            "last_daily": 0
        }
        write_json(USERS_FILE, users)
    # make sure keys exist
    changed = False
    if "referred_by" not in users[uid]:
        users[uid]["referred_by"] = None; changed = True
    if "last_daily" not in users[uid]:
        users[uid]["last_daily"] = 0; changed = True
    if changed:
        write_json(USERS_FILE, users)
    return users

def is_banned(uid: str) -> bool:
    users = read_json(USERS_FILE)
    return users.get(uid, {}).get("banned", False)

# ---------------- admin check (robust) ----------------
def is_admin_user(tuser) -> bool:
    if tuser is None:
        return False
    try:
        if int(tuser.id) in [int(x) for x in ADMIN_IDS]:
            return True
    except Exception:
        pass
    try:
        if tuser.username and tuser.username.lower() == str(BUY_CREDITS_USERNAME).lower():
            return True
    except Exception:
        pass
    return False

# ---------------- scrub copyright/owner fields ----------------
def scrub_response(obj):
    """Recursively remove developer/copyright/owner fields and values."""
    block_keys = [
        "developer", "developer_message", "developer_tag",
        "api_by", "api_owner", "owner", "source", "author", "dev", "creator", "footer", "tag"
    ]

    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            kl = k.lower().strip()
            # skip keys that contain block words
            if any(b in kl for b in block_keys):
                continue
            # skip short string values that look like developer credits
            if isinstance(v, str):
                lowv = v.lower()
                if any(b in lowv for b in block_keys):
                    continue
            clean[k] = scrub_response(v)
        return clean

    elif isinstance(obj, list):
        return [scrub_response(x) for x in obj]

    else:
        return obj

# ---------------- backup ----------------
def send_backup_to_admins() -> bool:
    meta = read_json(BACKUP_META)
    now = int(time.time())
    if now - meta.get("last", 0) < BACKUP_COOLDOWN:
        logger.info("backup cooldown active")
        return False
    try:
        bot = Bot(token=BOT_TOKEN)
        if os.path.exists(USERS_FILE):
            for admin_id in ADMIN_IDS:
                try:
                    with open(USERS_FILE, "rb") as f:
                        bot.send_document(chat_id=int(admin_id), document=f, filename="users.json", caption="📦 GOKU OSINT - users backup")
                except Exception as e:
                    logger.warning(f"send_backup to {admin_id} failed: {e}")
        meta["last"] = now
        write_json(BACKUP_META, meta)
        return True
    except Exception as e:
        logger.warning(f"backup failed: {e}")
        return False

# ---------------- Styled UI text ----------------
WELCOME_TEXT = (
    "👋 *𝗛𝗶 {name} — 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗚𝗢𝗞𝗨 𝗢𝗦𝗜𝗡𝗧 𝗕𝗢𝗧 ⚡*\n\n"
    "💡 *Educational & lawful OSINT use only.*\n"
    "📚 Use findings responsibly — do not harass, doxx, or commit illegal acts We Are Not Responsible For Anything Illigal.\n\n"
    "🔐 *Credits:* Each search costs *1 credit*.\n"
    "🎁 *Daily Bonus:* Claim once per 24 hours.\n"
    "🎯 *Referral:* Earn credits when a new user joins using your link.\n\n"
    "Need help? Contact @{owner}\n"
).format(name="{name}", owner=BUY_CREDITS_USERNAME)

HELP_TEXT = (
    "📘 *GOKU OSINT Assistant — Help Center*\n\n"
    "🔍 *Available Searches:*\n"
    "• Phone (India / Pakistan)\n"
    "• Aadhaar Information\n"
    "• CNIC Information\n"
    "• IFSC Bank Details\n"
    "• Vehicle / RC Information\n"
    "• Free Fire UID Info\n"
    "• Pincode Information\n"
    "• BIN Information\n\n"
    "💳 *Credits:* Each search costs *1 credit*. If no result, credit is refunded.\n"
    "🎁 *Daily Bonus:* Claim once per 24 hours for free credits.\n"
    "🎯 *Referral:* Share your link. You earn credits when a *new* user joins using your link.\n\n"
    "Contact @{owner} for support."
).format(owner=BUY_CREDITS_USERNAME)

CREDIT_DEDUCTED_MSG = (
    "⚠️ *Credits deducted by Admin*\n\n"
    "• Amount: *-{amt}*\n"
    "• New Balance: *{bal}*\n\n"
    "If you think this is an error, contact @{owner}."
)

CREDIT_ADDED_MSG = (
    "💰 *Credits added by Admin*\n\n"
    "• Amount: *+{amt}*\n"
    "• New Balance: *{bal}*\n\n"
    "Enjoy your searches! Contact @{owner} for help."
)

REFERRAL_EARNED_MSG = "🎉 *New user joined with your referral!* You earned *{amt}* credits. Thank you!"

DAILY_CLAIMED_MSG = "🎁 *You claimed your Daily Bonus!* +{amt} credits."

ERROR_REFUND_MSG = "⚠️ *Error fetching data.* Credits refunded."

# ---------------- Keyboards ----------------
def main_menu_keyboard():
    buy_url = f"https://t.me/{BUY_CREDITS_USERNAME}"
    kb = [
        [InlineKeyboardButton("Phone 🇮🇳", callback_data="phone_in"),
         InlineKeyboardButton("Phone 🇵🇰", callback_data="phone_pk"),
         InlineKeyboardButton("Aadhaar 🆔", callback_data="aadhaar")],
        [InlineKeyboardButton("CNIC 🇵🇰", callback_data="cnic"),
         InlineKeyboardButton("IFSC 🏦", callback_data="ifsc"),
         InlineKeyboardButton("Vehicle/RC 🚗", callback_data="vehicle_rc")],
        [InlineKeyboardButton("🎮 Free Fire UID", callback_data="ff_uid"),
         InlineKeyboardButton("📍 Pincode Info", callback_data="pincode"),
         InlineKeyboardButton("💳 BIN Info", callback_data="bin_info")],
        [InlineKeyboardButton("🎁 Redeem", callback_data="redeem"),
         InlineKeyboardButton("🎯 Referral", callback_data="referral")],
        [InlineKeyboardButton("💰 Credits", callback_data="credits"),
         InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily_bonus"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("💳 Buy Credits", url=buy_url)]
    ]
    return InlineKeyboardMarkup(kb)

def back_to_menu_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="to_menu")]])

def admin_panel_kb():
    kb = [
        [InlineKeyboardButton("📊 User Stats", callback_data="admin_stats"),
         InlineKeyboardButton("🎁 Generate Codes", callback_data="admin_gen_codes"),
         InlineKeyboardButton("🔎 User Info", callback_data="admin_user_info")],
        [InlineKeyboardButton("📦 Force Backup", callback_data="admin_backup"),
         InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"),
         InlineKeyboardButton("✅ Unban User", callback_data="admin_unban"),
         InlineKeyboardButton("➖ Deduct -1", callback_data="admin_deduct")],
        [InlineKeyboardButton("➖➖ Custom Deduct", callback_data="admin_deduct_custom"),
         InlineKeyboardButton("➕ Add Credits", callback_data="admin_add_credits"),
         InlineKeyboardButton("📣 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="to_menu")]
    ]
    return InlineKeyboardMarkup(kb)

def admin_action_back_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="admin_panel"),
         InlineKeyboardButton("🏠 Back to Main Menu", callback_data="to_menu")]
    ])

# ---------------- Commands ----------------
async def start_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    uid = str(user.id)
    args = context.args or []

    # check if user already existed before calling ensure_user
    users_before = read_json(USERS_FILE)
    user_existed_before = uid in users_before

    ensure_user(uid)
    if is_banned(uid):
        await update.message.reply_text("❌ *You are banned from using this bot.*", parse_mode="Markdown")
        return

    # Referral: only credit referrer once AND only if the user is NEW (joined using the link)
    if args:
        ref = args[0]
        try:
            ref_id = str(int(ref))
        except:
            ref_id = None
        # only process referral if:
        # 1) ref_id is valid and not self
        # 2) this user did NOT exist before (i.e. truly a new join)
        # 3) referred_by is still None (safety)
        if ref_id and ref_id != uid and not user_existed_before:
            users = read_json(USERS_FILE)
            if users.get(uid, {}).get("referred_by") is None:
                users[uid]["referred_by"] = ref_id
                write_json(USERS_FILE, users)
                if ref_id in users:
                    users[ref_id]["credits"] = users[ref_id].get("credits", 0) + REFERRAL_BONUS
                    users[ref_id]["referrals"] = users[ref_id].get("referrals", 0) + 1
                    write_json(USERS_FILE, users)
                    try:
                        await context.bot.send_message(int(ref_id), REFERRAL_EARNED_MSG.format(amt=REFERRAL_BONUS), parse_mode="Markdown")
                    except Exception:
                        logger.debug("could not DM referrer")

    # Welcome (styled)
    wtext = WELCOME_TEXT.format(name=user.first_name)
    await update.message.reply_text(wtext, parse_mode="Markdown")
    await update.message.reply_text("✅ *Select an option below:*", parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def menu_cmd(update: Update, context: CallbackContext):
    await update.message.reply_text("✅ *Select an option below:*", parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def admin_cmd(update: Update, context: CallbackContext):
    user = update.effective_user
    if not is_admin_user(user):
        await update.message.reply_text("❌ *You are not authorized to use admin commands.*", parse_mode="Markdown")
        return
    await update.message.reply_text("⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_panel_kb())

# ---------------- Callbacks ----------------
async def to_menu_callback(update: Update, context: CallbackContext):
    q = update.callback_query; await q.answer()
    try:
        await q.message.delete()
    except:
        pass
    await q.message.reply_text("✅ *Select an option below:*", parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def help_callback(update: Update, context: CallbackContext):
    q = update.callback_query; await q.answer()
    await q.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=back_to_menu_kb())

async def referral_callback(update: Update, context: CallbackContext):
    q = update.callback_query; await q.answer()
    uid = str(q.from_user.id)
    link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    text = (f"🎯 *Invite & Earn!* \n\nShare this link:\n`{link}`\n\nWhen a *new* user joins with your link, you earn *{REFERRAL_BONUS} credits*.")
    await q.message.reply_text(text, parse_mode="Markdown", reply_markup=back_to_menu_kb())

async def daily_bonus_callback(update: Update, context: CallbackContext):
    q = update.callback_query; await q.answer()
    uid = str(q.from_user.id)
    users = ensure_user(uid)
    now = int(time.time())
    if now - users[uid].get("last_daily", 0) >= DAILY_SECONDS:
        users[uid]["credits"] = users[uid].get("credits", 0) + DAILY_BONUS_AMOUNT
        users[uid]["last_daily"] = now
        write_json(USERS_FILE, users)
        await q.message.reply_text(DAILY_CLAIMED_MSG.format(amt=DAILY_BONUS_AMOUNT), parse_mode="Markdown")
    else:
        await q.message.reply_text("⏰ *You already claimed your daily bonus today.* Try again tomorrow.", parse_mode="Markdown")
    await q.message.reply_text("🔙 Back to Menu", reply_markup=back_to_menu_kb())

# ---------------- Generic callback handler ----------------
async def generic_callback(update: Update, context: CallbackContext):
    q = update.callback_query; await q.answer()
    data = q.data

    if data in ("phone_in", "phone_pk", "aadhaar", "cnic", "ifsc", "vehicle_rc", "ff_uid", "pincode", "bin_info"):
        context.user_data["mode"] = data
        label = {
            "phone_in": "Indian Phone Number",
            "phone_pk": "Pakistan Phone Number",
            "aadhaar": "Aadhaar Number",
            "cnic": "CNIC Number",
            "ifsc": "IFSC Code",
            "vehicle_rc": "Vehicle RC Number",
            "ff_uid": "Free Fire UID",
            "pincode": "Pincode",
            "bin_info": "BIN Number (first 6 digits)"
        }.get(data, data.upper())
        
        await q.message.reply_text(f"➡️ *Send the {label} to search now.*", parse_mode="Markdown")
        return

    if data == "redeem":
        context.user_data["mode"] = "redeem_code"
        await q.message.reply_text("🎁 *Send your redeem code now.*", parse_mode="Markdown")
        return

    if data == "credits":
        users = read_json(USERS_FILE)
        cr = users.get(str(q.from_user.id), {}).get("credits", 0)
        if is_admin_user(q.from_user):
            await q.message.reply_text("💳 *Credits:* Unlimited (Admin)", parse_mode="Markdown")
        else:
            await q.message.reply_text(f"💳 *Your Credits:* *{cr}*", parse_mode="Markdown")
        return

    if data == "referral":
        await referral_callback(update, context); return
    if data == "help":
        await help_callback(update, context); return
    if data == "daily_bonus":
        await daily_bonus_callback(update, context); return
    if data == "admin_panel":
        if not is_admin_user(q.from_user):
            await q.message.reply_text("❌ *You are not authorized to use admin commands.*", parse_mode="Markdown")
            return
        await q.message.reply_text("⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_panel_kb())
        return

    await q.message.reply_text("⚠️ *Unknown action.*", parse_mode="Markdown")

# ---------------- Message handler (search + admin states) ----------------
async def message_handler(update: Update, context: CallbackContext):
    user = update.effective_user; uid = str(user.id)
    ensure_user(uid)

    # admin interactive state machine
    admin_state = context.user_data.get("admin_state")
    if admin_state:
        if not is_admin_user(user):
            await update.message.reply_text("❌ *You are not authorized for admin actions.*", parse_mode="Markdown")
            context.user_data.pop("admin_state", None)
            return
        text = update.message.text.strip()

        # BAN
        if admin_state == "ban_waiting":
            try:
                target = str(int(text)); users = read_json(USERS_FILE)
                if target not in users:
                    await update.message.reply_text("❌ *User not found.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                else:
                    users[target]["banned"] = True; write_json(USERS_FILE, users)
                    await update.message.reply_text(f"🚫 *User `{target}` has been BANNED.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                    try: await context.bot.send_message(int(target), "🚫 You have been banned by the admin.")
                    except: pass
            except:
                await update.message.reply_text("❌ *Invalid user id.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

        # UNBAN
        if admin_state == "unban_waiting":
            try:
                target = str(int(text)); users = read_json(USERS_FILE)
                if target not in users:
                    await update.message.reply_text("❌ *User not found.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                else:
                    users[target]["banned"] = False; write_json(USERS_FILE, users)
                    await update.message.reply_text(f"✅ *User `{target}` has been UNBANNED.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                    try: await context.bot.send_message(int(target), "✅ You have been unbanned by the admin.")
                    except: pass
            except:
                await update.message.reply_text("❌ *Invalid user id.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

        # DEDUCT -1
        if admin_state == "deduct_waiting":
            try:
                target = str(int(text)); users = read_json(USERS_FILE)
                if target not in users:
                    await update.message.reply_text("❌ *User not found.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                else:
                    users[target]["credits"] = max(0, users[target].get("credits", 0) - 1)
                    write_json(USERS_FILE, users)
                    newbal = users[target]["credits"]
                    await update.message.reply_text(f"➖ *Deducted 1 credit* from `{target}`. New balance: *{newbal}*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                    try:
                        await context.bot.send_message(int(target), CREDIT_DEDUCTED_MSG.format(amt=1, bal=newbal, owner=BUY_CREDITS_USERNAME), parse_mode="Markdown")
                    except: pass
            except:
                await update.message.reply_text("❌ *Invalid user id.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

        # CUSTOM DEDUCT
        if admin_state == "deduct_custom_waiting":
            try:
                parts = text.split(); target = str(int(parts[0])); amt = int(parts[1])
                users = read_json(USERS_FILE)
                if target not in users:
                    await update.message.reply_text("❌ *User not found.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                else:
                    users[target]["credits"] = max(0, users[target].get("credits", 0) - amt); write_json(USERS_FILE, users)
                    newbal = users[target]["credits"]
                    await update.message.reply_text(f"➖ *Deducted {amt} credits* from `{target}`. New balance: *{newbal}*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                    try:
                        await context.bot.send_message(int(target), CREDIT_DEDUCTED_MSG.format(amt=amt, bal=newbal, owner=BUY_CREDITS_USERNAME), parse_mode="Markdown")
                    except: pass
            except:
                await update.message.reply_text("❌ *Invalid format.* Use: `<user_id> <amount>`", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

        # USER INFO
        if admin_state == "user_info_waiting":
            try:
                target = str(int(text)); users = read_json(USERS_FILE)
                if target not in users:
                    await update.message.reply_text("❌ *User not found.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                else:
                    u = users[target]
                    info = (f"🔎 *User `{target}`*\n• Credits: *{u.get('credits',0)}*\n• Referrals: *{u.get('referrals',0)}*\n• Referred by: `{u.get('referred_by')}`")
                    await update.message.reply_text(info, parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            except:
                await update.message.reply_text("❌ *Invalid user id.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

        # GENERATE CODES
        if admin_state == "gen_codes_waiting":
            try:
                parts = text.split(); credits = int(parts[0]); count = int(parts[1])
                codes = read_json(CODES_FILE); new = []
                for _ in range(count):
                    c = gen_code(); codes[c] = {"credits": credits, "used": False}; new.append(c)
                write_json(CODES_FILE, codes)
                await update.message.reply_text("✅ *Generated codes:* \n```\n" + "\n".join(new) + "\n```", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            except:
                await update.message.reply_text("❌ *Invalid format.* Use: `<credits> <count>`", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

        # ADD CREDITS
        if admin_state == "add_credit_waiting":
            try:
                parts = text.split(); target = str(int(parts[0])); amt = int(parts[1])
                users = read_json(USERS_FILE)
                if target not in users:
                    await update.message.reply_text("❌ *User not found.*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                else:
                    users[target]["credits"] = users[target].get("credits", 0) + amt
                    write_json(USERS_FILE, users)
                    newbal = users[target]["credits"]
                    await update.message.reply_text(f"💰 *Added {amt} credits* to `{target}`. New balance: *{newbal}*", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
                    try:
                        await context.bot.send_message(int(target), CREDIT_ADDED_MSG.format(amt=amt, bal=newbal, owner=BUY_CREDITS_USERNAME), parse_mode="Markdown")
                    except: pass
            except:
                await update.message.reply_text("❌ *Invalid format.* Use: `<user_id> <amount>`", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

        # BROADCAST
        if admin_state == "broadcast_waiting":
            msg_text = text
            users = read_json(USERS_FILE)
            total = len(users); sent = 0; failed = 0
            for user_id in list(users.keys()):
                try:
                    await context.bot.send_message(int(user_id), msg_text)
                    sent += 1
                except Exception:
                    failed += 1
            await update.message.reply_text(f"📣 *Broadcast complete.*\nTotal: {total}\nSent: {sent}\nFailed: {failed}", parse_mode="Markdown", reply_markup=admin_action_back_buttons())
            context.user_data.pop("admin_state", None); return

    # normal search flows
    if is_banned(uid):
        await update.message.reply_text("❌ *You are banned from using this bot.*", parse_mode="Markdown"); return

    mode = context.user_data.get("mode")
    if not mode:
        return

    text = update.message.text.strip(); users = ensure_user(uid)

    # Redeem
    if mode == "redeem_code":
        code = text.upper(); codes = read_json(CODES_FILE)
        if code in codes and not codes[code].get("used", False):
            amt = codes[code]["credits"]; users = read_json(USERS_FILE)
            users[uid]["credits"] = users[uid].get("credits",0) + amt; codes[code]["used"] = True
            write_json(USERS_FILE, users); write_json(CODES_FILE, codes)
            await update.message.reply_text(f"✅ *Redeemed +{amt} credits.* Balance: *{users[uid]['credits']}*", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ *Invalid or already used code.*", parse_mode="Markdown")
        context.user_data.pop("mode", None); return

    # credit check & deduct
    if not is_admin_user(user):
        if users[uid].get("credits", 0) < SEARCH_COST:
            await update.message.reply_text("❌ *Not enough credits.* Redeem or contact admin.", parse_mode="Markdown")
            context.user_data.pop("mode", None); return
        users[uid]["credits"] = users[uid].get("credits", 0) - SEARCH_COST; write_json(USERS_FILE, users)

    # progress message
    try: progress_msg = await update.message.reply_text("⏳ Fetching details...")
    except: progress_msg = None

    try:
        r = None
        if mode == "phone_in":
            if not (text.isdigit() and len(text) == 10): raise Exception("Invalid Indian phone number (10 digits required)")
            r = http_get(PHONE_IN_API.format(num=text))
        elif mode == "phone_pk":
            if not text.isdigit(): raise Exception("Invalid Pakistan phone number")
            r = http_get(PHONE_PK_API.format(num=text))
        elif mode == "aadhaar":
            if not text.isdigit() or len(text) != 12: raise Exception("Invalid Aadhaar number (12 digits required)")
            r = http_get(AADHAAR_API.format(aadhaar=text))
        elif mode == "cnic":
            if not text.isdigit() or len(text) != 13: raise Exception("Invalid CNIC number (13 digits required)")
            r = http_get(CNIC_API.format(cnic=text))
        elif mode == "ifsc":
            if not text.isalnum(): raise Exception("Invalid IFSC code")
            r = http_get(IFSC_API.format(ifsc=text.upper()))
        elif mode == "vehicle_rc":
            if not text.isalnum(): raise Exception("Invalid RC number")
            r = http_get(RC_API.format(rc=text))
        elif mode == "ff_uid":
            if not text.isdigit(): raise Exception("Invalid Free Fire UID")
            r = http_get(FF_UID_API.format(uid=text))
        elif mode == "pincode":
            if not text.isdigit() or len(text) != 6: raise Exception("Invalid Pincode (6 digits required)")
            r = http_get(PINCODE_API.format(pincode=text))
        elif mode == "bin_info":
            if not text.isdigit() or len(text) < 6: raise Exception("Invalid BIN (first 6 digits required)")
            r = http_get(BIN_API.format(bin=text[:6]))
        else:
            r = None

        if not r: raise Exception("No response from API")
        data = r.json()
        
        # Format the response based on API type
        if progress_msg:
            try: await progress_msg.delete()
            except: pass
            
        if mode == "pincode":
            # Special handling for pincode API
            if isinstance(data, list) and len(data) > 0:
                post_office = data[0].get('PostOffice', [])
                if post_office:
                    office = post_office[0]
                    response_text = f"""
📍 *Pincode Information*
• Pincode: {text}
• Office: {office.get('Name', 'N/A')}
• District: {office.get('District', 'N/A')}
• State: {office.get('State', 'N/A')}
• Region: {office.get('Region', 'N/A')}
• Country: {office.get('Country', 'N/A')}
                    """
                    await update.message.reply_text(response_text.strip(), parse_mode="Markdown")
                else:
                    await update.message.reply_text("❌ No information found for this pincode.")
            else:
                await update.message.reply_text("❌ No information found for this pincode.")
        
        elif mode == "ifsc":
            # Special handling for IFSC API
            if data.get("message") == "IFSC Not Found":
                raise Exception("IFSC code not found")
            response_text = f"""
🏦 *IFSC Information*
• Bank: {data.get('BANK', 'N/A')}
• IFSC: {data.get('IFSC', 'N/A')}
• Branch: {data.get('BRANCH', 'N/A')}
• Address: {data.get('ADDRESS', 'N/A')}
• City: {data.get('CITY', 'N/A')}
• District: {data.get('DISTRICT', 'N/A')}
• State: {data.get('STATE', 'N/A')}
• MICR: {data.get('MICR', 'N/A')}
            """
            await update.message.reply_text(response_text.strip(), parse_mode="Markdown")
        
        else:
            # Generic JSON response for other APIs
            data = scrub_response(data)
            js = json.dumps(data, indent=2, ensure_ascii=False)
            if len(js) > 4000:
                js = js[:4000] + "\n... (truncated)"
            await update.message.reply_text(f"🔎 *Results:*\n```{js}```", parse_mode="Markdown")
            
    except Exception as e:
        logger.warning(f"search error {mode}: {e}")
        # refund credit
        users = read_json(USERS_FILE); users[uid]["credits"] = users[uid].get("credits", 0) + SEARCH_COST; write_json(USERS_FILE, users)
        if progress_msg:
            try: await progress_msg.delete()
            except: pass
        await update.message.reply_text(f"❌ *Error:* {str(e)}\n\n" + ERROR_REFUND_MSG, parse_mode="Markdown")
    finally:
        context.user_data.pop("mode", None)

# ---------------- Admin panel callbacks ----------------
async def admin_panel_handler(update_or_msg: Union[Update, Message], context: CallbackContext):
    if isinstance(update_or_msg, Update):
        user = update_or_msg.effective_user; target = update_or_msg.message
    else:
        user = update_or_msg.from_user; target = update_or_msg
    if not is_admin_user(user):
        await target.reply_text("❌ *You are not authorized to use admin commands.*", parse_mode="Markdown")
        return
    await target.reply_text("⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_panel_kb())

async def admin_buttons(update: Update, context: CallbackContext):
    q = update.callback_query; await q.answer()
    user = q.from_user
    if not is_admin_user(user):
        await q.answer("❌ Not authorized", show_alert=True); return
    data = q.data

    if data == "admin_stats":
        users = read_json(USERS_FILE); total = len(users); total_credits = sum(u.get("credits",0) for u in users.values())
        await q.edit_message_text(f"👥 *Total users:* {total}\n💳 *Total credits:* {total_credits}", parse_mode="Markdown", reply_markup=admin_panel_kb()); return

    if data == "admin_gen_codes":
        context.user_data["admin_state"] = "gen_codes_waiting"; await q.edit_message_text("🧾 *Generate Codes*\nSend: `<credits> <count>` (e.g. `5 10`)", parse_mode="Markdown"); return

    if data == "admin_user_info":
        context.user_data["admin_state"] = "user_info_waiting"; await q.edit_message_text("🔎 Send numeric user_id to view user's balance & referrals:"); return

    if data == "admin_backup":
        ok = send_backup_to_admins(); await q.edit_message_text("📦 Backup sent to admins." if ok else "⚠️ Backup failed or cooldown active.", reply_markup=admin_panel_kb()); return

    if data == "admin_ban":
        context.user_data["admin_state"] = "ban_waiting"; await q.edit_message_text("🚫 Send numeric user_id to BAN:", reply_markup=admin_action_back_buttons()); return

    if data == "admin_unban":
        context.user_data["admin_state"] = "unban_waiting"; await q.edit_message_text("✅ Send numeric user_id to UNBAN:", reply_markup=admin_action_back_buttons()); return

    if data == "admin_deduct":
        context.user_data["admin_state"] = "deduct_waiting"; await q.edit_message_text("➖ Send numeric user_id to deduct 1 credit:", reply_markup=admin_action_back_buttons()); return

    if data == "admin_deduct_custom":
        context.user_data["admin_state"] = "deduct_custom_waiting"; await q.edit_message_text("➖ Send: `<user_id> <amount>` (e.g. `7845479937 5`)", reply_markup=admin_action_back_buttons()); return

    if data == "admin_add_credits":
        context.user_data["admin_state"] = "add_credit_waiting"; await q.edit_message_text("➕ Send: `<user_id> <amount>` (e.g. `7845479937 10`)", parse_mode="Markdown"); return

    if data == "admin_broadcast":
        context.user_data["admin_state"] = "broadcast_waiting"; await q.edit_message_text("📣 Send the broadcast message you want to send to all users:", reply_markup=admin_action_back_buttons()); return

    if data == "to_menu":
        try: await q.message.delete()
        except: pass
        await q.message.reply_text("✅ *Select an option below:*", parse_mode="Markdown", reply_markup=main_menu_keyboard()); return

    if data == "admin_panel":
        await q.edit_message_text("⚙️ *Admin Panel*", parse_mode="Markdown", reply_markup=admin_panel_kb()); return

    await q.message.reply_text("⚠️ *Unknown admin action.*", parse_mode="Markdown", reply_markup=admin_panel_kb())

# ---------------- Setup & run ----------------
def main():
    ensure_files_exist()
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))

    # Callbacks & Admin
    app.add_handler(CallbackQueryHandler(admin_buttons, pattern="^admin_.*$"))
    app.add_handler(CallbackQueryHandler(to_menu_callback, pattern="^to_menu$"))
    app.add_handler(CallbackQueryHandler(admin_buttons, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(generic_callback))  # generic handler

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("🚀 GOKU OSINT BOT - Starting...")
    print("""
    ╔══════════════════════════════╗
    ║      GOKU OSINT BOT          ║
    ║      Created by @Gokuuuu_1     ║
    ╚══════════════════════════════╝
    """)
    app.run_polling()

if __name__ == "__main__":
    main()