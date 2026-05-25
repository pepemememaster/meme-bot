# =========================================
# SAFE MODE V7
# HYBRID PUMPFUN + DEX + TG SCANNER
# =========================================
import asyncio
import logging
import os
import random
import re
import sqlite3
import time
from collections import defaultdict
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
# SAFE ENGINE SETTINGS
# =========================================
MIN_LIQUIDITY = 4000
MAX_LIQUIDITY = 150000
MIN_VOLUME_24H = 1200
MIN_BUYS = 10
MIN_VOLUME_PER_BUY = 70
MAX_SELL_RATIO = 1.15
MIN_BUY_DOMINANCE = 1.01
MAX_TOKEN_AGE_MINUTES = 45
MAX_ACTIVE_TRADES = 3
# =========================================
# EARLY ENGINE SETTINGS
# =========================================
EARLY_MIN_LIQUIDITY = 2500
EARLY_MIN_VOLUME = 600
EARLY_MIN_BUYS = 3
EARLY_ALERT_SCORE = 10
SAFE_BUY_SCORE = 18
# =========================================
# RISK
# =========================================
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
mention_cache = defaultdict(int)
mention_timestamps = defaultdict(list)
volume_history = {}
early_alerted = set()
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
🤖 SAFE MODE V7
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
🚀 SAFE MODE V7
Active Trades: {len(active_trades)}
Recent Mentions: {len(recent_mentions)}
Recent Tokens: {len(recent_tokens)}
Early Alerts: {len(early_alerted)}
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
    msg = f"""
📈 SAFE MODE STATS
Total Trades: {total_trades}
Total Mentions: {total_mentions}
Early Alerts:
{len(early_alerted)}
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
# SOCIAL SCORE
# =========================================
def calculate_x_heat():
    score = 0
    for keyword in X_HEAT_KEYWORDS:
        score += random.randint(0, 2)
    return score
# =========================================
def calculate_mention_velocity(token):
    now = time.time()
    timestamps = mention_timestamps[token]
    recent = [
        t for t in timestamps
        if now - t <= 300
    ]
    mention_timestamps[token] = recent
    return len(recent)
# =========================================
def calculate_volume_acceleration(token, current_volume):
    if token not in volume_history:
        volume_history[token] = {
            "volume": current_volume,
            "time": time.time()
        }
        return 1
    old_volume = volume_history[token]["volume"]
    growth = current_volume / max(old_volume, 1)
    volume_history[token] = {
        "volume": current_volume,
        "time": time.time()
    }
    return growth
# =========================================
def calculate_social_score(token, volume_growth):
    mentions = mention_cache[token]
    velocity = calculate_mention_velocity(token)
    x_heat = calculate_x_heat()
    score = 0
    score += mentions * 4
    score += velocity * 5
    score += x_heat
    if volume_growth > 1.5:
        score += 6
    if volume_growth > 2:
        score += 10
    if volume_growth > 4:
        score += 14
    return score
# =========================================
# PUMPFUN
# =========================================
async def fetch_pumpfun_tokens():
    url = "https://frontend-api.pump.fun/coins/for-you"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=15
            ) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                logger.info(
                    f"PUMPFUN TOKENS: {len(data)}"
                )
                return data
    except Exception as e:
        logger.error(
            f"PUMPFUN ERROR: {e}"
        )
        return []
# =========================================
# DEXSCREENER
# =========================================
async def fetch_pairs():
    urls = [
        "https://api.dexscreener.com/token-profiles/latest/v1",
        "https://api.dexscreener.com/latest/dex/search?q=solana",
    ]
    all_pairs = []
    try:
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(
                        url,
                        timeout=15
                    ) as response:
                        if response.status != 200:
                            continue
                        data = await response.json()
                        if isinstance(data, list):
                            all_pairs.extend(data)
                        elif isinstance(data, dict):
                            pairs = data.get(
                                "pairs",
                                []
                            )
                            for pair in pairs:
                                token_address = (
                                    pair.get(
                                        "baseToken",
                                        {}
                                    ).get(
                                        "address"
                                    )
                                )
                                if token_address:
                                    all_pairs.append({
                                        "tokenAddress":
                                            token_address
                                    })
                except Exception as e:
                    logger.error(
                        f"FETCH SOURCE ERROR: {e}"
                    )
        unique = {}
        for pair in all_pairs:
            token = pair.get(
                "tokenAddress"
            )
            if token:
                unique[token] = pair
        logger.info(
            f"TOTAL SCANNER TOKENS: "
            f"{len(unique)}"
        )
        return list(unique.values())
    except Exception as e:
        logger.error(f"DEX ERROR: {e}")
        return []
# =========================================
# FETCH TOKEN DATA
# =========================================
async def fetch_pair_data(token):
    url = (
        f"https://api.dexscreener.com/latest/dex/tokens/{token}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=15
            ) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                pairs = data.get("pairs", [])
                if not pairs:
                    return None
                return pairs[0]
    except Exception as e:
        logger.error(f"PAIR FETCH ERROR: {e}")
        return None
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
            mention_cache[token] += 1
            mention_timestamps[token].append(
                time.time()
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
            pump_tokens = await fetch_pumpfun_tokens()
            for pump in pump_tokens:
                mint = pump.get("mint")
                if mint:
                    pairs.append({
                        "tokenAddress": mint
                    })
            if not pairs:
                await asyncio.sleep(10)
                continue
            for pair in pairs:
                try:
                    token = pair.get("tokenAddress")
                    if not token:
                        continue
                    pair_data = await fetch_pair_data(
                        token
                    )
                    if not pair_data:
                        continue
                    liquidity = float(
                        pair_data.get(
                            "liquidity",
                            {}
                        ).get("usd", 0)
                    )
                    volume = float(
                        pair_data.get(
                            "volume",
                            {}
                        ).get("h24", 0)
                    )
                    buys = pair_data.get(
                        "txns",
                        {}
                    ).get(
                        "h24",
                        {}
                    ).get("buys", 0)
                    sells = pair_data.get(
                        "txns",
                        {}
                    ).get(
                        "h24",
                        {}
                    ).get("sells", 0)
                    volume_per_buy = (
                        volume / max(buys, 1)
                    )
                    if volume_per_buy < MIN_VOLUME_PER_BUY:
                        continue
                    # =====================================
                    # EARLY ENGINE
                    # =====================================
                    if (
                        liquidity >= EARLY_MIN_LIQUIDITY
                        and volume >= EARLY_MIN_VOLUME
                        and buys >= EARLY_MIN_BUYS
                    ):
                        volume_growth = (
                            calculate_volume_acceleration(
                                token,
                                volume
                            )
                        )
                        social_score = (
                            calculate_social_score(
                                token,
                                volume_growth
                            )
                        )
                        if (
                            social_score >= EARLY_ALERT_SCORE
                            and token not in early_alerted
                        ):
                            early_alerted.add(token)
                            logger.info(
                                f"🚀 EARLY ALERT | "
                                f"{token[:8]} | "
                                f"SCORE={social_score}"
                            )
                            try:
                                await app.bot.send_message(
                                    chat_id=CHAT_ID,
                                    text=(
                                        f"🚀 EARLY SIGNAL\n\n"
                                        f"Token: {token}\n"
                                        f"Score: {social_score}\n"
                                        f"Liquidity: ${liquidity:,.0f}\n"
                                        f"Volume Growth: {volume_growth:.2f}x"
                                    )
                                )
                            except Exception as e:
                                logger.error(
                                    f"EARLY TG ERROR: {e}"
                                )
                    # =====================================
                    # SAFE ENGINE
                    # =====================================
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
                    volume_growth = (
                        calculate_volume_acceleration(
                            token,
                            volume
                        )
                    )
                    social_score = (
                        calculate_social_score(
                            token,
                            volume_growth
                        )
                    )
                    if social_score < SAFE_BUY_SCORE:
                        continue
                    logger.info(
                        f"🔥 SAFE BUY | "
                        f"{token[:8]} | "
                        f"SCORE={social_score}"
                    )
                    recent_tokens.append(token)
                    if len(recent_tokens) > 25:
                        recent_tokens.pop(0)
                    if (
                        token not in active_trades
                        and len(active_trades)
                        < MAX_ACTIVE_TRADES
                    ):
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
                            "time":
                                datetime.utcnow()
                                .isoformat()
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
                            datetime.utcnow()
                            .isoformat()
                        ))
                        conn.commit()
                        try:
                            await app.bot.send_message(
                                chat_id=CHAT_ID,
                                text=(
                                    f"🔥 SAFE MODE BUY\n\n"
                                    f"Token: {token}\n"
                                    f"Social Score: "
                                    f"{social_score}\n"
                                    f"Liquidity: "
                                    f"${liquidity:,.0f}\n"
                                    f"Volume: "
                                    f"${volume:,.0f}\n"
                                    f"Volume Growth: "
                                    f"{volume_growth:.2f}x"
                                )
                            )
                        except Exception as e:
                            logger.error(
                                f"SAFE TG ERROR: {e}"
                            )
                except Exception as e:
                    logger.error(
                        f"PAIR ERROR: {e}"
                    )
            await asyncio.sleep(15)
        except Exception as e:
            logger.error(
                f"SCANNER LOOP ERROR: {e}"
            )
            await asyncio.sleep(10)
# =========================================
# MAIN
# =========================================
async def main():
    logger.info("🚀 STARTING SAFE MODE V7")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
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
    await app.bot.delete_webhook(
        drop_pending_updates=True
    )
    await tg_client.connect()
    if not await tg_client.is_user_authorized():
        logger.error(
            "TG SESSION NOT AUTHORIZED"
        )
        return
    logger.info("✅ TG SCANNER ACTIVE")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("✅ COMMAND SYSTEM ACTIVE")
    asyncio.create_task(
        scanner_loop(app)
    )
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
