import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# Seiten-Konfiguration (Muss ganz oben stehen)
st.set_page_config(page_title="ETF Profi-Dashboard", page_icon="📈", layout="wide")

st.title("📈 Euer ETF Profi-Dashboard")

# 1. Ticker Definition
assets = {
    "Amazon": "AMZN",
    "Xtrackers MSCI Taiwan": "DBX5.DE", 
    "iShares S&P 500 Info Tech": "QDVE.DE",
    "Xtrackers MSCI World": "XDWD.DE",
    "iShares Core MSCI EM IMI": "IS3N.DE",
    "Xtrackers MSCI China": "XCS6.DE"
}
benchmark_name = "Xtrackers MSCI World"

# Daten-Cache: Lädt die Daten nur einmal pro Stunde neu, damit die App rasend schnell bleibt
@st.cache_data(ttl=3600)
def load_data():
    tickers = list(assets.values())
    end_date = datetime.now()
    start_date_max = end_date - timedelta(days=10*365)
    df_raw = yf.download(tickers, start=start_date_max, end=end_date)['Close'].ffill()
    inv_map = {v: k for k, v in assets.items()}
    df_raw = df_raw.rename(columns=inv_map)
    return df_raw

with st.spinner("Lade Live-Börsendaten..."):
    df_raw = load_data()

# 2. Seitenleiste (Sidebar) für die interaktiven Eingaben
st.sidebar.header("⚙️ Einstellungen")
startkapital = st.sidebar.slider("Startkapital pro ETF (€)", min_value=1000, max_value=50000, value=10000, step=1000)

st.sidebar.markdown("---")
st.sidebar.subheader("ETF Auswahl")
# Checkboxen: Standardmäßig sind alle an
selected_assets = st.sidebar.multiselect("Wähle aus, was angezeigt werden soll:", list(assets.keys()), default=list(assets.keys()))

if not selected_assets:
    st.warning("Bitte wähle mindestens einen ETF aus der Seitenleiste aus.")
    st.stop()

# 3. Zeitraum-Auswahl (Streamlit Native UI)
timeframes = {"1M": 30, "3M": 90, "6M": 180, "1J": 365, "3J": 3*365, "YTD": "YTD", "Seit Kauf (Jan 21)": "KAUF", "MAX": "MAX"}
selected_tf = st.radio("Fokus Zeitraum wählen:", list(timeframes.keys()), horizontal=True, index=6)

kauf_datum = datetime(2021, 1, 1)
end_date = datetime.now()
days = timeframes[selected_tf]

if days == "MAX":
    start_date = df_raw.index.min()
elif days == "KAUF":
    start_date = kauf_datum
elif days == "YTD":
    start_date = datetime(end_date.year, 1, 1)
else:
    start_date = end_date - timedelta(days=days)

start_date = max(pd.to_datetime(start_date), df_raw.index.min())
df_period = df_raw[df_raw.index >= start_date].copy()

if len(df_period) < 5:
    st.error("Für diesen Zeitraum liegen nicht genügend Daten vor.")
    st.stop()

# Berechnungen für Prozente und harte Euros!
df_norm = (df_period / df_period.iloc[0] - 1) * 100
df_euro = (df_period / df_period.iloc[0]) * startkapital

# 4. Diagramm-Logik
fig = go.Figure()
colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3']
color_map = {asset: colors[i % len(colors)] for i, asset in enumerate(assets.keys())}

min_val_period = df_norm[selected_assets].min().min()
red_zone_bottom = min(min_val_period * 1.2, -5)
bench_perf = df_norm[benchmark_name].iloc[-1] if benchmark_name in df_norm else 0

for asset in selected_assets:
    prices = df_period[asset]
    perf = df_norm[asset]
    euro = df_euro[asset]
    
    alpha = perf.iloc[-1] - bench_perf if benchmark_name in selected_assets else 0
    vola = (prices.pct_change().std() * np.sqrt(252) * 100)
    trend_5d = ((prices.iloc[-1] / prices.iloc[-5]) - 1) * 100 if len(prices) >= 5 else 0
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    cagr = ((prices.iloc[-1] / prices.iloc[0])**(1/years) - 1) * 100 if years >= 0.7 else 0
    max_dd = ((prices - prices.cummax()) / prices.cummax() * 100).min()

    dates_txt = prices.index.strftime('%d. %m. %Y')
    cdata = np.stack((
        euro.values, # Hier liegt jetzt der Euro-Wert, nicht der Stückpreis!
        [f"{cagr:.2f}% p.a." if years >= 0.7 else "N/V"]*len(prices),
        [f"{max_dd:.2f}%"]*len(prices),
        [f"{alpha:+.2f}%" if asset != benchmark_name and benchmark_name in selected_assets else "---"]*len(prices),
        [f"{vola:.1f}%"]*len(prices),
        [f"{trend_5d:+.2f}%"]*len(prices),
        dates_txt
    ), axis=-1)

    fig.add_trace(go.Scatter(
        x=perf.index, y=perf, name=asset, 
        line=dict(width=2.5, color=color_map[asset]),
        customdata=cdata,
        hoverlabel=dict(bgcolor="#1a1a1a", bordercolor=color_map[asset], font_size=13),
        hovertemplate=(
            '<span style="color:gray;">%{customdata[6]}</span><br>' +
            '<span style="font-size:16px;"><b>%{fullData.name}</b></span><br>' +
            'Wert: <b style="color:#00CC96;">%{customdata[0]:.0f} €</b><br>' +
            'Rendite: <b>%{y:.2f}%</b><br>' +
            '<i>Trend (5T): %{customdata[5]}</i><br>' +
            '----------------------------<br>' +
            'vs. MSCI World: <b>%{customdata[3]}</b><br>' +
            'Vola (Risiko): %{customdata[4]}<br>' +
            'Max. Drawdown: %{customdata[2]}<br>' +
            'Rendite p.a.: %{customdata[1]}<br>' +
            '<extra></extra>'
        )
    ))

fig.add_hrect(y0=red_zone_bottom, y1=0, fillcolor="red", opacity=0.15, layer="below", line_width=0)

fig.update_layout(
    template="plotly_dark", 
    paper_bgcolor="#0e1117", # Streamlit Dark Mode Hintergrund
    plot_bgcolor="#0e1117",
    hovermode="closest",
    xaxis=dict(showgrid=False, title=""), 
    yaxis=dict(title="Performance (%)", ticksuffix="%", gridcolor="#333", autorange=True),
    legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"), margin=dict(t=40)
)

# Zeichnet den Graphen in voller Breite
st.plotly_chart(fig, use_container_width=True)
