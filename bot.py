import asyncio
import aiohttp
import logging
import os
import re
import time
from datetime import datetime

from telethon import TelegramClient, events

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# ENV
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# =========================================================
# SAFE MODE SETTINGS
# =========================================================

MIN_LIQUIDITY = 2500
MAX_LIQUIDITY = 12000

MIN_VOLUME_24H = 2500
MIN_VOLUME_PER_BUY = 180
MIN_BUYS = 22

MAX_SELL_RATIO = 1.05
MIN_BUY_DOMINANCE = 1.08

MAX_TOKEN_AGE_MINUTES = 20

MAX_ACTIVE_TRADES = 2

TAKE_PROFIT = 0.25
STOP_LOSS = 0.12

TRAILING_STOP_ENABLED = True
TRAILING_TRIGGER = 0.15
TRAILING_GAP = 0.10

SCAN_INTERVAL = 45

AUTO_PAUSE_AFTER_LOSSES = 3
PAUSE_MINUTES = 45

SOCIAL_SCORE_THRESHOLD = 4

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
    "Fire Dragon Alpha": 3,
    "Chigga's Gambles": 2,
    "Gambler's Lounge": 2,
    "XXYY MEME Group": 1,
    "Crypto Tribe": 2,
}

# =========================================================
# GLOBALS
# =========================================================

paper_balance = 0.5

active_trades = {}
trade_history = []

recent_tokens = set()

loss_streak = 0
pause_until = 0

mention_cache = {}
x_heat_cache = {}

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# =========================================================
# TELETHON CLIENT
# =========================================================

tg_client = TelegramClient(
    "safe_mode_scanner",
    API_ID,
    API_HASH
)

# =========================================================
# TOKEN REGEX
# =========================================================

SOLANA_REGEX = r"\b[A-Za-z0-9]{32,44}\b"

# =========================================================
# TELEGRAM ALERT
# =========================================================

async def send_telegram_message(text):

    try:

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }

        async with aiohttp.ClientSession() as session:

            async with session.post(
                url,
                json=payload
            ) as response:

                await response.text()

    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# =========================================================
# DEX FETCH
# =========================================================

async def fetch_pair_data(token_address):

    url = (
        f"https://api.dexscreener.com/latest/dex/tokens/"
        f"{token_address}"
    )

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                timeout=20
            ) as response:

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

                best_pair = max(
                    sol_pairs,
                    key=lambda x: float(
                        x.get("liquidity", {}).get("usd", 0)
                    )
                )

                return best_pair

    except Exception as e:
        logging.error(f"Dex fetch error: {e}")
        return None

# =========================================================
# SAFE FILTER
# =========================================================

def token_passes_filters(pair):

    try:

        liquidity = float(
            pair.get("liquidity", {}).get("usd", 0)
        )

        volume_24h = float(
            pair.get("volume", {}).get("h24", 0)
        )

        txns = pair.get("txns", {}).get("h24", {})

        buys = int(txns.get("buys", 0))
        sells = int(txns.get("sells", 0))

        pair_created = pair.get("pairCreatedAt")

        if not pair_created:
            return False

        age_minutes = (
            time.time() - (pair_created / 1000)
        ) / 60

        if liquidity < MIN_LIQUIDITY:
            return False

        if liquidity > MAX_LIQUIDITY:
            return False

        if volume_24h < MIN_VOLUME_24H:
            return False

        if buys < MIN_BUYS:
            return False

        if sells <= 0:
            sells = 1

        sell_ratio = sells / buys

        if sell_ratio > MAX_SELL_RATIO:
            return False

        buy_dominance = buys / sells

        if buy_dominance < MIN_BUY_DOMINANCE:
            return False

        volume_per_buy = volume_24h / buys

        if volume_per_buy < MIN_VOLUME_PER_BUY:
            return False

        if age_minutes > MAX_TOKEN_AGE_MINUTES:
            return False

        return True

    except:
        return False

