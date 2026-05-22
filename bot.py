from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import random
from datetime import datetime

# =========================
# CONFIG
# =========================

BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

TAKE_PROFIT = 60
STOP_LOSS = -20

MAX_CONSECUTIVE_LOSSES = 5

# =========================
# GLOBAL STATS
# =========================

paper_trades = 0
wins = 0
losses = 0
consecutive_losses = 0
pnl_total = 0
paused = False

active_positions = {}
trade_history = []

# =========================
# SAMPLE TOKENS
# =========================

sample_tokens = [
    "PEPEAI",
    "BRAINCAT",
    "DOGWIFAI",
    "SIGMAGOBLIN",
    "HYPERFROG",
    "CHAOSCAT",
    "MEMEENGINE",
    "BASEDPEPE",
]

# =========================
# STATUS COMMAND
# =========================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global paper_trades
    global wins
    global losses
    global pnl_total
    global consecutive_losses
    global paused

    total = wins + losses

    if total > 0:
        winrate = (wins / total) * 100
    else:
        winrate = 0

    text = f"""
📊 ADVANCED PAPER TRADING

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

# =========================
# POSITIONS COMMAND
# =========================

async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not active_positions:
        await update.message.reply_text("No active positions.")
        return

    text = "📈 ACTIVE POSITIONS\n\n"

    for token, data in active_positions.items():

        text += f"""
Token: {token}
Entry: {data['entry_price']}
Current: {data['current_price']}
Liquidity: ${data['liquidity']}

"""

    await update.message.reply_text(text)

# =========================
# HISTORY COMMAND
# =========================

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

# =========================
# PAUSE COMMAND
# =========================

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global paused

    paused = True

    await update.message.reply_text("⏸ Bot paused.")

# =========================
# RESUME COMMAND
# =========================

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global paused

    paused = False

    await update.message.reply_text("✅ Bot resumed.")

# =========================
# SIMULATED TRADING LOOP
# =========================

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
                await asyncio.sleep(15)
                continue

            # RANDOM TOKEN

            token_name = random.choice(sample_tokens)

            entry_price = round(random.uniform(0.00001, 0.001), 8)

            liquidity = random.randint(5000, 100000)

            # BUY

            paper_trades += 1

            active_positions[token_name] = {
                "entry_price": entry_price,
                "current_price": entry_price,
                "liquidity": liquidity,
                "timestamp": datetime.now()
            }

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=f"""
🟢 BUY SIGNAL

Token: {token_name}

Entry: {entry_price}

Liquidity: ${liquidity}

TP: +{TAKE_PROFIT}%
SL: {STOP_LOSS}%
"""
            )

            # WAIT

            await asyncio.sleep(10)

            # RANDOM PNL

            pnl_percent = round(random.uniform(-35, 120), 2)

            active_positions[token_name]["current_price"] = round(
                entry_price * (1 + pnl_percent / 100),
                8
            )

            # SELL

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

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=f"""
{emoji} SELL SIGNAL

Token: {token_name}

PnL: {pnl_percent}%

Result: {result}
"""
            )

            # REMOVE POSITION

            if token_name in active_positions:
                del active_positions[token_name]

            # AUTO PAUSE

            if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:

                paused = True

                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text="""
⛔ BOT AUTO-PAUSED

Too many consecutive losses.
"""
                )

            # WAIT NEXT TRADE

            await asyncio.sleep(20)

        except Exception as e:

            print("ERROR:", e)

            await asyncio.sleep(10)

# =========================
# MAIN
# =========================

async def main():

    app = Application.builder().token(BOT_TOKEN).build()

    # COMMANDS

    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("positions", positions))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))

    # START LOOP

    asyncio.create_task(trading_loop(app))

    print("BOT RUNNING...")

    await app.run_polling()

# =========================
# START
# =========================

if __name__ == "__main__":
    asyncio.run(main())
