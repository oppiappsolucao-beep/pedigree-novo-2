import time
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Teste planilha", layout="wide")

SHEET_ID = "1Q0mLvOBxEGCojUITBLxCXRtpXVMAHE3ngvGsa2Cgf9Q"
GID_BASE = 1396326144

@st.cache_data(ttl=60)
def load_data():
    bust = int(time.time() * 1000)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID_BASE}&_={bust}"
    df = pd.read_csv(url)
    df.columns = [str(c).strip() for c in df.columns]
    return df

st.title("Teste da planilha")

try:
    df = load_data()
    st.success("Planilha carregada com sucesso")
    st.write("Colunas encontradas:")
    st.write(list(df.columns))
    st.write("Quantidade de linhas:", len(df))
    st.dataframe(df.head(10), use_container_width=True)
except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
    st.exception(e)