# =========================================================
# X HEAT SCORE
# =========================================================

def calculate_x_heat(symbol, name):

    score = 0

    bullish_keywords = [
        "launch",
        "moon",
        "ai",
        "100x",
        "gem",
        "trending",
        "viral",
    ]

    text = f"{symbol} {name}".lower()

    for word in bullish_keywords:

        if word in text:
            score += 1

    return score

# =========================================================
# SOCIAL SCORE
# =========================================================

def calculate_social_score(token_address):

    data = mention_cache.get(token_address)

    if not data:
        return 0

    groups = data["groups"]

    score = 0

    for g in groups:
        score += GROUP_WEIGHTS.get(g, 1)

    score += data["mentions"]

    return score

# =========================================================
# PAPER BUY
# =========================================================

async def paper_buy(pair, social_score):

    global active_trades

    if len(active_trades) >= MAX_ACTIVE_TRADES:
        return

    token_address = pair.get(
        "baseToken",
        {}
    ).get("address")

    if token_address in active_trades:
        return

    symbol = pair.get(
        "baseToken",
        {}
    ).get("symbol", "UNKNOWN")

    name = pair.get(
        "baseToken",
        {}
    ).get("name", "UNKNOWN")

    entry_price = float(
        pair.get("priceUsd", 0)
    )

    active_trades[token_address] = {
        "symbol": symbol,
        "name": name,
        "entry_price": entry_price,
        "highest_price": entry_price,
        "buy_time": datetime.utcnow(),
    }

    await send_telegram_message(
        f"🟢 <b>SAFE MODE BUY</b>\n\n"
        f"Name: {name}\n"
        f"Symbol: {symbol}\n"
        f"Social Score: {social_score}\n"
        f"Price: ${entry_price:.8f}"
    )

# =========================================================
# MONITOR TRADES
# =========================================================

async def monitor_trades():

    global active_trades
    global trade_history
    global loss_streak
    global pause_until

    remove_list = []

    for token_address, trade in active_trades.items():

        pair = await fetch_pair_data(token_address)

        if not pair:
            continue

        current_price = float(
            pair.get("priceUsd", 0)
        )

        entry_price = trade["entry_price"]

        pnl = (
            current_price - entry_price
        ) / entry_price

        if current_price > trade["highest_price"]:
            trade["highest_price"] = current_price

        # TAKE PROFIT

        if pnl >= TAKE_PROFIT:

            trade_history.append(pnl)

            remove_list.append(token_address)

            loss_streak = 0

            await send_telegram_message(
                f"🎯 TAKE PROFIT\n\n"
                f"{trade['symbol']}\n"
                f"PNL: +{pnl*100:.2f}%"
            )

            continue

        # STOP LOSS

        if pnl <= -STOP_LOSS:

            trade_history.append(pnl)

            remove_list.append(token_address)

            loss_streak += 1

            await send_telegram_message(
                f"🔴 STOP LOSS\n\n"
                f"{trade['symbol']}\n"
                f"PNL: {pnl*100:.2f}%"
            )

            continue

        # TRAILING STOP

        if TRAILING_STOP_ENABLED:

            highest = trade["highest_price"]

            gain_from_entry = (
                highest - entry_price
            ) / entry_price

            pullback = (
                highest - current_price
            ) / highest

            if (
                gain_from_entry >= TRAILING_TRIGGER
                and pullback >= TRAILING_GAP
            ):

                trade_history.append(pnl)

                remove_list.append(token_address)

                await send_telegram_message(
                    f"📉 TRAILING STOP\n\n"
                    f"{trade['symbol']}\n"
                    f"PNL: {pnl*100:.2f}%"
                )

    for token in remove_list:
        active_trades.pop(token, None)

    # AUTO PAUSE

    if loss_streak >= AUTO_PAUSE_AFTER_LOSSES:

        pause_until = (
            time.time() +
            (PAUSE_MINUTES * 60)
        )

        loss_streak = 0

        await send_telegram_message(
            f"⏸ AUTO PAUSE\n\n"
            f"Paused for {PAUSE_MINUTES} mins"
        )

