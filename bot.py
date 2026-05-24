import asyncio
import aiohttp
import logging
import os
import time
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = 45
PAPER_TRADE_AMOUNT = 100
# =========================
# UPGRADED EARLY MOMENTUM FILTERS
# =========================
MIN_LIQUIDITY = 1800
MAX_LIQUIDITY = 18000
MIN_VOLUME_24H = 700
MAX_VOLUME_24H = 45000
MIN_BUYS = 10
MAX_BUYS = 350
MAX_SELL_RATIO = 1.25
MIN_BUY_SELL_DELTA = 5
MIN_VOLUME_PER_BUY = 70
MAX_TOKEN_AGE_MINUTES = 35
MAX_VOLUME_LIQ_RATIO = 8
MIN_MOMENTUM_SCORE = 80
MAX_MOMENTUM_SCORE = 1200
# NEW EARLY MOMENTUM FILTERS
MIN_5M_VOLUME = 250
MIN_5M_BUYS = 4
# =========================
# RISK MANAGEMENT
# =========================
TAKE_PROFIT = 0.25
STOP_LOSS = 0.12
TRAILING_STOP_ENABLED = True
TRAILING_TRIGGER = 0.15
TRAILING_GAP = 0.10
# =========================
# BOT SETTINGS
# =========================
MAX_ACTIVE_TRADES = 2
COOLDOWN_MINUTES = 20
AUTO_PAUSE_AFTER_LOSSES = 3
PAUSE_DURATION_MINUTES = 45
# =========================
# GLOBALS
# =========================
active_trades = {}
trade_history = []
total_pnl = 0
wins = 0
losses = 0
consecutive_losses = 0
paused_until = 0
last_trade_time = 0
# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
# =========================
# HELPERS
# =========================
def calculate_token_age_minutes(pair_created_at):
    try:
        now_ms = int(time.time() * 1000)
        age_ms = now_ms - pair_created_at
        return age_ms / 60000
    except:
        return 9999
def calculate_momentum_score(
    buys,
    sells,
    volume_24h,
    liquidity,
    age_minutes,
    volume_5m,
    buys_5m
):
    try:
        if sells <= 0:
            sells = 1
        buy_sell_strength = buys / sells
        volume_quality = volume_24h / liquidity
        score = (
            (buys * 1.8)
            + (buy_sell_strength * 100)
            + (volume_quality * 60)
            + (volume_5m / 12)
            + (buys_5m * 8)
            - (age_minutes * 3)
        )
        return round(score, 2)
    except:
        return 0
# =========================
# TELEGRAM COMMANDS
# =========================
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "🚀 Solana Alpha Momentum Bot Online"
    )
async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "/stats - Bot statistics\n"
        "/positions - Active positions\n"
        "/pause - Pause bot\n"
        "/resume - Resume bot"
    )
async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    total_trades = wins + losses
    winrate = (
        (wins / total_trades * 100)
        if total_trades > 0 else 0
    )
    msg = (
        "📊 BOT STATS\n"
        f"Trades: {total_trades}\n"
        f"Wins: {wins}\n"
        f"Losses: {losses}\n"
        f"Winrate: {winrate:.2f}%\n"
        f"PnL: {total_pnl:.2f}%\n"
        f"Consecutive Losses: {consecutive_losses}\n"
        f"Active Positions: {len(active_trades)}"
    )
    await update.message.reply_text(msg)
async def positions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not active_trades:
        await update.message.reply_text(
            "No active positions."
        )
        return
    msg = "📌 ACTIVE POSITIONS\n\n"
    for token, trade in active_trades.items():
        current_price = trade["current_price"]
        pnl = (
            (current_price - trade["entry_price"])
            / trade["entry_price"]
        ) * 100
        msg += (
            f"{trade['symbol']}\n"
            f"PnL: {pnl:.2f}%\n"
            f"Entry: {trade['entry_price']}\n"
            f"Current: {current_price}\n\n"
        )
    await update.message.reply_text(msg)
