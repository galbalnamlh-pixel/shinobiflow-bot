import time
import requests
from datetime import datetime
from binance.client import Client
import pytz

# ================== CONFIG ==================
BOT_TOKEN = "8420448991:AAG2lkBDA9gUZzHblSbQ48kAbQpYqX7BwJo"
CHAT_ID = "5837332461"

MAX_SIGNALS_PER_DAY = 15
COOLDOWN_HOURS = 12
INTERVAL = Client.KLINE_INTERVAL_5MINUTE
TIMEZONE = pytz.UTC

MIN_24H_VOLUME = 2_000_000      # USDT
VOLUME_SPIKE_MULTIPLIER = 3
PRICE_MOVE_MIN = 1.8            # %

TP_LEVELS = [0.02, 0.04, 0.06]  # 2% 4% 6%
SL_PERCENT = 0.03               # 3%

CHECK_DELAY = 30  # seconds
# ============================================

client = Client()

sent_signals = {}
daily_counter = {}

# ---------- TELEGRAM ----------
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload, timeout=10)

# ---------- UTIL ----------
def today_key():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

def can_send(symbol):
    now = time.time()
    if symbol in sent_signals:
        if now - sent_signals[symbol] < COOLDOWN_HOURS * 3600:
            return False
    return True

def daily_limit_ok():
    key = today_key()
    if key not in daily_counter:
        daily_counter[key] = 0
    return daily_counter[key] < MAX_SIGNALS_PER_DAY

# ---------- DATA ----------
def get_klines(symbol, limit=30):
    return client.get_klines(symbol=symbol, interval=INTERVAL, limit=limit)

def get_24h_volume(symbol):
    data = client.get_ticker(symbol=symbol)
    return float(data["quoteVolume"])

# ---------- ANALYSIS ----------
def analyze(symbol):
    try:
        klines = get_klines(symbol)
        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]

        last_close = closes[-1]
        prev_close = closes[-2]

        price_change = ((last_close - prev_close) / prev_close) * 100

        avg_volume = sum(volumes[:-1]) / (len(volumes) - 1)
        last_volume = volumes[-1]

        vol_24h = get_24h_volume(symbol)

        if price_change < PRICE_MOVE_MIN:
            return None

        if last_volume < avg_volume * VOLUME_SPIKE_MULTIPLIER:
            return None

        if vol_24h < MIN_24H_VOLUME:
            return None

        return {
            "price": last_close,
            "change": price_change,
            "volume_24h": vol_24h
        }

    except Exception:
        return None

# ---------- SIGNAL ----------
def build_message(symbol, data):
    entry = data["price"]
    tps = [round(entry * (1 + tp), 6) for tp in TP_LEVELS]
    sl = round(entry * (1 - SL_PERCENT), 6)

    return f"""
🚨 <b>فرصة فورية (Spot)</b>

🔹 <b>الزوج:</b> {symbol}
⏱ <b>الفريم:</b> 5 دقائق
💰 <b>دخول:</b> {entry}

🎯 <b>الأهداف:</b>
1️⃣ {tps[0]}
2️⃣ {tps[1]}
3️⃣ {tps[2]}

🛑 <b>وقف الخسارة:</b> {sl}

📊 <b>حجم التداول 24h:</b> {int(data["volume_24h"]):,} USDT
🕒 <b>التوقيت:</b> {datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M UTC")}

⚔️ <b>ShinobiFlow</b> — اضرب واطلع 🎯
"""

# ---------- MAIN LOOP ----------
def run():
    send_message("🟢 ShinobiFlow بدأ المراقبة…")

    while True:
        try:
            symbols = client.get_exchange_info()["symbols"]

            for s in symbols:
                symbol = s["symbol"]

                if not symbol.endswith("USDT"):
                    continue
                if s["status"] != "TRADING":
                    continue
                if not daily_limit_ok():
                    break
                if not can_send(symbol):
                    continue

                result = analyze(symbol)
                if result:
                    msg = build_message(symbol, result)
                    send_message(msg)

                    sent_signals[symbol] = time.time()
                    daily_counter[today_key()] += 1

                    time.sleep(2)

            time.sleep(CHECK_DELAY)

        except Exception as e:
            time.sleep(10)

# ---------- START ----------
if __name__ == "__main__":
    run()
