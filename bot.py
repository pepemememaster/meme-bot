# =========================================================
# SAFE MODE V4 PROFESSIONAL ULTRA
# TG + X + SMART WALLET + AI SCORE + ANTI RUG
# PAPER TRADE ONLY
# OVERWRITE READY
# =========================================================

import asyncio
import aiohttp
import logging
import os
import re
import time
import sqlite3
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from telethon import TelegramClient, events

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

API_ID = 31204558
API_HASH = "a9b21092d21b1d5892e9f0118045dac2"

TG_SESSION = "safe_mode_scanner"

# =========================================================
# SAFE MODE SETTINGS
# =========================================================

MIN_LIQUIDITY = 3500
MAX_LIQUIDITY = 25000

MIN_VOLUME_24H = 4000
MIN_VOLUME_5M = 500

MIN_BUYS_24H = 30
MIN_BUYS_5M = 6

MAX_SELL_RATIO = 0.95
MIN_BUY_DOMINANCE = 1.15

MIN_VOLUME_PER_BUY = 200

MAX_TOKEN_AGE_MINUTES = 35

MAX_ACTIVE_TRADES = 2

TAKE_PROFIT = 0.30
STOP_LOSS = 0.12

TRAILING_STOP_TRIGGER = 0.20
TRAILING_STOP_GAP = 0.10

AUTO_PAUSE_AFTER_LOSSES = 3
AUTO_PAUSE_MINUTES = 60

FINAL_SCORE_THRESHOLD = 80

# =========================================================
# TG GROUPS
# =========================================================

TARGET_GROUPS = [
    "Fire Dragon Alpha",
    "Chigga's Gambles",
    "Gambler's Lounge",
    "XXYY MEME Group",
    "Crypto Tribe",
]

GROUP_WEIGHTS = {
    "Fire Dragon Alpha": 5,
    "Chigga's Gambles": 4,
    "Gambler's Lounge": 3,
    "XXYY MEME Group": 2,
    "Crypto Tribe": 3,
}

# =========================================================
# X HEAT
# =========================================================

X_HEAT_KEYWORDS = [
    "100x",
    "moon",
    "runner",
    "gem",
    "viral",
    "cto",
    "pump",
    "ai",
    "early",
    "alpha",
    "send",
    "next",
]

# =========================================================
# SMART WALLET TRACKING
# =========================================================

SMART_WALLET_KEYWORDS = [
    "smart money",
    "ape",
    "loaded",
    "whale",
    "alpha",
    "early",
]

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# =========================================================
# SQLITE DATABASE
# =========================================================