async def pause(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    global paused_until
    paused_until = time.time() + 999999
    await update.message.reply_text(
        "⏸ Bot paused"
    )
async def resume(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    global paused_until
    paused_until = 0
    await update.message.reply_text(
        "▶️ Bot resumed"
    )
# =========================
# FETCH TOKENS
# =========================
async def fetch_pairs():
    url = "https://api.dexscreener.com/token-profiles/latest/v1"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url,
                timeout=20
            ) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                return data
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return []
async def fetch_pair_data(token_address):
    url = (
        f"https://api.dexscreener.com/latest/dex/tokens/"
        f"{token_address}"
    )
    async with aiohttp.ClientSession() as session:
        try:
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
                return pairs[0]
        except Exception as e:
            logger.error(f"Pair fetch error: {e}")
            return None
# =========================
# FILTER LOGIC
# =========================
async def analyze_token(token):
    try:
        if token.get("chainId") != "solana":
            return None
        token_address = token.get("tokenAddress")
        if not token_address:
            return None
        pair = await fetch_pair_data(token_address)
        if not pair:
            return None
        liquidity = float(
            pair.get("liquidity", {}).get("usd", 0)
        )
        volume_24h = float(
            pair.get("volume", {}).get("h24", 0)
        )
        volume_5m = float(
            pair.get("volume", {}).get("m5", 0)
        )
        buys = int(
            pair.get("txns", {})
            .get("h24", {})
            .get("buys", 0)
        )
        sells = int(
            pair.get("txns", {})
            .get("h24", {})
            .get("sells", 0)
        )
        buys_5m = int(
            pair.get("txns", {})
            .get("m5", {})
            .get("buys", 0)
        )
        price = float(pair.get("priceUsd", 0))
        pair_created_at = pair.get(
            "pairCreatedAt",
            0
        )
        age_minutes = calculate_token_age_minutes(
            pair_created_at
        )
        # =========================
        # FILTERS
        # =========================
        if liquidity < MIN_LIQUIDITY:
            return None
        if liquidity > MAX_LIQUIDITY:
            return None
        if volume_24h < MIN_VOLUME_24H:
            return None
        if volume_24h > MAX_VOLUME_24H:
            return None
        if volume_5m < MIN_5M_VOLUME:
            return None
        if buys_5m < MIN_5M_BUYS:
            return None
        if buys < MIN_BUYS:
            return None
        if buys > MAX_BUYS:
            return None
        if sells > (buys * MAX_SELL_RATIO):
            return None
        buy_sell_delta = buys - sells
        if buy_sell_delta < MIN_BUY_SELL_DELTA:
            return None
        volume_per_buy = (
            volume_24h / max(buys, 1)
        )
        if volume_per_buy < MIN_VOLUME_PER_BUY:
            return None
        if age_minutes > MAX_TOKEN_AGE_MINUTES:
            return None
        vol_liq_ratio = (
            volume_24h / liquidity
        )
        if vol_liq_ratio > MAX_VOLUME_LIQ_RATIO:
            return None
        momentum_score = calculate_momentum_score(
            buys,
            sells,
            volume_24h,
            liquidity,
            age_minutes,
            volume_5m,
            buys_5m
        )
        if momentum_score < MIN_MOMENTUM_SCORE:
            return None
        if momentum_score > MAX_MOMENTUM_SCORE:
            return None
        return {
            "token_address": token_address,
            "name": pair.get(
                "baseToken",
                {}
            ).get("name", "Unknown"),
            "symbol": pair.get(
                "baseToken",
                {}
            ).get("symbol", "???"),
            "price": price,
            "liquidity": liquidity,
            "volume": volume_24h,
            "volume_5m": volume_5m,
            "buys": buys,
            "buys_5m": buys_5m,
            "sells": sells,
            "age": age_minutes,
            "score": momentum_score,
        }
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        return None
# =========================
# PAPER BUY
# =========================
async def paper_buy(token_data, app):
    global last_trade_time
    if len(active_trades) >= MAX_ACTIVE_TRADES:
        return
    now = time.time()
    if now - last_trade_time < (
        COOLDOWN_MINUTES * 60
    ):
        return
    token_address = token_data["token_address"]
    if token_address in active_trades:
        return
    active_trades[token_address] = {
        "symbol": token_data["symbol"],
        "entry_price": token_data["price"],
        "current_price": token_data["price"],
        "highest_price": token_data["price"],
        "entry_time": time.time(),
    }
    last_trade_time = now
    msg = (
        "🚀 PAPER BUY\n\n"
        f"{token_data['name']} "
        f"({token_data['symbol']})\n\n"
        f"Entry:\n"
        f"${token_data['price']}\n\n"
        f"Liquidity:\n"
        f"${token_data['liquidity']:.0f}\n\n"
        f"24H Volume:\n"
        f"${token_data['volume']:.0f}\n\n"
        f"5M Volume:\n"
        f"${token_data['volume_5m']:.0f}\n\n"
        f"24H Buys/Sells:\n"
        f"{token_data['buys']} "
        f"/ {token_data['sells']}\n\n"
        f"5M Buys:\n"
        f"{token_data['buys_5m']}\n\n"
        f"Momentum Score:\n"
        f"{token_data['score']}\n\n"
        f"Age:\n"
        f"{token_data['age']:.1f} minutes"
    )
    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=msg
    )
