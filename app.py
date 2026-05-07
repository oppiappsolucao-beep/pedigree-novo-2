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
COMM_WORKSHEET_NAME = "Pedigree Comissão Ju"

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


@st.cache_data(show_spinner=False, ttl=CACHE_TTL_SECONDS)
def load_commission_data() -> pd.DataFrame:
    worksheet = get_worksheet(COMM_WORKSHEET_NAME)
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


def parse_money(v) -> float:
    if pd.isna(v):
        return 0.0
    s = str(v).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return 0.0


def format_money(v) -> str:
    try:
        n = float(v)
    except Exception:
        n = 0.0
    return f"R$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
        "",
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
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

    row_values = [dados.get(header, "") for header in headers]

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


def render_realtime_table(df_table: pd.DataFrame, cols_to_show: list[str], height: int = 590):
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
                max-height: {height - 30}px;
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

    components.html(table_html, height=height, scrolling=True)


# O código completo está no arquivo gerado anteriormente. A alteração principal está no bloco final:
# elif page == "Comissão":
#     ... renderiza apenas a caixa "Comissão Jullia".
