import asyncio
import logging
import os
import random
import re
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

SESSION_NAME = "safe_mode_scanner"

# =========================================
# SAFE MODE SETTINGS
# =========================================

MIN_LIQUIDITY = 3000
MAX_LIQUIDITY = 18000

MIN_VOLUME_24H = 1800
MIN_BUYS = 20

MAX_SELL_RATIO = 1.05
MIN_BUY_DOMINANCE = 1.10

MAX_TOKEN_AGE_MINUTES = 25

MAX_ACTIVE_TRADES = 2

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
# GLOBALS
# =========================================

active_trades = {}
recent_mentions = []
recent_tokens = []

paused_until = 0

mention_cache = {}

# =========================================
# TELEGRAM CLIENT
# =========================================

tg_client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH
)

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
# TOKEN REGEX
# =========================================

TOKEN_REGEX = r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"

# =========================================
# COMMANDS
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


async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not active_trades:
        await update.message.reply_text("No active positions.")
        return

    msg = "📊 ACTIVE POSITIONS\n\n"

    for token, data in active_trades.items():
        msg += (
            f"{token[:8]}...\n"
            f"Entry: {data['entry_price']}\n"
            f"Size: {data['size']}\n\n"
        )

    await update.message.reply_text(msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = """
🤖 SAFE MODE COMMANDS

/status
/positions
/help
"""

    await update.message.reply_text(msg)

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
# SOCIAL SCORE
# =========================================

def calculate_social_score(token):

    score = 0

    mentions = mention_cache.get(token, 0)

    score += mentions * 12

    heat_keywords = [
        "alpha",
        "send",
        "moon",
        "runner",
        "gem",
        "ape",
        "100x",
        "early",
    ]

    random_heat = random.randint(0, 15)

    score += random_heat

    return score

# =========================================
# SCANNER LOOP
# =========================================

async def scanner_loop(app):

    global paused_until

    while True:

        try:

            if time.time() < paused_until:

                await asyncio.sleep(20)
                continue

            logger.info("SCANNING TOKENS...")

            pairs = await fetch_pairs()

            if not pairs:

                await asyncio.sleep(15)
                continue

            for pair in pairs:

                try:

                    liquidity = float(pair.get("liquidity", {}).get("usd", 0))
                    volume = float(pair.get("volume", {}).get("h24", 0))

                    buys = pair.get("txns", {}).get("h24", {}).get("buys", 0)
                    sells = pair.get("txns", {}).get("h24", {}).get("sells", 0)

                    token_address = pair.get("tokenAddress")

                    if not token_address:
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

                    buy_dominance = buys / max(sells, 1)

                    if buy_dominance < MIN_BUY_DOMINANCE:
                        continue

                    social_score = calculate_social_score(token_address)

                    if social_score < 18:
                        continue

                    logger.info(
                        f"🚀 ALPHA DETECTED | "
                        f"{token_address[:8]} | "
                        f"SOCIAL={social_score}"
                    )

                    recent_tokens.append(token_address)

                    if len(recent_tokens) > 20:
                        recent_tokens.pop(0)

                    if len(active_trades) >= MAX_ACTIVE_TRADES:
                        continue

                    if token_address not in active_trades:

                        active_trades[token_address] = {
                            "entry_price": random.uniform(0.0001, 0.001),
                            "size": round(random.uniform(0.1, 0.3), 3),
                            "time": datetime.utcnow().isoformat(),
                        }

                        logger.info(
                            f"🔥 SAFE MODE BUY | "
                            f"{token_address[:8]}"
                        )

                        try:

                            await app.bot.send_message(
                                chat_id=os.getenv("TELEGRAM_CHAT_ID"),
                                text=(
                                    f"🔥 SAFE MODE BUY\n\n"
                                    f"Token: {token_address}\n"
                                    f"Social Score: {social_score}"
                                )
                            )

                        except Exception as e:
                            logger.error(f"TG SEND ERROR: {e}")

                except Exception as e:

                    logger.error(f"PAIR ERROR: {e}")

            await asyncio.sleep(20)

        except Exception as e:

            logger.error(f"SCANNER LOOP ERROR: {e}")

            await asyncio.sleep(10)

# =========================================
# TG SCANNER
# =========================================

@tg_client.on(events.NewMessage)
async def tg_message_handler(event):

    try:

        group_name = getattr(event.chat, "title", "UNKNOWN")

        if TARGET_GROUPS:

            matched = False

            for group in TARGET_GROUPS:

                if group.lower() in group_name.lower():
                    matched = True
                    break

            if not matched:
                return

        message = event.raw_text

        matches = re.findall(TOKEN_REGEX, message)

        if not matches:
            return

        for token in matches:

            mention_cache[token] = mention_cache.get(token, 0) + 1

            logger.info(
                f"TG MENTION | "
                f"{token[:8]} | "
                f"{group_name}"
            )

            recent_mentions.append({
                "token": token,
                "group": group_name,
                "time": datetime.utcnow().isoformat()
            })

            if len(recent_mentions) > 50:
                recent_mentions.pop(0)

    except Exception as e:

        logger.error(f"TG SCANNER ERROR: {e}")

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

    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("positions", positions_command))
    app.add_handler(CommandHandler("help", help_command))

    # CLEAR WEBHOOK

    await app.bot.delete_webhook(drop_pending_updates=True)

    # START TELETHON

    await tg_client.connect()

    if not await tg_client.is_user_authorized():

        logger.error("TG SESSION NOT AUTHORIZED")
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

    # BACKGROUND TASKS

    asyncio.create_task(scanner_loop(app))

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
