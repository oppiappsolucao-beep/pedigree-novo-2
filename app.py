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
            "janeiro": 1,
            "fevereiro": 2,
            "março": 3,
            "marco": 3,
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
        "Endereço completo",
        "Status Pedigree",
        "Transferência",
        "Observações Status",
        "Nome Cachorro",
        "Data Nascimento",
        "Pelagem",
        "Raça",
        "Sexo",
        "Cor",
        "Microchip",
        "Observações gerais",
        "Data Compra",
        "Mês",
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

    if status_atual in status_opcoes:
        status_index = status_opcoes.index(status_atual)
    else:
        status_index = 0

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

    month_df = df[df["_mes_key"] == selected_month].copy() if not df.empty and "_mes_key" in df.columns else pd.DataFrame()

    races = ["Todas"]
    if not month_df.empty and COL_RACA and COL_RACA in month_df.columns:
        race_vals = sorted([r for r in month_df[COL_RACA].dropna().astype(str).str.strip().unique() if r])
        races += race_vals

    filter_col1, filter_col2 = st.columns([1.2, 1.2])

    with filter_col1:
        selected_race = st.selectbox("Raça", races, index=0)

    with filter_col2:
        search_top = st.text_input("Busca rápida", placeholder="Nome, CPF, telefone ou e-mail")

    filtered_df = month_df.copy()

    if not filtered_df.empty:
        if selected_race != "Todas" and COL_RACA and COL_RACA in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[COL_RACA].astype(str).str.strip() == selected_race].copy()

        if search_top.strip():
            q = normalize_search_text(search_top)
            q_digits = re.sub(r"\D", "", search_top)

            mask = filtered_df["_nome_norm"].str.contains(q, na=False)

            if q_digits:
                mask = (
                    mask
                    | filtered_df["_tel_norm"].str.contains(q_digits, na=False)
                    | filtered_df["_cpf_norm"].str.contains(q_digits, na=False)
                )

            if "_email_norm" in filtered_df.columns:
                mask = mask | filtered_df["_email_norm"].str.contains(q, na=False)

            filtered_df = filtered_df[mask].copy()

    primeiro_contato = count_filled_matching_columns(month_df, "1° contato") if not month_df.empty else 0
    segundo_contato = count_filled_matching_columns(month_df, "2° contato") if not month_df.empty else 0
    terceiro_contato = count_filled_matching_columns(month_df, "3° contato") if not month_df.empty else 0
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

    if not filtered_df.empty:
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
    st.markdown('<div class="page-title">Pedigree</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Consulta completa de clientes para análise de Pedigree.</div>',
        unsafe_allow_html=True,
    )

    status_opcoes = [
        "Pendências / Problemas",
        "Fazer Pedigree venda",
        "Fazer Pedigree s/ trans",
        "Fazer RG/Certidão",
        "Aprovação Cliente",
        "Para Imprimir Pedigree",
        "Imprimir Etiqueta",
        "Imprimir RG + Certidão",
        "Airtag",
        "Envio Correio",
        "Postado/Enviado Correio",
        "Postado/Enviado Corr",
        "Postado/ enviado loja",
        "Pendência Cliente",
        "Sem Matriz",
    ]

    MAP_STATUS_ACAO = {
        "Fazer Pedigree venda": "Transferência",
        "Fazer Pedigree s/ trans": "Sem transferência",
        "Fazer RG/Certidão": "RG E CERTIDÃO",
        "Pendências / Problemas": "Problemas",
        "Aprovação Cliente": "Aprovação",
        "Para Imprimir Pedigree": "Imprimir Pedigree",
        "Imprimir Etiqueta": "Imprimir etiqueta",
        "Imprimir RG + Certidão": "Imprimir RG e CERTIDÃO",
        "Airtag": "Airtag",
        "Envio Correio": "Enviar",
        "Postado/Enviado Correio": "Enviado Cliente",
        "Postado/Enviado Corr": "Enviado Cliente",
        "Postado/ enviado loja": "Enviado Cliente",
        "Pendência Cliente": "Problemas",
        "Sem Matriz": "Problemas",
    }

    df_ped = load_pedigree_data().copy()

    if not df_ped.empty:
        df_ped["__row_number"] = df_ped.index + 2

        for col in [
            "Nome",
            "Telefone",
            "CPF",
            "E-mail",
            "Endereço completo",
            "Status Pedigree",
            "Transferência",
            "Observações Status",
            "Nome Cachorro",
            "Data Nascimento",
            "Pelagem",
            "Raça",
            "Sexo",
            "Cor",
            "Microchip",
            "Observações gerais",
            "Data Compra",
            "Mês",
        ]:
            if col not in df_ped.columns:
                df_ped[col] = ""

        ped_col_data = "Data Compra" if "Data Compra" in df_ped.columns else None
        ped_col_mes = "Mês" if "Mês" in df_ped.columns else None
        df_ped["_mes_key"] = df_ped.apply(lambda row: build_month_key(row, ped_col_mes, ped_col_data), axis=1)

        def normalize_full_row(row):
            values = []
            for v in row:
                if pd.isna(v):
                    continue
                values.append(normalize_search_text(v))
            return " ".join(values)

        df_ped["_search_all"] = df_ped.apply(normalize_full_row, axis=1)
        df_ped["_tel_digits_ped"] = df_ped["Telefone"].apply(only_digits)
        df_ped["ACAO"] = df_ped["Status Pedigree"].map(MAP_STATUS_ACAO).fillna("")
    else:
        df_ped = pd.DataFrame(columns=[
            "Nome", "Telefone", "CPF", "E-mail", "Endereço completo",
            "Status Pedigree", "Transferência", "Observações Status",
            "Nome Cachorro", "Data Nascimento", "Pelagem", "Raça",
            "Sexo", "Cor", "Microchip", "Observações gerais",
            "Data Compra", "Mês", "__row_number", "_search_all",
            "_tel_digits_ped", "ACAO", "_mes_key"
        ])

    ped_months_from_sheet = []
    if not df_ped.empty and "_mes_key" in df_ped.columns:
        ped_months_from_sheet = [m for m in df_ped["_mes_key"].dropna().unique().tolist()]

    main_months_from_sheet = []
    if not df.empty and "_mes_key" in df.columns:
        main_months_from_sheet = [m for m in df["_mes_key"].dropna().unique().tolist()]

    ped_month_options = sorted(
        list(set(ped_months_from_sheet + main_months_from_sheet + future_months)),
        key=lambda x: (x[0], x[1]),
    )

    if not ped_month_options:
        ped_month_options = [(today.year, today.month)]

    default_ped_month = (today.year, today.month) if (today.year, today.month) in ped_month_options else ped_month_options[-1]

    filtro_mes_col, vazio_col = st.columns([1.2, 2.8])

    with filtro_mes_col:
        selected_ped_month = st.selectbox(
            "Mês de referência",
            options=ped_month_options,
            index=ped_month_options.index(default_ped_month) if default_ped_month in ped_month_options else 0,
            format_func=month_key_to_label,
            key="mes_referencia_pedigree",
        )

    busca_ped = st.text_input(
        "Buscar cliente no Pedigree",
        placeholder="Cole o telefone copiado da Visão Geral ou busque por nome, código, status, raça...",
    )

    if busca_ped.strip():
        q = normalize_search_text(busca_ped)
        q_digits = re.sub(r"\D", "", busca_ped)

        mask = df_ped["_search_all"].str.contains(q, na=False)

        if q_digits:
            clean_variants = [q_digits]

            if q_digits.startswith("55") and len(q_digits) > 11:
                clean_variants.append(q_digits[2:])

            phone_mask = pd.Series(False, index=df_ped.index)

            for variant in clean_variants:
                phone_mask = phone_mask | df_ped["_tel_digits_ped"].str.contains(variant, na=False)

            mask = mask | phone_mask

        df_busca = df_ped[mask].copy()

        if not df_busca.empty:
            cols_ped = [
                c for c in df_busca.columns
                if not str(c).startswith("_") and c not in ["ACAO", "__row_number"]
            ]
            render_realtime_table(df_busca, cols_ped)
        else:
            st.warning("Nenhum cliente encontrado com essa busca.")

    st.markdown('<div class="ped-btn-title">Ações do Pedigree</div>', unsafe_allow_html=True)

    if "acao_ped" not in st.session_state:
        st.session_state.acao_ped = None

    def set_acao_ped(nome):
        st.session_state.acao_ped = nome

    linha1 = st.columns(4)
    linha2 = st.columns(4)
    linha3 = st.columns(4)

    with linha1[0]:
        st.button("Novo", use_container_width=True, on_click=set_acao_ped, args=("Novo",))
    with linha1[1]:
        st.button("Transferência", use_container_width=True, on_click=set_acao_ped, args=("Transferência",))
    with linha1[2]:
        st.button("Sem transferência", use_container_width=True, on_click=set_acao_ped, args=("Sem transferência",))
    with linha1[3]:
        st.button("RG E CERTIDÃO", use_container_width=True, on_click=set_acao_ped, args=("RG E CERTIDÃO",))

    with linha2[0]:
        st.button("Problemas", use_container_width=True, on_click=set_acao_ped, args=("Problemas",))
    with linha2[1]:
        st.button("Aprovação", use_container_width=True, on_click=set_acao_ped, args=("Aprovação",))
    with linha2[2]:
        st.button("Imprimir Pedigree", use_container_width=True, on_click=set_acao_ped, args=("Imprimir Pedigree",))
    with linha2[3]:
        st.button("Imprimir RG e CERTIDÃO", use_container_width=True, on_click=set_acao_ped, args=("Imprimir RG e CERTIDÃO",))

    with linha3[0]:
        st.button("Imprimir etiqueta", use_container_width=True, on_click=set_acao_ped, args=("Imprimir etiqueta",))
    with linha3[1]:
        st.button("Airtag", use_container_width=True, on_click=set_acao_ped, args=("Airtag",))
    with linha3[2]:
        st.button("Enviar", use_container_width=True, on_click=set_acao_ped, args=("Enviar",))
    with linha3[3]:
        st.button("Enviado Cliente", use_container_width=True, on_click=set_acao_ped, args=("Enviado Cliente",))

    if st.session_state.acao_ped:
        acao_atual = st.session_state.acao_ped

        st.markdown(
            f"""
            <div class="ped-action-card">
                <div class="ped-action-title">{html.escape(acao_atual)}</div>
                <div class="ped-action-sub">
                    Área aberta dentro da própria página Pedigree.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if acao_atual == "Novo":
            st.markdown("### Formulário Pedigree")

            with st.form("formulario_pedigree_novo"):
                st.markdown("#### Informações Tutor")

                col1, col2 = st.columns(2)

                with col1:
                    tutor_nome = st.text_input("Nome do tutor")
                    tutor_telefone = st.text_input("Telefone")
                    tutor_cpf = st.text_input("CPF")
                    tutor_email = st.text_input("E-mail")
                    tutor_endereco = st.text_input("Endereço completo")

                with col2:
                    status_cliente = st.selectbox("Status do Pedigree", status_opcoes)
                    transferencia = st.radio("Houve pedido de transferência?", ["Sim", "Não"], horizontal=True)
                    observacoes_status = st.text_area("Observações do status")

                st.markdown("#### Informações Cão")

                col3, col4 = st.columns(2)

                with col3:
                    cao_nome = st.text_input("Nome do cão")
                    nascimento = st.date_input("Data de nascimento")
                    pelagem = st.text_input("Pelagem")
                    raca = st.text_input("Raça do pet")
                    sexo = st.selectbox("Sexo", ["", "MACHO", "FÊMEA"])
                    cor = st.text_input("Cor")
                    microchip = st.text_input("Microchip")

                with col4:
                    foto_pet = st.file_uploader("Foto do pet", type=["png", "jpg", "jpeg"])
                    if foto_pet:
                        st.image(foto_pet, caption="Foto do pet", width=220)

                observacoes = st.text_area("Observações gerais")

                salvar = st.form_submit_button("Executar tudo")

                if salvar:
                    hoje = dt.date.today()

                    dados_formulario = {
                        "Nome": tutor_nome,
                        "Telefone": tutor_telefone,
                        "CPF": tutor_cpf,
                        "E-mail": tutor_email,
                        "Endereço completo": tutor_endereco,
                        "Status Pedigree": status_cliente,
                        "Transferência": transferencia,
                        "Observações Status": observacoes_status,
                        "Nome Cachorro": cao_nome,
                        "Data Nascimento": nascimento.strftime("%d/%m/%Y"),
                        "Pelagem": pelagem,
                        "Raça": raca,
                        "Sexo": sexo,
                        "Cor": cor,
                        "Microchip": microchip,
                        "Observações gerais": observacoes,
                        "Data Compra": hoje.strftime("%d/%m/%Y"),
                        "Mês": hoje.strftime("%m/%Y"),
                    }

                    try:
                        salvar_formulario_pedigree(dados_formulario)
                        st.session_state["novo_pedigree_form"] = dados_formulario
                        st.success("Formulário salvo/atualizado na planilha com sucesso.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")

        else:
            df_acao = df_ped[df_ped["ACAO"] == acao_atual].copy()
            total_acao = len(df_acao)

            st.markdown(
                f"""
                <div class="ped-count-card">
                    📂 {total_acao} formulário(s) em {html.escape(acao_atual)}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if total_acao > 0:
                opcoes_clientes = []

                for _, row in df_acao.iterrows():
                    nome_row = normalize_text(row.get("Nome", ""))
                    tel_row = format_phone_br(row.get("Telefone", ""))
                    row_number = int(row.get("__row_number", 0))

                    if nome_row:
                        label = f"{nome_row} — {tel_row}"
                    else:
                        label = f"Sem nome — linha {row_number}"

                    opcoes_clientes.append((label, row_number))

                labels = [x[0] for x in opcoes_clientes]

                nome_escolhido = st.selectbox(
                    "Clique e selecione um nome para abrir a ficha",
                    labels,
                    key=f"select_{acao_atual}",
                )

                row_escolhida = dict(opcoes_clientes)[nome_escolhido]
                cliente = df_acao[df_acao["__row_number"] == row_escolhida].iloc[0]

                render_cliente_card(cliente, status_opcoes)
            else:
                st.info("Nenhum formulário nesta ação no momento.")

    st.markdown("<br><br>", unsafe_allow_html=True)

    df_ped_mes = df_ped[df_ped["_mes_key"] == selected_ped_month].copy() if "_mes_key" in df_ped.columns else pd.DataFrame()
    df_caes_mes = df[df["_mes_key"] == selected_ped_month].copy() if not df.empty and "_mes_key" in df.columns else pd.DataFrame()

    if not df_ped_mes.empty and "Status Pedigree" in df_ped_mes.columns:
        total_pedigrees_vendidos = int(
            df_ped_mes["Status Pedigree"].apply(is_status_pedigree_vendido).sum()
        )
    else:
        total_pedigrees_vendidos = 0

    if not df_caes_mes.empty and COL_NOME and COL_NOME in df_caes_mes.columns:
        total_caes_vendidos = int(
            (df_caes_mes[COL_NOME].astype(str).str.strip() != "").sum()
        )
    else:
        total_caes_vendidos = 0

    total_col1, total_col2 = st.columns(2)

    with total_col1:
        card_metric_big(
            "Total de Pedigrees",
            f"{total_pedigrees_vendidos}",
            f"vendidos em {month_key_to_label(selected_ped_month)}",
            "⚖️",
            "#8E0E3F",
        )

    with total_col2:
        card_metric_big(
            "Cães vendidos",
            f"{total_caes_vendidos}",
            f"no mês de {month_key_to_label(selected_ped_month)}",
            "🐶",
            "#071B49",
        )


elif page == "Comissão":
    render_placeholder_page("Comissão", "Aqui ficará a página exclusiva de Comissão.")
