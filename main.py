import os
import time
import pytz
import pandas as pd
import ta
import telebot
import yfinance as yf
from threading import Thread
from flask import Flask
from datetime import datetime

# ১. টেলিগ্রাম বট টোকেন
API_TOKEN = os.environ.get("BOT_TOKEN", "8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs")
bot = telebot.TeleBot(API_TOKEN)

# ২. ওয়েব সার্ভার
app = Flask('')
@app.route('/')
def home(): return "Pro Trading Bot is Online!"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

# ৩. ডাটা ফেচ ফাংশন
def fetch_market_data(symbol):
    symbol = symbol.upper()
    forex_map = {'GOLD': 'GC=F', 'SILVER': 'SI=F', 'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X'}
    
    if symbol in forex_map:
        search_symbol = forex_map[symbol]
    elif len(symbol) == 6 and symbol.isalpha():
        search_symbol = f"{symbol}=X"
    else:
        search_symbol = f"{symbol}-USD"

    try:
        data = yf.download(search_symbol, period="10d", interval="1h", progress=False)
        if not data.empty:
            df = data.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [col.lower() for col in df.columns]
            return df, symbol
    except Exception:
        pass
    raise Exception("Data not found")

# ৪. উন্নত অ্যানালাইসিস লজিক (সব ইন্ডিকেটর সহ)
def analyze_market(df):
    close_prices = df['close'].astype(float)
    high_prices = df['high'].astype(float)
    low_prices = df['low'].astype(float)

    # ১. Bollinger Bands
    bb = ta.volatility.BollingerBands(close=close_prices, window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()

    # ২. RSI (14)
    df['rsi'] = ta.momentum.rsi(close=close_prices, window=14)

    # ৩. Stochastic Oscillator
    stoch = ta.momentum.StochasticOscillator(high=high_prices, low=low_prices, close=close_prices, window=14, smooth_window=3)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()

    # ৪. MACD
    macd = ta.trend.MACD(close=close_prices, window_slow=26, window_fast=12, window_sign=9)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()

    # ৫. ADX & EMA
    df['ema_50'] = ta.trend.ema_indicator(close=close_prices, window=50)
    adx_obj = ta.trend.ADXIndicator(high=high_prices, low=low_prices, close=close_prices, window=14)
    df['adx'] = adx_obj.adx()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # ভ্যালুগুলো নেওয়া
    close, rsi, adx = last['close'], last['rsi'], last['adx']
    stoch_k, stoch_d = last['stoch_k'], last['stoch_d']
    macd_diff = last['macd_diff']
    bb_low, bb_high, ema_50 = last['bb_low'], last['bb_high'], last['ema_50']

    action, target, sl, advice = "⏳ WAIT (NO ENTRY)", "N/A", "N/A", "মার্কেট এখন নিউট্রাল। সঠিক কনফার্মেশনের জন্য অপেক্ষা করুন।"

    # ৫. কড়া সিগন্যাল কন্ডিশন
    # 🟢 BUY / LONG: Price near BB Low + RSI < 35 + Stoch Oversold + MACD improving
    if close <= (bb_low * 1.002) and rsi < 38 and stoch_k < 20:
        action = "🟢 BUY / LONG"
        target = round(close * 1.015, 4)
        sl = round(close * 0.992, 4)
        advice = "প্রাইস সাপোর্ট জোনে এবং ইন্ডিকেটরগুলো ওভারসোল্ড দেখাচ্ছে। একটি বাউন্স আশা করা যায়।"

    # 🔴 SELL / SHORT: Price near BB High + RSI > 65 + Stoch Overbought
    elif close >= (bb_high * 0.998) and rsi > 62 and stoch_k > 80:
        action = "🔴 SELL / SHORT"
        target = round(close * 0.985, 4)
        sl = round(close * 1.008, 4)
        advice = "মার্কেট এখন রেজিস্ট্যান্স জোনে। প্রফিট বুকিংয়ের কারণে দাম কমতে পারে।"

    # 📈 TREND BUY: ADX strong + MACD positive + Price above EMA 50
    elif adx > 25 and macd_diff > 0 and close > ema_50:
        action = "📈 TREND BUY"
        target = round(close * 1.012, 4)
        sl = round(ema_50 * 0.995, 4)
        advice = "মার্কেটে শক্তিশালী বুলিশ ট্রেন্ড দেখা যাচ্ছে। ট্রেন্ডের সাথে ট্রেড করা নিরাপদ।"

    return {
        "price": round(close, 4), "action": action, "target": target, 
        "sl": sl, "advice": advice, "rsi": round(rsi, 1), 
        "adx": round(adx, 1), "stoch": round(stoch_k, 1)
    }

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🚀 **Pro Trader Bot (Multi-Indicator)**\n\nসিগন্যাল পেতে লিখুন:\n`/analyze btc` (ক্রিপ্টো)\n`/analyze gold` (ফরেক্স)", parse_mode="Markdown")

@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target = args[1] if len(args) > 1 else "BTC"
        df, final_symbol = fetch_market_data(target)
        data = analyze_market(df)
        
        bd_time = datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%I:%M %p, %d %b %Y')
        
        response = (
            f"📊 **{final_symbol} Pro Analysis**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ **Time:** {bd_time}\n"
            f"💰 **Price:** {data['price']}\n\n"
            f"🎯 **Action:** {data['action']}\n"
            f"📈 **Target:** {data['target']}\n"
            f"🛑 **Stop Loss:** {data['sl']}\n\n"
            f"⚡ **RSI:** {data['rsi']} | **ADX:** {data['adx']}\n"
            f"🌀 **Stoch:** {data['stoch']}\n"
            f"💡 **Advice:** {data['advice']}\n"
            f"━━━━━━━━━━━━━━━"
        )
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "❌ ডাটা পাওয়া যায়নি। সঠিক সিম্বল লিখুন।")

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