# =========================================================
# TG SCANNER
# =========================================================

@tg_client.on(events.NewMessage)
async def handler(event):

    try:

        chat = await event.get_chat()

        group_name = getattr(chat, "title", "")

        if group_name not in TARGET_GROUPS:
            return

        text = event.raw_text

        matches = re.findall(
            SOLANA_REGEX,
            text
        )

        if not matches:
            return

        for token_address in matches:

            if token_address not in mention_cache:

                mention_cache[token_address] = {
                    "mentions": 0,
                    "groups": set(),
                    "last_seen": time.time()
                }

            mention_cache[token_address]["mentions"] += 1

            mention_cache[token_address]["groups"].add(
                group_name
            )

            logging.info(
                f"Mention detected "
                f"{token_address} "
                f"in {group_name}"
            )

    except Exception as e:
        logging.error(f"TG scanner error: {e}")

# =========================================================
# MAIN SOCIAL LOOP
# =========================================================

async def social_scanner_loop():

    global recent_tokens

    while True:

        try:

            if time.time() < pause_until:

                await asyncio.sleep(60)
                continue

            for token_address, data in list(
                mention_cache.items()
            ):

                if token_address in recent_tokens:
                    continue

                social_score = calculate_social_score(
                    token_address
                )

                if social_score < SOCIAL_SCORE_THRESHOLD:
                    continue

                pair = await fetch_pair_data(
                    token_address
                )

                if not pair:
                    continue

                if not token_passes_filters(pair):
                    continue

                symbol = pair.get(
                    "baseToken",
                    {}
                ).get("symbol", "")

                name = pair.get(
                    "baseToken",
                    {}
                ).get("name", "")

                x_heat = calculate_x_heat(
                    symbol,
                    name
                )

                final_score = social_score + x_heat

                logging.info(
                    f"FINAL SCORE {symbol}: "
                    f"{final_score}"
                )

                if final_score >= 5:

                    recent_tokens.add(token_address)

                    await send_telegram_message(
                        f"🔥 <b>ALPHA DETECTED</b>\n\n"
                        f"{name} ({symbol})\n"
                        f"Social Score: {social_score}\n"
                        f"X Heat: {x_heat}\n"
                        f"Final Score: {final_score}"
                    )

                    await paper_buy(
                        pair,
                        final_score
                    )

            await monitor_trades()

        except Exception as e:
            logging.error(f"Social loop error: {e}")

        await asyncio.sleep(SCAN_INTERVAL)

# =========================================================
# COMMANDS
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "✅ SAFE MODE V2 RUNNING"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        f"Active Trades: {len(active_trades)}\n"
        f"Tracked Tokens: {len(mention_cache)}\n"
        f"Recent Tokens: {len(recent_tokens)}\n"
        f"Trade History: {len(trade_history)}"
    )

    await update.message.reply_text(text)

async def trades(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not active_trades:

        await update.message.reply_text(
            "No active trades"
        )

        return

    msg = "📊 ACTIVE TRADES\n\n"

    for trade in active_trades.values():

        msg += (
            f"{trade['symbol']}\n"
            f"Entry: ${trade['entry_price']:.8f}\n\n"
        )

    await update.message.reply_text(msg)

# =========================================================
# MAIN
# =========================================================

async def main():

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("status", status)
    )

    app.add_handler(
        CommandHandler("trades", trades)
    )

    asyncio.create_task(
        social_scanner_loop()
    )

    await tg_client.start()

    logging.info("TG scanner connected")

    asyncio.create_task(
        tg_client.run_until_disconnected()
    )

    logging.info("SAFE MODE V2 STARTED")

    await app.run_polling(
        drop_pending_updates=True
    )

if __name__ == "__main__":
    asyncio.run(main())
