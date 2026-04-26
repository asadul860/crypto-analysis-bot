import os
import time
import pytz
import ccxt
import pandas as pd
import ta
import telebot
import yfinance as yf
from threading import Thread
from flask import Flask
from datetime import datetime

# ১. টেলিগ্রাম বট টোকেন
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

# ২. ওয়েব সার্ভার (Render এর জন্য)
app = Flask('')
@app.route('/')
def home(): return "Multi-Market Trader Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ৩. ডাটা ফেচ ফাংশন (Crypto + Forex)
def fetch_market_data(symbol):
    symbol = symbol.upper()
    
    # ফরেক্স ডাটা চেক (যদি নামের শেষে USD থাকে বা নির্দিষ্ট ফরেক্স পেয়ার হয়)
    forex_pairs = ['EURUSD=X', 'GBPUSD=X', 'JPYUSD=X', 'GC=F', 'CL=F'] # Gold=GC=F
    search_symbol = symbol if "=" in symbol or symbol in ["GOLD", "SILVER"] else f"{symbol}USD=X"

    try:
        # প্রথমে Yahoo Finance (Forex) ট্রাই করবে
        data = yf.download(search_symbol, period="5d", interval="1h", progress=False)
        if not data.empty:
            df = data.copy()
            df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
            return df, search_symbol
    except:
        pass

    # যদি ফরেক্স না হয়, তবে Crypto (CCXT) ট্রাই করবে
    if "/" not in symbol: symbol = f"{symbol}/USDT"
    exchanges = [ccxt.binance(), ccxt.kucoin()]
    
    for exchange in exchanges:
        try:
            exchange.enableRateLimit = True
            bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
            if bars:
                df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                return df, symbol
        except:
            continue
            
    raise Exception("Data not found")

# ৪. সিগন্যাল অ্যানালাইসিস লজিক
def analyze_market(df):
    # ডাটা ফরম্যাট ঠিক করা (YFinance এর জন্য)
    close_prices = df['close'].squeeze()
    high_prices = df['high'].squeeze()
    low_prices = df['low'].squeeze()

    bb = ta.volatility.BollingerBands(close=close_prices, window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()
    df['rsi'] = ta.momentum.rsi(close=close_prices, window=14)
    df['ema_50'] = ta.trend.ema_indicator(close=close_prices, window=50)
    adx_ind = ta.trend.ADXIndicator(high=high_prices, low=low_prices, close=close_prices, window=14)
    df['adx'] = adx_ind.adx()
    stoch = ta.momentum.StochasticOscillator(high=high_prices, low=low_prices, close=close_prices, window=14)
    df['stoch_k'] = stoch.stoch()

    last = df.iloc[-1]
    close = float(last['close'])
    rsi = float(last['rsi'])
    adx = float(last['adx'])
    bb_low = float(last['bb_low'])
    bb_high = float(last['bb_high'])
    stoch_k = float(last['stoch_k'])
    ema_50 = float(last['ema_50'])

    action = "⏳ WAIT (NO ENTRY)"
    target = "N/A"
    sl = "N/A"
    advice = "মার্কেট এখন নিউট্রাল। সঠিক কনফার্মেশনের জন্য অপেক্ষা করুন।"

    if close <= (bb_low * 1.001) and rsi < 35 and stoch_k < 20:
        action = "🟢 BUY / LONG"
        target = round(close * 1.012, 5)
        sl = round(close * 0.994, 5)
        advice = "প্রাইস সাপোর্ট জোনে এবং ওভারসোল্ড। বাউন্স হওয়ার সম্ভাবনা বেশি।"

    elif close >= (bb_high * 0.999) and rsi > 65 and stoch_k > 80:
        action = "🔴 SELL / SHORT"
        target = round(close * 0.988, 5)
        sl = round(close * 1.006, 5)
        advice = "প্রাইস রেজিস্ট্যান্স জোনে এবং ওভারবট। কারেকশন হতে পারে।"
    
    elif adx > 25 and close > ema_50 and rsi < 65:
        action = "📈 TREND BUY"
        target = round(close * 1.008, 5)
        sl = round(ema_50 * 0.996, 5)
        advice = "মার্কেট শক্তিশালী আপট্রেন্ডে আছে। ট্রেন্ডের সাথে ট্রেড করা নিরাপদ।"

    return {
        "price": round(close, 5), "action": action, "target": target, 
        "sl": sl, "advice": advice, "rsi": round(rsi, 1), "adx": round(adx, 1)
    }

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target_coin = args[1] if len(args) > 1 else "BTC"
        
        df, final_symbol = fetch_market_data(target_coin)
        data = analyze_market(df)
        
        bd_timezone = pytz.timezone('Asia/Dhaka')
        bd_time = datetime.now(bd_timezone).strftime('%I:%M %p, %d %b %Y')
        
        response = (
            f"📊 **{final_symbol} Market Signal**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ **Time:** {bd_time} (BD)\n"
            f"💰 **Price:** {data['price']}\n\n"
            f"🎯 **Action:** {data['action']}\n"
            f"📈 **Target:** {data['target']}\n"
            f"🛑 **Stop Loss:** {data['sl']}\n\n"
            f"⚡ **RSI:** {data['rsi']} | **ADX:** {data['adx']}\n"
            f"💡 **Advice:** {data['advice']}\n"
            f"━━━━━━━━━━━━━━━"
        )
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ ডাটা পাওয়া যায়নি।\nক্রিপ্টো: `/analyze btc`\nফরেক্স: `/analyze eurusd` বা `/analyze gold` লিখুন।")

# ৬. রান করার প্রসেস
if __name__ == "__main__":
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    time.sleep(2)
    bot.remove_webhook()
    print("Bot is Live with Crypto & Forex Support...")
    bot.infinity_polling(skip_pending=True)
