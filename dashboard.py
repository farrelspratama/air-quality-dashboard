import os

import folium
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="Dashboard Kualitas Udara Beijing", page_icon="🌫️", layout="wide")
sns.set_theme(style="whitegrid")

BM_ID, BM_WHO = 55, 15  # baku mutu 24 jam PM2.5 Indonesia (PP 22/2021) dan pedoman WHO 2021 (µg/m³)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
CATEGORIES = ["1. Baik", "2. Sedang", "3. Tidak sehat bagi kelompok sensitif",
              "4. Tidak sehat", "5. Sangat tidak sehat", "6. Berbahaya"]
CAT_COLORS = ["#2a9d8f", "#e9c46a", "#f4a261", "#e76f51", "#9d4edd", "#6a040f"]
# Koordinat PERKIRAAN stasiun (bukan bagian dari dataset)
COORDS = pd.DataFrame({
    "station": ["Aotizhongxin", "Changping", "Dingling", "Dongsi", "Guanyuan", "Gucheng", "Huairou",
                "Nongzhanguan", "Shunyi", "Tiantan", "Wanliu", "Wanshouxigong"],
    "lat": [39.982, 40.220, 40.292, 39.929, 39.929, 39.914, 40.328, 39.937, 40.127, 39.886, 39.987, 39.878],
    "lon": [116.397, 116.230, 116.220, 116.417, 116.339, 116.184, 116.628, 116.461, 116.655, 116.407, 116.287, 116.352],
})


def kategori(x: float) -> str:
    if x <= 12: return CATEGORIES[0]
    if x <= 35.4: return CATEGORIES[1]
    if x <= 55.4: return CATEGORIES[2]
    if x <= 150.4: return CATEGORIES[3]
    if x <= 250.4: return CATEGORIES[4]
    return CATEGORIES[5]


@st.cache_data
def load_data() -> pd.DataFrame:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_data.csv")
    df = pd.read_csv(path, parse_dates=["datetime"])
    df["date"] = df["datetime"].dt.normalize()
    df["year"] = df["datetime"].dt.year
    df["month"] = df["datetime"].dt.month
    df["hour"] = df["datetime"].dt.hour
    return df


df_all = load_data()

# ---------------------------------------------------------------- Sidebar
st.sidebar.title("🌫️ Filter Data")
stations = sorted(df_all["station"].unique())
sel_stations = st.sidebar.multiselect("Stasiun pemantauan", stations, default=stations)
dmin, dmax = df_all["date"].min().date(), df_all["date"].max().date()
date_range = st.sidebar.date_input("Rentang tanggal", value=(dmin, dmax), min_value=dmin, max_value=dmax)
st.sidebar.caption("Baku mutu 24 jam PM2.5: **Indonesia 55 µg/m³**, **WHO 15 µg/m³**.")
st.sidebar.caption("Sumber data: PRSA Air Quality Dataset (12 stasiun Beijing, 1 Mar 2013 - 28 Feb 2017).")

if len(date_range) != 2:
    st.info("Pilih tanggal awal dan tanggal akhir pada filter rentang tanggal.")
    st.stop()
start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
df = df_all[df_all["station"].isin(sel_stations) & df_all["date"].between(start, end)]
if df.empty:
    st.warning("Tidak ada data untuk filter yang dipilih. Ubah pilihan stasiun atau rentang tanggal.")
    st.stop()

# agregat harian per stasiun
daily = df.groupby(["station", "date"], as_index=False)["PM2.5"].mean()
daily["kategori"] = daily["PM2.5"].apply(kategori)
station_summary = (daily.groupby("station")["PM2.5"]
                   .agg(mean_pm25="mean", max_daily="max")
                   .join(daily.groupby("station")["PM2.5"].apply(lambda s: (s > BM_ID).mean() * 100).rename("pct_ID"))
                   .join(daily.groupby("station")["PM2.5"].apply(lambda s: (s > BM_WHO).mean() * 100).rename("pct_WHO"))
                   .sort_values("mean_pm25", ascending=False))

# ---------------------------------------------------------------- Header & KPI
st.title("Dashboard Analisis Kualitas Udara (PM2.5) Beijing")
st.caption(f"Periode terpilih: {start:%d %b %Y} - {end:%d %b %Y} | {len(sel_stations)} stasiun | {len(df):,} pengukuran per jam")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Rata-rata PM2.5", f"{df['PM2.5'].mean():.1f} µg/m³")
c2.metric("Hari melampaui baku mutu ID (55)", f"{(daily['PM2.5'] > BM_ID).mean() * 100:.1f}%")
c3.metric("Stasiun tertinggi", station_summary.index[0], f"{station_summary['mean_pm25'].iloc[0]:.1f} µg/m³", delta_color="off")
c4.metric("Stasiun terendah", station_summary.index[-1], f"{station_summary['mean_pm25'].iloc[-1]:.1f} µg/m³", delta_color="off")

tab1, tab2, tab3, tab4 = st.tabs(["📍 Per Stasiun", "📅 Pola Waktu", "🌬️ Faktor Cuaca", "🗺️ Analisis Lanjutan"])