conn = sqlite3.connect(
    "safe_mode_v4.db"
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS trades (
    token TEXT,
    entry REAL,
    exit REAL,
    pnl REAL,
    result TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    token TEXT
)
""")

conn.commit()

# =========================================================
# GLOBALS
# =========================================================

active_trades = {}

mention_cache = {}
recent_tokens = set()

trade_history = []

paused_until = 0

# =========================================================
# TG CLIENT
# =========================================================

tg_client = TelegramClient(
    TG_SESSION,
    API_ID,
    API_HASH
)

# =========================================================
# TOKEN REGEX
# =========================================================

TOKEN_REGEX = r"\b[A-Za-z0-9]{32,44}\b"

# =========================================================
# HELPERS
# =========================================================

def is_paused():
    return time.time() < paused_until

def extract_tokens(text):
    return re.findall(TOKEN_REGEX, text)

def sell_ratio(buys, sells):
    if buys <= 0:
        return 999
    return sells / buys

def buy_dominance(buys, sells):
    if sells <= 0:
        return buys
    return buys / sells

# =========================================================
# TELEGRAM ALERT
# =========================================================

async def send_alert(message):

    try:

        url = (
            f"https://api.telegram.org/bot"
            f"{BOT_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": TG_CHAT_ID,
            "text": message,
        }

        async with aiohttp.ClientSession() as session:

            async with session.post(
                url,
                json=payload
            ):
                pass

    except Exception as e:
        logging.error(f"alert error: {e}")

# =========================================================
# TG SCANNER
# =========================================================

@tg_client.on(events.NewMessage)
async def tg_scanner(event):

    try:

        group_name = getattr(
            event.chat,
            "title",
            "Unknown"
        )

        matched = False

        for g in TARGET_GROUPS:

            if g.lower() in group_name.lower():
                matched = True
                break

        if not matched:
            return

        text = event.raw_text

        tokens = extract_tokens(text)

        if not tokens:
            return

        for token in tokens:

            if token not in mention_cache:

                mention_cache[token] = {
                    "mentions": 0,
                    "groups": set(),
                    "smart_wallet": 0,
                    "ai_score": 0,
                    "last_seen": time.time(),
                }

            mention_cache[token]["mentions"] += 1

            mention_cache[token]["groups"].add(
                group_name
            )

            mention_cache[token]["last_seen"] = (
                time.time()
            )

            # SMART WALLET DETECT

            lowered = text.lower()

            for kw in SMART_WALLET_KEYWORDS:

                if kw in lowered:

                    mention_cache[token][
                        "smart_wallet"
                    ] += 5

            # AI SENTIMENT SCORE

            positive_words = [
                "strong",
                "bullish",
                "runner",
                "early",
                "send",
                "moon",
                "alpha",
                "good",
            ]

            for p in positive_words:

                if p in lowered:
                    mention_cache[token][
                        "ai_score"
                    ] += 2

            logging.info(
                f"TG MENTION | "
                f"{token} | "
                f"{group_name}"
            )

    except Exception as e:
        logging.error(f"tg_scanner error: {e}")

# =========================================================
# SOCIAL SCORE
# =========================================================

def social_score(token):

    data = mention_cache.get(token)

    if not data:
        return 0

    score = 0

    score += data["mentions"] * 4

    for g in data["groups"]:
        score += GROUP_WEIGHTS.get(g, 1)

    score += data["smart_wallet"]

    score += data["ai_score"]

    return score

# =========================================================
# X HEAT
# =========================================================

def x_heat(symbol, name):

    text = f"{symbol} {name}".lower()

    score = 0

    for kw in X_HEAT_KEYWORDS:

        if kw in text:
            score += 3

    return score

# =========================================================
# FETCH PAIR
# =========================================================

async def fetch_pair(token):

    try:

        url = (
            f"https://api.dexscreener.com/"
            f"latest/dex/tokens/{token}"
        )

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                timeout=20
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                pairs = data.get("pairs", [])

                if not pairs:
                    return None

                sol_pairs = [
                    p for p in pairs
                    if p.get("chainId") == "solana"
                ]

                if not sol_pairs:
                    return None

                best = max(
                    sol_pairs,
                    key=lambda x: float(
                        x.get(
                            "liquidity",
                            {}
                        ).get("usd", 0)
                    )
                )

                return best

    except Exception as e:
        logging.error(f"fetch_pair error: {e}")

    return None

# =========================================================
# RUG CHECK
# =========================================================

def anti_rug(pair):

    try:

        liquidity = float(
            pair["liquidity"]["usd"]
        )

        fdv = float(
            pair.get("fdv", 0)
        )

        if liquidity < MIN_LIQUIDITY:
            return False

        if liquidity > MAX_LIQUIDITY:
            return False

        if fdv > 5000000:
            return False

        return True

    except:
        return False

# =========================================================
# MOMENTUM SCORE
# =========================================================

def momentum_score(pair):

    try:

        volume24 = float(
            pair["volume"]["h24"]
        )

        volume5 = float(
            pair["volume"]["m5"]
        )

        buys24 = int(
            pair["txns"]["h24"]["buys"]
        )

        sells24 = int(
            pair["txns"]["h24"]["sells"]
        )

        buys5 = int(
            pair["txns"]["m5"]["buys"]
        )

        dominance = buy_dominance(
            buys24,
            sells24
        )

        score = 0

        score += min(volume24 / 1000, 25)

        score += min(volume5 / 50, 25)

        score += min(buys24 / 4, 20)

        score += min(buys5 * 2, 15)

        score += min(dominance * 10, 15)

        return round(score, 2)

    except:
        return 0

# =========================================================
# FILTERS
# =========================================================

def passes_filters(pair):

    try:

        liquidity = float(
            pair["liquidity"]["usd"]
        )

        volume24 = float(
            pair["volume"]["h24"]
        )

        volume5 = float(
            pair["volume"]["m5"]
        )

        buys24 = int(
            pair["txns"]["h24"]["buys"]
        )

        buys5 = int(
            pair["txns"]["m5"]["buys"]
        )

        sells24 = int(
            pair["txns"]["h24"]["sells"]
        )

        created = pair.get(
            "pairCreatedAt",
            0
        )

        age_minutes = (
            time.time() -
            (created / 1000)
        ) / 60

        ratio = sell_ratio(
            buys24,
            sells24
        )

        dominance = buy_dominance(
            buys24,
            sells24
        )

        volume_per_buy = (
            volume24 / max(buys24, 1)
        )

        if volume24 < MIN_VOLUME_24H:
            return False

        if volume5 < MIN_VOLUME_5M:
            return False

        if buys24 < MIN_BUYS_24H:
            return False

        if buys5 < MIN_BUYS_5M:
            return False

        if ratio > MAX_SELL_RATIO:
            return False

        if dominance < MIN_BUY_DOMINANCE:
            return False

        if volume_per_buy < MIN_VOLUME_PER_BUY:
            return False

        if age_minutes > MAX_TOKEN_AGE_MINUTES:
            return False

        return True

    except:
        return False

# =========================================================
# DYNAMIC POSITION SCORE
# =========================================================

def dynamic_position_size(score):

    if score >= 120:
        return 1.5

    if score >= 100:
        return 1.2

    return 1.0

# =========================================================
# PAPER BUY
# =========================================================

async def paper_buy(pair, final_score):

    token = pair["baseToken"]["symbol"]
    address = pair["baseToken"]["address"]

    if address in active_trades:
        return

    if len(active_trades) >= MAX_ACTIVE_TRADES:
        return

    entry = float(pair["priceUsd"])

    position_size = dynamic_position_size(
        final_score
    )

    active_trades[address] = {
        "token": token,
        "entry": entry,
        "highest": entry,
        "size": position_size,
        "buy_time": time.time(),
    }

    await send_alert(
        f"🔥 SAFE MODE V4 BUY\n\n"
        f"{token}\n"
        f"Score: {final_score}\n"
        f"Size: {position_size}x\n"
        f"Entry: ${entry}"
    )

# =========================================================
# SAVE TRADE
# =========================================================

def save_trade(
    token,
    entry,
    exit_price,
    pnl,
    result
):

    cursor.execute(
        """
        INSERT INTO trades
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            entry,
            exit_price,
            pnl,
            result,
            str(datetime.utcnow())
        )
    )

    conn.commit()

