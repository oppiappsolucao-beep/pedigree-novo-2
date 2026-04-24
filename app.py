import re
import time
import base64
import html
import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Dashboard Vendas Clear",
    layout="wide"
)

SHEET_ID = "1Q0mLvOBxEGCojUITBLxCXRtpXVMAHE3ngvGsa2Cgf9Q"
GID = "1396326144"

# =========================================================
# LOAD DATA
# =========================================================
@st.cache_data(ttl=60)
def load_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}&_={int(time.time())}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    return df

df = load_data()

# =========================================================
# FUNÇÕES
# =========================================================
def normalize_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def format_phone_br(v):
    if pd.isna(v):
        return ""

    s = str(v).replace(".0", "").strip()
    digits = re.sub(r"\D", "", s)

    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    
    return digits


def only_digits(v):
    return re.sub(r"\D", "", normalize_text(v))


# =========================================================
# FILTRO DE MÊS
# =========================================================
def parse_date(v):
    try:
        return pd.to_datetime(v, dayfirst=True)
    except:
        return None

df["Data Compra"] = df["Data Compra"].apply(parse_date)

df["mes_ref"] = df["Data Compra"].dt.to_period("M")

meses = sorted(df["mes_ref"].dropna().unique())

mes_sel = st.selectbox(
    "Mês de referência",
    meses,
    format_func=lambda x: x.strftime("%B / %Y")
)

df = df[df["mes_ref"] == mes_sel]

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.title("📊 Dashboard Vendas Clear")
    page = st.radio("", ["Visão Geral"])

# =========================================================
# METRICAS
# =========================================================
st.title("Visão Geral")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Primeiro contato", df["1° contato"].notna().sum())
col2.metric("Segundo contato", df["2° contato"].notna().sum())
col3.metric("Terceiro contato", df["3° contato"].notna().sum())
col4.metric("Total contratos", len(df))

# =========================================================
# TABELA COM BOTÃO COPIAR
# =========================================================
st.markdown("### 📋 Contratos em tempo real")

cols = list(df.columns)

# pegar até WhatsApp
if "WhatsApp" in cols:
    cols = cols[:cols.index("WhatsApp")+1]

rows_html = ""

for _, row in df.iterrows():
    row_html = "<tr>"

    for col in cols:
        val = normalize_text(row[col])

        if col == "Telefone":
            tel_formatado = format_phone_br(val)
            digits = only_digits(val)

            cell = f"""
            <div style="display:flex;align-items:center;gap:6px;">
                <span>{tel_formatado}</span>
                <button onclick="copyText('{digits}', this)" style="
                    border:none;
                    padding:4px 8px;
                    border-radius:999px;
                    background:#D39A33;
                    color:white;
                    font-size:10px;
                    cursor:pointer;
                ">Copiar</button>
            </div>
            """
        else:
            cell = html.escape(val)

        row_html += f"<td>{cell}</td>"

    row_html += "</tr>"
    rows_html += row_html

headers = "".join([f"<th>{c}</th>" for c in cols])

html_table = f"""
<html>
<head>
<style>
table {{
    width:100%;
    border-collapse: collapse;
    font-size:13px;
}}
th {{
    background:#071B49;
    color:white;
    padding:10px;
    position:sticky;
    top:0;
}}
td {{
    padding:8px;
    border-bottom:1px solid #eee;
}}
tr:hover {{
    background:#f5f7ff;
}}
</style>
</head>

<body>
<table>
<thead>
<tr>{headers}</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>

<script>
function copyText(text, btn){{
    navigator.clipboard.writeText(text);
    btn.innerText = "Copiado";
    setTimeout(()=>btn.innerText="Copiar",1000);
}}
</script>

</body>
</html>
"""

components.html(html_table, height=600, scrolling=True)
