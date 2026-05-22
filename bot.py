import os
import time
import random
import threading
import requests

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# ======================================================
# SETTINGS
# ======================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)

TAKE_PROFIT = 1.20
STOP_LOSS = 0.90

SCAN_INTERVAL = 15

MIN_LIQUIDITY = 35000
MIN_VOLUME = 120000

AI_SCORE_ENTRY = 78

MAX_ACTIVE_TRADES = 5

# ======================================================
# GLOBALS
# ======================================================

TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

TOTAL_PNL = 0

ACTIVE_TRADES = {}

BOT_PAUSED = False

# ======================================================
# TELEGRAM COMMANDS
# ======================================================

async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global TOTAL_TRADES
    global WINS
    global LOSSES
    global TOTAL_PNL

    winrate = 0

    if TOTAL_TRADES > 0:

        winrate = (
            WINS / TOTAL_TRADES
        ) * 100

    msg = f"""
📊 BOT STATUS

Trades:
{TOTAL_TRADES}

Wins:
{WINS}

Losses:
{LOSSES}

Win Rate:
{winrate:.2f}%

PnL:
{TOTAL_PNL:.2f}%

Active:
{len(ACTIVE_TRADES)}

Paused:
{BOT_PAUSED}
"""

    await update.message.reply_text(msg)

# ======================================================

async def pnl_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
f"""
💰 CURRENT PNL

PnL:
{TOTAL_PNL:.2f}%

Trades:
{TOTAL_TRADES}
"""
    )

# ======================================================

async def pause_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global BOT_PAUSED

    BOT_PAUSED = True

    await update.message.reply_text(
"""
⏸ BOT PAUSED
"""
    )

# ======================================================

async def resume_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global BOT_PAUSED

    BOT_PAUSED = False

    await update.message.reply_text(
"""
▶️ BOT RESUMED
"""
    )

# ======================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
"""
🤖 COMMANDS

/status
/pnl
/pause
/resume
/help
"""
    )

# ======================================================
# MARKET SCAN
# ======================================================

def get_tokens():

    try:

        url = (
            "https://api.dexscreener.com/"
            "latest/dex/search?q=solana"
        )

        response = requests.get(
            url,
            timeout=10
        )

        if response.status_code != 200:
            return []

        data = response.json()

        pairs = data.get("pairs", [])

        tokens = []

        for pair in pairs[:120]:

            try:

                token = {

                    "symbol":
                    pair["baseToken"]["symbol"],

                    "price":
                    float(
                        pair.get(
                            "priceUsd",
                            0
                        )
                    ),

                    "liquidity":
                    float(
                        pair.get(
                            "liquidity",
                            {}
                        ).get(
                            "usd",
                            0
                        )
                    ),

                    "volume":
                    float(
                        pair.get(
                            "volume",
                            {}
                        ).get(
                            "h24",
                            0
                        )
                    )

                }

                tokens.append(token)

            except:
                continue

        return tokens

    except Exception as e:

        print("SCAN ERROR:", e)

        return []

# ======================================================
# AI SCORE
# ======================================================

def calculate_score(token):

    score = 0

    if token["liquidity"] > 35000:
        score += 40

    if token["volume"] > 120000:
        score += 40

    score += random.randint(0, 20)

    return score

# ======================================================
# SIMULATE TRADE
# ======================================================

def simulate_trade(token):

    global TOTAL_TRADES
    global WINS
    global LOSSES
    global TOTAL_PNL

    symbol = token["symbol"]

    if symbol in ACTIVE_TRADES:
        return

    if len(ACTIVE_TRADES) >= MAX_ACTIVE_TRADES:
        return

    ACTIVE_TRADES[symbol] = True

    buy_price = token["price"]

    print(f"BUY {symbol}")

    current = buy_price

    for _ in range(20):

        time.sleep(2)

        movement = random.uniform(
            0.95,
            1.12
        )

        current *= movement

        pnl = (
            (
                current / buy_price
            ) - 1
        ) * 100

        print(
            f"{symbol} "
            f"PnL: {pnl:.2f}%"
        )

        if current >= buy_price * TAKE_PROFIT:

            TOTAL_TRADES += 1
            WINS += 1

            TOTAL_PNL += pnl

            print(f"TP HIT {symbol}")

            ACTIVE_TRADES.pop(symbol)

            return

        if current <= buy_price * STOP_LOSS:

            TOTAL_TRADES += 1
            LOSSES += 1

            TOTAL_PNL += pnl

            print(f"SL HIT {symbol}")

            ACTIVE_TRADES.pop(symbol)

            return

    ACTIVE_TRADES.pop(symbol)

# ======================================================
# TRADING LOOP
# ======================================================

def trading_loop():

    global BOT_PAUSED

    print("BOT STARTED")

    while True:

        try:

            if BOT_PAUSED:

                print("BOT PAUSED")

                time.sleep(10)

                continue

            tokens = get_tokens()

            for token in tokens:

                if (
                    token["liquidity"]
                    < MIN_LIQUIDITY
                ):
                    continue

                if (
                    token["volume"]
                    < MIN_VOLUME
                ):
                    continue

                score = calculate_score(
                    token
                )

                if score >= AI_SCORE_ENTRY:

                    simulate_trade(token)

            print(
                f"Trades: {TOTAL_TRADES}"
            )

            print(
                f"PnL: {TOTAL_PNL:.2f}%"
            )

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("MAIN ERROR:", e)

            time.sleep(10)

# ======================================================
# MAIN
# ======================================================

def main():

    app = (
        ApplicationBuilder()
        .token(
            TELEGRAM_BOT_TOKEN
        )
        .build()
    )

    app.add_handler(
        CommandHandler(
            "status",
            status_command
        )
    )

    app.add_handler(
        CommandHandler(
            "pnl",
            pnl_command
        )
    )

    app.add_handler(
        CommandHandler(
            "pause",
            pause_command
        )
    )

    app.add_handler(
        CommandHandler(
            "resume",
            resume_command
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    trading_thread = threading.Thread(
        target=trading_loop
    )

    trading_thread.start()

    print("Telegram Started")

    app.run_polling()

# ======================================================
# START
# ======================================================

if __name__ == "__main__":
    main()
