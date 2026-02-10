import time
import requests
from datetime import datetime, timedelta
from binance.client import Client
import pytz

# ================== CONFIG ==================
BOT_TOKEN = "8420448991:AAG2lkBDA9gUZzHblSbQ48kAbQpYqX7BwJo"
CHAT_ID = "5837332461"

MAX_SIGNALS_PER_DAY = 20
COOLDOWN_HOURS = 12
INTERVAL = Client.KLINE_INTERVAL_5MINUTE
TIMEZONE = pytz.UTC

MIN_24H_VOLUME = 2_000_000

# ---- Excluded majors (Market indicators only)
EXCLUDED_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

# ---- B (Naruto - Explosion) ❌ لم يتم المساس به
VOLUME_SPIKE_MULTIPLIER = 3
PRICE_MOVE_MIN = 1.8

# ---- A (Sniper - Early)
SNIPER_PRICE_MIN = 0.6
SNIPER_PRICE_MAX = 1.8
SNIPER_VOLUME_MULTIPLIER = 1.4
SNIPER_TIMEOUT_MINUTES = 45

TP_LEVELS = [0.02, 0.04, 0.06]
SL_PERCENT = 0.03

CHECK_DELAY = 30
# ============================================

client = Client()

sent_signals = {}
daily_counter = {}
active_snipers = {}

stats = {
    "A_win": 0,
    "A_fail": 0,
    "B_win": 0,
    "B_fail": 0
}

last_report_date = None

# ---------- TELEGRAM ----------
def send_message(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10
    )

# ---------- UTIL ----------
def today_key():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

def can_send(key):
    now = time.time()
    return key not in sent_signals or now - sent_signals[key] > COOLDOWN_HOURS * 3600

def daily_limit_ok():
    daily_counter.setdefault(today_key(), 0)
    return daily_counter[today_key()] < MAX_SIGNALS_PER_DAY

# ---------- DATA ----------
def get_klines(symbol, limit=30):
    return client.get_klines(symbol=symbol, interval=INTERVAL, limit=limit)

def get_24h_volume(symbol):
    return float(client.get_ticker(symbol=symbol)["quoteVolume"])

def get_price(symbol):
    return float(client.get_symbol_ticker(symbol=symbol)["price"])

# ---------- ANALYSIS ----------
def analyze_sniper(symbol):
    k = get_klines(symbol, 20)
    closes = [float(x[4]) for x in k]
    volumes = [float(x[5]) for x in k]

    change = ((closes[-1] - closes[-3]) / closes[-3]) * 100
    if not SNIPER_PRICE_MIN <= change <= SNIPER_PRICE_MAX:
        return None

    avg_vol = sum(volumes[:-2]) / (len(volumes) - 2)
    if volumes[-1] < avg_vol * SNIPER_VOLUME_MULTIPLIER:
        return None

    if get_24h_volume(symbol) < MIN_24H_VOLUME:
        return None

    return closes[-1]

def analyze_naruto(symbol):
    k = get_klines(symbol)
    closes = [float(x[4]) for x in k]
    volumes = [float(x[5]) for x in k]

    change = ((closes[-1] - closes[-2]) / closes[-2]) * 100
    if change < PRICE_MOVE_MIN:
        return None

    avg_vol = sum(volumes[:-1]) / (len(volumes) - 1)
    if volumes[-1] < avg_vol * VOLUME_SPIKE_MULTIPLIER:
        return None

    if get_24h_volume(symbol) < MIN_24H_VOLUME:
        return None

    return closes[-1]

# ---------- TARGETS ----------
def build_targets(entry):
    tps = [round(entry * (1 + tp), 6) for tp in TP_LEVELS]
    sl = round(entry * (1 - SL_PERCENT), 6)
    return tps, sl