# =========================================================
# MANAGE TRADES
# =========================================================

async def manage_trades():

    global paused_until

    while True:

        try:

            remove = []

            for address, trade in active_trades.items():

                pair = await fetch_pair(address)

                if not pair:
                    continue

                current = float(
                    pair["priceUsd"]
                )

                entry = trade["entry"]

                pnl = (
                    current - entry
                ) / entry

                if current > trade["highest"]:
                    trade["highest"] = current

                pullback = (
                    trade["highest"] - current
                ) / trade["highest"]

                if pnl >= TAKE_PROFIT:

                    await send_alert(
                        f"🎯 TAKE PROFIT\n\n"
                        f"{trade['token']}\n"
                        f"PNL: {round(pnl*100,2)}%"
                    )

                    save_trade(
                        trade["token"],
                        entry,
                        current,
                        pnl,
                        "TP"
                    )

                    trade_history.append(1)

                    remove.append(address)

                    continue

                if pnl <= -STOP_LOSS:

                    await send_alert(
                        f"🔴 STOP LOSS\n\n"
                        f"{trade['token']}\n"
                        f"PNL: {round(pnl*100,2)}%"
                    )

                    save_trade(
                        trade["token"],
                        entry,
                        current,
                        pnl,
                        "SL"
                    )

                    trade_history.append(-1)

                    remove.append(address)

                    continue

                if (
                    pnl >= TRAILING_STOP_TRIGGER and
                    pullback >= TRAILING_STOP_GAP
                ):

                    await send_alert(
                        f"📉 TRAILING STOP\n\n"
                        f"{trade['token']}\n"
                        f"PNL: {round(pnl*100,2)}%"
                    )

                    save_trade(
                        trade["token"],
                        entry,
                        current,
                        pnl,
                        "TRAIL"
                    )

                    trade_history.append(1)

                    remove.append(address)

            for r in remove:
                active_trades.pop(r, None)

            recent = trade_history[
                -AUTO_PAUSE_AFTER_LOSSES:
            ]

            if (
                len(recent) >=
                AUTO_PAUSE_AFTER_LOSSES and
                all(x == -1 for x in recent)
            ):

                paused_until = (
                    time.time() +
                    AUTO_PAUSE_MINUTES * 60
                )

                await send_alert(
                    f"⏸ AUTO PAUSE\n\n"
                    f"{AUTO_PAUSE_MINUTES} mins"
                )

            await asyncio.sleep(20)

        except Exception as e:
            logging.error(f"manage error: {e}")

            await asyncio.sleep(10)