# ---------------------------------------------------------------- Tab 1
with tab1:
    st.subheader("Pertanyaan 1: Stasiun mana yang paling tercemar PM2.5?")
    order = station_summary.sort_values("mean_pm25").index
    colors = ["#d62828" if s == station_summary.index[0] else "#2a9d8f" if s == station_summary.index[-1] else "#adb5bd" for s in order]
    fig, axes = plt.subplots(1, 2, figsize=(14, max(3, 0.5 * len(order) + 1.5)), sharey=True)
    axes[0].barh(order, station_summary.loc[order, "mean_pm25"], color=colors)
    axes[0].axvline(BM_ID, color="black", ls="--", lw=1)
    axes[0].set_title("Rata-rata PM2.5 (µg/m³)")
    for i, v in enumerate(station_summary.loc[order, "mean_pm25"]):
        axes[0].text(v + 0.5, i, f"{v:.1f}", va="center", fontsize=9)
    axes[1].barh(order, station_summary.loc[order, "pct_ID"], color=colors)
    axes[1].set_title("% hari melampaui baku mutu Indonesia (55 µg/m³)")
    for i, v in enumerate(station_summary.loc[order, "pct_ID"]):
        axes[1].text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=9)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Garis putus-putus = baku mutu 24 jam Indonesia. Merah = stasiun tertinggi, hijau = terendah.")
    with st.expander("Lihat tabel ringkasan"):
        st.dataframe(station_summary.rename(columns={
            "mean_pm25": "Rata-rata PM2.5", "max_daily": "Maks. harian",
            "pct_ID": "% hari > 55", "pct_WHO": "% hari > 15"}).round(2))

# ---------------------------------------------------------------- Tab 2
with tab2:
    st.subheader("Pertanyaan 2: Kapan PM2.5 memuncak, dan bagaimana tren tahunannya?")
    monthly = df.groupby("month")["PM2.5"].mean().reindex(range(1, 13))
    yearly = df.groupby("year")["PM2.5"].mean()
    left, right = st.columns(2)
    with left:
        fig, ax = plt.subplots(figsize=(7, 4.2))
        valid = monthly.dropna()
        mcol = ["#d62828" if m == valid.idxmax() else "#2a9d8f" if m == valid.idxmin() else "#adb5bd" for m in monthly.index]
        ax.bar(MONTHS, monthly.fillna(0).values, color=mcol)
        for i, v in enumerate(monthly.values):
            if pd.notna(v):
                ax.text(i, v + 1, f"{v:.0f}", ha="center", fontsize=8)
        ax.set_ylabel("µg/m³"); ax.set_title("Rata-rata PM2.5 per bulan")
        st.pyplot(fig); plt.close(fig)
        st.write(f"Puncak: **{MONTHS[valid.idxmax()-1]}** ({valid.max():.1f}) | Terendah: **{MONTHS[valid.idxmin()-1]}** ({valid.min():.1f})")
    with right:
        full_years = [y for y in (2014, 2015, 2016)
                      if ((df_all["year"] == y) & df_all["station"].isin(sel_stations)).any()
                      and start <= pd.Timestamp(y, 1, 1) and end >= pd.Timestamp(y, 12, 31)]
        if len(full_years) >= 2:
            yr = yearly.loc[full_years]
            fig, ax = plt.subplots(figsize=(7, 4.2))
            ax.plot(yr.index, yr.values, marker="o", lw=2.5, color="#264653")
            for x, v in yr.items():
                ax.annotate(f"{v:.1f}", (x, v), textcoords="offset points", xytext=(0, 9), ha="center")
            ax.set_xticks(yr.index); ax.set_ylim(0, max(100, yr.max() * 1.15))
            ax.set_ylabel("µg/m³"); ax.set_title("Tren tahunan PM2.5 (hanya tahun penuh)")
            st.pyplot(fig); plt.close(fig)
            chg = (yr.iloc[-1] / yr.iloc[0] - 1) * 100
            st.write(f"Perubahan {full_years[0]} → {full_years[-1]}: **{chg:+.1f}%**")
        else:
            st.info("Tren tahunan ditampilkan jika rentang tanggal mencakup minimal dua tahun penuh (2014-2016), "
                    "karena 2013 dan 2017 tidak mencakup 12 bulan.")
    pivot = df.pivot_table(index="hour", columns="month", values="PM2.5", aggfunc="mean")
    pivot = pivot.reindex(columns=range(1, 13))
    fig, ax = plt.subplots(figsize=(12, 4.5))
    sns.heatmap(pivot, cmap="YlOrRd", xticklabels=MONTHS, cbar_kws={"label": "PM2.5 (µg/m³)"}, ax=ax)
    ax.set_title("Rata-rata PM2.5 menurut jam dan bulan"); ax.set_ylabel("Jam"); ax.set_xlabel("Bulan")
    st.pyplot(fig); plt.close(fig)