# ---------- MESSAGES ----------
def sniper_message(symbol, entry, now):
    tps, sl = build_targets(entry)
    return f"""
🎯 <b>توصية القنّاص (دخول مبكر)</b>

🪙 الزوج: {symbol}
💰 الدخول: {entry}
⏱ الفريم: 5 دقائق
🕒 وقت الإشارة: {now.strftime('%Y-%m-%d %H:%M UTC')}

🎯 الأهداف:
1️⃣ {tps[0]}
2️⃣ {tps[1]}
3️⃣ {tps[2]}

🛑 وقف الخسارة: {sl}

🔥 نسبة الثقة: 90%
"""

def sniper_fail_message(symbol):
    return f"""
⚠️ <b>فشل توصية القنّاص</b>

🪙 الزوج: {symbol}
❌ لم يصل الهدف الأول خلال 45 دقيقة
📉 ضعف الاستمرارية السعرية
"""

def naruto_message(symbol, entry, now):
    tps, sl = build_targets(entry)
    return f"""
🚨 <b>شمعة انفجار – جرس فرص</b>

🪙 الزوج: {symbol}
💰 السعر الحالي: {entry}
⏱ الفريم: 5 دقائق
🕒 وقت الإشارة: {now.strftime('%Y-%m-%d %H:%M UTC')}

🎯 مستويات مقترحة:
1️⃣ {tps[0]}
2️⃣ {tps[1]}
3️⃣ {tps[2]}

🛑 وقف خسارة مرجعي: {sl}

⚠️ <b>تنبيه مهم:</b>
بداية انفجار سعري — الدخول بعد المراقبة
وتحمل كامل مسؤولية المخاطرة

🔥 هذه شمعة الفرص… القرار بيدك
"""

def daily_report():
    return f"""
📊 <b>تقرير ShinobiFlow اليومي</b>

🎯 القنّاص:
✅ {stats['A_win']} | ❌ {stats['A_fail']}

🚨 نارتو:
📌 إشارات انفجار: {stats['B_win']}

⚔️ تداول بعقل لا بعاطفة
"""

# ---------- MAIN LOOP ----------
def run():
    global last_report_date
    send_message("🟢 ShinobiFlow بدأ المراقبة…")

    while True:
        now = datetime.now(TIMEZONE)

        if last_report_date != today_key() and now.hour == 23 and now.minute >= 59:
            send_message(daily_report())
            last_report_date = today_key()
            for k in stats: stats[k] = 0

        for symbol, data in list(active_snipers.items()):
            if get_price(symbol) >= data["tp1"]:
                stats["A_win"] += 1
                del active_snipers[symbol]
            elif now - data["time"] > timedelta(minutes=SNIPER_TIMEOUT_MINUTES):
                send_message(sniper_fail_message(symbol))
                stats["A_fail"] += 1
                del active_snipers[symbol]

        try:
            for s in client.get_exchange_info()["symbols"]:
                symbol = s["symbol"]
                if (
                    not symbol.endswith("USDT")
                    or symbol in EXCLUDED_SYMBOLS
                    or s["status"] != "TRADING"
                ):
                    continue

                if not daily_limit_ok():
                    break

                if can_send(symbol+"_A"):
                    entry = analyze_sniper(symbol)
                    if entry:
                        tps,_ = build_targets(entry)
                        active_snipers[symbol] = {"tp1":tps[0],"time":now}
                        send_message(sniper_message(symbol, entry, now))
                        sent_signals[symbol+"_A"] = time.time()
                        daily_counter[today_key()] += 1

                if can_send(symbol+"_B"):
                    entry = analyze_naruto(symbol)
                    if entry:
                        send_message(naruto_message(symbol, entry, now))
                        stats["B_win"] += 1
                        sent_signals[symbol+"_B"] = time.time()
                        daily_counter[today_key()] += 1

            time.sleep(CHECK_DELAY)

        except Exception:
            time.sleep(10)

# ---------- START ----------
if __name__ == "__main__":
    run()
