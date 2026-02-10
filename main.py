import time
import requests
from datetime import datetime
from binance.client import Client
import pytz

# ================== CONFIG ==================
BOT_TOKEN = "8420448991:AAG2lkBDA9gUZzHblSbQ48kAbQpYqX7BwJo"
CHAT_ID = "5837332461"

MAX_SIGNALS_PER_DAY = 20
COOLDOWN_HOURS = 12
INTERVAL = Client.KLINE_INTERVAL_5MINUTE
TIMEZONE = pytz.UTC

MIN_24H_VOLUME = 2_000_000      # USDT

# ---- B (Naruto - Explosion)
VOLUME_SPIKE_MULTIPLIER = 3
PRICE_MOVE_MIN = 1.8            # %

# ---- A (Sniper - Early)
SNIPER_PRICE_MIN = 0.6
SNIPER_PRICE_MAX = 1.8
SNIPER_VOLUME_MULTIPLIER = 1.4

TP_LEVELS = [0.02, 0.04, 0.06]
SL_PERCENT = 0.03

CHECK_DELAY = 30
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

def can_send(key):
    now = time.time()
    if key in sent_signals:
        if now - sent_signals[key] < COOLDOWN_HOURS * 3600:
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

# ---------- ANALYSIS B (Naruto Explosion) ----------
def analyze(symbol):
    try:
        klines = get_klines(symbol)
        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]

        last_close = closes[-1]
        prev_close = closes[-2]

        price_change = ((last_close - prev_close) / prev_close) * 100
        if price_change < PRICE_MOVE_MIN:
            return None

        avg_volume = sum(volumes[:-1]) / (len(volumes) - 1)
        if volumes[-1] < avg_volume * VOLUME_SPIKE_MULTIPLIER:
            return None

        vol_24h = get_24h_volume(symbol)
        if vol_24h < MIN_24H_VOLUME:
            return None

        return {
            "price": last_close,
            "volume_24h": vol_24h
        }

    except Exception:
        return None

# ---------- ANALYSIS A (Sniper Early Entry) ----------
def analyze_sniper(symbol):
    try:
        klines = get_klines(symbol, limit=20)
        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]

        price_change = ((closes[-1] - closes[-3]) / closes[-3]) * 100
        if not (SNIPER_PRICE_MIN <= price_change <= SNIPER_PRICE_MAX):
            return None

        avg_volume = sum(volumes[:-2]) / (len(volumes) - 2)
        if volumes[-1] < avg_volume * SNIPER_VOLUME_MULTIPLIER:
            return None

        vol_24h = get_24h_volume(symbol)
        if vol_24h < MIN_24H_VOLUME:
            return None

        return {
            "price": closes[-1],
            "volume_24h": vol_24h
        }

    except Exception:
        return None

# ---------- MESSAGES ----------
def build_targets(entry):
    tps = [round(entry * (1 + tp), 6) for tp in TP_LEVELS]
    sl = round(entry * (1 - SL_PERCENT), 6)
    return tps, sl

def build_sniper_message(symbol, data):
    entry = data["price"]
    tps, sl = build_targets(entry)

    return f"""
🎯 <b>توصية القنّاص (دخول مبكر)</b>

🪙 الزوج: {symbol}
⏱ الفريم: 5 دقائق
💰 الدخول: {entry}

🎯 الأهداف:
1️⃣ {tps[0]}
2️⃣ {tps[1]}
3️⃣ {tps[2]}

🛑 وقف الخسارة: {sl}

💧 السيولة 24h: {int(data["volume_24h"]):,} USDT
🕒 الوقت: {datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M UTC")}

📊 التقييم: 92%
🔥 نسبة الثقة: 90%
"""

def build_naruto_message(symbol, data):
    entry = data["price"]
    tps, sl = build_targets(entry)

    return f"""
🚨 <b>توصية نارتو (انفجار)</b>

🪙 الزوج: {symbol}
⏱ الفريم: 5 دقائق
💰 الدخول: {entry}

🎯 الأهداف:
1️⃣ {tps[0]}
2️⃣ {tps[1]}
3️⃣ {tps[2]}

🛑 وقف الخسارة: {sl}

📊 حجم التداول 24h: {int(data["volume_24h"]):,} USDT
🕒 الوقت: {datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M UTC")}

💥 تأكيد انفجار سعري
"""

# ---------- MAIN LOOP ----------
def run():
    send_message("🟢 ShinobiFlow بدأ المراقبة (القنّاص + نارتو)…")

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

                # ---- SNIPER A ----
                if can_send(symbol + "_A"):
                    sniper = analyze_sniper(symbol)
                    if sniper:
                        send_message(build_sniper_message(symbol, sniper))
                        sent_signals[symbol + "_A"] = time.time()
                        daily_counter[today_key()] += 1
                        time.sleep(2)

                # ---- NARUTO B ----
                if can_send(symbol + "_B"):
                    result = analyze(symbol)
                    if result:
                        send_message(build_naruto_message(symbol, result))
                        sent_signals[symbol + "_B"] = time.time()
                        daily_counter[today_key()] += 1
                        time.sleep(2)

            time.sleep(CHECK_DELAY)

        except Exception:
            time.sleep(10)

# ---------- START ----------
if __name__ == "__main__":
    run()
