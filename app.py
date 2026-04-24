import re
import time
import base64
import html
import datetime as dt
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Dashboard Vendas Clear",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_TTL_SECONDS = 60
SHEET_ID = "1Q0mLvOBxEGCojUITBLxCXRtpXVMAHE3ngvGsa2Cgf9Q"
GID_BASE = 1396326144


def image_to_base64(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return base64.b64encode(file_path.read_bytes()).decode()


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


def parse_date_any(v) -> Optional[dt.date]:
    if pd.isna(v):
        return None

    s = str(v).strip()
    if not s:
        return None

    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"]:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except Exception:
            pass

    d = pd.to_datetime(s, dayfirst=True, errors="coerce")
    if pd.isna(d):
        return None

    return d.date()


def format_date(v) -> str:
    d = parse_date_any(v)
    if d:
        return d.strftime("%d/%m/%Y")
    return normalize_text(v)


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
    for col in df.columns:
        lc = str(col).strip().lower()
        for group in keywords:
            if all(k in lc for k in group):
                return col
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
                return yy, mm

        m2 = re.search(r"(20\d{2})[-/](\d{1,2})", s)
        if m2:
            yy = int(m2.group(1))
            mm = int(m2.group(2))
            if 1 <= mm <= 12:
                return yy, mm

        nomes = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
            "abril": 4, "maio": 5, "junho": 6, "julho": 7,
            "agosto": 8, "setembro": 9, "outubro": 10,
            "novembro": 11, "dezembro": 12,
        }

        for nome, num in nomes.items():
            if nome in s:
                ano_match = re.search(r"(20\d{2})", s)
                ano = int(ano_match.group(1)) if ano_match else dt.date.today().year
                return ano, num

    d = parse_date_any(raw_data)
    if d:
        return d.year, d.month

    return None


def normalize_header_name(s: str) -> str:
    s = str(s).strip().lower()
    s = s.replace("º", "o").replace("°", "o")
    s = re.sub(r"\s+", " ", s)
    return s


def find_matching_columns(df: pd.DataFrame, target: str) -> list[str]:
    target_norm = normalize_header_name(target)
    return [c for c in df.columns if normalize_header_name(c) == target_norm]


def count_filled_matching_columns(df_month: pd.DataFrame, target: str) -> int:
    matching_cols = find_matching_columns(df_month, target)
    if not matching_cols:
        return 0

    masks = []
    for col in matching_cols:
        s = df_month[col]
        if isinstance(s, pd.DataFrame):
            for subcol in s.columns:
                ss = s[subcol]
                masks.append((~ss.isna()) & (ss.astype(str).str.strip() != ""))
        else:
            masks.append((~s.isna()) & (s.astype(str).str.strip() != ""))

    if not masks:
        return 0

    final_mask = masks[0].copy()
    for m in masks[1:]:
        final_mask = final_mask | m

    return int(final_mask.sum())


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


def render_placeholder_page(title: str, subtitle: str):
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="empty-page-card">
            <div class="empty-page-title">{title}</div>
            <div class="empty-page-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_realtime_table(df_table: pd.DataFrame, cols_to_show: list[str]):
    safe_rows = []

    for _, row in df_table.iterrows():
        cells = []

        for col in cols_to_show:
            val = normalize_text(row.get(col, ""))

            if "data" in normalize_header_name(col) or "nascimento" in normalize_header_name(col):
                val = format_date(val)

            if normalize_header_name(col) == "telefone":
                digits = only_digits(val)
                cell = f"""
                <div class="phone-cell">
                    <span>{html.escape(val)}</span>
                    <button class="copy-btn" onclick="copyText('{html.escape(digits)}', this)">Copiar</button>
                </div>
                """
            else:
                cell = html.escape(val)

            cells.append(f"<td>{cell}</td>")

        safe_rows.append("<tr>" + "".join(cells) + "</tr>")

    headers = "".join([f"<th>{html.escape(c)}</th>" for c in cols_to_show])
    rows = "".join(safe_rows)

    table_html = f"""
    <html>
    <head>
        <style>
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: transparent;
            }}

            .table-wrap {{
                border: 1px solid #E7EAF3;
                border-radius: 18px;
                overflow: auto;
                background: white;
                max-height: 520px;
            }}

            table {{
                border-collapse: collapse;
                width: 100%;
                min-width: 980px;
                font-size: 13px;
            }}

            thead th {{
                position: sticky;
                top: 0;
                background: #071B49;
                color: white;
                padding: 12px 10px;
                text-align: left;
                z-index: 2;
                white-space: nowrap;
            }}

            tbody td {{
                border-bottom: 1px solid #EEF1F7;
                padding: 10px;
                color: #17213A;
                white-space: nowrap;
            }}

            tbody tr:hover {{
                background: #F8FAFF;
            }}

            .phone-cell {{
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .copy-btn {{
                border: none;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 700;
                background: #D39A33;
                color: white;
                cursor: pointer;
            }}

            .copy-btn:hover {{
                filter: brightness(0.95);
            }}
        </style>
    </head>

    <body>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>{headers}</tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>

        <script>
            function copyText(text, btn) {{
                navigator.clipboard.writeText(text).then(function() {{
                    const old = btn.innerText;
                    btn.innerText = "Copiado";
                    setTimeout(function() {{
                        btn.innerText = old;
                    }}, 1200);
                }});
            }}
        </script>
    </body>
    </html>
    """

    components.html(table_html, height=560, scrolling=True)


