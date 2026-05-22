
# =========================================================
# HIGH FREQUENCY AI QUANT BOT
# TELEGRAM CONTROL PANEL VERSION
# =========================================================

import os
import time
import asyncio
import requests
import random
import threading

from telegram import Bot, Update
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

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# =========================================================
# SETTINGS
# =========================================================

TAKE_PROFIT_1 = 1.20
TAKE_PROFIT_2 = 1.80

STOP_LOSS = 0.90

TRAILING_STOP = 0.22

MIN_LIQUIDITY = 35000
MIN_VOLUME = 120000

MAX_ACTIVE_TRADES = 5

SCAN_INTERVAL = 15

AI_SCORE_ENTRY = 78

# =========================================================
# GLOBAL STATS
# =========================================================

TOTAL_TRADES = 0

WINS = 0
LOSSES = 0

TOTAL_PNL = 0

ACTIVE_TRADES = {}

BOT_PAUSED = False

# =========================================================
# TELEGRAM SEND
# =========================================================

def send_telegram(msg):

    print(msg)

    if not TELEGRAM_BOT_TOKEN:
        return

    async def send():

        try:

            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg
            )

        except Exception as e:

            print(
                "Telegram Error:",
                e
            )

    asyncio.run(send())

# =========================================================
# TELEGRAM COMMANDS
# =========================================================

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

Active Trades:
{len(ACTIVE_TRADES)}

Bot Paused:
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

async def positions_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if len(ACTIVE_TRADES) == 0:

        await update.message.reply_text(
"""
📭 NO ACTIVE TRADES
"""
        )

        return

    msg = "🚀 ACTIVE TRADES\n\n"

    for symbol in ACTIVE_TRADES:

        msg += f"{symbol}\n"

    await update.message.reply_text(msg)

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

async def settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    msg = f"""
⚙️ SETTINGS

AI SCORE:
{AI_SCORE_ENTRY}

MIN LIQUIDITY:
{MIN_LIQUIDITY}

MIN VOLUME:
{MIN_VOLUME}

MAX ACTIVE:
{MAX_ACTIVE_TRADES}

SCAN:
{SCAN_INTERVAL}s

TP1:
{TAKE_PROFIT_1}

TP2:
{TAKE_PROFIT_2}

STOP LOSS:
{STOP_LOSS}
"""

    await update.message.reply_text(msg)

# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    msg = """
🤖 COMMANDS

/status
/pnl
/positions
/pause
/resume
/settings
/help
"""

    await update.message.reply_text(msg)

# =========================================================
# REAL MARKET SCAN
# =========================================================

def get_trending_tokens():

    try:

        url = (
            "https://api.dexscreener.com/"
            "latest/dex/search?q=solana"
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

        for pair in pairs[:120]:

            try:

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

                holders = random.randint(
                    300,
                    8000
                )

                smart_money = random.randint(
                    0,
                    100
                )

                token = {

                    "name": pair["baseToken"]["name"],

                    "symbol": pair["baseToken"]["symbol"],

                    "price": float(
                        pair.get(
                            "priceUsd",
                            0
                        )
                    ),

                    "liquidity": liquidity,

                    "volume": volume,

                    "buys": buys,

                    "sells": sells,

                    "price_change": price_change,

                    "holders": holders,

                    "smart_money": smart_money,

                    "fdv": float(
                        pair.get(
                            "fdv",
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

# =========================================================
# AI SCORE
# =========================================================

def calculate_score(token):

    score = 0

    if token["liquidity"] > 35000:
        score += 15

    if token["liquidity"] > 100000:
        score += 10

    if token["volume"] > 120000:
        score += 15

    if token["volume"] > 500000:
        score += 10

    if token["price_change"] > 15:
        score += 15

    if token["price_change"] > 60:
        score += 10

    if token["buys"] > token["sells"]:
        score += 15

    if token["holders"] > 500:
        score += 10

    if token["smart_money"] > 60:
        score += 10

    return min(score, 100)

# =========================================================
# FILTER
# =========================================================

def is_safe(token):

    if token["liquidity"] < MIN_LIQUIDITY:
        return False

    if token["volume"] < MIN_VOLUME:
        return False

    if token["fdv"] <= 0:
        return False

    return True

# =========================================================
# SIMULATE TRADE
# =========================================================

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

    send_telegram(
f"""
🚀 HIGH FREQUENCY ENTRY

{symbol}

AI Score:
{token['score']}

Liquidity:
${int(token['liquidity'])}

Volume:
${int(token['volume'])}

Buy:
${buy_price:.8f}
"""
    )

    current = buy_price
    highest = buy_price

    tp1_hit = False
    tp2_hit = False

    for _ in range(30):

        time.sleep(2)

        movement = random.uniform(
            0.96,
            1.14
        )

        current *= movement

        pnl = (
            (
                current / buy_price
            ) - 1
        ) * 100

        if current > highest:
            highest = current

        print(
            f"{symbol} "
            f"PnL: {pnl:.2f}%"
        )

        # STOP LOSS

        if current <= buy_price * STOP_LOSS:

            TOTAL_TRADES += 1
            LOSSES += 1
            TOTAL_PNL += pnl

            send_telegram(
f"""
🛑 STOP LOSS

{symbol}

PnL:
{pnl:.2f}%
"""
            )

            ACTIVE_TRADES.pop(symbol)

            return

        # TP1

        if (
            not tp1_hit
            and current >= buy_price * TAKE_PROFIT_1
        ):

            tp1_hit = True

            send_telegram(
f"""
✅ TP1 HIT

{symbol}

+20%
"""
            )

        # TP2

        if (
            not tp2_hit
            and current >= buy_price * TAKE_PROFIT_2
        ):

            tp2_hit = True

            send_telegram(
f"""
🔥 TP2 HIT

{symbol}

Moonbag Running
"""
            )

        # TRAILING

        trailing_price = (
            highest * (
                1 - TRAILING_STOP
            )
        )

        if (
            current <= trailing_price
            and highest > buy_price * 1.4
        ):

            TOTAL_TRADES += 1
            WINS += 1
            TOTAL_PNL += pnl

            send_telegram(
f"""
🌕 MOON EXIT

{symbol}

Final PnL:
+{pnl:.2f}%
"""
            )

            ACTIVE_TRADES.pop(symbol)

            return

    ACTIVE_TRADES.pop(symbol)

# =========================================================
# REPORT
# =========================================================

def send_report():

    winrate = 0

    if TOTAL_TRADES > 0:

        winrate = (
            WINS / TOTAL_TRADES
        ) * 100

    send_telegram(
f"""
📊 HIGH FREQUENCY REPORT

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
"""
    )

# =========================================================
# BOT LOOP
# =========================================================

def trading_loop():

    global BOT_PAUSED

    send_telegram(
"""
🤖 HIGH FREQUENCY AI STARTED

Mode:
SAFE + HIGHER VOLUME

Target:
20~50 Trades Daily
"""
    )

    while True:

        try:

            if BOT_PAUSED:

                print("BOT PAUSED")

                time.sleep(10)

                continue

            tokens = get_trending_tokens()

            for token in tokens:

                token["score"] = calculate_score(
                    token
                )

                if not is_safe(token):
                    continue

                if token["score"] >= AI_SCORE_ENTRY:

                    send_telegram(
f"""
🔥 SIGNAL

{token['symbol']}

AI Score:
{token['score']}
"""
                    )

                    simulate_trade(token)

            send_report()

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
        .token(TELEGRAM_BOT_TOKEN)
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
            "positions",
            positions_command
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
            "settings",
            settings_command
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

    print("Telegram Bot Started")

    app.run_polling()

# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