# ---------------------------------------------------------------- Tab 3
with tab3:
    st.subheader("Pertanyaan 3: Variabel cuaca apa yang paling berkaitan dengan PM2.5?")
    weather = {"WSPM": "Kecepatan angin", "TEMP": "Suhu", "PRES": "Tekanan", "DEWP": "Titik embun", "RAIN": "Curah hujan"}
    corr = df[["PM2.5"] + list(weather)].corr(method="spearman")["PM2.5"].drop("PM2.5").sort_values()
    wb = df.assign(bin=pd.cut(df["WSPM"], bins=[-0.01, 0.5, 1, 2, 3, 5, 20],
                              labels=["0-0.5", "0.5-1", "1-2", "2-3", "3-5", ">5"]))
    wind_bin = wb.groupby("bin", observed=True)["PM2.5"].mean()
    left, right = st.columns(2)
    with left:
        fig, ax = plt.subplots(figsize=(7, 4.2))
        ax.barh([weather[k] for k in corr.index], corr.values, color=["#2a9d8f" if v < 0 else "#e76f51" for v in corr.values])
        ax.axvline(0, color="black", lw=0.8); ax.set_xlim(-0.5, 0.5)
        for i, v in enumerate(corr.values):
            ax.text(v + (0.01 if v >= 0 else -0.01), i, f"{v:.2f}", va="center", ha="left" if v >= 0 else "right")
        ax.set_title("Korelasi Spearman terhadap PM2.5")
        st.pyplot(fig); plt.close(fig)
    with right:
        fig, ax = plt.subplots(figsize=(7, 4.2))
        ax.bar(wind_bin.index.astype(str), wind_bin.values, color="#457b9d")
        for i, v in enumerate(wind_bin.values):
            ax.text(i, v + 1, f"{v:.0f}", ha="center")
        ax.set_xlabel("Kecepatan angin (m/s)"); ax.set_ylabel("µg/m³"); ax.set_title("Rata-rata PM2.5 menurut kecepatan angin")
        st.pyplot(fig); plt.close(fig)
    st.caption("Korelasi menunjukkan asosiasi, bukan bukti sebab-akibat.")

# ---------------------------------------------------------------- Tab 4
with tab4:
    st.subheader("Kategori kualitas udara harian (binning PM2.5)")
    kat = pd.crosstab(daily["station"], daily["kategori"], normalize="index").reindex(columns=CATEGORIES, fill_value=0) * 100
    kat = kat.loc[station_summary.index]
    fig, ax = plt.subplots(figsize=(12, max(3, 0.5 * len(kat) + 1.5)))
    kat.plot(kind="barh", stacked=True, color=CAT_COLORS, ax=ax)
    ax.invert_yaxis(); ax.set_xlabel("% hari"); ax.set_ylabel("")
    ax.legend(title="Kategori", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    st.pyplot(fig); plt.close(fig)
    share = (daily["kategori"].value_counts(normalize=True) * 100).reindex(CATEGORIES, fill_value=0)
    st.write(f"Hari kategori **Baik**: {share.iloc[0]:.1f}% | **Tidak sehat atau lebih buruk**: {share.iloc[3:].sum():.1f}%")

    st.subheader("Peta rata-rata PM2.5 per stasiun")
    geo = station_summary.reset_index().merge(COORDS, on="station")
    vmin, vmax = geo["mean_pm25"].min(), geo["mean_pm25"].max()
    span = (vmax - vmin) or 1
    m = folium.Map(location=[39.98, 116.40], zoom_start=9, tiles=None)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri", name="Esri Light Gray", max_zoom=16).add_to(m)
    for _, r in geo.iterrows():
        ratio = (r["mean_pm25"] - vmin) / span
        folium.CircleMarker(
            [r["lat"], r["lon"]], radius=8 + ratio * 14,
            color="#2a9d8f" if ratio < 0.33 else "#f4a261" if ratio < 0.66 else "#d62828",
            fill=True, fill_opacity=0.75,
            tooltip=f"{r['station']}: {r['mean_pm25']:.1f} µg/m³ | {r['pct_ID']:.1f}% hari > 55").add_to(m)
    st_folium(m, height=450, use_container_width=True, returned_objects=[])
    st.caption("Posisi stasiun adalah perkiraan. Warna dan ukuran lingkaran menunjukkan rata-rata PM2.5 (hijau rendah, jingga sedang, merah tinggi).")

st.divider()
st.subheader("Rekomendasi")
st.markdown("""
- **Spasial:** prioritaskan pengendalian emisi di wilayah pusat-selatan kota (mis. Dongsi, Nongzhanguan, Wanshouxigong, Gucheng).
- **Musiman:** terapkan kebijakan emisi musim dingin dari **Oktober sampai Maret**, dengan kewaspadaan tertinggi pada **Desember**.
- **Peringatan dini:** keluarkan peringatan saat prakiraan menunjukkan angin lemah (< 1 m/s) dan udara lembap.
- **Evaluasi:** pertahankan tren penurunan 2014-2016 dan kaji penyebabnya dengan data meteorologi.
""")
