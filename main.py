import ccxt
import pandas as pd
import ta
import telebot
import os
import time
from threading import Thread
from flask import Flask

# ১. টেলিগ্রাম বট টোকেন (এখানে আপনার আসল টোকেন বসান)
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

# ২. ওয়েব সার্ভার (Render এর জন্য)
app = Flask('')

@app.route('/')
def home():
    return "Ultra-Analysis Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ৩. ডাটা ফেচ করার ফাংশন
def fetch_market_data(symbol):
    # সিম্বল ফরম্যাট ঠিক করা
    if "/" not in symbol:
        symbol = f"{symbol.upper()}/USDT"
    else:
        symbol = symbol.upper()

    try:
        # প্রথমে বিন্যান্স থেকে ট্রাই করবে
        exchange = ccxt.binance({'enableRateLimit': True})
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=300)
    except:
        # বিন্যান্স না পারলে কু-কয়েন থেকে ট্রাই করবে
        exchange = ccxt.kucoin({'enableRateLimit': True})
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=300)
    
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df, symbol

# ৪. পাওয়ারফুল এনালাইসিস লজিক
def analyze_market(df):
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df["close"], window=14)
    
    # MACD
    macd = ta.trend.MACD(close=df["close"])
    df['macd_line'], df['macd_signal'] = macd.macd(), macd.macd_signal()
    
    # EMA (50 and 200)
    df['ema_50'] = ta.trend.ema_indicator(df["close"], window=50)
    df['ema_200'] = ta.trend.ema_indicator(df["close"], window=200)
    
    # ADX (Trend Strength)
    adx_ind = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
    df['adx'] = adx_ind.adx()
    
    # Stochastic Oscillator
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
    df['stoch_k'] = stoch.stoch()

    last = df.iloc[-1]
    close, rsi, adx = last['close'], last['rsi'], last['adx']
    bb_high, bb_low = last['bb_high'], last['bb_low']
    stoch_k = last['stoch_k']
    ema_50, ema_200 = last['ema_50'], last['ema_200']
    macd_line, macd_signal = last['macd_line'], last['macd_signal']

    # --- সুপার সিগন্যাল লজিক ---
    if close <= bb_low and rsi < 30 and stoch_k < 20:
        strength = "💎 ULTRA BUY (Extreme Oversold)"
        reason = "প্রাইস লোয়ার ব্যান্ডে, RSI এবং Stochastic ওভারসোল্ড। বাউন্স করার প্রবল সম্ভাবনা!"
    
    elif close >= bb_high and rsi > 70 and stoch_k > 80:
        strength = "🚨 ULTRA SELL (Extreme Overbought)"
        reason = "মার্কেট অনেক বেশি উপরে। প্রফিট বুক করার সময় হয়েছে।"
        
    elif adx > 25 and close > ema_50:
        strength = "🚀 STRONG BULLISH TREND"
        reason = f"শক্তিশালী উর্ধমুখী ট্রেন্ড (ADX: {round(adx, 1)}) এবং EMA 50 এর উপরে সাপোর্ট।"
        
    elif adx > 25 and close < ema_50:
        strength = "📉 STRONG BEARISH TREND"
        reason = "শক্তিশালী নিম্নমুখী ট্রেন্ড। সেল সাইডে থাকা নিরাপদ।"
        
    elif close > ema_200:
        strength = "📈 BULLISH BIAS"
        reason = "দাম EMA 200 এর উপরে, লং-টার্ম ট্রেন্ড এখনো পজিটিভ।"
    else:
        strength = "⚖️ SIDEWAYS / NEUTRAL"
        reason = "মার্কেট বর্তমানে রেঞ্জিং মুডে আছে। বড় মুভমেন্টের অপেক্ষা করুন।"

    return {
        "price": close, "rsi": round(rsi, 2), "adx": round(adx, 2),
        "ema_50": round(ema_50, 2), "strength": strength, "reason": reason
    }

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "স্বাগতম! এনালাইসিস পেতে লিখুন:\n`/analyze btc` বা `/analyze eth` বা `/analyze eur`")

@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target = args[1] if len(args) > 1 else "BTC"
        bot.send_message(message.chat.id, f"🔍 {target} এর প্রো-এনালাইসিস চলছে...")
        
        df, final_symbol = fetch_market_data(target)
        data = analyze_market(df)
        
        msg = (
            f"📊 **{final_symbol} Ultra Analysis**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 **Current Price:** {data['price']}\n"
            f"⚡ **RSI:** {data['rsi']}\n"
            f"📉 **EMA 50:** {data['ema_50']}\n"
            f"📈 **ADX (Trend):** {data['adx']}\n\n"
            f"🎯 **Final Signal:** {data['strength']}\n"
            f"💡 **Reason:** {data['reason']}\n"
            f"━━━━━━━━━━━━━━━"
        )
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ এরর: পেয়ারটি পাওয়া যায়নি বা ডাটা লোড হয়নি। উদাহরণ: `/analyze sol`")

# ৬. রান করার অংশ (কনফ্লিক্ট ফিক্স সহ)
if __name__ == "__main__":
    # ওয়েব সার্ভার ব্যাকগ্রাউন্ডে চালু করা
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    
    # পুরোনো সেশন ক্লিয়ার করার জন্য একটু সময় নেওয়া
    print("Waiting for old sessions to clear...")
    time.sleep(2)
    
    print("Bot is alive and polling...")
    
    try:
        # পুরোনো কানেকশন রিমুভ করা
        bot.remove_webhook()
        # বট চালু করা
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Final Polling error: {e}")