st.markdown(
    """
<style>
    :root{
        --navy:#071B49;
        --wine:#8E0E3F;
        --gold:#D39A33;
        --bg:#F4F6FB;
        --card:#FFFFFF;
        --line:#E7EAF3;
        --text:#18243D;
        --muted:#6B7280;
    }

    .stApp { background: var(--bg); }
    [data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer { visibility: hidden; }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--navy) 0%, #051535 100%);
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    [data-testid="stSidebar"] > div:first-child { padding-top: 0rem !important; }

    [data-testid="stSidebar"] .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0.5rem !important;
    }

    [data-testid="stSidebar"] * { color: white; }

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

    div[role="radiogroup"] > label {
        padding: 0.48rem 0.25rem !important;
        margin-bottom: 0.22rem !important;
        min-height: 42px !important;
        border-radius: 10px;
        display: flex !important;
        align-items: center !important;
    }

    div[role="radiogroup"] label p {
        font-size: 1.08rem !important;
        font-weight: 600 !important;
    }

    .sidebar-logo-bottom {
        width: 100%;
        display: flex;
        justify-content: center;
        margin-top: 2rem;
    }

    .sidebar-logo-circle {
        width: 145px;
        height: 145px;
        border-radius: 50%;
        overflow: hidden;
        border: 3px solid var(--gold);
        display: flex;
        align-items: center;
        justify-content: center;
        background: #1f5ca8;
    }

    .sidebar-logo-circle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
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

    .section-space { margin-top: 1rem; }

    .live-card {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        margin-top: 1rem;
    }

    .live-title {
        color: var(--text);
        font-size: 1.2rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .live-sub {
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 0.8rem;
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


with st.sidebar:
    logo_b64 = image_to_base64("campmotors.png")

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

    if logo_b64:
        st.markdown(
            f"""
            <div class="sidebar-logo-bottom">
                <div class="sidebar-logo-circle">
                    <img src="data:image/png;base64,{logo_b64}">
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


df = load_data().copy()

COL_NOME = "Nome" if "Nome" in df.columns else detect_col(df, [["nome"]])
COL_TEL = "Telefone" if "Telefone" in df.columns else detect_col(df, [["telefone"]])
COL_CPF = "CPF" if "CPF" in df.columns else detect_col(df, [["cpf"]])
COL_EMAIL = detect_col(df, [["e-mail"], ["email"]])
COL_DATA = detect_col(df, [["data", "compra"], ["data"]])
COL_MES = detect_col(df, [["mês"], ["mes"]])
COL_RACA = detect_col(df, [["raça"], ["raca"]])
COL_WHATSAPP = "WhatsApp" if "WhatsApp" in df.columns else detect_col(df, [["whatsapp"], ["whats"]])

df["_data_compra"] = df[COL_DATA].apply(parse_date_any) if COL_DATA else None
df["_mes_key"] = df.apply(lambda row: build_month_key(row, COL_MES, COL_DATA), axis=1)

df["_nome_norm"] = df[COL_NOME].astype(str).str.strip() if COL_NOME and COL_NOME in df.columns else ""
df["_tel_norm"] = df[COL_TEL].apply(only_digits) if COL_TEL and COL_TEL in df.columns else ""
df["_cpf_norm"] = df[COL_CPF].apply(only_digits) if COL_CPF and COL_CPF in df.columns else ""
df["_email_norm"] = df[COL_EMAIL].astype(str).str.strip().str.lower() if COL_EMAIL and COL_EMAIL in df.columns else ""
df["_raca_norm"] = df[COL_RACA].astype(str).str.strip() if COL_RACA and COL_RACA in df.columns else "Não informado"

all_months = sorted(
    [m for m in df["_mes_key"].dropna().unique().tolist()],
    key=lambda x: (x[0], x[1]),
)

if all_months:
    default_month = all_months[-1]
else:
    today = dt.date.today()
    default_month = (today.year, today.month)
    all_months = [default_month]


if page == "Visão Geral":
    header_left, header_right = st.columns([3.2, 1.2])

    with header_left:
        st.markdown('<div class="page-title">Visão Geral</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="page-subtitle">Acompanhe os contratos recebidos em tempo real, filtrados pelo mês selecionado.</div>',
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

    primeiro_contato = count_filled_matching_columns(month_df, "1° contato")
    segundo_contato = count_filled_matching_columns(month_df, "2° contato")
    terceiro_contato = count_filled_matching_columns(month_df, "3° contato")
    total_contratos = len(month_df)

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        card_metric("Primeiro contato", f"{primeiro_contato}", "no mês", "📞", "#8E0E3F")

    with m2:
        card_metric("Segundo contato", f"{segundo_contato}", "no mês", "📋", "#071B49")

    with m3:
        card_metric("Terceiro contato", f"{terceiro_contato}", "no mês", "🗂", "#D39A33")

    with m4:
        card_metric("Total de contratos", f"{total_contratos}", month_key_to_label(selected_month), "📄", "#071B49")

    st.markdown(
        f"""
        <div class="live-card">
            <div class="live-title">Contratos em tempo real</div>
            <div class="live-sub">
                Exibindo {len(filtered_df)} registros de {month_key_to_label(selected_month)} até a coluna WhatsApp.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols_until_whatsapp = []

    if COL_WHATSAPP and COL_WHATSAPP in df.columns:
        end_idx = list(df.columns).index(COL_WHATSAPP)
        cols_until_whatsapp = [
            c for c in df.columns[: end_idx + 1]
            if not str(c).startswith("_") and not str(c).lower().startswith("unnamed")
        ]
    else:
        preferred_cols = [COL_NOME, COL_TEL, COL_RACA, COL_DATA]
        cols_until_whatsapp = [c for c in preferred_cols if c and c in df.columns]

    render_realtime_table(filtered_df, cols_until_whatsapp)

elif page == "Pedigree":
    render_placeholder_page("Pedigree", "Aqui ficará a página exclusiva de Pedigree.")

elif page == "Comissão":
    render_placeholder_page("Comissão", "Aqui ficará a página exclusiva de Comissão.")