# =========================================================
# MAIN LOOP
# =========================================================

async def scanner_loop():

    while True:

        try:

            if is_paused():

                logging.warning(
                    "BOT PAUSED"
                )

                await asyncio.sleep(30)

                continue

            for token in list(
                mention_cache.keys()
            ):

                if token in recent_tokens:
                    continue

                pair = await fetch_pair(token)

                if not pair:
                    continue

                if not anti_rug(pair):
                    continue

                if not passes_filters(pair):
                    continue

                symbol = pair[
                    "baseToken"
                ].get("symbol", "")

                name = pair[
                    "baseToken"
                ].get("name", "")

                social = social_score(token)

                xscore = x_heat(
                    symbol,
                    name
                )

                momentum = momentum_score(
                    pair
                )

                final = (
                    social +
                    xscore +
                    momentum
                )

                logging.info(
                    f"PASS | "
                    f"{symbol} | "
                    f"Social={social} | "
                    f"X={xscore} | "
                    f"Momentum={momentum} | "
                    f"Final={final}"
                )

                if final >= FINAL_SCORE_THRESHOLD:

                    recent_tokens.add(token)

                    await send_alert(
                        f"🚀 ALPHA DETECTED\n\n"
                        f"{symbol}\n"
                        f"Social: {social}\n"
                        f"X Heat: {xscore}\n"
                        f"Momentum: {momentum}\n"
                        f"Final: {final}"
                    )

                    await paper_buy(
                        pair,
                        final
                    )

            await asyncio.sleep(15)

        except Exception as e:
            logging.error(
                f"scanner_loop error: {e}"
            )

            await asyncio.sleep(10)

# =========================================================
# COMMANDS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    msg = (
        f"SAFE MODE V4 ULTRA\n\n"
        f"Trades: {len(active_trades)}\n"
        f"Mentions: {len(mention_cache)}\n"
        f"Recent: {len(recent_tokens)}\n"
        f"Paused: {is_paused()}"
    )

    await update.message.reply_text(msg)

async def positions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not active_trades:

        await update.message.reply_text(
            "No active trades"
        )

        return

    text = "📊 ACTIVE TRADES\n\n"

    for trade in active_trades.values():

        text += (
            f"{trade['token']}\n"
            f"Entry: {trade['entry']}\n"
            f"Size: {trade['size']}x\n\n"
        )

    await update.message.reply_text(text)

# =========================================================
# MAIN
# =========================================================

async def main():

    logging.info(
        "STARTING SAFE MODE V4 ULTRA"
    )

    await tg_client.connect()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "status",
            status
        )
    )

    app.add_handler(
        CommandHandler(
            "positions",
            positions
        )
    )

    asyncio.create_task(
        scanner_loop()
    )

    asyncio.create_task(
        manage_trades()
    )

    logging.info(
        "TG SCANNER ACTIVE"
    )

    await app.initialize()

    await app.start()

    await app.updater.start_polling(
        drop_pending_updates=True
    )

    while True:
        await asyncio.sleep(3600)

# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