# =========================
# PAPER SELL
# =========================
async def paper_sell(
    token_address,
    reason,
    app
):
    global wins
    global losses
    global total_pnl
    global consecutive_losses
    global paused_until
    trade = active_trades[token_address]
    pnl = (
        (trade["current_price"]
        - trade["entry_price"])
        / trade["entry_price"]
    )
    pnl_percent = pnl * 100
    total_pnl += pnl_percent
    if pnl > 0:
        wins += 1
        consecutive_losses = 0
    else:
        losses += 1
        consecutive_losses += 1
    if (
        consecutive_losses
        >= AUTO_PAUSE_AFTER_LOSSES
    ):
        paused_until = (
            time.time()
            + (PAUSE_DURATION_MINUTES * 60)
        )
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text="⏸ AUTO PAUSE ACTIVATED"
        )
    msg = (
        "❌ PAPER SELL\n\n"
        f"{trade['symbol']}\n\n"
        f"Reason: {reason}\n"
        f"PnL: {pnl_percent:.2f}%"
    )
    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=msg
    )
    del active_trades[token_address]
# =========================
# MANAGE POSITIONS
# =========================
async def manage_positions(app):
    tokens_to_close = []
    for token_address, trade in list(
        active_trades.items()
    ):
        pair = await fetch_pair_data(
            token_address
        )
        if not pair:
            continue
        current_price = float(
            pair.get("priceUsd", 0)
        )
        trade["current_price"] = current_price
        if current_price > trade["highest_price"]:
            trade["highest_price"] = current_price
        pnl = (
            (current_price
            - trade["entry_price"])
            / trade["entry_price"]
        )
        # STOP LOSS
        if pnl <= -STOP_LOSS:
            tokens_to_close.append(
                (
                    token_address,
                    "STOP LOSS"
                )
            )
            continue
        # TAKE PROFIT
        if pnl >= TAKE_PROFIT:
            tokens_to_close.append(
                (
                    token_address,
                    "TAKE PROFIT"
                )
            )
            continue
        # TRAILING STOP
        if TRAILING_STOP_ENABLED:
            highest_pnl = (
                (
                    trade["highest_price"]
                    - trade["entry_price"]
                )
                / trade["entry_price"]
            )
            drawdown = (
                (
                    trade["highest_price"]
                    - current_price
                )
                / trade["highest_price"]
            )
            if (
                highest_pnl
                >= TRAILING_TRIGGER
                and drawdown
                >= TRAILING_GAP
            ):
                tokens_to_close.append(
                    (
                        token_address,
                        "TRAILING STOP"
                    )
                )
    for token_address, reason in tokens_to_close:
        await paper_sell(
            token_address,
            reason,
            app
        )
# =========================
# MAIN LOOP
# =========================
async def scanner_loop(app):
    while True:
        try:
            if time.time() < paused_until:
                await asyncio.sleep(30)
                continue
            await manage_positions(app)
            pairs = await fetch_pairs()
            logger.info(
                f"Fetched {len(pairs)} tokens"
            )
            candidates = []
            for token in pairs:
                analyzed = await analyze_token(
                    token
                )
                if analyzed:
                    candidates.append(analyzed)
            candidates.sort(
                key=lambda x: x["score"],
                reverse=True
            )
            logger.info(
                f"Valid candidates: "
                f"{len(candidates)}"
            )
            # HOT TOKEN LOGS
            for token_data in candidates[:5]:
                logger.info(
                    f"HOT TOKEN | "
                    f"{token_data['symbol']} | "
                    f"Score {token_data['score']} | "
                    f"5m Buys {token_data['buys_5m']}"
                )
            # TOP 2 ONLY
            for token_data in candidates[:2]:
                await paper_buy(
                    token_data,
                    app
                )
            await asyncio.sleep(
                CHECK_INTERVAL
            )
        except Exception as e:
            logger.error(
                f"Scanner loop error: {e}"
            )
            await asyncio.sleep(15)
# =========================
# MAIN
# =========================
async def post_init(app):
    asyncio.create_task(
        scanner_loop(app)
    )
def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(
        CommandHandler("start", start)
    )
    app.add_handler(
        CommandHandler("help", help_command)
    )
    app.add_handler(
        CommandHandler("stats", stats)
    )
    app.add_handler(
        CommandHandler("positions", positions)
    )
    app.add_handler(
        CommandHandler("pause", pause)
    )
    app.add_handler(
        CommandHandler("resume", resume)
    )
    logger.info("Bot started")
    # FIX TELEGRAM CONFLICT
    app.run_polling(
        drop_pending_updates=True
    )
if __name__ == "__main__":
    main()
