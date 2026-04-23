import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import time

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Dashboard Vendas Clear",
    layout="wide",
    initial_sidebar_state="expanded"
)

SHEET_ID = "1Q0mLvOBxEGCojUITBLxCXRtpXVMAHE3ngvGsa2Cgf9Q"
GID = 1396326144

# =========================================================
# ESTILO
# =========================================================
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #071B49 0%, #051535 100%);
}

.brand-box {
    padding: 10px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}

.brand-logo {
    width: 60px;
    height: 60px;
    border: 2px solid #D39A33;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    color: #D39A33;
    margin-bottom: 5px;
}

.brand-title {
    color: #F6D089;
    font-size: 16px;
    font-weight: bold;
}

.brand-sub {
    color: #E7C27A;
    font-size: 11px;
}

.brand-user {
    width: 45px;
    height: 45px;
    border: 2px solid #D39A33;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 6px;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("""
    <div class="brand-box">
        <div class="brand-logo">⚖</div>
        <div class="brand-title">DASHBOARD VENDAS CLEAR</div>
        <div class="brand-sub">GESTÃO DE CONTRATOS</div>
        <div class="brand-user">👤</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Menu",
        ["Visão Geral", "Pedigree", "Comissão"],
        label_visibility="collapsed"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # 🔥 LOGO CORRIGIDA AQUI
    logo_path = Path("campmotors.png")

    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
    else:
        st.error("Imagem não encontrada!")

# =========================================================
# DADOS
# =========================================================
@st.cache_data(ttl=60)
def load_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}&_={int(time.time())}"
    return pd.read_csv(url)

df = load_data()

# =========================================================
# PÁGINAS
# =========================================================
if page == "Visão Geral":

    st.title("Visão Geral")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total", len(df))
    col2.metric("Clientes", df.iloc[:,0].nunique() if not df.empty else 0)
    col3.metric("Linhas", len(df))

    if not df.empty:
        st.dataframe(df)

elif page == "Pedigree":
    st.title("Pedigree")
    st.info("Página em construção")

elif page == "Comissão":
    st.title("Comissão")
    st.info("Página em construção")
