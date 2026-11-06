import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. СТРОГИЙ КОРПОРАТИВНЫЙ СТИЛЬ СТРАНИЦЫ
st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")

st.markdown("<h2 style='text-align: center; color: #333;'>Ichimoku Analytical Terminal</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Профессиональная среда анализа рынков (Методология Гоити Хосоды)</p>", unsafe_allow_html=True)

# 2. ПАНЕЛЬ НАСТРОЕК
st.sidebar.header("Параметры анализа")
asset = st.sidebar.selectbox("Символ:", ["BTC-USD", "GC=F", "EURUSD=X", "^GSPC"])
tf = st.sidebar.selectbox("Таймфрейм:", ["1d", "1h", "15m", "5m", "1m"])

st.write(f"Загрузка рыночных данных: **{asset}** [{tf}]...")

# 3. ДОБЫЧА ДАННЫХ
df = yf.download(asset, period="7d" if tf in ["1m", "5m"] else "1y", interval=tf, progress=False)

if not df.empty:
    if isinstance(df.columns, pd.MultiIndex): 
        df.columns = df.columns.get_level_values(0)
    
    # Расчет волатильности (ATR) для красивого отступа точек
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Prev_Close']), abs(df['Low'] - df['Prev_Close'])))
    df['ATR'] = df['TR'].rolling(14).mean()

    # 4. ПОИСК ЭКСТРЕМУМОВ (ФРАКТАЛОВ) РАЗНОГО ВЕСА
    # Младшие экстремумы (окно 5 свечей)
    df['Minor_High'] = df['High'] == df['High'].rolling(5, center=True).max()
    df['Minor_Low'] = df['Low'] == df['Low'].rolling(5, center=True).min()
    
    # Старшие экстремумы (окно 21 свеча)
    df['Major_High'] = df['High'] == df['High'].rolling(21, center=True).max()
    df['Major_Low'] = df['Low'] == df['Low'].rolling(21, center=True).min()

    # 5. ОТРИСОВКА ГРАФИКА (Строгий Японский стиль)
    fig = go.Figure()
    
    # Черно-белые свечи
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        increasing_line_color='black', increasing_fillcolor='white',
        decreasing_line_color='black', decreasing_fillcolor='black',
        name='Цена'
    ))

    # Рисуем Младшие точки (Малый вес)
    minor_highs = df[df['Minor_High'] & ~df['Major_High']]
    fig.add_trace(go.Scatter(
        x=minor_highs.index, y=minor_highs['High'] + (minor_highs['ATR'] * 0.3), # Отступ вверх
        mode='markers', marker=dict(size=5, color='gray', symbol='circle'), name='Младший Максимум'
    ))
    
    minor_lows = df[df['Minor_Low'] & ~df['Major_Low']]
    fig.add_trace(go.Scatter(
        x=minor_lows.index, y=minor_lows['Low'] - (minor_lows['ATR'] * 0.3), # Отступ вниз
        mode='markers', marker=dict(size=5, color='gray', symbol='circle'), name='Младший Минимум'
    ))

    # Рисуем Старшие точки (Большой вес)
    major_highs = df[df['Major_High']]
    fig.add_trace(go.Scatter(
        x=major_highs.index, y=major_highs['High'] + (major_highs['ATR'] * 0.6), # Отступ больше
        mode='markers', marker=dict(size=10, color='black', symbol='circle'), name='Старший Максимум'
    ))
    
    major_lows = df[df['Major_Low']]
    fig.add_trace(go.Scatter(
        x=major_lows.index, y=major_lows['Low'] - (major_lows['ATR'] * 0.6),
        mode='markers', marker=dict(size=10, color='black', symbol='circle'), name='Старший Минимум'
    ))

    # Чистая и светлая тема
    fig.update_layout(
        xaxis_rangeslider_visible=False, 
        height=700, 
        template="plotly_white",
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Нет данных от биржи.")
