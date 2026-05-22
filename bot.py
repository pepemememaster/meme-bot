from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import asyncio
import requests
from datetime import datetime

# ====================================
# CONFIG
# ====================================

BOT_TOKEN = "8644117212:AAEBI7xTEIzc4NgYxNhhiNeluHG9nWwu0Hw"
CHAT_ID = "5034825126"

TAKE_PROFIT = 60
STOP_LOSS = -20

MIN_LIQUIDITY = 5000
MAX_LIQUIDITY = 150000

MIN_VOLUME_24H = 10000

MIN_BUYS = 20
MAX_SELL_RATIO = 0.8

CHECK_INTERVAL = 30

MAX_CONSECUTIVE_LOSSES = 5

# ====================================
# GLOBALS
# ====================================

paper_trades = 0
wins = 0
losses = 0
consecutive_losses = 0
pnl_total = 0
paused = False

active_positions = {}
trade_history = []
recent_tokens = set()

# ====================================
# STATUS
# ====================================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    total = wins + losses

    if total > 0:
        winrate = (wins / total) * 100
    else:
        winrate = 0

    text = f"""
📊 MEME SNIPER PAPER BOT

Trades: {paper_trades}

Wins: {wins}
Losses: {losses}

Win Rate: {winrate:.2f}%

PnL: {pnl_total:.2f}%

Consecutive Losses: {consecutive_losses}

Active Trades: {len(active_positions)}

Paused: {paused}
"""

    await update.message.reply_text(text)

# ====================================
# POSITIONS
# ====================================

async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not active_positions:
        await update.message.reply_text("No active positions.")
        return

    text = "📈 ACTIVE POSITIONS\n\n"

    for token, data in active_positions.items():

        pnl = (
            (data["current_price"] - data["entry_price"])
            / data["entry_price"]
        ) * 100

        text += f"""
Token: {token}

Entry: {data['entry_price']}
Current: {data['current_price']}

PnL: {pnl:.2f}%

Liquidity: ${data['liquidity']}
"""

    await update.message.reply_text(text)

# ====================================
# HISTORY
# ====================================

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not trade_history:
        await update.message.reply_text("No trade history.")
        return

    text = "📊 TRADE HISTORY\n\n"

    for trade in trade_history[-10:]:

        emoji = "✅" if trade["pnl"] > 0 else "❌"

        text += f"""
{emoji} {trade['token']}

PnL: {trade['pnl']:.2f}%
"""

    await update.message.reply_text(text)

# ====================================
# PAUSE / RESUME
# ====================================

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global paused

    paused = True

    await update.message.reply_text("⏸ Bot paused.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global paused

    paused = False

    await update.message.reply_text("✅ Bot resumed.")

# ====================================
# FETCH TOKENS
# ====================================

def fetch_tokens():

    try:

        url = "https://api.dexscreener.com/latest/dex/search/?q=SOL"

        response = requests.get(url, timeout=10)

        data = response.json()

        pairs = data.get("pairs", [])

        valid_tokens = []

        for pair in pairs:

            try:

                token_name = pair["baseToken"]["symbol"]

                if token_name in [
                    "SOL",
                    "USDC",
                    "USDT",
                    "WETH",
                    "WBTC",
                ]:
                    continue

                liquidity = pair.get("liquidity", {}).get("usd", 0)

                volume = pair.get("volume", {}).get("h24", 0)

                buys = pair.get("txns", {}).get("h24", {}).get("buys", 0)

                sells = pair.get("txns", {}).get("h24", {}).get("sells", 0)

                price = float(pair.get("priceUsd", 0))

                if sells == 0:
                    sell_ratio = 0
                else:
                    sell_ratio = sells / max(buys, 1)

                if (
                    liquidity >= MIN_LIQUIDITY
                    and liquidity <= MAX_LIQUIDITY
                    and volume >= MIN_VOLUME_24H
                    and buys >= MIN_BUYS
                    and sell_ratio <= MAX_SELL_RATIO
                    and price > 0
                ):

                    valid_tokens.append({
                        "token": token_name,
                        "price": price,
                        "liquidity": liquidity,
                        "volume": volume,
                        "buys": buys,
                        "sells": sells
                    })

            except:
                pass

        return valid_tokens

    except Exception as e:

        print("FETCH ERROR:", e)

        return []

# ====================================
# TRADING LOOP
# ====================================

async def trading_loop(app):

    global paper_trades
    global wins
    global losses
    global pnl_total
    global consecutive_losses
    global paused

    while True:

        try:

            if paused:

                await asyncio.sleep(10)
                continue

            tokens = fetch_tokens()

            if not tokens:

                await asyncio.sleep(20)
                continue

            for token_data in tokens[:5]:

                token_name = token_data["token"]

                if token_name in active_positions:
                    continue

                if token_name in recent_tokens:
                    continue

                entry_price = token_data["price"]

                liquidity = round(token_data["liquidity"], 2)

                volume = round(token_data["volume"], 2)

                buys = token_data["buys"]
                sells = token_data["sells"]

                paper_trades += 1

                active_positions[token_name] = {
                    "entry_price": entry_price,
                    "current_price": entry_price,
                    "liquidity": liquidity,
                    "buy_time": datetime.now()
                }

                recent_tokens.add(token_name)

                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"""
🟢 BUY SIGNAL

Token: {token_name}

Entry: {entry_price}

Liquidity: ${liquidity}

24H Volume: ${volume}

Buys/Sells: {buys}/{sells}

TP: +{TAKE_PROFIT}%
SL: {STOP_LOSS}%
"""
                )

                await asyncio.sleep(20)

                updated_tokens = fetch_tokens()

                current_price = entry_price

                for updated in updated_tokens:

                    if updated["token"] == token_name:

                        current_price = updated["price"]
                        break

                active_positions[token_name]["current_price"] = current_price

                pnl_percent = (
                    (current_price - entry_price)
                    / entry_price
                ) * 100

                pnl_percent = round(pnl_percent, 2)

                should_sell = False

                if pnl_percent >= TAKE_PROFIT:
                    should_sell = True

                if pnl_percent <= STOP_LOSS:
                    should_sell = True

                if should_sell:

                    if pnl_percent > 0:

                        wins += 1
                        consecutive_losses = 0

                        result = "WIN"
                        emoji = "✅"

                    else:

                        losses += 1
                        consecutive_losses += 1

                        result = "LOSS"
                        emoji = "❌"

                    pnl_total += pnl_percent

                    trade_history.append({
                        "token": token_name,
                        "pnl": pnl_percent,
                        "result": result
                    })

                    held_time = (
                        datetime.now()
                        - active_positions[token_name]["buy_time"]
                    )

                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=f"""
{emoji} SELL SIGNAL

Token: {token_name}

PnL: {pnl_percent}%

Result: {result}

Held: {held_time}
"""
                    )

                    del active_positions[token_name]

                    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:

                        paused = True

                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text="""
⛔ BOT AUTO-PAUSED

Too many consecutive losses.
"""
                        )

            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:

            print("LOOP ERROR:", e)

            await asyncio.sleep(10)

# ====================================
# POST INIT
# ====================================

async def post_init(application: Application):

    application.create_task(trading_loop(application))

# ====================================
# START
# ====================================

if __name__ == "__main__":

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))

    print("BOT RUNNING...")

    app.run_polling()
