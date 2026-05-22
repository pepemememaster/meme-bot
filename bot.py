# =========================================================
# ADVANCED REAL MARKET PAPER TRADING BOT
# REAL EXECUTION SIMULATION VERSION
# 100 TRADES DAILY MODE
# =========================================================

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

# =========================================================
# TELEGRAM
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

# =========================================================
# SETTINGS
# =========================================================

TAKE_PROFIT = 1.28
STOP_LOSS = 0.90

SCAN_INTERVAL = 8

MIN_LIQUIDITY = 25000
MIN_VOLUME = 90000

AI_SCORE_ENTRY = 75

MAX_ACTIVE_TRADES = 7
MAX_TRADES_PER_DAY = 100

# =========================================================
# REAL EXECUTION SETTINGS
# =========================================================

BUY_SLIPPAGE_MIN = 1.01
BUY_SLIPPAGE_MAX = 1.06

SELL_SLIPPAGE_MIN = 0.94
SELL_SLIPPAGE_MAX = 0.99

RUG_SELL_FAIL_CHANCE = 0.12

TRADE_TIMEOUT = 90

MAX_CONSECUTIVE_LOSSES = 4

DAILY_MAX_LOSS = -35

# =========================================================
# GLOBALS
# =========================================================

TOTAL_TRADES = 0
WINS = 0
LOSSES = 0

TOTAL_PNL = 0

ACTIVE_TRADES = {}

BOT_PAUSED = False

TODAY_TRADES = 0

CONSECUTIVE_LOSSES = 0

BLACKLIST = [
    "USDC",
    "USDT",
    "SOL",
    "BONK"
]

# =========================================================
# COMMANDS
# =========================================================

async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    winrate = 0

    if TOTAL_TRADES > 0:

        winrate = (
            WINS / TOTAL_TRADES
        ) * 100

    msg = f"""
📊 ADVANCED PAPER TRADING

Trades:
{TOTAL_TRADES}

Today:
{TODAY_TRADES}

Wins:
{WINS}

Losses:
{LOSSES}

Win Rate:
{winrate:.2f}%

PnL:
{TOTAL_PNL:.2f}%

Consecutive Losses:
{CONSECUTIVE_LOSSES}

Active Trades:
{len(ACTIVE_TRADES)}

Paused:
{BOT_PAUSED}
"""

    await update.message.reply_text(msg)

# =========================================================

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

# =========================================================

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

# =========================================================

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

# =========================================================

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

# =========================================================
# MARKET SCAN
# =========================================================

def get_tokens():

    try:

        url = (
            "https://api.dexscreener.com/latest/dex/search?q=pump"
        )

        response = requests.get(
            url,
            timeout=15
        )

        if response.status_code != 200:
            return []

        data = response.json()

        pairs = data.get("pairs", [])

        tokens = []

        for pair in pairs[:250]:

            try:

                symbol = (
                    pair["baseToken"]["symbol"]
                )

                if symbol in BLACKLIST:
                    continue

                liquidity = float(
                    pair.get(
                        "liquidity",
                        {}
                    ).get(
                        "usd",
                        0
                    )
                )

                volume = float(
                    pair.get(
                        "volume",
                        {}
                    ).get(
                        "h24",
                        0
                    )
                )

                buys = pair.get(
                    "txns",
                    {}
                ).get(
                    "h24",
                    {}
                ).get(
                    "buys",
                    0
                )

                sells = pair.get(
                    "txns",
                    {}
                ).get(
                    "h24",
                    {}
                ).get(
                    "sells",
                    0
                )

                price_change = float(
                    pair.get(
                        "priceChange",
                        {}
                    ).get(
                        "h24",
                        0
                    )
                )

                token = {

                    "symbol": symbol,

                    "price":
                    float(
                        pair.get(
                            "priceUsd",
                            0
                        )
                    ),

                    "liquidity":
                    liquidity,

                    "volume":
                    volume,

                    "buys":
                    buys,

                    "sells":
                    sells,

                    "price_change":
                    price_change

                }

                tokens.append(token)

            except:
                continue

        return tokens

    except Exception as e:

        print("SCAN ERROR:", e)

        return []

# =========================================================
# AI SCORE
# =========================================================

def calculate_score(token):

    score = 0

    if token["liquidity"] > 25000:
        score += 20

    if token["liquidity"] > 60000:
        score += 10

    if token["volume"] > 90000:
        score += 20

    if token["volume"] > 400000:
        score += 20

    if token["price_change"] > 15:
        score += 10

    if token["buys"] > token["sells"]:
        score += 20

    return min(score, 100)

# =========================================================
# FILTER
# =========================================================

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    if token["volume"] < MIN_VOLUME:
        return False

    if token["buys"] <= token["sells"]:
        return False

    return True

# =========================================================
# LIVE PRICE
# =========================================================

def get_live_price(symbol):

    try:

        url = (
            f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
        )

        response = requests.get(
            url,
            timeout=10
        )

        if response.status_code != 200:
            return None

        data = response.json()

        pairs = data.get("pairs", [])

        if not pairs:
            return None

        price = float(
            pairs[0].get(
                "priceUsd",
                0
            )
        )

        return price

    except:

        return None

# =========================================================
# ADVANCED PAPER TRADE
# =========================================================

