import os
import re
import time
import datetime as dt
from typing import Optional, List, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Dashboard Vendas Clear",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_TTL_SECONDS = 60

SHEET_ID = "1Q0mLvOBxEGCojUITBLxCXRtpXVMAHE3ngvGsa2Cgf9Q"
GID_BASE = 1396326144

APP_BOOT = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
APP_VERSION = os.getenv("APP_VERSION", f"boot@{APP_BOOT}")

# =========================================================
# ESTILO
# =========================================================
st.markdown(
    """
<style>
    :root{
        --navy:#071B49;
        --navy-2:#0D2A6B;
        --wine:#8E0E3F;
        --gold:#D39A33;
        --bg:#F4F6FB;
        --card:#FFFFFF;
        --line:#E7EAF3;
        --text:#18243D;
        --muted:#6B7280;
        --soft:#F9FAFB;
    }

    .stApp {
        background: var(--bg);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--navy) 0%, #051535 100%);
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0rem !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0.5rem !important;
    }

    [data-testid="stSidebar"] * {
        color: white;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    .brand-box {
        padding: 0rem 0.5rem 0.7rem 0.5rem;
        margin-top: -0.65rem;
        margin-bottom: 0.45rem;
        border-bottom: 1px solid rgba(255,255,255,0.12);
    }

    .brand-logo {
        width: 62px;
        height: 62px;
        border: 2px solid var(--gold);
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 0.35rem;
        color: var(--gold);
        font-size: 28px;
        font-weight: 800;
    }

    .brand-user {
        width: 46px;
        height: 46px;
        border: 2px solid var(--gold);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-top: 0.4rem;
        color: var(--gold);
        font-size: 21px;
        font-weight: 800;
    }

    .brand-title {
        color: #F6D089;
        font-size: 1.08rem;
        font-weight: 800;
        line-height: 1.1;
        margin: 0;
        white-space: nowrap;
    }

    .brand-sub {
        color: #E7C27A;
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        margin-top: 0.28rem;
    }

    .page-title {
        font-size: 2.3rem;
        font-weight: 800;
        color: var(--text);
        line-height: 1.1;
        margin-bottom: 0.15rem;
    }

    .page-subtitle {
        color: var(--muted);
        font-size: 1rem;
        margin-bottom: 1rem;
    }

    .metric-card {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        min-height: 126px;
    }

    .metric-wrap {
        display: flex;
        gap: 14px;
        align-items: center;
    }

    .metric-icon {
        width: 58px;
        height: 58px;
        min-width: 58px;
        border-radius: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 24px;
        font-weight: 800;
    }

    .metric-label {
        color: #55627A;
        font-size: 0.98rem;
        font-weight: 600;
        margin-bottom: 0.1rem;
    }

    .metric-value {
        color: var(--text);
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.05;
    }

    .metric-sub {
        color: var(--muted);
        font-size: 0.92rem;
        margin-top: 0.15rem;
    }

    .card {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1rem 1rem 0.9rem 1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        height: 100%;
    }

    .card-title {
        color: var(--text);
        font-size: 1.05rem;
        font-weight: 800;
        margin-bottom: 0.75rem;
    }

    .small-note {
        color: var(--muted);
        font-size: 0.86rem;
    }

    .search-shell {
        background: linear-gradient(90deg, var(--navy) 0%, #0A225D 100%);
        border-radius: 22px;
        padding: 1.1rem 1.1rem;
        border: 1px solid rgba(7,27,73,0.08);
        margin-top: 0.5rem;
    }

    .search-title {
        color: white;
        font-size: 1.3rem;
        font-weight: 800;
        margin: 0;
    }

    .search-sub {
        color: rgba(255,255,255,0.78);
        font-size: 0.92rem;
        margin-top: 0.15rem;
        margin-bottom: 0.7rem;
    }

    .client-preview {
        background: #FFF9EF;
        border: 1px solid #F2DFC1;
        border-radius: 18px;
        padding: 1rem;
        margin-top: 1rem;
    }

    .client-title {
        color: var(--text);
        font-size: 1.12rem;
        font-weight: 800;
        margin-bottom: 0.35rem;
    }

    .detail-badge {
        display: inline-block;
        background: #F6E7C5;
        color: #7A4C00;
        border-radius: 999px;
        padding: 0.25rem 0.6rem;
        font-size: 0.78rem;
        font-weight: 700;
        margin-left: 0.4rem;
    }

    .detail-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px 18px;
        margin-top: 0.8rem;
    }

    .detail-item {
        background: white;
        border: 1px solid #EFE4CF;
        border-radius: 14px;
        padding: 0.7rem 0.8rem;
    }

    .detail-label {
        color: #7B8495;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.2rem;
    }

    .detail-value {
        color: var(--text);
        font-size: 0.95rem;
        font-weight: 600;
        word-break: break-word;
    }

    .section-space {
        margin-top: 0.6rem;
    }

    div[data-testid="stMetricValue"] {
        font-weight: 800;
    }

    .stDataFrame, .stTable {
        border-radius: 16px;
        overflow: hidden;
    }

    .empty-page-card {
        background: white;
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1.4rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        color: var(--text);
    }

    .empty-page-title {
        font-size: 1.35rem;
        font-weight: 800;
        margin-bottom: 0.35rem;
    }

    .empty-page-sub {
        color: var(--muted);
        font-size: 0.98rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# HELPERS
# =========================================================
@st.cache_data(show_spinner=False, ttl=CACHE_TTL_SECONDS)
def load_data() -> pd.DataFrame:
    bust = int(time.time() * 1000)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID_BASE}&_={bust}"
    df = pd.read_csv(url)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def normalize_text(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip()


def only_digits(v) -> str:
    return re.sub(r"\D", "", normalize_text(v))


def format_phone(v) -> str:
    s = only_digits(v)
    if len(s) == 11:
        return f"({s[:2]}) {s[2:7]}-{s[7:]}"
    if len(s) == 10:
        return f"({s[:2]}) {s[2:6]}-{s[6:]}"
    return normalize_text(v)


def format_cpf(v) -> str:
    s = only_digits(v)
    if len(s) == 11:
        return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"
    return normalize_text(v)


def parse_date_any(v) -> Optional[dt.date]:
    if pd.isna(v):
        return None
    s = str(v).strip()
    if not s:
        return None

    fixed_formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
        "%d-%m-%y",
    ]
    for fmt in fixed_formats:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except Exception:
            pass

    d = pd.to_datetime(s, dayfirst=True, errors="coerce")
    if pd.isna(d):
        return None
    return d.date()


def month_name_pt(m: int) -> str:
    meses = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    return meses[m] if 1 <= m <= 12 else ""


def month_key_to_label(ym: Tuple[int, int]) -> str:
    y, m = ym
    return f"{month_name_pt(m)} / {y}"


def detect_col(df: pd.DataFrame, keywords: List[List[str]]) -> Optional[str]:
    cols = list(df.columns)
    lowered = {c: str(c).strip().lower() for c in cols}

    for c in cols:
        lc = lowered[c]
        for group in keywords:
            if all(k in lc for k in group):
                return c
    return None


def build_month_key(row, col_mes, col_data) -> Optional[Tuple[int, int]]:
    raw_mes = normalize_text(row[col_mes]) if col_mes and col_mes in row else ""
    raw_data = normalize_text(row[col_data]) if col_data and col_data in row else ""

    if raw_mes:
        s = raw_mes.lower()

        m1 = re.search(r"(\d{1,2})/(20\d{2})", s)
        if m1:
            mm = int(m1.group(1))
            yy = int(m1.group(2))
            if 1 <= mm <= 12:
                return (yy, mm)

        m2 = re.search(r"(20\d{2})[-/](\d{1,2})", s)
        if m2:
            yy = int(m2.group(1))
            mm = int(m2.group(2))
            if 1 <= mm <= 12:
                return (yy, mm)

        nomes = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
            "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
            "outubro": 10, "novembro": 11, "dezembro": 12
        }
        achou_mes = None
        for nome, num in nomes.items():
            if nome in s:
                achou_mes = num
                break
        if achou_mes:
            ano_match = re.search(r"(20\d{2})", s)
            ano = int(ano_match.group(1)) if ano_match else dt.date.today().year
            return (ano, achou_mes)

    d = parse_date_any(raw_data)
    if d:
        return (d.year, d.month)

    return None


def card_metric(title: str, value: str, subtitle: str, emoji: str, color: str):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-wrap">
                <div class="metric-icon" style="background:{color};">{emoji}</div>
                <div>
                    <div class="metric-label">{title}</div>
                    <div class="metric-value">{value}</div>
                    <div class="metric-sub">{subtitle}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_detail_grid(record: pd.Series, ordered_cols: List[str]):
    shown_cols = []
    for c in ordered_cols:
        if c in record.index and normalize_text(record[c]) != "":
            shown_cols.append(c)

    for c in record.index:
        if c not in shown_cols and not str(c).startswith("_") and normalize_text(record[c]) != "":
            shown_cols.append(c)

    html = ['<div class="detail-grid">']
    for c in shown_cols:
        val = normalize_text(record[c])
        html.append(
            f"""
            <div class="detail-item">
                <div class="detail-label">{c}</div>
                <div class="detail-value">{val}</div>
            </div>
            """
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_placeholder_page(title: str, subtitle: str):
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="empty-page-card">
            <div class="empty-page-title">{title}</div>
            <div class="empty-page-sub">
                Esta página já foi criada no menu e está pronta para receber os cards, gráficos e tabelas que vocês quiserem colocar.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown(
        """
        <div class="brand-box">
            <div class="brand-logo">⚖</div>
            <div class="brand-title">DASHBOARD VENDAS CLEAR</div>
            <div class="brand-sub">GESTÃO DE CONTRATOS</div>
            <div class="brand-user">👤</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navegação",
        ["Visão Geral", "Pedigree", "Comissão"],
        label_visibility="collapsed",
    )

