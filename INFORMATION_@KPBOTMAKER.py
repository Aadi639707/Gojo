import re
import sqlite3
import requests
import telebot
import time
from telebot import types
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import os
from datetime import date
import datetime
from threading import Thread
from flask import Flask

# ========== BOT INITIALIZATION ==========
# Render dashboard par 'BOT_TOKEN' aur 'ADMIN_ID' Environment Variables mein set karein
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = telebot.TeleBot(BOT_TOKEN)

# ========== CONFIG ==========
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8401733642")) #
DB_FILE = "users.db"

# ========== CHANNEL CONFIG (Updated) ==========
CHANNEL_LINK = "https://t.me/+hoooOr15vkUzMGNl" #
CHANNEL_ID = "-1002331607869" #
SUPPORT_GROUP_LINK = "https://t.me/+bKiZqZVkbVs4ZjFh" #
SUPPORT_GROUP_ID = "-1003743864008" #

# ========== LOGGING SETUP ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DATABASE SETUP ==========
class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self._create_tables()
    
    def get_cursor(self):
        conn = sqlite3.connect(self.db_file)
        return conn.cursor()
    
    def _create_tables(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 5, 
                      last_credit_date TEXT, is_blocked INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                      query TEXT, api_type TEXT, ts TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS blocked_users
                     (user_id INTEGER PRIMARY KEY, blocked_by INTEGER, 
                      reason TEXT, blocked_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS profile_views 
                     (user_id INTEGER, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))''')
        conn.commit()
        conn.close()

db = Database(DB_FILE)

# ========== SPECIAL USERS ==========
SPECIAL_USERS = [
    {"id": 8401733642, "name": "Admin"} #
]

# ========== UTILITY FUNCTIONS ==========
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_special_user(user_id):
    return any(user["id"] == user_id for user in SPECIAL_USERS)

def init_user(user_id):
    cur = db.get_cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, credits) VALUES (?, 5)", (user_id,))
    cur.connection.commit()

def get_credits(user_id):
    cur = db.get_cursor()
    cur.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else 0

def set_credits(user_id, credits):
    cur = db.get_cursor()
    cur.execute("UPDATE users SET credits=? WHERE user_id=?", (credits, user_id))
    cur.connection.commit()

def change_credits(user_id, amount):
    cur = db.get_cursor()
    cur.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
    cur.connection.commit()
    return get_credits(user_id)

def add_history(user_id, query, api_type):
    cur = db.get_cursor()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO history (user_id, query, api_type, ts) VALUES (?, ?, ?, ?)",
                (user_id, query, api_type, ts))
    cur.connection.commit()

def refund_credit(user_id):
    cur = db.get_cursor()
    cur.execute("UPDATE users SET credits = credits + 1 WHERE user_id=?", (user_id,))
    cur.connection.commit()

def is_user_blocked(user_id):
    cur = db.get_cursor()
    cur.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row and row[0] == 1

def check_and_give_daily_credits(user_id):
    today = date.today().isoformat()
    cur = db.get_cursor()
    cur.execute("SELECT last_credit_date FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    last_date = row[0] if row else None
    
    if last_date != today:
        cur.execute("UPDATE users SET credits=credits+10, last_credit_date=? WHERE user_id=?", (today, user_id))
        cur.connection.commit()
        return True
    return False

def clean(text):
    if text is None: return None
    text = str(text).strip()
    if not text or text.lower() in ['null', 'none', 'nil', 'nan', '']: return None
    return text

# ========== CHANNEL FORCE JOIN ==========
def check_channel_membership(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

def send_channel_join_message(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    keyboard.add(types.InlineKeyboardButton("✅ I've Joined", callback_data="check_join"))
    
    bot.send_message(chat_id, "🔒 <b>Channel Membership Required</b>\n\nPlease join our channel to use this bot.", reply_markup=keyboard, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    if check_channel_membership(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Verification successful!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        cmd_start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Join first!", show_alert=True)

# ========== COMMANDS ==========
@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    init_user(uid)
    
    if not is_admin(uid) and not check_channel_membership(uid):
        send_channel_join_message(m.chat.id)
        return

    check_and_give_daily_credits(uid)
    credits = get_credits(uid)
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("👤 Telegram ID Info", "🇮🇳 India Number Info")
    kb.add("📮 Pincode Info", "🚘 Vehicle Info")
    kb.add("🎮 Free Fire Info", "💳 My Credits")
    kb.add("🎁 Get Daily Credits", "📞 Contact Admin")
    if is_admin(uid): kb.add("⚙️ Admin Panel")

    bot.send_message(m.chat.id, f"Welcome! Your Credits: {credits}", reply_markup=kb)

# ========== WEB SERVER FOR RENDER ==========
app = Flask('app')

@app.route('/')
def home():
    return "Bot is running on Render!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ========== START BOT ==========
if __name__ == "__main__":
    # Flask ko alag thread mein chalayein Render ke liye
    Thread(target=run_flask).start()
    
    logger.info("Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)
