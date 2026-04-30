import re
import base64
import html
import unicodedata
import datetime as dt
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials


st.set_page_config(
    page_title="Dashboard Vendas Clear",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_TTL_SECONDS = 60
SHEET_ID = "1Q0mLvOBxEGCojUITBLxCXRtpXVMAHE3ngvGsa2Cgf9Q"

MAIN_WORKSHEET_NAME = "Clear"
PED_WORKSHEET_NAME = "Planilha Dash Valéria sem mayra"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def get_gsheet_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def get_worksheet(worksheet_name: str):
    client = get_gsheet_client()
    sheet = client.open_by_key(SHEET_ID)
    return sheet.worksheet(worksheet_name)


@st.cache_data(show_spinner=False, ttl=CACHE_TTL_SECONDS)
def load_main_data() -> pd.DataFrame:
    worksheet = get_worksheet(MAIN_WORKSHEET_NAME)
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(show_spinner=False, ttl=CACHE_TTL_SECONDS)
def load_pedigree_data() -> pd.DataFrame:
    worksheet = get_worksheet(PED_WORKSHEET_NAME)
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def image_to_base64(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return base64.b64encode(file_path.read_bytes()).decode()


def normalize_text(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip()


def normalize_search_text(v) -> str:
    if pd.isna(v):
        return ""
    s = str(v).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s


def only_digits(v) -> str:
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s)


def format_phone_br(v) -> str:
    digits = only_digits(v)

    if len(digits) == 13 and digits.startswith("55"):
        digits = digits[2:]

    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"

    return digits


def parse_date_any(v) -> Optional[dt.date]:
    if pd.isna(v):
        return None

    s = str(v).strip()
    if not s:
        return None

    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%y", "%d-%m-%y"]:
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
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    return meses[m] if 1 <= m <= 12 else ""


def month_key_to_label(ym: Tuple[int, int]) -> str:
    y, m = ym
    return f"{month_name_pt(m)} / {y}"


def detect_col(df: pd.DataFrame, keywords: List[List[str]]) -> Optional[str]:
    for col in df.columns:
        lc_norm = normalize_search_text(str(col).strip().lower())
        for group in keywords:
            if all(normalize_search_text(k) in lc_norm for k in group):
                return col
    return None


def build_month_key_from_values(raw_mes="", raw_data="") -> Optional[Tuple[int, int]]:
    raw_mes = normalize_text(raw_mes)
    raw_data = normalize_text(raw_data)

    if raw_mes:
        s = normalize_search_text(raw_mes)

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
            "janeiro": 1,
            "fevereiro": 2,
            "marco": 3,
            "março": 3,
            "abril": 4,
            "maio": 5,
            "junho": 6,
            "julho": 7,
            "agosto": 8,
            "setembro": 9,
            "outubro": 10,
            "novembro": 11,
            "dezembro": 12,
        }

        for nome, num in nomes.items():
            if normalize_search_text(nome) in s:
                ano_match = re.search(r"(20\d{2})", s)
                ano = int(ano_match.group(1)) if ano_match else dt.date.today().year
                return ano, num

    d = parse_date_any(raw_data)
    if d:
        return d.year, d.month

    return None


def build_month_key(row, col_mes, col_data) -> Optional[Tuple[int, int]]:
    raw_mes = row[col_mes] if col_mes and col_mes in row else ""
    raw_data = row[col_data] if col_data and col_data in row else ""
    return build_month_key_from_values(raw_mes, raw_data)


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
        masks.append((~s.isna()) & (s.astype(str).str.strip() != ""))

    final_mask = masks[0].copy()
    for m in masks[1:]:
        final_mask = final_mask | m

    return int(final_mask.sum())


def is_status_pedigree_vendido(v) -> bool:
    status = normalize_search_text(v)
    return status.startswith("postado/enviado")


def ensure_columns(worksheet, required_cols):
    headers = worksheet.row_values(1)

    for col in required_cols:
        if col not in headers:
            headers.append(col)

    worksheet.update("A1", [headers])
    return headers


def find_row_by_phone_or_cpf(worksheet, telefone, cpf):
    records = worksheet.get_all_records()
    tel_digits = only_digits(telefone)
    cpf_digits = only_digits(cpf)

    for idx, row in enumerate(records, start=2):
        row_tel = only_digits(row.get("Telefone", ""))
        row_cpf = only_digits(row.get("CPF", ""))

        if tel_digits and row_tel == tel_digits:
            return idx

        if cpf_digits and row_cpf == cpf_digits:
            return idx

    return None


def salvar_formulario_pedigree(dados):
    worksheet = get_worksheet(PED_WORKSHEET_NAME)

    required_cols = [
        "Nome",
        "Telefone",
        "CPF",
        "E-mail",
        "Mês",
        "Raça",
        "Sexo",
        "Cor",
        "Endereço completo",
        "Status Pedigree",
        "Transferência",
        "Observações Status",
        "Nome Cachorro",
        "Data Nascimento",
        "Pelagem",
        "Microchip",
        "Observações gerais",
    ]

    headers = ensure_columns(worksheet, required_cols)

    row_number = find_row_by_phone_or_cpf(
        worksheet,
        dados.get("Telefone", ""),
        dados.get("CPF", ""),
    )

    row_values = []
    for header in headers:
        row_values.append(dados.get(header, ""))

    if row_number:
        worksheet.update(f"A{row_number}", [row_values], value_input_option="USER_ENTERED")
    else:
        worksheet.append_row(row_values, value_input_option="USER_ENTERED")

    st.cache_data.clear()


def atualizar_status_pedigree(row_number: int, novo_status: str):
    worksheet = get_worksheet(PED_WORKSHEET_NAME)

    headers = worksheet.row_values(1)

    if "Status Pedigree" not in headers:
        headers.append("Status Pedigree")
        worksheet.update("A1", [headers])

    headers = worksheet.row_values(1)
    col_number = headers.index("Status Pedigree") + 1

    worksheet.update_cell(row_number, col_number, novo_status)
    st.cache_data.clear()


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


def card_metric_big(title: str, value: str, subtitle: str, emoji: str, color: str):
    st.markdown(
        f"""
        <div class="metric-card-big">
            <div class="metric-wrap-big">
                <div class="metric-icon-big" style="background:{color};">{emoji}</div>
                <div>
                    <div class="metric-label-big">{title}</div>
                    <div class="metric-value-big">{value}</div>
                    <div class="metric-sub-big">{subtitle}</div>
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
            val = row.get(col, "")

            if normalize_header_name(col) == "telefone":
                formatted_phone = format_phone_br(val)
                digits = only_digits(val)

                if len(digits) == 13 and digits.startswith("55"):
                    copy_digits = digits
                elif len(digits) in [10, 11]:
                    copy_digits = "55" + digits
                else:
                    copy_digits = digits

                cell = f"""
                <div class="phone-cell">
                    <span>{html.escape(formatted_phone)}</span>
                    <button class="copy-btn" onclick="copyText('{html.escape(copy_digits)}', this)">Copiar</button>
                </div>
                """
            else:
                clean_val = normalize_text(val)

                if "data" in normalize_header_name(col) or "nascimento" in normalize_header_name(col):
                    clean_val = format_date(clean_val)

                cell = html.escape(clean_val)

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
                max-height: 560px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                min-width: 1100px;
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

    components.html(table_html, height=590, scrolling=True)


def render_cliente_card(cliente: pd.Series, status_opcoes: list):
    row_number = int(cliente.get("__row_number", 0))

    nome = normalize_text(cliente.get("Nome", ""))
    telefone = format_phone_br(cliente.get("Telefone", ""))
    cpf = normalize_text(cliente.get("CPF", ""))
    email = normalize_text(cliente.get("E-mail", ""))
    endereco = normalize_text(cliente.get("Endereço completo", ""))
    status_atual = normalize_text(cliente.get("Status Pedigree", ""))
    transferencia = normalize_text(cliente.get("Transferência", ""))
    obs_status = normalize_text(cliente.get("Observações Status", ""))
    cao = normalize_text(cliente.get("Nome Cachorro", ""))
    nascimento = format_date(cliente.get("Data Nascimento", ""))
    pelagem = normalize_text(cliente.get("Pelagem", ""))
    raca = normalize_text(cliente.get("Raça", ""))
    sexo = normalize_text(cliente.get("Sexo", ""))
    cor = normalize_text(cliente.get("Cor", ""))
    microchip = normalize_text(cliente.get("Microchip", ""))
    obs = normalize_text(cliente.get("Observações gerais", ""))

    st.markdown(
        f"""
        <div class="ped-ficha">
            <div class="ped-ficha-title">{html.escape(nome)}</div>
            <div class="ped-ficha-sub">Ficha completa do formulário</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status_index = status_opcoes.index(status_atual) if status_atual in status_opcoes else 0

    col_status_1, col_status_2 = st.columns([3, 1])

    with col_status_1:
        novo_status = st.selectbox(
            "Status do Pedigree",
            status_opcoes,
            index=status_index,
            key=f"status_pedigree_{row_number}",
        )

    with col_status_2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Atualizar status", use_container_width=True, key=f"btn_status_{row_number}"):
            try:
                atualizar_status_pedigree(row_number, novo_status)
                st.success("Status atualizado com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar status: {e}")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Informações Tutor")
        st.write("**Nome:**", nome)
        st.write("**Telefone:**", telefone)
        st.write("**CPF:**", cpf)
        st.write("**E-mail:**", email)
        st.write("**Endereço:**", endereco)
        st.write("**Status Pedigree:**", status_atual)
        st.write("**Transferência:**", transferencia)
        st.write("**Observações Status:**", obs_status)

    with c2:
        st.markdown("#### Informações Cão")
        st.write("**Nome do cão:**", cao)
        st.write("**Data de nascimento:**", nascimento)
        st.write("**Pelagem:**", pelagem)
        st.write("**Raça:**", raca)
        st.write("**Sexo:**", sexo)
        st.write("**Cor:**", cor)
        st.write("**Microchip:**", microchip)
        st.write("**Observações gerais:**", obs)


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

    .metric-card-big {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 1.4rem 1.6rem;
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
        min-height: 165px;
        display: flex;
        align-items: center;
    }

    .metric-wrap-big {
        display: flex;
        gap: 20px;
        align-items: center;
    }

    .metric-icon-big {
        width: 72px;
        height: 72px;
        min-width: 72px;
        border-radius: 22px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 31px;
        font-weight: 900;
    }

    .metric-label-big {
        color: #55627A;
        font-size: 1.08rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }

    .metric-value-big {
        color: var(--text);
        font-size: 2.55rem;
        font-weight: 900;
        line-height: 1.02;
    }

    .metric-sub-big {
        color: var(--muted);
        font-size: 1rem;
        margin-top: 0.2rem;
    }

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

    .ped-btn-title {
        color: var(--text);
        font-size: 1.1rem;
        font-weight: 800;
        margin-top: 1rem;
        margin-bottom: 0.6rem;
    }

    .ped-action-card {
        background: white;
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1.2rem;
        margin-top: 1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
    }

    .ped-action-title {
        color: var(--text);
        font-size: 1.35rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
    }

    .ped-action-sub {
        color: var(--muted);
        font-size: 0.95rem;
    }

    .ped-count-card {
        background: #EAF2FF;
        border: 1px solid #CFE0FA;
        color: #073B7A;
        border-radius: 18px;
        padding: 1rem;
        margin-top: 1rem;
        font-weight: 700;
    }

    .ped-ficha {
        background: white;
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1.2rem;
        margin-top: 1rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
    }

    .ped-ficha-title {
        color: var(--text);
        font-size: 1.35rem;
        font-weight: 800;
    }

    .ped-ficha-sub {
        color: var(--muted);
        font-size: 0.95rem;
        margin-top: 0.2rem;
    }

    div.stButton > button {
        border-radius: 999px !important;
        border: 1px solid #D8DDEA !important;
        background: #FFFFFF !important;
        color: #071B49 !important;
        font-weight: 700 !important;
        font-size: 0.82rem !important;
        padding: 0.45rem 0.6rem !important;
        min-height: 36px !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04) !important;
    }

    div.stButton > button:hover {
        border-color: #D39A33 !important;
        color: #D39A33 !important;
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


df = load_main_data().copy()

COL_NOME = "Nome" if "Nome" in df.columns else detect_col(df, [["nome"]])
COL_TEL = "Telefone" if "Telefone" in df.columns else detect_col(df, [["telefone"]])
COL_CPF = "CPF" if "CPF" in df.columns else detect_col(df, [["cpf"]])
COL_EMAIL = detect_col(df, [["e-mail"], ["email"]])
COL_DATA = detect_col(df, [["data", "compra"], ["data"]])
COL_MES = detect_col(df, [["mês"], ["mes"]])
COL_RACA = detect_col(df, [["raça"], ["raca"]])
COL_WHATSAPP = "WhatsApp" if "WhatsApp" in df.columns else detect_col(df, [["whatsapp"], ["whats"]])

if not df.empty:
    df["_data_compra"] = df[COL_DATA].apply(parse_date_any) if COL_DATA else None
    df["_mes_key"] = df.apply(lambda row: build_month_key(row, COL_MES, COL_DATA), axis=1)

    df["_nome_norm"] = df[COL_NOME].apply(normalize_search_text) if COL_NOME and COL_NOME in df.columns else ""
    df["_tel_norm"] = df[COL_TEL].apply(only_digits) if COL_TEL and COL_TEL in df.columns else ""
    df["_cpf_norm"] = df[COL_CPF].apply(only_digits) if COL_CPF and COL_CPF in df.columns else ""
    df["_email_norm"] = df[COL_EMAIL].apply(normalize_search_text) if COL_EMAIL and COL_EMAIL in df.columns else ""
    df["_raca_norm"] = df[COL_RACA].astype(str).str.strip() if COL_RACA and COL_RACA in df.columns else "Não informado"

    all_months = sorted(
        [m for m in df["_mes_key"].dropna().unique().tolist()],
        key=lambda x: (x[0], x[1]),
    )
else:
    all_months = []

today = dt.date.today()
future_months = []
for i in range(0, 12):
    month = today.month + i
    year = today.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    future_months.append((year, month))

all_months = sorted(list(set(all_months + future_months)), key=lambda x: (x[0], x[1]))

if all_months:
    default_month = (today.year, today.month) if (today.year, today.month) in all_months else all_months[-1]
else:
    default_month = (today.year, today.month)
    all_months = [default_month]