# =========================================================
# LOAD + PREP
# =========================================================
df = load_data().copy()

COL_NOME = detect_col(df, [["nome"]]) or "Nome"
COL_TEL = detect_col(df, [["telefone"]])
COL_CPF = detect_col(df, [["cpf"]])
COL_EMAIL = detect_col(df, [["e-mail"], ["email"]])
COL_DATA = detect_col(df, [["data", "compra"], ["data"]])
COL_MES = detect_col(df, [["mês"], ["mes"]])
COL_RACA = detect_col(df, [["raça"], ["raca"]])

if COL_DATA:
    df["_data_compra"] = df[COL_DATA].apply(parse_date_any)
else:
    df["_data_compra"] = None

df["_mes_key"] = df.apply(lambda row: build_month_key(row, COL_MES, COL_DATA), axis=1)

if COL_NOME in df.columns:
    df["_nome_norm"] = df[COL_NOME].astype(str).str.strip()
else:
    df["_nome_norm"] = ""

if COL_TEL and COL_TEL in df.columns:
    df["_tel_norm"] = df[COL_TEL].apply(only_digits)
else:
    df["_tel_norm"] = ""

if COL_CPF and COL_CPF in df.columns:
    df["_cpf_norm"] = df[COL_CPF].apply(only_digits)
