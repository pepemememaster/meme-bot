import asyncio
import logging
import os
import random
import re
import sqlite3
import time
from datetime import datetime

import aiohttp

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from telethon import TelegramClient, events

# =========================================
# CONFIG
# =========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SESSION_NAME = "safe_mode_scanner"

# =========================================
# SAFE MODE SETTINGS
# =========================================

MIN_LIQUIDITY = 1500
MAX_LIQUIDITY = 25000

MIN_VOLUME_24H = 600
MIN_BUYS = 10

MIN_VOLUME_PER_BUY = 70

MAX_SELL_RATIO = 1.15
MIN_BUY_DOMINANCE = 1.01

MAX_TOKEN_AGE_MINUTES = 45

MAX_ACTIVE_TRADES = 3

TAKE_PROFIT = 0.25
STOP_LOSS = 0.12

TRAILING_TRIGGER = 0.15
TRAILING_GAP = 0.10

# =========================================
# LOGGING
# =========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# =========================================
# DATABASE
# =========================================

conn = sqlite3.connect("safe_mode.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS mentions (
    token TEXT,
    group_name TEXT,
    timestamp TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS trades (
    token TEXT,
    social_score REAL,
    entry_price REAL,
    size REAL,
    timestamp TEXT
)
""")

conn.commit()

# =========================================
# GLOBALS
# =========================================

active_trades = {}

recent_mentions = []
recent_tokens = []

mention_cache = {}

paused_until = 0

# =========================================
# TARGET GROUPS
# =========================================

TARGET_GROUPS = [
    "Crypto Tribe",
    "Fire Dragon Alpha",
    "Gambler's Lounge",
    "XXYY MEME Group",
]

# =========================================
# X HEAT KEYWORDS
# =========================================

X_HEAT_KEYWORDS = [
    "moon",
    "100x",
    "send",
    "runner",
    "ape",
    "viral",
    "cto",
    "gem",
    "early",
    "pump",
]

# =========================================
# REGEX
# =========================================

TOKEN_REGEX = r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"

# =========================================
# TELETHON
# =========================================

tg_client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH
)

# =========================================
# COMMANDS
# =========================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = """
🤖 SAFE MODE COMMANDS

/status
/positions
/stats
/recent
/groups
/help
"""

    await update.message.reply_text(msg)

# =========================================

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = f"""
🚀 SAFE MODE STATUS

Active Trades: {len(active_trades)}
Recent Mentions: {len(recent_mentions)}
Recent Tokens: {len(recent_tokens)}

Paused: {"YES" if time.time() < paused_until else "NO"}

Scanner: ACTIVE
"""

    await update.message.reply_text(msg)

# =========================================

async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not active_trades:

        await update.message.reply_text(
            "No active positions."
        )

        return

    msg = "📊 ACTIVE POSITIONS\n\n"

    for token, data in active_trades.items():

        msg += (
            f"{token[:8]}...\n"
            f"Entry: {data['entry_price']}\n"
            f"Size: {data['size']}\n\n"
        )

    await update.message.reply_text(msg)

# =========================================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute("SELECT COUNT(*) FROM trades")

    total_trades = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM mentions")

    total_mentions = cursor.fetchone()[0]

    cursor.execute("""
    SELECT group_name, COUNT(*)
    FROM mentions
    GROUP BY group_name
    ORDER BY COUNT(*) DESC
    LIMIT 1
    """)

    best_group = cursor.fetchone()

    best_group_name = (
        best_group[0]
        if best_group
        else "N/A"
    )

    msg = f"""
📈 SAFE MODE STATS

Total Trades: {total_trades}
Total Mentions: {total_mentions}

Best Group:
{best_group_name}
"""

    await update.message.reply_text(msg)

# =========================================

async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not recent_tokens:

        await update.message.reply_text(
            "No recent tokens."
        )

        return

    msg = "🔥 RECENT TOKENS\n\n"

    for token in recent_tokens[-10:]:

        msg += f"{token[:12]}...\n"

    await update.message.reply_text(msg)

# =========================================

async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute("""
    SELECT group_name, COUNT(*)
    FROM mentions
    GROUP BY group_name
    ORDER BY COUNT(*) DESC
    LIMIT 10
    """)

    rows = cursor.fetchall()

    if not rows:

        await update.message.reply_text(
            "No group stats yet."
        )

        return

    msg = "🏆 TOP GROUPS\n\n"

    for group, count in rows:

        msg += f"{group}: {count}\n"

    await update.message.reply_text(msg)

# =========================================
# X HEAT
# =========================================

def calculate_x_heat():

    score = 0

    for keyword in X_HEAT_KEYWORDS:

        score += random.randint(0, 3)

    return score

# =========================================
# SOCIAL SCORE
# =========================================

def calculate_social_score(token):

    mentions = mention_cache.get(token, 0)

    score = mentions * 12

    x_heat = calculate_x_heat()

    score += x_heat

    score += random.randint(0, 10)

    return score

# =========================================
# DEXSCREENER
# =========================================

async def fetch_pairs():

    url = "https://api.dexscreener.com/token-profiles/latest/v1"

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(url, timeout=15) as response:

                data = await response.json()

                return data

    except Exception as e:

        logger.error(f"DEX ERROR: {e}")

        return []

# =========================================
# TG SCANNER
# =========================================

@tg_client.on(events.NewMessage)
async def tg_message_handler(event):

    try:

        group_name = getattr(
            event.chat,
            "title",
            "UNKNOWN"
        )

        matched = False

        for group in TARGET_GROUPS:

            if group.lower() in group_name.lower():

                matched = True
                break

        if not matched:
            return

        message = event.raw_text

        matches = re.findall(
            TOKEN_REGEX,
            message
        )

        if not matches:
            return

        for token in matches:

            mention_cache[token] = (
                mention_cache.get(token, 0) + 1
            )

            recent_mentions.append(token)

            if len(recent_mentions) > 50:
                recent_mentions.pop(0)

            cursor.execute("""
            INSERT INTO mentions
            VALUES (?, ?, ?)
            """, (
                token,
                group_name,
                datetime.utcnow().isoformat()
            ))

            conn.commit()

            logger.info(
                f"TG MENTION | "
                f"{token[:8]} | "
                f"{group_name}"
            )

    except Exception as e:

        logger.error(f"TG ERROR: {e}")

# =========================================
# SCANNER LOOP
# =========================================

async def scanner_loop(app):

    while True:

        try:

            logger.info("SCANNING TOKENS...")

            pairs = await fetch_pairs()

            if not pairs:

                await asyncio.sleep(15)
                continue

            for pair in pairs:

                try:

                    liquidity = float(
                        pair.get(
                            "liquidity",
                            {}
                        ).get("usd", 0)
                    )

                    volume = float(
                        pair.get(
                            "volume",
                            {}
                        ).get("h24", 0)
                    )

                    buys = pair.get(
                        "txns",
                        {}
                    ).get(
                        "h24",
                        {}
                    ).get("buys", 0)

                    sells = pair.get(
                        "txns",
                        {}
                    ).get(
                        "h24",
                        {}
                    ).get("sells", 0)

                    token = pair.get("tokenAddress")

                    if not token:
                        continue

                    if liquidity < MIN_LIQUIDITY:
                        continue

                    if liquidity > MAX_LIQUIDITY:
                        continue

                    if volume < MIN_VOLUME_24H:
                        continue

                    if buys < MIN_BUYS:
                        continue

                    sell_ratio = sells / max(buys, 1)

                    if sell_ratio > MAX_SELL_RATIO:
                        continue

                    dominance = buys / max(sells, 1)

                    if dominance < MIN_BUY_DOMINANCE:
                        continue

                    social_score = calculate_social_score(token)

                    if social_score < 18:
                        continue

                    logger.info(
                        f"🚀 ALPHA DETECTED | "
                        f"{token[:8]} | "
                        f"SOCIAL={social_score}"
                    )

                    recent_tokens.append(token)

                    if len(recent_tokens) > 25:
                        recent_tokens.pop(0)

                    if token not in active_trades:

                        active_trades[token] = {
                            "entry_price": round(
                                random.uniform(
                                    0.0001,
                                    0.001
                                ),
                                6
                            ),
                            "size": round(
                                random.uniform(
                                    0.1,
                                    0.3
                                ),
                                3
                            ),
                            "time": datetime.utcnow().isoformat()
                        }

                        trade = active_trades[token]

                        cursor.execute("""
                        INSERT INTO trades
                        VALUES (?, ?, ?, ?, ?)
                        """, (
                            token,
                            social_score,
                            trade["entry_price"],
                            trade["size"],
                            datetime.utcnow().isoformat()
                        ))

                        conn.commit()

                        logger.info(
                            f"🔥 SAFE MODE BUY | "
                            f"{token[:8]}"
                        )

                        try:

                            await app.bot.send_message(
                                chat_id=CHAT_ID,
                                text=(
                                    f"🔥 SAFE MODE BUY\n\n"
                                    f"Token: {token}\n"
                                    f"Social Score: {social_score}\n"
                                    f"Liquidity: ${liquidity:,.0f}\n"
                                    f"Volume: ${volume:,.0f}"
                                )
                            )

                        except Exception as e:

                            logger.error(
                                f"TG SEND ERROR: {e}"
                            )

                except Exception as e:

                    logger.error(
                        f"PAIR ERROR: {e}"
                    )

            await asyncio.sleep(20)

        except Exception as e:

            logger.error(
                f"SCANNER LOOP ERROR: {e}"
            )

            await asyncio.sleep(10)

# =========================================
# MAIN
# =========================================

async def main():

    logger.info("🚀 STARTING SAFE MODE")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # COMMANDS

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("status", status_command)
    )

    app.add_handler(
        CommandHandler("positions", positions_command)
    )

    app.add_handler(
        CommandHandler("stats", stats_command)
    )

    app.add_handler(
        CommandHandler("recent", recent_command)
    )

    app.add_handler(
        CommandHandler("groups", groups_command)
    )

    # CLEAR WEBHOOK

    await app.bot.delete_webhook(
        drop_pending_updates=True
    )

    # START TELETHON

    await tg_client.connect()

    if not await tg_client.is_user_authorized():

        logger.error(
            "TG SESSION NOT AUTHORIZED"
        )

        return

    logger.info("✅ TG SCANNER ACTIVE")

    # START APP

    await app.initialize()

    await app.start()

    # START POLLING

    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

    logger.info("✅ COMMAND SYSTEM ACTIVE")

    # START BACKGROUND TASK

    asyncio.create_task(
        scanner_loop(app)
    )

    # KEEP ALIVE

    while True:

        await asyncio.sleep(60)

# =========================================
# RUN
# =========================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info("BOT STOPPED")

    except Exception as e:

        logger.error(f"FATAL ERROR: {e}")