def simulate_trade(token):

    global TOTAL_TRADES
    global WINS
    global LOSSES
    global TOTAL_PNL
    global TODAY_TRADES
    global CONSECUTIVE_LOSSES
    global BOT_PAUSED

    if TOTAL_PNL <= DAILY_MAX_LOSS:

        BOT_PAUSED = True

        print("DAILY LOSS LIMIT HIT")

        return

    if CONSECUTIVE_LOSSES >= MAX_CONSECUTIVE_LOSSES:

        BOT_PAUSED = True

        print("MAX LOSING STREAK HIT")

        return

    symbol = token["symbol"]

    if TODAY_TRADES >= MAX_TRADES_PER_DAY:
        return

    if symbol in ACTIVE_TRADES:
        return

    if len(ACTIVE_TRADES) >= MAX_ACTIVE_TRADES:
        return

    ACTIVE_TRADES[symbol] = True

    TODAY_TRADES += 1

    market_price = token["price"]

    # =====================================================
    # REAL BUY SLIPPAGE
    # =====================================================

    buy_price = (
        market_price *
        random.uniform(
            BUY_SLIPPAGE_MIN,
            BUY_SLIPPAGE_MAX
        )
    )

    highest = buy_price

    print(f"""
🚀 BUY

{symbol}

MARKET:
{market_price:.8f}

FILLED:
{buy_price:.8f}
""")

    for _ in range(TRADE_TIMEOUT):

        time.sleep(5)

        current = get_live_price(symbol)

        if current is None:
            continue

        # =================================================
        # REAL SELL SLIPPAGE
        # =================================================

        current = (
            current *
            random.uniform(
                SELL_SLIPPAGE_MIN,
                SELL_SLIPPAGE_MAX
            )
        )

        # =================================================
        # RUG FAIL SIMULATION
        # =================================================

        if current <= buy_price * 0.5:

            if random.random() <= RUG_SELL_FAIL_CHANCE:

                current *= 0.5

        if current > highest:
            highest = current

        pnl = (
            (
                current / buy_price
            ) - 1
        ) * 100

        print(f"""
{symbol}

ENTRY:
{buy_price:.8f}

CURRENT:
{current:.8f}

PNL:
{pnl:.2f}%
""")

        # =================================================
        # STOP LOSS
        # =================================================

        if current <= buy_price * STOP_LOSS:

            TOTAL_TRADES += 1
            LOSSES += 1

            CONSECUTIVE_LOSSES += 1

            TOTAL_PNL += pnl

            print(f"""
🛑 STOP LOSS

{symbol}

FINAL:
{pnl:.2f}%
""")

            ACTIVE_TRADES.pop(symbol)

            return

        # =================================================
        # TAKE PROFIT
        # =================================================

        if current >= buy_price * TAKE_PROFIT:

            TOTAL_TRADES += 1
            WINS += 1

            CONSECUTIVE_LOSSES = 0

            TOTAL_PNL += pnl

            print(f"""
✅ TAKE PROFIT

{symbol}

FINAL:
{pnl:.2f}%
""")

            ACTIVE_TRADES.pop(symbol)

            return

        # =================================================
        # MOON EXIT
        # =================================================

        if highest >= buy_price * 2:

            trailing = highest * 0.72

            if current <= trailing:

                TOTAL_TRADES += 1
                WINS += 1

                CONSECUTIVE_LOSSES = 0

                TOTAL_PNL += pnl

                print(f"""
🌕 MOON EXIT

{symbol}

FINAL:
{pnl:.2f}%
""")

                ACTIVE_TRADES.pop(symbol)

                return

    # =====================================================
    # TIME EXIT
    # =====================================================

    final_price = get_live_price(symbol)

    if final_price:

        final_price *= random.uniform(
            SELL_SLIPPAGE_MIN,
            SELL_SLIPPAGE_MAX
        )

        pnl = (
            (
                final_price / buy_price
            ) - 1
        ) * 100

        TOTAL_TRADES += 1

        if pnl > 0:

            WINS += 1

            CONSECUTIVE_LOSSES = 0

        else:

            LOSSES += 1

            CONSECUTIVE_LOSSES += 1

        TOTAL_PNL += pnl

        print(f"""
⏰ TIME EXIT

{symbol}

FINAL:
{pnl:.2f}%
""")

    ACTIVE_TRADES.pop(symbol)

# =========================================================
# LOOP
# =========================================================

def trading_loop():

    global BOT_PAUSED

    print("ADVANCED PAPER BOT STARTED")

    while True:

        try:

            if BOT_PAUSED:

                print("BOT PAUSED")

                time.sleep(30)

                continue

            tokens = get_tokens()

            for token in tokens:

                if not is_safe(token):
                    continue

                score = calculate_score(
                    token
                )

                if score >= AI_SCORE_ENTRY:

                    print(f"""
🔥 SIGNAL

{token['symbol']}

AI SCORE:
{score}
""")

                    simulate_trade(token)

            print(f"""
====================

TOTAL:
{TOTAL_TRADES}

WINS:
{WINS}

LOSSES:
{LOSSES}

PNL:
{TOTAL_PNL:.2f}%

LOSS STREAK:
{CONSECUTIVE_LOSSES}

====================
""")

            time.sleep(SCAN_INTERVAL)

        except Exception as e:

            print("MAIN ERROR:", e)

            time.sleep(10)

# =========================================================
# MAIN
# =========================================================

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

    print("TELEGRAM STARTED")

    app.run_polling()

# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
