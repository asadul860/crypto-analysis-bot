import ccxt
import pandas as pd
import pandas_ta as ta
import telebot

# আপনার টেলিগ্রাম বট টোকেন এখানে দিন
API_TOKEN = '8537303678:AAFVsbISMZZkfCMlqcJ9EQScz5OjbIwrXvs'
bot = telebot.TeleBot(API_TOKEN)

exchange = ccxt.binance()

def fetch_data(symbol='BTC/USDT'):
    bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def analyze_market(df):
    # বোলিঙ্গার ব্যান্ডস সেটআপ (Period 20, Deviation 2)
    bbands = ta.bbands(df['close'], length=20, std=2)
    df = pd.concat([df, bbands], axis=1)
    
    # কলামের নামগুলো সাধারণত: BBL_20_2.0 (Lower), BBM_20_2.0 (Middle), BBU_20_2.0 (Upper)
    last_row = df.iloc[-1]
    close = last_row['close']
    upper_band = last_row['BBU_20_2.0']
    lower_band = last_row['BBL_20_2.0']
    mid_band = last_row['BBM_20_2.0']

    signal = "⚖️ Market Neutral"
    
    # বোলিঙ্গার ব্যান্ডস লজিক
    if close <= lower_band:
        signal = "🚀 Strong BUY (Price at Lower Band)"
    elif close >= upper_band:
        signal = "🔻 Strong SELL (Price at Upper Band)"
    elif close > mid_band:
        signal = "📈 Bullish Trend (Above Middle Band)"
    else:
        signal = "📉 Bearish Trend (Below Middle Band)"

    return f"Price: {close}\nUpper: {upper_band:.2f}\nLower: {lower_band:.2f}\n\nDirection: {signal}"

@bot.message_handler(commands=['analyze'])
def send_analysis(message):
    try:
        df = fetch_data()
        result = analyze_market(df)
        bot.reply_to(message, f"📊 **BTC/USDT Bollinger Bands Analysis**\n\n{result}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

if __name__ == "__main__":
    bot.infinity_polling()
