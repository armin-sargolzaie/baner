import MetaTrader5 as mt5  
import pandas as pd  
import numpy as np  
from datetime import datetime, timedelta  
import tkinter as tk  
from tkinter import ttk  
import matplotlib.pyplot as plt  
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  
  
# تنظیمات  
SYMBOL = "XAUUSD"  
LOT = 0.01  
EMA_FAST = 100  
EMA_SLOW = 200  
ENTRY_LEVEL = 0.36  
SL_LEVEL = 0.9  
TP_LEVEL = 1.31  
LOOKBACK_BARS = 50  
DAYS = 6  
TIMEFRAME = mt5.TIMEFRAME_M1  
  
# تابع برای محاسبه نقاط فیبوناچی  
def calculate_fib_levels(row, df, i, trade_type):  
    high = df.iloc[i - LOOKBACK_BARS:i]['high'].max()  
    low = df.iloc[i - LOOKBACK_BARS:i]['low'].min()  
  
    if trade_type == 'buy':  
        fib0 = low  
        fib1 = high  
    else:  
        fib0 = high  
        fib1 = low  
  
    entry = fib0 + (fib1 - fib0) * ENTRY_LEVEL  
    sl = fib0 + (fib1 - fib0) * SL_LEVEL  
    tp = fib0 + (fib1 - fib0) * TP_LEVEL  
    return entry, sl, tp, fib0, fib1  
  
# اتصال به متاتریدر  
if not mt5.initialize():  
    raise RuntimeError(f"⛔ اتصال به MT5 برقرار نشد: {mt5.last_error()}")  
  
start_time = datetime.now() - timedelta(days=DAYS)  
rates = mt5.copy_rates_from(SYMBOL, TIMEFRAME, start_time, DAYS * 24 * 60)  
  
if rates is None or len(rates) == 0:  
    mt5.shutdown()  
    raise RuntimeError("❌ داده‌ای دریافت نشد یا خالی بود. خطا: " + str(mt5.last_error()))  
  
mt5.shutdown()  
  
# تبدیل به DataFrame  
df = pd.DataFrame(rates)  
df['time'] = pd.to_datetime(df['time'], unit='s')  
df.set_index('time', inplace=True)  
  
# محاسبه EMAها  
df['ema100'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()  
df['ema200'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()  
  
# تشخیص کراس‌ها  
df['crossover'] = np.where(  
    (df['ema100'].shift(1) < df['ema200'].shift(1)) & (df['ema100'] > df['ema200']), 'buy',  
    np.where(  
        (df['ema100'].shift(1) > df['ema200'].shift(1)) & (df['ema100'] < df['ema200']), 'sell',  
        None  
    )  
)  
  
# لیست معاملات  
trades = []  
active_trade = None  
last_crossover_index = None  
  
for i in range(max(EMA_SLOW, LOOKBACK_BARS), len(df)):  
    row = df.iloc[i]  
  
    # ورود به معامله  
    if row['crossover'] in ['buy', 'sell'] and active_trade is None:  
        entry, sl, tp, fib0, fib1 = calculate_fib_levels(row, df, i, row['crossover'])  
  
        active_trade = {  
            'type': row['crossover'],  
            'entry_price': entry,  
            'sl': sl,  
            'tp': tp,  
            'entry_time': df.index[i],  
            'fib0': fib0,  
            'fib1': fib1  
        }  
        last_crossover_index = i  
  
    # بررسی بستن معامله  
    elif active_trade:  
        price = row['low'] if active_trade['type'] == 'buy' else row['high']  
        hit_tp = (active_trade['type'] == 'buy' and row['high'] >= active_trade['tp']) or \  
                 (active_trade['type'] == 'sell' and row['low'] <= active_trade['tp'])  
        hit_sl = (active_trade['type'] == 'buy' and row['low'] <= active_trade['sl']) or \  
                 (active_trade['type'] == 'sell' and row['high'] >= active_trade['sl'])  
        new_cross = row['crossover'] is not None and i != last_crossover_index  
  
        if hit_tp or hit_sl or new_cross:  
            active_trade['exit_time'] = df.index[i]  
            active_trade['exit_price'] = price  
            active_trade['reason'] = 'TP' if hit_tp else 'SL' if hit_sl else 'New Cross'  
            trades.append(active_trade)  
            active_trade = None  
  
# محاسبه سود/زیان  
profit = 0  
for trade in trades:  
    if trade["type"] == "buy":  
        profit += (trade["exit_price"] - trade["entry_price"])  
    else:  
        profit += (trade["entry_price"] - trade["exit_price"])  
total_profit_pips = profit * 100  # هر پیپ 0.01 است  
  
# نمایش در GUI همراه با فیبوناچی  
def show_plot():  
    global canvas  
    # اگر قبلا نمودار بود، پاکش کن  
    if 'canvas' in globals():  
        canvas.get_tk_widget().pack_forget()  
  
    fig, ax = plt.subplots(figsize=(12, 6))  
    ax.plot(df['close'][-500:], label='Close')  
    ax.plot(df['ema100'][-500:], label='EMA 100')  
    ax.plot(df['ema200'][-500:], label='EMA 200')  
  
    for trade in trades:  
        idx = df.index.get_loc(trade['entry_time'])  
        next_idx = min(idx + 20, len(df) - 1)  
  
        # خطوط ورود، TP، SL  
        ax.axvline(trade['entry_time'], color='green' if trade['type'] == 'buy' else 'red', linestyle='--')  
        ax.hlines([trade['entry_price'], trade['sl'], trade['tp']],  
                  df.index[idx], df.index[next_idx],  
                  colors=['blue', 'orange', 'purple'], linestyles='dotted')  
  
        # رسم فیبوناچی  
        levels = [0, 0.36, 0.9, 1, -1.31]  
        for lvl in levels:  
            level_price = trade['fib0'] + (trade['fib1'] - trade['fib0']) * lvl  
            ax.hlines(level_price, df.index[idx], df.index[next_idx],  
                      colors='gray', linestyles='dashed', alpha=0.4)  
            ax.text(df.index[next_idx], level_price, f"{lvl:.2f}", fontsize=8, color='gray')  
  
    ax.set_title(f"Backtest - EMA + Fibonacci | سود کل: {total_profit_pips:.1f} پیپ")  
    ax.legend()  
    canvas = FigureCanvasTkAgg(fig, master=window)  
    canvas.draw()  
    canvas.get_tk_widget().pack()  
  
# GUI  
window = tk.Tk()  
window.title("نتیجه بک‌تست استراتژی")  
  
ttk.Label(window, text=f"📊 تعداد معاملات: {len(trades)}", font=("Arial", 14)).pack(pady=10)  
ttk.Label(window, text=f"💰 سود کل: {total_profit_pips:.1f} پیپ", font=("Arial", 12)).pack(pady=5)  
ttk.Button(window, text="📈 نمایش نمودار", command=show_plot).pack(pady=10)  
  
window.mainloop()
