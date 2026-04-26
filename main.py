import ccxt
import pandas as pd
import ta
import telebot
import os

# আপনার টোকেন দিন
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

exchange = ccxt.binance()

def fetch_data(symbol='BTC/USDT'):
    bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def analyze_market(df):
    # বোলিঙ্গার ব্যান্ডস (ta লাইব্রেরি ব্যবহার করে)
    indicator_bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
    
    df['bb_high'] = indicator_bb.bollinger_hband()
    df['bb_low'] = indicator_bb.bollinger_lband()
    df['bb_mid'] = indicator_bb.bollinger_mavg()
    
    last_row = df.iloc[-1]
    close = last_row['close']
    upper = last_row['bb_high']
    lower = last_row['bb_low']

    if close <= lower:
        signal = "🚀 Strong BUY (Price at Lower Band)"
    elif close >= upper:
        signal = "🔻 Strong SELL (Price at Upper Band)"
    else:
        signal = "⚖️ Neutral"

    return f"Price: {close}\nUpper: {upper:.2f}\nLower: {lower:.2f}\nDirection: {signal}"

@bot.message_handler(commands=['analyze'])
def send_analysis(message):
    try:
        df = fetch_data()
        result = analyze_market(df)
        bot.reply_to(message, f"📊 **Market Analysis:**\n\n{result}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

if __name__ == "__main__":
    bot.infinity_polling()