else:
    df["_cpf_norm"] = ""

if COL_EMAIL and COL_EMAIL in df.columns:
    df["_email_norm"] = df[COL_EMAIL].astype(str).str.strip().str.lower()
else:
    df["_email_norm"] = ""

if COL_RACA and COL_RACA in df.columns:
    df["_raca_norm"] = df[COL_RACA].astype(str).str.strip()
else:
    df["_raca_norm"] = "Não informado"

all_months = sorted(
    [m for m in df["_mes_key"].dropna().unique().tolist()],
    key=lambda x: (x[0], x[1])
)

if all_months:
    default_month = all_months[-1]
else:
    today = dt.date.today()
    default_month = (today.year, today.month)
    all_months = [default_month]

# =========================================================
# PÁGINA 1 — VISÃO GERAL
# =========================================================
if page == "Visão Geral":
    header_left, header_right = st.columns([3.2, 1.2])

    with header_left:
        st.markdown('<div class="page-title">Visão Geral</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="page-subtitle">Acompanhe os contratos recebidos e consulte todos os dados do cliente sem alterar a origem.</div>',
            unsafe_allow_html=True,
        )

    with header_right:
        selected_month = st.selectbox(
            "Mês de referência",
            options=all_months,
            index=all_months.index(default_month) if default_month in all_months else 0,
            format_func=month_key_to_label,
        )

    month_df = df[df["_mes_key"] == selected_month].copy()

    races = ["Todas"]
    if COL_RACA and COL_RACA in month_df.columns:
        race_vals = sorted([r for r in month_df[COL_RACA].dropna().astype(str).str.strip().unique() if r])
        races += race_vals

    filter_col1, filter_col2 = st.columns([1.2, 1.2])

    with filter_col1:
        selected_race = st.selectbox("Raça", races, index=0)

    with filter_col2:
        search_top = st.text_input("Busca rápida", placeholder="Nome, CPF, telefone ou e-mail")

    filtered_df = month_df.copy()

    if selected_race != "Todas" and COL_RACA and COL_RACA in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[COL_RACA].astype(str).str.strip() == selected_race].copy()

    if search_top.strip():
        q = search_top.strip().lower()
        q_digits = re.sub(r"\D", "", q)
        mask = (
            filtered_df["_nome_norm"].str.lower().str.contains(q, na=False)
            | filtered_df["_tel_norm"].str.contains(q_digits, na=False)
            | filtered_df["_cpf_norm"].str.contains(q_digits, na=False)
            | filtered_df["_email_norm"].str.contains(q, na=False)
        )
        filtered_df = filtered_df[mask].copy()

    total_contracts = len(df)
    contracts_month = len(month_df)
    clients_month = month_df["_nome_norm"].replace("", pd.NA).dropna().nunique()

    days_in_month = 30
    try:
        year_, month_ = selected_month
        if month_ == 12:
            next_first = dt.date(year_ + 1, 1, 1)
        else:
            next_first = dt.date(year_, month_ + 1, 1)
        first = dt.date(year_, month_, 1)
        days_in_month = (next_first - first).days
    except Exception:
        pass

    avg_per_day = contracts_month / days_in_month if days_in_month else 0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        card_metric("Total de Contratos", f"{total_contracts}", "base completa", "📄", "#8E0E3F")
    with m2:
        card_metric("Contratos no Mês", f"{contracts_month}", month_key_to_label(selected_month), "🗓", "#071B49")
    with m3:
        card_metric("Clientes Únicos", f"{clients_month}", "no mês", "👤", "#D39A33")
    with m4:
        card_metric("Média por Dia", f"{avg_per_day:.2f}".replace(".", ","), "contratos / dia", "📊", "#071B49")

    st.markdown('<div class="section-space"></div>', unsafe_allow_html=True)

    left_chart, right_chart = st.columns([1.65, 1.0])

    with left_chart:
        st.markdown('<div class="card-title">Contratos por Dia</div>', unsafe_allow_html=True)
        if not month_df.empty and month_df["_data_compra"].notna().any():
            day_df = month_df[month_df["_data_compra"].notna()].copy()
            day_df["_dia"] = day_df["_data_compra"].apply(lambda d: d.day if d else None)
            chart_day = (
                day_df.groupby("_dia", as_index=False)
                .size()
                .rename(columns={"size": "Quantidade"})
            )

            if not chart_day.empty:
                full_days = pd.DataFrame({"_dia": list(range(1, days_in_month + 1))})
                chart_day = full_days.merge(chart_day, on="_dia", how="left").fillna(0)
                chart_day["Quantidade"] = chart_day["Quantidade"].astype(int)

                fig_day = px.bar(
                    chart_day,
                    x="_dia",
                    y="Quantidade",
                    labels={"_dia": "Dia", "Quantidade": "Contratos"},
                )
                fig_day.update_traces(marker_color="#8E0E3F")
                fig_day.update_layout(
                    height=320,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    xaxis=dict(tickmode="linear"),
                    yaxis_title="",
                    xaxis_title="",
                )
                st.plotly_chart(fig_day, use_container_width=True)
            else:
                st.info("Não há datas suficientes para montar o gráfico deste mês.")
        else:
            st.info("Não há datas suficientes para montar o gráfico deste mês.")

    with right_chart:
        st.markdown('<div class="card-title">Contratos por Raça</div>', unsafe_allow_html=True)
        if COL_RACA and COL_RACA in month_df.columns:
            race_chart = (
                month_df[COL_RACA]
                .fillna("Não informado")
                .astype(str)
                .str.strip()
                .replace("", "Não informado")
                .value_counts()
                .reset_index()
            )
            race_chart.columns = ["Raça", "Quantidade"]

            if not race_chart.empty:
                fig_race = px.pie(
                    race_chart,
                    names="Raça",
                    values="Quantidade",
                    hole=0.56,
                )
                fig_race.update_layout(
                    height=320,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="white",
                )
                st.plotly_chart(fig_race, use_container_width=True)
            else:
                st.info("Sem dados de raça para o mês selecionado.")
        else:
            st.info("Coluna de raça não encontrada na base.")

    c1, c2, c3 = st.columns([1.0, 1.0, 1.1])

    with c1:
        st.markdown('<div class="card"><div class="card-title">Contratos por Raça (Top 5)</div>', unsafe_allow_html=True)
        if COL_RACA and COL_RACA in month_df.columns:
            top5 = (
                month_df[COL_RACA]
                .fillna("Não informado")
                .astype(str)
                .str.strip()
                .replace("", "Não informado")
                .value_counts()
                .head(5)
                .reset_index()
            )
            top5.columns = ["Raça", "Quantidade"]

            if not top5.empty:
                fig_top = px.bar(
                    top5.sort_values("Quantidade", ascending=True),
                    x="Quantidade",
                    y="Raça",
                    orientation="h",
                    text="Quantidade",
                )
                fig_top.update_traces(marker_color="#8E0E3F", textposition="outside")
                fig_top.update_layout(
                    height=260,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    xaxis_title="",
                    yaxis_title="",
                    showlegend=False,
                )
                st.plotly_chart(fig_top, use_container_width=True)
            else:
                st.info("Sem dados para o Top 5.")
        else:
            st.info("Coluna de raça não encontrada.")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card"><div class="card-title">Resumo do Mês</div>', unsafe_allow_html=True)

        first_date = None
        last_date = None
        if month_df["_data_compra"].notna().any():
            valid_dates = month_df["_data_compra"].dropna()
            if not valid_dates.empty:
                first_date = min(valid_dates)
                last_date = max(valid_dates)

        resumo_a, resumo_b = st.columns(2)
        with resumo_a:
            st.metric("Primeiro contrato", first_date.strftime("%d/%m/%Y") if first_date else "—")
            st.metric("Total de registros", f"{contracts_month}")
        with resumo_b:
            st.metric("Último contrato", last_date.strftime("%d/%m/%Y") if last_date else "—")
            st.metric("Clientes no mês", f"{clients_month}")

        st.markdown(
            """
            <div class="small-note">
                Os contratos exibidos neste mês seguem exatamente o que foi recebido na planilha de origem.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="card"><div class="card-title">Últimos Contratos</div>', unsafe_allow_html=True)
        display_cols = [c for c in [COL_NOME, COL_RACA, COL_DATA, COL_TEL] if c and c in month_df.columns]
        recent_df = month_df.copy()

        if "_data_compra" in recent_df.columns and recent_df["_data_compra"].notna().any():
            recent_df = recent_df.sort_values("_data_compra", ascending=False)
        else:
            recent_df = recent_df.tail(8).copy()

        if display_cols:
            st.dataframe(
                recent_df[display_cols].head(8),
                use_container_width=True,
                height=260,
                hide_index=True,
            )
        else:
            st.info("Não foi possível montar a lista de contratos recentes.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="search-shell">
            <div class="search-title">Busca Rápida</div>
            <div class="search-sub">Encontre contratos por nome, CPF, telefone ou e-mail e visualize todos os dados do cliente.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_value = st.text_input(
        "Buscar cliente ou contrato",
        placeholder="Digite nome, CPF, telefone ou e-mail...",
        label_visibility="collapsed",
    )

    selected_record = None
    search_results = pd.DataFrame()

    if search_value.strip():
        q = search_value.strip().lower()
        q_digits = re.sub(r"\D", "", q)

        mask = (
            df["_nome_norm"].str.lower().str.contains(q, na=False)
            | df["_email_norm"].str.contains(q, na=False)
            | df["_tel_norm"].str.contains(q_digits, na=False)
            | df["_cpf_norm"].str.contains(q_digits, na=False)
        )
        search_results = df[mask].copy()

        if search_results.empty:
            st.warning("Nenhum cliente encontrado para essa busca.")
        else:
            search_results = search_results.copy()
            if "_data_compra" in search_results.columns:
                search_results["_data_label"] = search_results["_data_compra"].apply(
                    lambda d: d.strftime("%d/%m/%Y") if d else "Sem data"
                )
            else:
                search_results["_data_label"] = "Sem data"

            option_labels = []
            for idx, row in search_results.head(50).iterrows():
                nome = normalize_text(row.get(COL_NOME, "Cliente sem nome")) or "Cliente sem nome"
                cpf = format_cpf(row.get(COL_CPF, "")) if COL_CPF else ""
                tel = format_phone(row.get(COL_TEL, "")) if COL_TEL else ""
                data_label = row.get("_data_label", "Sem data")
                label = f"{nome} • {data_label}"
                if cpf:
                    label += f" • CPF {cpf}"
                elif tel:
                    label += f" • {tel}"
                option_labels.append((label, idx))

            selected_label = st.selectbox(
                "Selecione o registro",
                options=option_labels,
                format_func=lambda x: x[0],
            )
            selected_record = search_results.loc[selected_label[1]]

    elif search_top.strip() and not filtered_df.empty:
        selected_record = filtered_df.iloc[0]

    if selected_record is not None:
        nome_sel = normalize_text(selected_record.get(COL_NOME, "Cliente")) or "Cliente"

        st.markdown(
            f"""
            <div class="client-preview">
                <div class="client-title">
                    {nome_sel}
                    <span class="detail-badge">registro da base</span>
                </div>
                <div class="small-note">
                    Visualização completa das informações recebidas para este cliente.
                </div>
            """,
            unsafe_allow_html=True,
        )

        ordered = [c for c in [COL_NOME, COL_TEL, COL_CPF, COL_EMAIL, COL_DATA, COL_MES, COL_RACA] if c]
        render_detail_grid(selected_record, ordered)

        if COL_NOME and COL_NOME in df.columns:
            hist = df[df["_nome_norm"].str.lower() == nome_sel.lower()].copy()
            if len(hist) > 1:
                hist_cols = [c for c in [COL_NOME, COL_DATA, COL_RACA, COL_TEL, COL_EMAIL] if c and c in hist.columns]
                st.markdown("### Histórico do cliente na base")
                st.dataframe(
                    hist[hist_cols].copy(),
                    use_container_width=True,
                    hide_index=True,
                    height=min(320, 80 + 35 * len(hist)),
                )

        st.markdown("</div>", unsafe_allow_html=True)

elif page == "Pedigree":
    render_placeholder_page(
        "Pedigree",
        "Aqui ficará a página exclusiva de Pedigree."
    )

elif page == "Comissão":
    render_placeholder_page(
        "Comissão",
        "Aqui ficará a página exclusiva de Comissão."
    )
