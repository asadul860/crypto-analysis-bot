import ccxt
import pandas as pd
import ta
import telebot
import os
from threading import Thread
from flask import Flask

# ১. টেলিগ্রাম বট টোকেন
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

# ২. ওয়েব সার্ভার (Render এর জন্য)
app = Flask('')
@app.route('/')
def home(): return "Ultra-Analysis Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ৩. ডাটা ফেচ ফাংশন
def fetch_market_data(symbol):
    if "/" not in symbol: symbol = f"{symbol.upper()}/USDT"
    else: symbol = symbol.upper()
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=300)
    except:
        exchange = ccxt.kucoin({'enableRateLimit': True})
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=300)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df, symbol

# ৪. আল্ট্রা এনালাইসিস লজিক (BB + RSI + MACD + EMA + ADX + Stochastic)
def analyze_market(df):
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    df['bb_high'], df['bb_low'] = bb.bollinger_hband(), bb.bollinger_lband()
    
    # RSI
    df['rsi'] = ta.momentum.rsi(df["close"], window=14)
    
    # MACD
    macd = ta.trend.MACD(close=df["close"])
    df['macd_line'], df['macd_signal'] = macd.macd(), macd.macd_signal()
    
    # EMA
    df['ema_50'] = ta.trend.ema_indicator(df["close"], window=50)
    
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
    ema_50 = last['ema_50']

    # --- সুপার সিগন্যাল লজিক ---
    if close <= bb_low and rsi < 30 and stoch_k < 20:
        strength = "💎 ULTRA BUY (Extreme Oversold)"
        reason = "বোলিঙ্গার ব্যান্ড, RSI এবং Stochastic সবগুলোই মার্কেটকে অনেক নিচে দেখাচ্ছে। এখান থেকে বাউন্স করার সম্ভাবনা অনেক বেশি।"
    
    elif close >= bb_high and rsi > 70 and stoch_k > 80:
        strength = "🚨 ULTRA SELL (Extreme Overbought)"
        reason = "মার্কেট অনেক বেশি উপরে উঠে গেছে, প্রফিট বুক করার সময় হয়েছে।"
        
    elif adx > 25 and close > ema_50:
        strength = "🚀 STRONG BULLISH TREND"
        reason = f"মার্কেট একটি শক্তিশালী উর্ধমুখী ট্রেন্ডে আছে (ADX: {round(adx, 2)}) এবং EMA 50 এর উপরে সাপোর্ট নিচ্ছে।"
        
    elif adx > 25 and close < ema_50:
        strength = "📉 STRONG BEARISH TREND"
        reason = "মার্কেট শক্তিশালী নিম্নমুখী ট্রেন্ডে আছে। সেল করা নিরাপদ হতে পারে।"
        
    else:
        strength = "⚖️ SIDEWAYS / NEUTRAL"
        reason = "মার্কেট বর্তমানে একটি নির্দিষ্ট রেঞ্জে ঘুরপাক খাচ্ছে, বড় কোনো মুভমেন্টের অপেক্ষায় থাকুন।"

    return {
        "price": close, "rsi": round(rsi, 2), "adx": round(adx, 2),
        "strength": strength, "reason": reason
    }

# ৫. কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['analyze'])
def get_analysis(message):
    try:
        args = message.text.split()
        target = args[1] if len(args) > 1 else "BTC"
        bot.send_message(message.chat.id, f"🔍 {target} এর গভীর এনালাইসিস চলছে...")
        
        df, final_symbol = fetch_market_data(target)
        data = analyze_market(df)
        
        msg = (
            f"📊 **{final_symbol} Ultra Analysis**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 **Price:** {data['price']}\n"
            f"⚡ **RSI:** {data['rsi']}\n"
            f"📈 **ADX (Trend Strength):** {data['adx']}\n\n"
            f"🎯 **Final Signal:** {data['strength']}\n"
            f"💡 **Reason:** {data['reason']}\n"
            f"━━━━━━━━━━━━━━━"
        )
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ ডাটা প্রসেস করতে সমস্যা হয়েছে। দয়া করে কিছুক্ষণ পর চেষ্টা করুন।")

if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.infinity_polling()
