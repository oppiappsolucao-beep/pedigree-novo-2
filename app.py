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

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None
import gspread
from google.oauth2.service_account import Credentials


# Login atualizado: usuário clear / senha Clear@2026!

# atualização: ícone normal/colorido no card Terceiro contato
st.set_page_config(
    page_title="Dashboard Vendas Clear",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_TTL_SECONDS = 15
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
    values = worksheet.get_all_values()

    if not values:
        return pd.DataFrame()

    headers = [str(c).strip() for c in values[0]]
    rows = values[1:]

    clean_headers = []
    seen = {}

    for i, header in enumerate(headers):
        if not header:
            header = f"Coluna {i + 1}"

        if header in seen:
            seen[header] += 1
            header = f"{header}_{seen[header]}"
        else:
            seen[header] = 1

        clean_headers.append(header)

    df = pd.DataFrame(rows, columns=clean_headers)

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

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


# Valores usados no simulador da Comissão.
# Transferência na tela = Pedigree base (249,90) + Frete Correios (35,80) = 285,70.
# Sem transferência usa o mesmo valor do frete: 35,80.
VALOR_PEDIGREE_TRANSFERENCIA = 249.90
VALOR_PEDIGREE_SEM_TRANSFERENCIA = 35.80
VALOR_CORREIO = 35.80
VALOR_RG = 30.00
VALOR_CERTIDAO = 30.00
VALOR_AIRTAG = 130.00
VALOR_COMBO_RG_CERTIDAO_AIRTAG = 190.00

# Ajustes manuais definidos para meses históricos.
# Janeiro a Abril/2026 ficam fechados pela conferência manual,
# sem depender das marcações feitas no dashboard.
COMISSAO_JULLIA_HISTORICO_FIXA = {
    (2026, 1): 339.46,
    (2026, 2): 273.28,
    (2026, 3): 422.90,
    (2026, 4): 443.67,
}

VALORES_CLIENTES_HISTORICO_FIXOS = {
    ((2026, 1), normalize_search_text("Silvia Regina Leite Faganello")): 534.80,
    ((2026, 4), normalize_search_text("Nilbea Regina Silva")): 534.80,
    ((2026, 4), normalize_search_text("Mariana Sebanico Perim Bonassa")): 700.00,
}

QUANTIDADES_CLIENTES_HISTORICO_FIXAS = {
    ((2026, 1), normalize_search_text("Silvia Regina Leite Faganello")): 2,
    ((2026, 4), normalize_search_text("Nilbea Regina Silva")): 2,
    ((2026, 4), normalize_search_text("Mariana Sebanico Perim Bonassa")): 3,
}


def aplicar_valores_historicos_fixos(df_base: pd.DataFrame, col_cliente: Optional[str], col_valor: Optional[str]) -> pd.DataFrame:
    """Aplica valores conferidos manualmente em clientes históricos."""
    if df_base is None or df_base.empty or not col_cliente or col_cliente not in df_base.columns:
        return df_base

    df_ajustada = df_base.copy()

    if "_mes_key" not in df_ajustada.columns:
        return df_ajustada

    if "_valor_num" not in df_ajustada.columns:
        df_ajustada["_valor_num"] = df_ajustada[col_valor].apply(parse_money) if col_valor and col_valor in df_ajustada.columns else 0.0

    # Garante a coluna de quantidade para os clientes que compraram mais de 1 pedigree.
    if "Quantidade de Pedigrees" not in df_ajustada.columns:
        df_ajustada["Quantidade de Pedigrees"] = 1

    for (mes_key, cliente_norm), valor_fixo in VALORES_CLIENTES_HISTORICO_FIXOS.items():
        mask_cliente = (
            (df_ajustada["_mes_key"] == mes_key)
            & (df_ajustada[col_cliente].apply(normalize_search_text) == cliente_norm)
        )

        if mask_cliente.any():
            df_ajustada.loc[mask_cliente, "_valor_num"] = float(valor_fixo)
            if col_valor and col_valor in df_ajustada.columns:
                df_ajustada.loc[mask_cliente, col_valor] = format_money(valor_fixo)

            qtd_fixa = QUANTIDADES_CLIENTES_HISTORICO_FIXAS.get((mes_key, cliente_norm))
            if qtd_fixa:
                df_ajustada.loc[mask_cliente, "Quantidade de Pedigrees"] = int(qtd_fixa)

    return df_ajustada


def comissao_historica_fixa(mes_key) -> Optional[float]:
    return COMISSAO_JULLIA_HISTORICO_FIXA.get(mes_key)


def is_transferencia_sim(v) -> bool:
    texto = normalize_search_text(v)
    return texto in ["sim", "s", "yes", "true", "1"]


def produto_pedigree_por_transferencia(v) -> str:
    return "Pedigree" if is_transferencia_sim(v) else "Pedigree s/ troca"


def valor_pedigree_por_transferencia(v) -> float:
    return VALOR_PEDIGREE_TRANSFERENCIA if is_transferencia_sim(v) else VALOR_PEDIGREE_SEM_TRANSFERENCIA


def mes_nome_from_date(d: dt.date) -> str:
    return month_name_pt(d.month)


def find_commission_row_by_cliente(worksheet, cliente_nome: str):
    headers = [str(h).strip() for h in worksheet.row_values(1)]
    if "Cliente" not in headers:
        return None

    col_cliente = headers.index("Cliente") + 1
    cliente_norm = normalize_search_text(cliente_nome)

    if not cliente_norm:
        return None

    values = worksheet.col_values(col_cliente)

    for idx, value in enumerate(values[1:], start=2):
        if normalize_search_text(value) == cliente_norm:
            return idx

    return None


def ensure_commission_base_headers():
    """
    MODO SOMENTE LEITURA DA COMISSÃO.

    Não cria nem atualiza cabeçalhos na aba Pedigree Comissão Ju.
    Apenas retorna a estrutura esperada para compatibilidade interna.
    """
    return [
        "Data da Venda",
        "Mês da Venda",
        "Cliente",
        "Quantidade de Pedigrees",
        "Produtos",
        "Mês da Compra do Cliente",
        "Valor",
        "Vendedor",
        "Silmário",
        "Correio",
        "Jullia",
    ]


def salvar_pedigree_na_comissao(dados):
    """
    MODO SOMENTE LEITURA DA COMISSÃO.

    Esta função foi mantida apenas para não quebrar chamadas antigas,
    mas NÃO grava mais nada na aba Pedigree Comissão Ju.

    Regra atual:
    - Pedigree salva somente na aba Planilha Dash Valéria sem mayra.
    - Comissão apenas lê a aba Pedigree Comissão Ju e calcula na tela.
    """
    return None


def proxima_linha_real_por_coluna(worksheet, header_name: str) -> int:
    """
    Retorna a primeira linha vazia logo depois do bloco principal de dados.

    Exemplo:
    preenchido até 168, vazio de 169 até 832, lixo antigo em 833.
    Retorna 169, não 842.
    """
    values = worksheet.get_all_values()

    if not values:
        return 2

    headers = [str(h).strip() for h in values[0]]

    if header_name not in headers:
        return len(values) + 1

    col_idx = headers.index(header_name)

    encontrou_dados = False
    linhas_vazias_seguidas = 0
    ultima_linha_bloco_principal = 1

    for i, row in enumerate(values[1:], start=2):
        valor = ""

        if col_idx < len(row):
            valor = normalize_text(row[col_idx])

        if valor:
            encontrou_dados = True
            linhas_vazias_seguidas = 0
            ultima_linha_bloco_principal = i
        else:
            if encontrou_dados:
                linhas_vazias_seguidas += 1

                if linhas_vazias_seguidas >= 3:
                    return ultima_linha_bloco_principal + 1

    return ultima_linha_bloco_principal + 1


def update_row_values(worksheet, row_number: int, values: list):
    """
    MODO SOMENTE LEITURA DA COMISSÃO.

    Mantida por compatibilidade, mas não grava linhas.
    """
    return None




def safe_int_zero(v) -> int:
    """
    Converte valores vindos do st.data_editor para inteiro com segurança.
    Quando a linha é nova, o Streamlit pode mandar vazio, None, NaN ou string.
    """
    try:
        if pd.isna(v):
            return 0
    except Exception:
        pass

    try:
        texto = str(v).strip()
        if not texto:
            return 0
        if texto.endswith(".0"):
            texto = texto[:-2]
        return int(float(texto))
    except Exception:
        return 0


def garantir_colunas_comissao(worksheet, required_cols: list[str]) -> list[str]:
    """Garante as colunas básicas da aba Pedigree Comissão Ju."""
    headers = [str(h).strip() for h in worksheet.row_values(1)]

    if not headers:
        worksheet.update("A1", [required_cols], value_input_option="USER_ENTERED")
        return required_cols

    changed = False
    for col in required_cols:
        if col not in headers:
            headers.append(col)
            changed = True

    if changed:
        worksheet.update("A1", [headers], value_input_option="USER_ENTERED")

    return headers


def proxima_linha_real_comissao(worksheet) -> int:
    """
    Retorna SEMPRE a próxima linha logo abaixo da última linha com escrita real.

    Não usa append_row, porque o Google Sheets pode considerar linhas formatadas
    como usadas e jogar o registro muito para baixo.
    """
    values = worksheet.get_all_values()

    if not values:
        return 2

    headers = [str(h).strip() for h in values[0]]

    colunas_base = [
        "Data da Venda",
        "Mês da Venda",
        "Cliente",
        "Quantidade de Pedigrees",
        "Produtos",
        "Mês da Compra do Cliente",
        "Valor",
        "Vendedor",
    ]

    idxs = [headers.index(c) for c in colunas_base if c in headers]

    if not idxs:
        return len(values) + 1

    ultima_linha_com_texto = 1

    for row_number, row in enumerate(values[1:], start=2):
        tem_texto = False

        for idx in idxs:
            if idx < len(row) and str(row[idx]).strip():
                tem_texto = True
                break

        if tem_texto:
            ultima_linha_com_texto = row_number

    return ultima_linha_com_texto + 1


def salvar_novas_linhas_comissao(novas_linhas: list[dict]) -> int:
    """
    Salva novas vendas na aba Pedigree Comissão Ju.

    Salva somente linhas novas criadas no editor. Linhas já existentes continuam
    sem alteração. A inserção é feita exatamente na linha abaixo da última com escrita.
    """
    if not novas_linhas:
        return 0

    worksheet = get_worksheet(COMM_WORKSHEET_NAME)

    required_cols = [
        "Data da Venda",
        "Mês da Venda",
        "Cliente",
        "Quantidade de Pedigrees",
        "Produtos",
        "Mês da Compra do Cliente",
        "Valor",
        "Vendedor",
    ]

    headers = garantir_colunas_comissao(worksheet, required_cols)
    next_row = proxima_linha_real_comissao(worksheet)

    rows_to_write = []

    for item in novas_linhas:
        data_venda = normalize_text(item.get("Data da Venda", ""))
        mes_venda = normalize_text(item.get("Mês da Venda", ""))
        cliente = normalize_text(item.get("Cliente", ""))
        qtd_pedigrees = safe_int_zero(item.get("Quantidade de Pedigrees", 1)) or 1
        produtos = normalize_text(item.get("Produtos", ""))
        valor = normalize_text(item.get("Valor", ""))

        # Evita salvar linha completamente vazia criada sem querer no editor.
        if not any([data_venda, mes_venda, cliente, produtos, valor]):
            continue

        row_data = {
            "Data da Venda": data_venda,
            "Mês da Venda": mes_venda,
            "Cliente": cliente,
            "Quantidade de Pedigrees": qtd_pedigrees,
            "Produtos": produtos,
            "Mês da Compra do Cliente": normalize_text(item.get("Mês da Compra do Cliente", mes_venda)),
            "Valor": valor,
            "Vendedor": normalize_text(item.get("Vendedor", "Jullia")) or "Jullia",
        }

        rows_to_write.append([row_data.get(header, "") for header in headers])

    if not rows_to_write:
        return 0

    worksheet.update(
        f"A{next_row}",
        rows_to_write,
        value_input_option="USER_ENTERED",
    )

    st.cache_data.clear()
    return len(rows_to_write)


def sync_pedigrees_para_comissao():
    """
    Sincronizar agora NÃO copia mais nomes da aba Pedigree para a Comissão.

    O botão Sincronizar serve somente para limpar o cache e reler a aba
    'Pedigree Comissão Ju', mostrando exatamente o que já está na planilha.

    Isso evita trazer de volta clientes que foram excluídos manualmente
    ou bagunçar a base de comissão.
    """
    st.cache_data.clear()
    return 0




def salvar_edicoes_linhas_comissao(edicoes_linhas: list[dict]) -> int:
    """
    Atualiza linhas já existentes da aba Pedigree Comissão Ju diretamente pelo dashboard.

    Atualiza somente as colunas operacionais pedidas para comissão:
    Data da Venda, Mês da Venda, Cliente, Quantidade de Pedigrees, Produtos,
    Mês da Compra do Cliente, Valor e Vendedor.
    """
    if not edicoes_linhas:
        return 0

    worksheet = get_worksheet(COMM_WORKSHEET_NAME)
    required_cols = [
        "Data da Venda",
        "Mês da Venda",
        "Cliente",
        "Quantidade de Pedigrees",
        "Produtos",
        "Mês da Compra do Cliente",
        "Valor",
        "Vendedor",
    ]
    headers = garantir_colunas_comissao(worksheet, required_cols)

    atualizadas = 0

    for item in edicoes_linhas:
        row_number = safe_int_zero(item.get("Linha", 0))
        if row_number <= 1:
            continue

        row_values = worksheet.row_values(row_number)
        if len(row_values) < len(headers):
            row_values += [""] * (len(headers) - len(row_values))

        novos_valores = {
            "Data da Venda": normalize_text(item.get("Data da Venda", "")),
            "Mês da Venda": normalize_text(item.get("Mês da Venda", "")),
            "Cliente": normalize_text(item.get("Cliente", "")),
            "Quantidade de Pedigrees": safe_int_zero(item.get("Quantidade de Pedigrees", 1)) or 1,
            "Produtos": normalize_text(item.get("Produtos", "")),
            "Mês da Compra do Cliente": normalize_text(item.get("Mês da Compra do Cliente", item.get("Mês da Venda", ""))),
            "Valor": normalize_text(item.get("Valor", "")),
            "Vendedor": normalize_text(item.get("Vendedor", "Jullia")) or "Jullia",
        }

        for col_name, value in novos_valores.items():
            if col_name in headers:
                col_idx = headers.index(col_name)
                row_values[col_idx] = value

        worksheet.update(f"A{row_number}", [row_values], value_input_option="USER_ENTERED")
        atualizadas += 1

    if atualizadas:
        st.cache_data.clear()

    return atualizadas


def is_produto_sem_transferencia(v) -> bool:
    texto = normalize_search_text(v)
    padroes = [
        "sem transferencia",
        "s/ transferencia",
        "s/ trans",
        "s/ troca",
        "sem trans",
        "sem transf",
        "pedigree sem",
    ]
    return any(p in texto for p in padroes)


def calcular_comissao_jullia(df_mes: pd.DataFrame, col_produtos: Optional[str], col_valor: Optional[str], col_vendedor: Optional[str]) -> dict:
    if df_mes is None or df_mes.empty:
        return {
            "total_vendas_validas_mes": 0,
            "qtd_vendas_jullia_validas": 0,
            "valor_vendas_jullia_validas": 0.0,
            "percentual_jullia": 0.0,
            "comissao_jullia": 0.0,
            "faixa": "Sem vendas",
        }

    df_calc = df_mes.copy()

    # Garante coluna de valor numérico vinda da planilha.
    if col_valor and col_valor in df_calc.columns:
        df_calc["_valor_calculo_jullia"] = df_calc[col_valor].apply(parse_money)
    else:
        df_calc["_valor_calculo_jullia"] = 0.0

    # Identifica Pedigree sem transferência pelo texto do produto.
    if col_produtos and col_produtos in df_calc.columns:
        df_calc["_produto_preenchido_calc"] = df_calc[col_produtos].astype(str).str.strip() != ""
        df_calc["_sem_transferencia_calc"] = df_calc[col_produtos].apply(is_produto_sem_transferencia)
    else:
        df_calc["_produto_preenchido_calc"] = False
        df_calc["_sem_transferencia_calc"] = False

    # Segurança: quando o produto vier escrito errado/vazio, valores próximos do frete/sem transferência também são ignorados para a Jullia.
    df_calc["_sem_transferencia_calc"] = (
        df_calc["_sem_transferencia_calc"]
        | df_calc["_valor_calculo_jullia"].between(34.50, 36.50)
    )

    # Quantidade de Pedigrees:
    # quando uma linha representa mais de 1 pedigree, ela precisa contar como várias vendas
    # para a Comissão Jullia, e não apenas como 1 linha.
    col_qtd_calc = None
    for possivel_col in ["Quantidade de Pedigrees", "Qtd Pedigrees", "Quantidade", "Qtd"]:
        if possivel_col in df_calc.columns:
            col_qtd_calc = possivel_col
            break

    if col_qtd_calc:
        df_calc["_qtd_pedigrees_calc"] = df_calc[col_qtd_calc].apply(safe_int_zero)
        df_calc.loc[df_calc["_qtd_pedigrees_calc"] <= 0, "_qtd_pedigrees_calc"] = 1
    else:
        df_calc["_qtd_pedigrees_calc"] = 1

    # BASE DO PERCENTUAL:
    # todas as vendas do mês com produto escolhido, MENOS os pedidos sem transferência.
    # Aqui a quantidade digitada multiplica a venda válida.
    df_validas_mes = df_calc[
        (df_calc["_produto_preenchido_calc"])
        & (~df_calc["_sem_transferencia_calc"])
    ].copy()
    total_vendas_validas_mes = int(df_validas_mes["_qtd_pedigrees_calc"].sum()) if not df_validas_mes.empty else 0

    if col_vendedor and col_vendedor in df_validas_mes.columns:
        mask_jullia = df_validas_mes[col_vendedor].apply(normalize_search_text).str.contains(
            r"jul+ia",
            na=False,
            regex=True,
        )
        df_jullia = df_validas_mes[mask_jullia].copy()
    else:
        df_jullia = pd.DataFrame()

    qtd_vendas_jullia_validas = int(df_jullia["_qtd_pedigrees_calc"].sum()) if not df_jullia.empty and "_qtd_pedigrees_calc" in df_jullia.columns else 0
    valor_vendas_jullia_validas = (
        float(df_jullia["_valor_calculo_jullia"].sum())
        if not df_jullia.empty and "_valor_calculo_jullia" in df_jullia.columns
        else 0.0
    )

    percentual_jullia = (
        qtd_vendas_jullia_validas / total_vendas_validas_mes
        if total_vendas_validas_mes > 0
        else 0.0
    )

    if qtd_vendas_jullia_validas <= 0:
        comissao_jullia = 0.0
        faixa = "Sem vendas válidas"
    elif percentual_jullia <= 0.50:
        comissao_jullia = valor_vendas_jullia_validas * 0.05
        faixa = "5% sobre o valor final das vendas válidas"
    elif percentual_jullia <= 0.74:
        comissao_jullia = qtd_vendas_jullia_validas * 3.50
        faixa = "R$ 3,50 por venda válida"
    else:
        comissao_jullia = qtd_vendas_jullia_validas * 5.00
        faixa = "R$ 5,00 por venda válida"

    return {
        "total_vendas_validas_mes": total_vendas_validas_mes,
        "qtd_vendas_jullia_validas": qtd_vendas_jullia_validas,
        "valor_vendas_jullia_validas": valor_vendas_jullia_validas,
        "percentual_jullia": percentual_jullia,
        "comissao_jullia": float(comissao_jullia),
        "faixa": faixa,
    }


OPCOES_PRODUTOS_COMISSAO = [
    "",
    "Pedigree Transferência",
    "Pedigree Sem Transferência",
    "RG",
    "Certidão",
    "Airtag",
    "RG + Certidão",
    "RG + Certidão + Airtag",
    "Pedigree Transferência + RG",
    "Pedigree Transferência + Certidão",
    "Pedigree Transferência + Airtag",
    "Pedigree Transferência + RG + Certidão",
    "Pedigree Transferência + RG + Airtag",
    "Pedigree Transferência + Certidão + Airtag",
    "Pedigree Transferência + RG + Certidão + Airtag",
    "Pedigree Sem Transferência + RG",
    "Pedigree Sem Transferência + Certidão",
    "Pedigree Sem Transferência + Airtag",
    "Pedigree Sem Transferência + RG + Certidão",
    "Pedigree Sem Transferência + RG + Airtag",
    "Pedigree Sem Transferência + Certidão + Airtag",
    "Pedigree Sem Transferência + RG + Certidão + Airtag",
]


def calcular_valor_por_checks(
    ped_trans: bool,
    ped_sem: bool,
    correios: bool,
    rg: bool,
    certidao: bool,
    airtag: bool,
    quantidade_pedigrees: int = 1,
) -> float:
    """
    Calcula o valor somente para exibição no dashboard.

    Quantidade de Pedigrees multiplica a combinação marcada na linha.
    Exemplo: 3 pedigrees com transferência + correios = 3 x 285,70.
    """
    qtd = safe_int_zero(quantidade_pedigrees) or 1
    if qtd < 1:
        qtd = 1

    total_unitario = 0.0

    if ped_trans:
        total_unitario += VALOR_PEDIGREE_TRANSFERENCIA

    if ped_sem:
        total_unitario += VALOR_PEDIGREE_SEM_TRANSFERENCIA

    if correios:
        total_unitario += VALOR_CORREIO

    if rg and certidao and airtag:
        total_unitario += VALOR_COMBO_RG_CERTIDAO_AIRTAG
    else:
        if rg:
            total_unitario += VALOR_RG
        if certidao:
            total_unitario += VALOR_CERTIDAO
        if airtag:
            total_unitario += VALOR_AIRTAG

    return float(total_unitario * qtd)


def calcular_valor_por_checks_antigo(ped_trans: bool, ped_sem: bool, rg: bool, certidao: bool, airtag: bool) -> float:
    # Mantido apenas por compatibilidade interna, caso algum trecho antigo chame a função sem Correios.
    correios = bool(ped_trans)
    return calcular_valor_por_checks(ped_trans, ped_sem, correios, rg, certidao, airtag, 1)

def calcular_valor_produtos_comissao(produto: str) -> float:
    texto = normalize_search_text(produto)

    if not texto:
        return 0.0

    tem_pedigree_transferencia = (
        "pedigree transferencia" in texto
        or "pedigree transferência" in texto
    )
    tem_sem_transferencia = is_produto_sem_transferencia(produto)
    tem_rg = "rg" in texto
    tem_certidao = "certidao" in texto or "certidão" in texto
    tem_airtag = "airtag" in texto or "air tag" in texto

    # Compatibilidade para produtos vindos como texto da planilha.
    # Quando houver Pedigree Transferência no texto antigo, considera Correios junto,
    # porque o frete é obrigatório no valor base de R$ 285,70.
    tem_correios = tem_pedigree_transferencia or ("correio" in texto) or ("correios" in texto)

    return calcular_valor_por_checks(
        tem_pedigree_transferencia,
        tem_sem_transferencia,
        tem_correios,
        tem_rg,
        tem_certidao,
        tem_airtag,
        1,
    )


def atualizar_produtos_comissao(row_number: int, produto: str):
    """
    MODO SOMENTE LEITURA DA COMISSÃO.

    Antes esta função gravava Produto, Valor e Correio na aba Pedigree Comissão Ju.
    Agora ela não altera a planilha. O cálculo é feito somente em memória,
    dentro do dashboard.
    """
    return None


def montar_produto_por_checks(ped_trans: bool, ped_sem: bool, rg: bool, certidao: bool, airtag: bool) -> str:
    partes = []

    # Permite múltiplas escolhas simultâneas.
    # Transferência e Sem Transferência não são mais travadas uma contra a outra.
    if ped_trans:
        partes.append("Pedigree Transferência")
    if ped_sem:
        partes.append("Pedigree Sem Transferência")

    extras = []
    if rg:
        extras.append("RG")
    if certidao:
        extras.append("Certidão")
    if airtag:
        extras.append("Airtag")

    partes.extend(extras)
    return " + ".join(partes)



def montar_produto_com_correios(ped_trans: bool, ped_sem: bool, correios: bool, rg: bool, certidao: bool, airtag: bool) -> str:
    partes = []

    if ped_trans:
        partes.append("Pedigree Transferência")
    if ped_sem:
        partes.append("Pedigree Sem Transferência")
    if correios:
        partes.append("Correios")

    extras = []
    if rg:
        extras.append("RG")
    if certidao:
        extras.append("Certidão")
    if airtag:
        extras.append("Airtag")

    partes.extend(extras)
    return " + ".join(partes)


def checks_por_produto(produto: str) -> dict:
    texto = normalize_search_text(produto)

    ped_trans = ("pedigree" in texto and not is_produto_sem_transferencia(produto))
    sem_trans = is_produto_sem_transferencia(produto)

    return {
        "Pedigree Transferência": ped_trans,
        "Sem Transferência": sem_trans,
        "Correios": ped_trans,
        "RG": "rg" in texto,
        "Certidão": ("certidao" in texto or "certidão" in texto),
        "Airtag": ("airtag" in texto or "air tag" in texto),
    }


def checkbox_marcado(v) -> bool:
    try:
        if pd.isna(v):
            return False
    except Exception:
        pass

    if isinstance(v, bool):
        return v

    return str(v).strip().lower() in ["true", "1", "sim", "s", "yes"]


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


def count_contact_dates_by_selected_month(df_base: pd.DataFrame, target: str, selected_month: Tuple[int, int]) -> int:
    """
    Conta contatos pela DATA da própria coluna de contato.

    Exemplo: para Maio/2026, a caixa "Segundo contato" conta somente
    as células da coluna "2º contato" cuja data esteja em 05/2026,
    independente do mês original da venda/contrato.
    """
    if df_base is None or df_base.empty or not selected_month:
        return 0

    matching_cols = find_matching_columns(df_base, target)
    if not matching_cols:
        return 0

    selected_year, selected_month_num = selected_month
    final_mask = pd.Series(False, index=df_base.index)

    for col in matching_cols:
        datas_coluna = df_base[col].apply(parse_date_any)
        mask_coluna = datas_coluna.apply(
            lambda d: bool(d and d.year == selected_year and d.month == selected_month_num)
        )
        final_mask = final_mask | mask_coluna

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
        "Linha Clear Origem",
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

    # Comissão é somente leitura: não envia mais este cadastro para a aba Pedigree Comissão Ju.
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



def atualizar_status_venda_pedigree_clear(row_number: int, novo_status: str):
    """
    Atualiza SOMENTE a coluna Status Venda Pedigree na aba Clear.
    Quando a alteração for feita pelo dashboard para Vendido,
    marca a linha como Novo Formulário Pedigree = Pendente.
    Assim o formulário pega só vendas novas feitas pelo dashboard,
    sem puxar todos os vendidos antigos da planilha.
    """
    worksheet = get_worksheet(MAIN_WORKSHEET_NAME)
    headers = [str(h).strip() for h in worksheet.row_values(1)]

    required_headers = [
        "Status Venda Pedigree",
        "Novo Formulário Pedigree",
    ]

    mudou_header = False

    for header in required_headers:
        if header not in headers:
            headers.append(header)
            mudou_header = True

    if mudou_header:
        worksheet.update("A1", [headers], value_input_option="USER_ENTERED")

    headers = [str(h).strip() for h in worksheet.row_values(1)]

    col_status_number = headers.index("Status Venda Pedigree") + 1
    col_novo_form_number = headers.index("Novo Formulário Pedigree") + 1

    mapa_status_planilha = {
        "": "",
        "Novo Lead": "",
        "Não tem interesse": "Não tem interesse",
        "Com transferência": "Vendido",
        "Conversando": "Conversando",
        "Sem Resposta": "Sem Resposta",
        "Sem transferência": "Emitir Sem Venda",
    }

    status_para_salvar = mapa_status_planilha.get(novo_status, novo_status)

    worksheet.update_cell(int(row_number), col_status_number, status_para_salvar)

    if normalize_search_text(status_para_salvar) == normalize_search_text("Vendido"):
        worksheet.update_cell(int(row_number), col_novo_form_number, "Pendente")
    else:
        valor_atual_flag = normalize_text(
            worksheet.cell(int(row_number), col_novo_form_number).value
        )

        if normalize_search_text(valor_atual_flag) != normalize_search_text("Feito"):
            worksheet.update_cell(int(row_number), col_novo_form_number, "")

    st.cache_data.clear()



def marcar_novo_formulario_pedigree_feito(row_number: int):
    """
    Marca a linha da aba Clear como já lançada no formulário de Pedigree.
    """
    if not row_number:
        return

    worksheet = get_worksheet(MAIN_WORKSHEET_NAME)
    headers = [str(h).strip() for h in worksheet.row_values(1)]

    if "Novo Formulário Pedigree" not in headers:
        headers.append("Novo Formulário Pedigree")
        worksheet.update("A1", [headers], value_input_option="USER_ENTERED")

    headers = [str(h).strip() for h in worksheet.row_values(1)]
    col_number = headers.index("Novo Formulário Pedigree") + 1

    worksheet.update_cell(int(row_number), col_number, "Feito")
    st.cache_data.clear()


def find_commission_row_by_cliente_name(cliente_nome: str):
    worksheet = get_worksheet(COMM_WORKSHEET_NAME)
    values = worksheet.get_all_values()

    if not values:
        return None

    headers = [str(h).strip() for h in values[0]]

    if "Cliente" not in headers:
        return None

    col_cliente = headers.index("Cliente")

    for idx, row in enumerate(values[1:], start=2):
        try:
            nome_sheet = str(row[col_cliente]).strip().lower()
        except:
            nome_sheet = ""

        if nome_sheet == str(cliente_nome).strip().lower():
            return idx

    return None


def excluir_ficha_pedigree(row_number: int, cliente_nome: str):
    """
    Exclui somente a ficha da aba Planilha Dash Valéria sem mayra.

    A aba Pedigree Comissão Ju não é alterada pelo dashboard.
    """
    ped_ws = get_worksheet(PED_WORKSHEET_NAME)
    ped_ws.delete_rows(int(row_number))
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
                background: #032450;
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
                background: #2e6cbf;
                color: white;
                cursor: pointer;
            }}


            /* SCROLLBAR MAIS GROSSA */
            ::-webkit-scrollbar {{
                width: 22px !important;
                height: 22px !important;
            }}

            ::-webkit-scrollbar-track {{
                background: #E5E7EB !important;
                border-radius: 999px !important;
            }}

            ::-webkit-scrollbar-thumb {{
                background: #9CA3AF !important;
                border-radius: 999px !important;
                border: 4px solid #E5E7EB !important;
            }}

            ::-webkit-scrollbar-thumb:hover {{
                background: #6B7280 !important;
            }}

            * {{
                scrollbar-width: auto;
                scrollbar-color: #9CA3AF #E5E7EB;
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



def render_status_venda_editavel_table(df_table: pd.DataFrame, cols_to_show: list[str], height: int = 520):
    """
    Tabela visual igual à anterior, com botão Copiar no telefone/WhatsApp
    e dropdown editável somente em Status Venda Pedigree.
    Ao alterar o dropdown, salva automaticamente pela URL.
    """
    status_options = [
        "",
        "Vendido",
        "Não tem interesse",
        "Sem Resposta",
        "Emitir Sem Venda",
        "Conversando",
    ]

    safe_rows = []

    for idx_row, row in df_table.iterrows():
        row_number = int(row.get("Linha", int(idx_row) + 2))
        cells = []

        for col in cols_to_show:
            val = row.get(col, "")

            if col == "Linha":
                cell = html.escape(str(row_number))

            elif normalize_header_name(col) in ["telefone", "whatsapp"]:
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

            elif normalize_header_name(col) == normalize_header_name("Status Venda Pedigree"):
                current_status = normalize_text(val)

                if current_status == "Com transferência":
                    current_status = "Vendido"
                elif current_status == "Sem transferência":
                    current_status = "Emitir Sem Venda"

                if current_status == "Vender":
                    current_status = ""

                if current_status not in status_options:
                    current_status = ""

                options_html = "".join(
                    [
                        f'<option value="{html.escape(opt)}" {"selected" if opt == current_status else ""}>{html.escape(opt)}</option>'
                        for opt in status_options
                    ]
                )

                cell = f"""
                <select class="status-select" onchange="saveStatus({row_number}, this.value)">
                    {options_html}
                </select>
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
                min-width: 1250px;
                font-size: 13px;
            }}

            thead th {{
                position: sticky;
                top: 0;
                background: #032450;
                color: white;
                padding: 12px 10px;
                text-align: left;
                z-index: 2;
                white-space: nowrap;
            }}

            tbody td {{
                border-bottom: 1px solid #EEF1F7;
                padding: 9px 10px;
                color: #17213A;
                white-space: nowrap;
                vertical-align: middle;
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
                background: #2e6cbf;
                color: white;
                cursor: pointer;
            }}

            .status-select {{
                min-width: 190px;
                border: none;
                border-radius: 999px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
                color: #073B7A;
                background: #EAF2FF;
                outline: none;
                cursor: pointer;
            }}

            ::-webkit-scrollbar {{
                width: 22px !important;
                height: 22px !important;
            }}

            ::-webkit-scrollbar-track {{
                background: #E5E7EB !important;
                border-radius: 999px !important;
            }}

            ::-webkit-scrollbar-thumb {{
                background: #9CA3AF !important;
                border-radius: 999px !important;
                border: 4px solid #E5E7EB !important;
            }}

            ::-webkit-scrollbar-thumb:hover {{
                background: #6B7280 !important;
            }}

            * {{
                scrollbar-width: auto;
                scrollbar-color: #9CA3AF #E5E7EB;
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

            function saveStatus(rowNumber, value) {{
                const selectEl = event.target;
                const rowEl = selectEl.closest("tr");

                selectEl.disabled = true;
                selectEl.style.background = "#DCFCE7";
                selectEl.style.color = "#166534";

                const params = new URLSearchParams(window.parent.location.search);
                params.set("editar_status_row", rowNumber);
                params.set("editar_status_val", value);
                params.set("clear_auth", "ok");

                const updateUrl =
                    window.parent.location.origin +
                    window.parent.location.pathname +
                    "?" +
                    params.toString();

                const hiddenFrame = document.createElement("iframe");
                hiddenFrame.src = updateUrl;
                hiddenFrame.style.display = "none";
                hiddenFrame.style.width = "0";
                hiddenFrame.style.height = "0";
                hiddenFrame.style.border = "0";

                document.body.appendChild(hiddenFrame);

                if (rowEl) {{
                    rowEl.style.transition = "all 0.35s ease";
                    rowEl.style.opacity = "0";
                    rowEl.style.transform = "translateX(18px)";

                    setTimeout(function() {{
                        rowEl.remove();
                    }}, 380);
                }}

                setTimeout(function() {{
                    hiddenFrame.remove();
                }}, 3500);
            }}
        </script>
    </body>
    </html>
    """

    components.html(table_html, height=height, scrolling=True)

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

    col_status_1, col_status_2, col_status_3 = st.columns([3, 1, 1])

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

    with col_status_3:
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🗑️ Excluir ficha", use_container_width=True, key=f"btn_excluir_{row_number}"):
            st.session_state[f"confirmar_exclusao_{row_number}"] = True

    if st.session_state.get(f"confirmar_exclusao_{row_number}", False):

        st.warning(f"Tem certeza que deseja excluir a ficha de {nome}?")

        col_conf_1, col_conf_2 = st.columns(2)

        with col_conf_1:
            if st.button("Sim, excluir", use_container_width=True, key=f"sim_excluir_{row_number}"):

                excluir_ficha_pedigree(row_number, nome)

                st.success("Ficha excluída com sucesso.")
                st.rerun()

        with col_conf_2:
            if st.button("Cancelar", use_container_width=True, key=f"cancelar_excluir_{row_number}"):

                st.session_state[f"confirmar_exclusao_{row_number}"] = False
                st.rerun()

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
        --navy:#032450;
        --wine:#2e6cbf;
        --gold:#2e6cbf;
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
        padding: 1rem 0.9rem;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        min-height: 132px;
        height: 132px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
    }

    .metric-wrap {
        width: 100%;
        display: grid;
        grid-template-columns: 50px 1fr;
        gap: 10px;
        align-items: center;
    }

    .metric-icon {
        width: 50px;
        height: 50px;
        min-width: 50px;
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 21px;
        font-weight: 800;
    }

    .metric-label {
        color: #55627A;
        font-size: 0.82rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
        line-height: 1.15;
        min-height: 30px;
        display: flex;
        align-items: flex-end;
    }

    .metric-value {
        color: var(--text);
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.05;
    }

    .metric-sub {
        color: var(--muted);
        font-size: 0.78rem;
        margin-top: 0.15rem;
        white-space: nowrap;
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
        color: #032450 !important;
        font-weight: 700 !important;
        font-size: 0.82rem !important;
        padding: 0.45rem 0.6rem !important;
        min-height: 36px !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04) !important;
    }

    div.stButton > button:hover {
        border-color: #2e6cbf !important;
        color: #2e6cbf !important;
    }

    /* PALETA CLEAR - SIDEBAR FINAL */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #032450 0%, #032450 58%, #2e6cbf 155%) !important;
        border-right: 1px solid rgba(255,255,255,0.18) !important;
    }

    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] .brand-title,
    [data-testid="stSidebar"] .brand-sub,
    [data-testid="stSidebar"] label p {
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] .brand-logo,
    [data-testid="stSidebar"] .brand-user,
    [data-testid="stSidebar"] .sidebar-logo-circle {
        border-color: #2e6cbf !important;
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] .brand-logo *,
    [data-testid="stSidebar"] .brand-user * {
        color: #ffffff !important;
        fill: #ffffff !important;
    }

    [data-testid="stSidebar"] .brand-box {
        border-bottom: 1px solid rgba(255,255,255,0.22) !important;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(46,108,191,0.22) !important;
    }

    [data-testid="stSidebar"] .sidebar-logo-circle {
        background: #2e6cbf !important;
        box-shadow: 0 12px 30px rgba(46,108,191,0.20) !important;
    }



            /* SCROLLBAR MAIS GROSSA */
            ::-webkit-scrollbar {{
                width: 22px !important;
                height: 22px !important;
            }}

            ::-webkit-scrollbar-track {{
                background: #E5E7EB !important;
                border-radius: 999px !important;
            }}

            ::-webkit-scrollbar-thumb {{
                background: #9CA3AF !important;
                border-radius: 999px !important;
                border: 4px solid #E5E7EB !important;
            }}

            ::-webkit-scrollbar-thumb:hover {{
                background: #6B7280 !important;
            }}

            * {{
                scrollbar-width: auto;
                scrollbar-color: #9CA3AF #E5E7EB;
            }}


    /* BARRA DE ROLAGEM DA TABELA MAIS GROSSA */
    [data-testid="stDataFrame"] ::-webkit-scrollbar {
        width: 22px !important;
        height: 22px !important;
    }

    [data-testid="stDataFrame"] ::-webkit-scrollbar-track {
        background: #D1D5DB !important;
        border-radius: 999px !important;
    }

    [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb {
        background: #6B7280 !important;
        border-radius: 999px !important;
        border: 4px solid #D1D5DB !important;
    }

    [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb:hover {
        background: #374151 !important;
    }

</style>
""",
    unsafe_allow_html=True,
)


LOGIN_HERO_B64 = """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"""


def render_login_screen():
    clear_logo_b64 = image_to_base64("campmotors.png")

    badge_html = (
        f'<img src="data:image/png;base64,{clear_logo_b64}" alt="Clear" class="login-badge-img">'
        if clear_logo_b64
        else '<span class="login-badge-fallback">⚖</span>'
    )

    st.markdown(
        f"""
        <style>
            [data-testid="stSidebar"] {{ display: none !important; }}
            [data-testid="stHeader"] {{ background: transparent !important; }}
            [data-testid="stToolbar"] {{ display: none !important; }}
            #MainMenu, footer {{ visibility: hidden !important; }}

            .stApp {{
                background:
                    radial-gradient(circle at 50% 35%, rgba(46,108,191,0.55) 0%, rgba(46,108,191,0.20) 34%, rgba(3,36,80,0.10) 58%, rgba(3,36,80,0.00) 76%),
                    linear-gradient(135deg, #032450 0%, #174f96 58%, #2e6cbf 100%) !important;
            }}

            .block-container {{
                max-width: 100% !important;
                padding-top: 1.2rem !important;
                padding-bottom: 1.2rem !important;
            }}

            .login-shell {{
                width: 50vw;
                min-width: 700px;
                max-width: 950px;
                margin: 0 auto;
                padding-top: 0.15rem;
            }}

            .login-card-top {{
                width: 100%;
                border-radius: 22px 22px 0 0;
                overflow: hidden;
                box-shadow: 0 24px 60px rgba(0,0,0,0.28);
                border: 1px solid rgba(255,255,255,0.22);
                border-bottom: 0;
                background: #26384B;
            }}

            .login-hero {{
                height: 170px;
                background-image: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(3,36,80,0.05)), url('data:image/jpeg;base64,{LOGIN_HERO_B64}');
                background-size: cover;
                background-position: center;
            }}

            .login-panel {{
                background: #26384B;
                color: #ffffff;
                text-align: center;
                padding: 0 42px 26px 42px;
                position: relative;
            }}

            .login-badge {{
                width: 82px;
                height: 82px;
                border-radius: 50%;
                background: #2e6cbf;
                margin: -41px auto 12px auto;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                border: 4px solid #ffffff;
                box-shadow: 0 10px 24px rgba(0,0,0,0.28);
            }}

            .login-badge-img {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                display: block;
            }}

            .login-badge-fallback {{
                color: #ffffff;
                font-size: 25px;
                font-weight: 900;
            }}

            .login-title {{
                font-size: 1.22rem;
                font-weight: 900;
                letter-spacing: 0.05em;
                text-transform: uppercase;
                margin-bottom: 4px;
            }}

            .login-subtitle {{
                color: rgba(255,255,255,0.74);
                font-size: 0.9rem;
                margin-bottom: 0;
            }}

            div[data-testid="stForm"] {{
                width: 50vw !important;
                min-width: 700px !important;
                max-width: 950px !important;
                margin: 0 auto !important;
                background: #26384B !important;
                padding: 18px 42px 120px 42px !important;
                border-radius: 0 0 22px 22px !important;
                border: 1px solid rgba(255,255,255,0.22) !important;
                border-top: 0 !important;
                box-shadow: 0 24px 60px rgba(0,0,0,0.28) !important;
            }}

            div[data-testid="stForm"] [data-testid="stVerticalBlock"] {{
                gap: 0.48rem !important;
            }}

            div[data-testid="stForm"] label p {{
                color: rgba(255,255,255,0.92) !important;
                font-weight: 800 !important;
                font-size: 0.86rem !important;
                margin-bottom: 3px !important;
            }}

            div[data-testid="stForm"] input {{
                background: #FFFFFF !important;
                color: #032450 !important;
                -webkit-text-fill-color: #032450 !important;
                border: 1px solid rgba(255,255,255,0.92) !important;
                border-radius: 999px !important;
                min-height: 44px !important;
                padding-left: 16px !important;
                box-shadow: none !important;
            }}

            div[data-testid="stForm"] input::placeholder {{
                color: #6B7280 !important;
                -webkit-text-fill-color: #6B7280 !important;
                opacity: 1 !important;
            }}

            div[data-testid="stForm"] input:focus {{
                background: #FFFFFF !important;
                color: #032450 !important;
                -webkit-text-fill-color: #032450 !important;
                border: 2px solid #2e6cbf !important;
                box-shadow: 0 0 0 3px rgba(46,108,191,0.18) !important;
            }}

            div[data-testid="stForm"] div.stButton > button {{
                width: 100% !important;
                border: none !important;
                border-radius: 999px !important;
                min-height: 46px !important;
                color: #ffffff !important;
                font-weight: 900 !important;
                background: linear-gradient(90deg, #20D8F0 0%, #2e6cbf 52%, #032450 100%) !important;
                box-shadow: 0 12px 24px rgba(46,108,191,0.28) !important;
                margin-top: 4px !important;
            }}

            .login-footer {{
                width: 50vw;
                min-width: 700px;
                max-width: 950px;
                margin: 22px auto 0 auto;
                text-align: center;
                color: rgba(255,255,255,0.76);
                font-weight: 800;
                font-size: 0.82rem;
                letter-spacing: 0.06em;
            }}

            .login-error {{
                width: 50vw;
                min-width: 700px;
                max-width: 950px;
                margin: 12px auto 0 auto;
                background: rgba(255, 86, 86, 0.15);
                border: 1px solid rgba(255, 86, 86, 0.42);
                color: #ffd4d4;
                border-radius: 14px;
                padding: 10px 12px;
                font-weight: 800;
                font-size: 0.92rem;
                text-align: center;
            }}

            @media (max-width: 640px) {{
                .login-shell, div[data-testid="stForm"], .login-footer, .login-error {{
                    width: 94vw !important;
                }}
                .login-hero {{ height: 108px; }}
                .login-panel {{ padding-left: 18px; padding-right: 18px; }}
                div[data-testid="stForm"] {{ padding-left: 18px !important; padding-right: 18px !important; }}
            }}
        </style>

        <div class="login-shell">
            <div class="login-card-top">
                <div class="login-hero"></div>
                <div class="login-panel">
                    <div class="login-badge">{badge_html}</div>
                    <div class="login-title">Clear Login</div>
                    <div class="login-subtitle">Acesse o painel de Pedigree e Comissão</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_clear_form", clear_on_submit=False):
        usuario = st.text_input("Usuário", placeholder="Digite o usuário")
        senha = st.text_input("Senha", placeholder="Digite a senha", type="password")
        entrar = st.form_submit_button("ENTRAR")

    if entrar:
        if usuario.strip() == "clear" and senha.strip() == "Clear@2026!":
            st.session_state["clear_logged_in"] = True
            st.query_params["clear_auth"] = "ok"
            st.rerun()
        else:
            st.markdown('<div class="login-error">Usuário ou senha incorretos.</div>', unsafe_allow_html=True)

    st.markdown('<div class="login-footer">DASHBOARD VENDAS CLEAR</div>', unsafe_allow_html=True)


if "clear_logged_in" not in st.session_state:
    st.session_state["clear_logged_in"] = False

if st.query_params.get("clear_auth") == "ok":
    st.session_state["clear_logged_in"] = True

if not st.session_state["clear_logged_in"]:
    render_login_screen()
    st.stop()


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

# Atualização automática da coluna Status Venda Pedigree vinda do dropdown da tabela.
# Processa antes dos cálculos da Visão Geral para o lead sair da caixa antiga e entrar na nova.
status_row_param = st.query_params.get("editar_status_row")
status_val_param = st.query_params.get("editar_status_val")

if status_row_param and status_val_param:
    try:
        atualizar_status_venda_pedigree_clear(
            int(status_row_param),
            str(status_val_param),
        )

        if "status_card_aberto" in st.session_state:
            st.session_state["status_card_aberto"] = ""

        params_preservados = {}

        if st.query_params.get("clear_auth"):
            params_preservados["clear_auth"] = st.query_params.get("clear_auth")

        st.query_params.clear()

        for chave_param, valor_param in params_preservados.items():
            st.query_params[chave_param] = valor_param

        df = load_main_data().copy()
        st.toast("Status atualizado com sucesso.")
        st.rerun()

    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")

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
    # Atualização automática SOMENTE na Visão Geral.
    # Usa o refresh interno do Streamlit para não sair do dashboard e não voltar ao login.
    if st_autorefresh is not None:
        st_autorefresh(
            interval=30000,
            limit=None,
            key="visao_geral_auto_refresh",
        )

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

    def semanas_do_calendario_mes(ano: int, mes: int):
        nomes_semana = [
            "Primeira",
            "Segunda",
            "Terceira",
            "Quarta",
            "Quinta",
            "Sexta",
        ]

        ultimo_dia = (dt.date(ano + (1 if mes == 12 else 0), 1 if mes == 12 else mes + 1, 1) - dt.timedelta(days=1)).day
        semanas_mes = []
        inicio = 1
        ordem = 1

        while inicio <= ultimo_dia and ordem <= len(nomes_semana):
            data_inicio = dt.date(ano, mes, inicio)
            dias_ate_sabado = (5 - data_inicio.weekday()) % 7
            fim = min(inicio + dias_ate_sabado, ultimo_dia)

            semanas_mes.append(
                {
                    "Semana": nomes_semana[ordem - 1],
                    "Ordem": ordem,
                    "Inicio": inicio,
                    "Fim": fim,
                    "Label": f"{nomes_semana[ordem - 1]} ({inicio:02d}/{mes:02d} a {fim:02d}/{mes:02d})",
                }
            )

            inicio = fim + 1
            ordem += 1

        return semanas_mes

    semanas_calendario = semanas_do_calendario_mes(selected_month[0], selected_month[1])
    semanas = ["Todas"] + [item["Semana"] for item in semanas_calendario]

    filter_col1, filter_col2 = st.columns([1.2, 1.2])

    with filter_col1:
        selected_week = st.selectbox("Semana", semanas, index=0)

    with filter_col2:
        search_top = st.text_input("Busca rápida", placeholder="Nome, CPF, telefone ou e-mail")

    filtered_df = month_df.copy()

    if not filtered_df.empty:
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

    # ============================================
    # BUSCA RÁPIDA INTELIGENTE
    # Mostra em qual caixa/status o lead está e exibe os dados completos.
    # ============================================

    def status_venda_para_caixa(valor):
        texto_status = normalize_search_text(valor)

        if texto_status == normalize_search_text("Não tem interesse"):
            return "Não tem interesse"

        if texto_status == normalize_search_text("Vendido"):
            return "Com transferência"

        if texto_status == normalize_search_text("Conversando"):
            return "Conversando"

        if texto_status == normalize_search_text("Sem Resposta"):
            return "Sem Resposta"

        if texto_status == normalize_search_text("Emitir Sem Venda"):
            return "Sem transferência"

        if texto_status == normalize_search_text("Vender"):
            return "Novo Lead"

        if texto_status == "" or texto_status == normalize_search_text("(Espaços em branco)") or texto_status == normalize_search_text("Espaços em branco"):
            return "Novo Lead"

        return "Sem caixa definida"

    if search_top.strip():

        busca_resultado_df = month_df.copy()

        if not busca_resultado_df.empty:

            q_busca = normalize_search_text(search_top)
            q_digits_busca = re.sub(r"\D", "", search_top)

            mask_busca = pd.Series(False, index=busca_resultado_df.index)

            if COL_NOME and COL_NOME in busca_resultado_df.columns:
                mask_busca = mask_busca | busca_resultado_df[COL_NOME].astype(str).apply(normalize_search_text).str.contains(q_busca, na=False)

            if COL_TEL and COL_TEL in busca_resultado_df.columns and q_digits_busca:
                mask_busca = mask_busca | busca_resultado_df[COL_TEL].astype(str).apply(only_digits).str.contains(q_digits_busca, na=False)

            if COL_CPF and COL_CPF in busca_resultado_df.columns and q_digits_busca:
                mask_busca = mask_busca | busca_resultado_df[COL_CPF].astype(str).apply(only_digits).str.contains(q_digits_busca, na=False)

            if COL_EMAIL and COL_EMAIL in busca_resultado_df.columns:
                mask_busca = mask_busca | busca_resultado_df[COL_EMAIL].astype(str).apply(normalize_search_text).str.contains(q_busca, na=False)

            col_whatsapp_busca = "WhatsApp" if "WhatsApp" in busca_resultado_df.columns else detect_col(busca_resultado_df, [["whatsapp"], ["whats"]])

            if col_whatsapp_busca and col_whatsapp_busca in busca_resultado_df.columns and q_digits_busca:
                mask_busca = mask_busca | busca_resultado_df[col_whatsapp_busca].astype(str).apply(only_digits).str.contains(q_digits_busca, na=False)

            busca_resultado_df = busca_resultado_df[mask_busca].copy()

        if busca_resultado_df.empty:

            st.markdown(
                f"""
                <div class="live-card">
                    <div class="live-title">🔎 Busca rápida</div>
                    <div class="live-sub">
                        Nenhum lead encontrado para: <b>{html.escape(search_top)}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:

            col_status_busca = (
                "Status Venda Pedigree"
                if "Status Venda Pedigree" in busca_resultado_df.columns
                else detect_col(busca_resultado_df, [["status", "venda", "pedigree"], ["status", "venda"]])
            )

            if col_status_busca and col_status_busca in busca_resultado_df.columns:
                busca_resultado_df["Caixa atual"] = busca_resultado_df[col_status_busca].apply(status_venda_para_caixa)
            else:
                busca_resultado_df["Caixa atual"] = "Sem caixa definida"

            resumo_caixas_busca = (
                busca_resultado_df["Caixa atual"]
                .value_counts()
                .reset_index()
            )
            resumo_caixas_busca.columns = ["Caixa", "Quantidade"]

            caixas_texto_busca = " • ".join(
                [
                    f"{row['Caixa']}: {row['Quantidade']}"
                    for _, row in resumo_caixas_busca.iterrows()
                ]
            )

            st.markdown(
                f"""
                <div class="live-card">
                    <div class="live-title">🔎 Resultado da Busca Rápida</div>
                    <div class="live-sub">
                        {len(busca_resultado_df)} lead(s) encontrado(s). Caixa/status: <b>{html.escape(caixas_texto_busca)}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            colunas_busca_prioritarias = [
                "Caixa atual",
                "Nome",
                "Telefone",
                "WhatsApp",
                "CPF",
                "E-mail",
                "Email",
                "Data Compra",
                "Mês",
                "Raça",
                "Microchip",
                "Status Venda Pedigree",
            ]

            colunas_busca_exibir = [
                col
                for col in colunas_busca_prioritarias
                if col in busca_resultado_df.columns
            ]

            if not colunas_busca_exibir:
                colunas_busca_exibir = [
                    col
                    for col in busca_resultado_df.columns
                    if not str(col).startswith("_")
                ]

            render_realtime_table(
                busca_resultado_df,
                colunas_busca_exibir,
                height=360,
            )

            st.markdown("<br>", unsafe_allow_html=True)

    # ============================================
    # GRÁFICO VENDAS DA SEMANA
    # Fonte: aba "Pedigree Comissão Ju"
    # Regras:
    # - Conta a coluna Cliente
    # - Usa Data da Venda para posicionar na semana do calendário
    # - Usa Mês da Compra do Cliente para filtrar o mês selecionado
    # ============================================

    def mes_nome_para_numero(valor):
        texto = normalize_search_text(valor)

        mapa_meses = {
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

        for nome_mes, numero_mes in mapa_meses.items():
            if normalize_search_text(nome_mes) in texto:
                return numero_mes

        data_parseada = parse_date_any(valor)
        if data_parseada:
            return data_parseada.month

        m = re.search(r"\b(\d{1,2})\b", texto)
        if m:
            numero = int(m.group(1))
            if 1 <= numero <= 12:
                return numero

        return None

    def semana_calendario_por_data(data_ref, semanas_mes):
        if not data_ref:
            return None

        try:
            dia = int(data_ref.day)
        except Exception:
            return None

        for item in semanas_mes:
            if item["Inicio"] <= dia <= item["Fim"]:
                return item["Semana"]

        return None

    semanas_base = pd.DataFrame(
        [
            {
                "Semana": item["Semana"],
                "Ordem": item["Ordem"],
                "Período": item["Label"],
            }
            for item in semanas_calendario
        ]
    )

    df_comissao_vendas = load_commission_data().copy()

    if not df_comissao_vendas.empty:

        col_cliente_comissao = (
            "Cliente"
            if "Cliente" in df_comissao_vendas.columns
            else detect_col(df_comissao_vendas, [["cliente"]])
        )

        col_data_venda_comissao = (
            "Data da Venda"
            if "Data da Venda" in df_comissao_vendas.columns
            else detect_col(df_comissao_vendas, [["data", "venda"], ["data"]])
        )

        col_mes_compra_cliente = (
            "Mês da Compra do Cliente"
            if "Mês da Compra do Cliente" in df_comissao_vendas.columns
            else detect_col(
                df_comissao_vendas,
                [["mês", "compra", "cliente"], ["mes", "compra", "cliente"], ["compra", "cliente"]]
            )
        )

        df_comissao_vendas["_data_venda"] = (
            df_comissao_vendas[col_data_venda_comissao].apply(parse_date_any)
            if col_data_venda_comissao and col_data_venda_comissao in df_comissao_vendas.columns
            else None
        )

        df_comissao_vendas["_mes_compra_num"] = (
            df_comissao_vendas[col_mes_compra_cliente].apply(mes_nome_para_numero)
            if col_mes_compra_cliente and col_mes_compra_cliente in df_comissao_vendas.columns
            else None
        )

        df_comissao_mes = df_comissao_vendas[
            (df_comissao_vendas["_mes_compra_num"] == selected_month[1])
            & (
                df_comissao_vendas["_data_venda"].apply(
                    lambda d: bool(d and d.year == selected_month[0] and d.month == selected_month[1])
                )
            )
        ].copy()

        if col_cliente_comissao and col_cliente_comissao in df_comissao_mes.columns:
            df_comissao_mes = df_comissao_mes[
                df_comissao_mes[col_cliente_comissao].astype(str).str.strip() != ""
            ].copy()

        if not df_comissao_mes.empty:
            df_comissao_mes["_semana_label"] = df_comissao_mes["_data_venda"].apply(
                lambda d: semana_calendario_por_data(d, semanas_calendario)
            )
        else:
            df_comissao_mes["_semana_label"] = None

        if selected_week != "Todas" and not df_comissao_mes.empty:
            df_comissao_mes = df_comissao_mes[
                df_comissao_mes["_semana_label"] == selected_week
            ].copy()

        if not df_comissao_mes.empty:
            vendas_semana = (
                df_comissao_mes
                .groupby("_semana_label")
                .size()
                .reset_index(name="Vendas")
                .rename(columns={"_semana_label": "Semana"})
            )
        else:
            vendas_semana = pd.DataFrame(columns=["Semana", "Vendas"])

    else:

        vendas_semana = pd.DataFrame(columns=["Semana", "Vendas"])

    vendas_semana = semanas_base.merge(
        vendas_semana,
        on="Semana",
        how="left",
    )

    vendas_semana["Vendas"] = vendas_semana["Vendas"].fillna(0).astype(int)
    vendas_semana = vendas_semana.sort_values("Ordem")

    st.markdown(
        """
        <div class="live-card">
            <div class="live-title">📊 Vendas da semana</div>
            <div class="live-sub">
                Total de clientes da aba Pedigree Comissão Ju por semana real do calendário.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    fig_vendas_semana = px.bar(
        vendas_semana,
        x="Período",
        y="Vendas",
        text="Vendas",
    )

    fig_vendas_semana.update_layout(
        height=380,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="",
        yaxis_title="Vendas",
    )

    fig_vendas_semana.update_traces(
        textposition="outside",
    )

    st.plotly_chart(
        fig_vendas_semana,
        use_container_width=True,
    )


    st.markdown("<br><br>", unsafe_allow_html=True)

    # ============================================
    # PEDIGREE NA VISÃO GERAL
    # ============================================

    df_ped_visao = load_pedigree_data().copy()

    if not df_ped_visao.empty:

        ped_col_mes_vg = "Mês" if "Mês" in df_ped_visao.columns else detect_col(df_ped_visao, [["mês"], ["mes"]])
        ped_col_data_vg = detect_col(df_ped_visao, [["data", "compra"], ["data"]])

        df_ped_visao["_mes_key"] = df_ped_visao.apply(
            lambda row: build_month_key(row, ped_col_mes_vg, ped_col_data_vg),
            axis=1,
        )

    def mes_nome_para_numero_card(valor):
        texto = normalize_search_text(valor)

        mapa_meses = {
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

        for nome_mes, numero_mes in mapa_meses.items():
            if normalize_search_text(nome_mes) in texto:
                return numero_mes

        data_parseada = parse_date_any(valor)
        if data_parseada:
            return data_parseada.month

        m = re.search(r"\b(\d{1,2})\b", texto)
        if m:
            numero = int(m.group(1))
            if 1 <= numero <= 12:
                return numero

        return None

    # Total de Pedigrees agora vem da aba "Pedigree Comissão Ju",
    # contando somente as linhas preenchidas na coluna "Produtos" dentro do mês selecionado.
    df_comissao_card = load_commission_data().copy()

    if not df_comissao_card.empty:

        col_produtos_card = (
            "Produtos"
            if "Produtos" in df_comissao_card.columns
            else detect_col(df_comissao_card, [["produtos"], ["produto"]])
        )

        col_mes_compra_card = (
            "Mês da Compra do Cliente"
            if "Mês da Compra do Cliente" in df_comissao_card.columns
            else detect_col(
                df_comissao_card,
                [["mês", "compra", "cliente"], ["mes", "compra", "cliente"], ["compra", "cliente"]]
            )
        )

        if col_mes_compra_card and col_mes_compra_card in df_comissao_card.columns:
            df_comissao_card["_mes_compra_num_card"] = df_comissao_card[col_mes_compra_card].apply(mes_nome_para_numero_card)
            df_comissao_card = df_comissao_card[
                df_comissao_card["_mes_compra_num_card"] == selected_month[1]
            ].copy()

        if col_produtos_card and col_produtos_card in df_comissao_card.columns:
            total_pedigrees_vendidos = int(
                (df_comissao_card[col_produtos_card].astype(str).str.strip() != "").sum()
            )
        else:
            total_pedigrees_vendidos = 0

    else:

        total_pedigrees_vendidos = 0

    # Cães vendidos agora vem da aba "Clear", coluna "Status Venda Pedigree".
    # O card conta somente os nomes com status dentro do mês selecionado.
    df_caes_mes = (
        df[df["_mes_key"] == selected_month].copy()
        if not df.empty and "_mes_key" in df.columns
        else pd.DataFrame()
    )

    col_status_venda_pedigree = (
        "Status Venda Pedigree"
        if "Status Venda Pedigree" in df_caes_mes.columns
        else detect_col(df_caes_mes, [["status", "venda", "pedigree"], ["status", "venda"]])
    )

    status_resumo_caes = {
        "Não tem interesse": 0,
        "Com transferência": 0,
        "Conversando": 0,
        "Sem Resposta": 0,
        "Sem transferência": 0,
        "Novo Lead": 0,
    }

    status_masks_caes = {
        "Não tem interesse": pd.Series(False, index=df_caes_mes.index),
        "Com transferência": pd.Series(False, index=df_caes_mes.index),
        "Conversando": pd.Series(False, index=df_caes_mes.index),
        "Sem Resposta": pd.Series(False, index=df_caes_mes.index),
        "Sem transferência": pd.Series(False, index=df_caes_mes.index),
        "Novo Lead": pd.Series(False, index=df_caes_mes.index),
    }

    if not df_caes_mes.empty and col_status_venda_pedigree and col_status_venda_pedigree in df_caes_mes.columns:

        serie_status_caes = df_caes_mes[col_status_venda_pedigree].astype(str).apply(normalize_search_text)

        status_masks_caes["Não tem interesse"] = serie_status_caes.eq(normalize_search_text("Não tem interesse"))
        status_masks_caes["Com transferência"] = serie_status_caes.eq(normalize_search_text("Vendido"))
        status_masks_caes["Conversando"] = serie_status_caes.eq(normalize_search_text("Conversando"))
        status_masks_caes["Sem Resposta"] = serie_status_caes.eq(normalize_search_text("Sem Resposta"))
        status_masks_caes["Sem transferência"] = serie_status_caes.eq(normalize_search_text("Emitir Sem Venda"))
        status_masks_caes["Novo Lead"] = (
            serie_status_caes.eq(normalize_search_text("Vender"))
            | serie_status_caes.eq("")
            | serie_status_caes.eq(normalize_search_text("(Espaços em branco)"))
            | serie_status_caes.eq(normalize_search_text("Espaços em branco"))
        )

        for status_nome, status_mask in status_masks_caes.items():
            status_resumo_caes[status_nome] = int(status_mask.sum())

    total_caes_vendidos = int(sum(status_resumo_caes.values()))

    total_novos_leads = int(status_resumo_caes.get("Novo Lead", 0))
    mask_novos_leads = status_masks_caes.get(
        "Novo Lead",
        pd.Series(False, index=df_caes_mes.index),
    )

    total_col1, total_col2 = st.columns(2)

    with total_col1:
        card_metric_big(
            "Total de Pedigrees",
            f"{total_pedigrees_vendidos}",
            f"feitos em {month_key_to_label(selected_month)}",
            "⚖️",
            "#2e6cbf",
        )

    with total_col2:
        card_metric_big(
            "Controle Geral",
            f"{total_caes_vendidos}",
            f"nomes no mês de {month_key_to_label(selected_month)}",
            "🐶",
            "#032450",
        )

        if st.button(
            "Ver detalhes dos status",
            use_container_width=True,
            key="btn_detalhes_caes_vendidos",
        ):
            st.session_state["mostrar_detalhes_caes_vendidos"] = not st.session_state.get(
                "mostrar_detalhes_caes_vendidos",
                False,
            )

    if st.session_state.get("mostrar_detalhes_caes_vendidos", False):

        def selecionar_card_status(nome_status):
            st.session_state["status_card_aberto"] = nome_status

        d1, d2, d3, d4, d5, d6 = st.columns(6, gap="small")

        with d1:
            card_metric(
                "Não tem interesse",
                f"{status_resumo_caes.get('Não tem interesse', 0)}",
                month_key_to_label(selected_month),
                "🚫",
                "#0F5F6A",
            )
            st.button(
                "Ver nomes",
                use_container_width=True,
                key="btn_card_nao_tem_interesse",
                on_click=selecionar_card_status,
                args=("Não tem interesse",),
            )

        with d2:
            card_metric(
                "Com transferência",
                f"{status_resumo_caes.get('Com transferência', 0)}",
                month_key_to_label(selected_month),
                "✅",
                "#0E8A4A",
            )
            st.button(
                "Ver nomes",
                use_container_width=True,
                key="btn_card_com_transferencia",
                on_click=selecionar_card_status,
                args=("Com transferência",),
            )

        with d3:
            card_metric(
                "Conversando",
                f"{status_resumo_caes.get('Conversando', 0)}",
                month_key_to_label(selected_month),
                "💬",
                "#8B5A2B",
            )
            st.button(
                "Ver nomes",
                use_container_width=True,
                key="btn_card_conversando",
                on_click=selecionar_card_status,
                args=("Conversando",),
            )

        with d4:
            card_metric(
                "Sem Resposta",
                f"{status_resumo_caes.get('Sem Resposta', 0)}",
                month_key_to_label(selected_month),
                "📭",
                "#D64B3C",
            )
            st.button(
                "Ver nomes",
                use_container_width=True,
                key="btn_card_sem_resposta",
                on_click=selecionar_card_status,
                args=("Sem Resposta",),
            )

        with d5:
            card_metric(
                "Sem transferência",
                f"{status_resumo_caes.get('Sem transferência', 0)}",
                month_key_to_label(selected_month),
                "📄",
                "#6D4C9F",
            )
            st.button(
                "Ver nomes",
                use_container_width=True,
                key="btn_card_sem_transferencia",
                on_click=selecionar_card_status,
                args=("Sem transferência",),
            )

        with d6:
            card_metric(
                "Novo Lead",
                f"{total_novos_leads}",
                month_key_to_label(selected_month),
                "🆕",
                "#2e6cbf",
            )
            st.button(
                "Ver nomes",
                use_container_width=True,
                key="btn_card_novo_lead",
                on_click=selecionar_card_status,
                args=("Novo Lead",),
            )

        status_card_aberto = st.session_state.get("status_card_aberto", "")

        if status_card_aberto:

            st.markdown("<br>", unsafe_allow_html=True)

            if status_card_aberto == "Novo Lead":
                df_detalhes_status = df_caes_mes[mask_novos_leads].copy() if not df_caes_mes.empty else pd.DataFrame()
            else:
                mask_status_aberto = status_masks_caes.get(
                    status_card_aberto,
                    pd.Series(False, index=df_caes_mes.index),
                )
                df_detalhes_status = df_caes_mes[mask_status_aberto].copy() if not df_caes_mes.empty else pd.DataFrame()

            st.markdown(
                f"""
                <div class="live-card">
                    <div class="live-title">📋 {status_card_aberto}</div>
                    <div class="live-sub">
                        {len(df_detalhes_status)} nome(s) encontrado(s) em {month_key_to_label(selected_month)}.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if df_detalhes_status.empty:
                st.info("Nenhum nome encontrado para este status no mês selecionado.")
            else:
                colunas_prioritarias = [
                    "Nome",
                    "Telefone",
                    "WhatsApp",
                    "CPF",
                    "E-mail",
                    "Email",
                    "Data Compra",
                    "Mês",
                    "Raça",
                    "Microchip",
                    "Status Venda Pedigree",
                ]

                colunas_exibir = [
                    col
                    for col in colunas_prioritarias
                    if col in df_detalhes_status.columns
                ]

                if not colunas_exibir:
                    colunas_exibir = [
                        col
                        for col in df_detalhes_status.columns
                        if not str(col).startswith("_")
                    ]

                df_tabela_status = df_detalhes_status.copy()
                df_tabela_status["Linha"] = df_tabela_status.index.astype(int) + 2

                col_microchip_tabela = (
                    "Microchip"
                    if "Microchip" in df_tabela_status.columns
                    else detect_col(df_tabela_status, [["microchip"], ["micro", "chip"]])
                )

                if col_microchip_tabela and col_microchip_tabela in df_tabela_status.columns and col_microchip_tabela != "Microchip":
                    df_tabela_status["Microchip"] = df_tabela_status[col_microchip_tabela]

                if "Status Venda Pedigree" not in df_tabela_status.columns:
                    df_tabela_status["Status Venda Pedigree"] = ""

                if "Microchip" in df_tabela_status.columns and "Microchip" not in colunas_exibir:
                    if "Status Venda Pedigree" in colunas_exibir:
                        pos_status_venda = colunas_exibir.index("Status Venda Pedigree")
                        colunas_exibir.insert(pos_status_venda, "Microchip")
                    else:
                        colunas_exibir.append("Microchip")

                colunas_tabela_status = ["Linha"] + [
                    col
                    for col in colunas_exibir
                    if col != "Linha" and col != "Status Pedigree"
                ]

                st.markdown(
                    """
                    <div class="live-card">
                        <div class="live-title">✏️ Alterar Status Venda Pedigree</div>
                        <div class="live-sub">
                            Visual em planilha, com botão copiar no telefone. Novo Lead fica em branco até escolher um status.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                render_status_venda_editavel_table(
                    df_tabela_status,
                    colunas_tabela_status,
                    height=520,
                )

    st.markdown("<br>", unsafe_allow_html=True)

    # ============================================
    # GRÁFICO PRODUTOS VENDIDOS
    # Fonte: aba "Pedigree Comissão Ju", coluna "Produtos"
    # Regras:
    # - Filtra pelo Mês da Compra do Cliente
    # - Usa Data da Venda para identificar a semana real do calendário
    # - Conta os produtos vendidos no mês e semana selecionados
    # ============================================

    def produto_tem_rg(valor):
        texto = normalize_search_text(valor)
        return bool(re.search(r"\brg\b", texto))

    def produto_tem_certidao(valor):
        texto = normalize_search_text(valor)
        return "certidao" in texto or "certidão" in texto

    def produto_tem_airtag(valor):
        texto = normalize_search_text(valor)
        return "airtag" in texto or "air tag" in texto

    def produto_tem_pedigree_sem_transferencia(valor):
        return is_produto_sem_transferencia(valor)

    def produto_tem_pedigree_com_transferencia(valor):
        texto = normalize_search_text(valor)

        if "pedigree" not in texto:
            return False

        if produto_tem_pedigree_sem_transferencia(valor):
            return False

        return True

    produtos_base = pd.DataFrame(
        {
            "Produto": [
                "Pedigree com transferência",
                "Pedigree Sem Transferência",
                "RG",
                "Certidão",
                "Airtag",
            ],
            "Ordem": [1, 2, 3, 4, 5],
        }
    )

    df_produtos_vendidos = load_commission_data().copy()

    if not df_produtos_vendidos.empty:

        col_cliente_produtos = (
            "Cliente"
            if "Cliente" in df_produtos_vendidos.columns
            else detect_col(df_produtos_vendidos, [["cliente"]])
        )

        col_produtos_vendidos = (
            "Produtos"
            if "Produtos" in df_produtos_vendidos.columns
            else detect_col(df_produtos_vendidos, [["produtos"], ["produto"]])
        )

        col_data_venda_produtos = (
            "Data da Venda"
            if "Data da Venda" in df_produtos_vendidos.columns
            else detect_col(df_produtos_vendidos, [["data", "venda"], ["data"]])
        )

        col_mes_compra_produtos = (
            "Mês da Compra do Cliente"
            if "Mês da Compra do Cliente" in df_produtos_vendidos.columns
            else detect_col(
                df_produtos_vendidos,
                [["mês", "compra", "cliente"], ["mes", "compra", "cliente"], ["compra", "cliente"]]
            )
        )

        df_produtos_vendidos["_data_venda"] = (
            df_produtos_vendidos[col_data_venda_produtos].apply(parse_date_any)
            if col_data_venda_produtos and col_data_venda_produtos in df_produtos_vendidos.columns
            else None
        )

        df_produtos_vendidos["_mes_compra_num"] = (
            df_produtos_vendidos[col_mes_compra_produtos].apply(mes_nome_para_numero)
            if col_mes_compra_produtos and col_mes_compra_produtos in df_produtos_vendidos.columns
            else None
        )

        df_produtos_mes = df_produtos_vendidos[
            (df_produtos_vendidos["_mes_compra_num"] == selected_month[1])
            & (
                df_produtos_vendidos["_data_venda"].apply(
                    lambda d: bool(d and d.year == selected_month[0] and d.month == selected_month[1])
                )
            )
        ].copy()

        if col_cliente_produtos and col_cliente_produtos in df_produtos_mes.columns:
            df_produtos_mes = df_produtos_mes[
                df_produtos_mes[col_cliente_produtos].astype(str).str.strip() != ""
            ].copy()

        if not df_produtos_mes.empty:
            df_produtos_mes["_semana_label"] = df_produtos_mes["_data_venda"].apply(
                lambda d: semana_calendario_por_data(d, semanas_calendario)
            )

        if selected_week != "Todas" and not df_produtos_mes.empty:
            df_produtos_mes = df_produtos_mes[
                df_produtos_mes["_semana_label"] == selected_week
            ].copy()

        if col_produtos_vendidos and col_produtos_vendidos in df_produtos_mes.columns:

            resumo_produtos = {
                "Pedigree com transferência": int(
                    df_produtos_mes[col_produtos_vendidos].apply(produto_tem_pedigree_com_transferencia).sum()
                ),
                "Pedigree Sem Transferência": int(
                    df_produtos_mes[col_produtos_vendidos].apply(produto_tem_pedigree_sem_transferencia).sum()
                ),
                "RG": int(
                    df_produtos_mes[col_produtos_vendidos].apply(produto_tem_rg).sum()
                ),
                "Certidão": int(
                    df_produtos_mes[col_produtos_vendidos].apply(produto_tem_certidao).sum()
                ),
                "Airtag": int(
                    df_produtos_mes[col_produtos_vendidos].apply(produto_tem_airtag).sum()
                ),
            }

            produtos_vendidos = pd.DataFrame(
                [
                    {"Produto": produto, "Quantidade": quantidade}
                    for produto, quantidade in resumo_produtos.items()
                ]
            )

        else:

            produtos_vendidos = pd.DataFrame(columns=["Produto", "Quantidade"])

    else:

        produtos_vendidos = pd.DataFrame(columns=["Produto", "Quantidade"])

    produtos_vendidos = produtos_base.merge(
        produtos_vendidos,
        on="Produto",
        how="left",
    )

    produtos_vendidos["Quantidade"] = produtos_vendidos["Quantidade"].fillna(0).astype(int)
    produtos_vendidos = produtos_vendidos.sort_values("Ordem")

    st.markdown(
        """
        <div class="live-card">
            <div class="live-title">📦 Produtos vendidos</div>
            <div class="live-sub">
                Quantidade de produtos vendidos no mês e semana selecionados, com base na aba Pedigree Comissão Ju.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    fig_produtos_vendidos = px.bar(
        produtos_vendidos,
        x="Produto",
        y="Quantidade",
        text="Quantidade",
    )

    fig_produtos_vendidos.update_layout(
        height=420,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="",
        yaxis_title="Quantidade vendida",
    )

    fig_produtos_vendidos.update_traces(
        textposition="outside",
    )

    st.plotly_chart(
        fig_produtos_vendidos,
        use_container_width=True,
    )

    # Tabela/planilha da Visão Geral removida conforme solicitado.
    # Mantidos somente filtros e cards superiores desta página.

    # Mantidos somente filtros e cards superiores desta página.

elif page == "Pedigree":
    st.markdown('<div class="page-title">Pedigree</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Consulta completa de clientes para análise de Pedigree.</div>',
        unsafe_allow_html=True,
    )

    status_opcoes = [
        "Fazer Pedigree Venda",
        "Fazer Pedigree venda",
        "Fazer Pedigree s/ trans",
        "Fazer Pedrigree s/ trans",
        "Fazer RG/Certidão",
        "Fazer rg e certidão",
        "Pendência / Problemas",
        "Pendências / Problemas",
        "Aprovação Interna",
        "Aprovação Cliente",
        "Para Imprimir Pedigree",
        "Imprimir Pedigree",
        "Imprimir Etiqueta",
        "Imprimir RG E CERTIDÃO",
        "Imprimir RG + Certidão",
        "Airtag",
        "Envio Correio",
        "Postado/Enviado Correio",
        "Postado/Enviado Corr",
        "Postado/ enviado loja",
        "Pendência Cliente",
        "Sem Matriz",
    ]

    # Interpretação automática do texto da coluna "Status Pedigree" para abrir a área correta.
    # Não cria coluna nova: apenas lê o nome existente e mostra no botão/área correspondente.
    MAP_STATUS_ACAO = {
        "fazer pedigree venda": "Transferência",
        "fazer pedigree s/ trans": "Sem transferência",
        "fazer pedrigree s/ trans": "Sem transferência",
        "fazer rg/certidao": "RG E CERTIDÃO",
        "fazer rg e certidao": "RG E CERTIDÃO",
        "pendencia / problemas": "Problemas",
        "pendencias / problemas": "Problemas",
        "aprovacao interna": "Aprovação Interna",
        "aprovacao cliente": "Aprovação Cliente",
        "aprovacao": "Aprovação Interna",
        "para imprimir pedigree": "Imprimir Pedigree",
        "imprimir pedigree": "Imprimir Pedigree",
        "imprimir rg e certidao": "Imprimir RG+ Certidão",
        "imprimir rg + certidao": "Imprimir RG+ Certidão",
        "imprimir etiqueta": "Imprimir Etiqueta",
        "airtag": "Airtag",
        "envio correio": "Envio",
        "postado/enviado correio": "Enviado Cliente",
        "postado/enviado corr": "Enviado Cliente",
        "postado/ enviado loja": "Enviado Cliente",
        "pendencia cliente": "Problemas",
        "sem matriz": "Problemas",
    }

    def map_status_para_acao(status):
        status_norm = normalize_search_text(status)
        return MAP_STATUS_ACAO.get(status_norm, "")

    df_ped = load_pedigree_data().copy()

    if not df_ped.empty:
        df_ped["__row_number"] = df_ped.index + 2

        for col in [
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
        ]:
            if col not in df_ped.columns:
                df_ped[col] = ""

        ped_col_mes = "Mês" if "Mês" in df_ped.columns else detect_col(df_ped, [["mês"], ["mes"]])
        ped_col_data = detect_col(df_ped, [["data", "compra"], ["data"]])

        df_ped["_mes_key"] = df_ped.apply(
            lambda row: build_month_key(row, ped_col_mes, ped_col_data),
            axis=1,
        )

        def normalize_full_row(row):
            values = []
            for v in row:
                if pd.isna(v):
                    continue
                values.append(normalize_search_text(v))
            return " ".join(values)

        df_ped["_search_all"] = df_ped.apply(normalize_full_row, axis=1)
        df_ped["_tel_digits_ped"] = df_ped["Telefone"].apply(only_digits)
        df_ped["ACAO"] = df_ped["Status Pedigree"].apply(map_status_para_acao)
    else:
        df_ped = pd.DataFrame(
            columns=[
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
                "__row_number",
                "_search_all",
                "_tel_digits_ped",
                "ACAO",
                "_mes_key",
            ]
        )

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

    default_ped_month = (
        (today.year, today.month)
        if (today.year, today.month) in ped_month_options
        else ped_month_options[-1]
    )

    filtro_mes_col, vazio_col = st.columns([1.2, 2.8])

    with filtro_mes_col:
        selected_ped_month = st.selectbox(
            "Mês de referência",
            options=ped_month_options,
            index=ped_month_options.index(default_ped_month)
            if default_ped_month in ped_month_options
            else 0,
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
                c
                for c in df_busca.columns
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

    def titulo_responsavel(nome, subtitulo, cor):
        st.markdown(
            f"""
            <div style="
                margin: 18px 0 10px 0;
                padding: 12px 16px;
                border-radius: 16px;
                background: #FFFFFF;
                border: 1px solid #E7EAF3;
                border-left: 8px solid {cor};
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
            ">
                <div style="font-weight: 900; color: #032450; font-size: 1rem;">
                    {html.escape(nome)}
                </div>
                <div style="color: #6B7280; font-size: 0.82rem; margin-top: 2px;">
                    {html.escape(subtitulo)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # =========================
    # JULLIA
    # =========================
    titulo_responsavel(
        "Jullia",
        "Entrada, transferência, problemas e aprovação com cliente.",
        "#7C3AED",
    )

    jullia_linha1 = st.columns(4)
    jullia_linha2 = st.columns(4)

    with jullia_linha1[0]:
        st.button("Novo", use_container_width=True, on_click=set_acao_ped, args=("Novo",))
    with jullia_linha1[1]:
        st.button("Transferência", use_container_width=True, on_click=set_acao_ped, args=("Transferência",))
    with jullia_linha1[2]:
        st.button("Sem transferência", use_container_width=True, on_click=set_acao_ped, args=("Sem transferência",))
    with jullia_linha1[3]:
        st.button("Problemas", use_container_width=True, on_click=set_acao_ped, args=("Problemas",))

    with jullia_linha2[0]:
        st.button("Aprovação Cliente", use_container_width=True, on_click=set_acao_ped, args=("Aprovação Cliente",))

    # =========================
    # VALÉRIA
    # =========================
    titulo_responsavel(
        "Valéria",
        "Aprovação interna e preparação/impressão dos documentos.",
        "#EC4899",
    )

    valeria_linha1 = st.columns(4)
    valeria_linha2 = st.columns(4)

    with valeria_linha1[0]:
        st.button("Aprovação Interna", use_container_width=True, on_click=set_acao_ped, args=("Aprovação Interna",))
    with valeria_linha1[1]:
        st.button("Imprimir Pedigree", use_container_width=True, on_click=set_acao_ped, args=("Imprimir Pedigree",))
    with valeria_linha1[2]:
        st.button("Imprimir RG+ Certidão", use_container_width=True, on_click=set_acao_ped, args=("Imprimir RG+ Certidão",))
    with valeria_linha1[3]:
        st.button("Imprimir Etiqueta", use_container_width=True, on_click=set_acao_ped, args=("Imprimir Etiqueta",))

    with valeria_linha2[0]:
        st.button("Airtag", use_container_width=True, on_click=set_acao_ped, args=("Airtag",))

    # =========================
    # MAYRA
    # =========================
    titulo_responsavel(
        "Mayra",
        "RG/Certidão, envio e confirmação com o cliente.",
        "#F2C94C",
    )

    mayra_linha1 = st.columns(4)

    with mayra_linha1[0]:
        st.button("RG E CERTIDÃO", use_container_width=True, on_click=set_acao_ped, args=("RG E CERTIDÃO",))
    with mayra_linha1[1]:
        st.button("Envio", use_container_width=True, on_click=set_acao_ped, args=("Envio",))
    with mayra_linha1[2]:
        st.button("Enviado Cliente", use_container_width=True, on_click=set_acao_ped, args=("Enviado Cliente",))

    if st.session_state.acao_ped:
        if st.session_state.acao_ped == "Aprovação":
            st.session_state.acao_ped = "Aprovação Interna"

        acao_atual = st.session_state.acao_ped

        st.markdown(
            f"""
            <div class="ped-action-card">
                <div class="ped-action-title">{html.escape(acao_atual)}</div>
                <div class="ped-action-sub">Área aberta dentro da própria página Pedigree.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if acao_atual == "Novo":
            st.markdown("### Formulário Pedigree")

            # Busca automática das informações do contrato/lead na aba Clear.
            df_contratos_form = df.copy()

            if not df_contratos_form.empty:
                df_contratos_form = df_contratos_form.copy()
                df_contratos_form["__linha_clear"] = df_contratos_form.index + 2

            def valor_coluna_form(row, opcoes_colunas):
                if row is None:
                    return ""

                for nome_coluna in opcoes_colunas:
                    if nome_coluna in row.index:
                        return normalize_text(row.get(nome_coluna, ""))

                return ""

            def detectar_coluna_form(df_base, grupos):
                coluna = detect_col(df_base, grupos) if df_base is not None and not df_base.empty else None
                return coluna

            col_nome_pet_clear = detectar_coluna_form(
                df_contratos_form,
                [["nome", "pet"], ["nome", "cao"], ["nome", "cão"], ["nome", "cachorro"]],
            )

            col_data_nascimento_clear = detectar_coluna_form(
                df_contratos_form,
                [["data", "nascimento"], ["nascimento"]],
            )

            col_pelagem_clear = detectar_coluna_form(
                df_contratos_form,
                [["pelagem"]],
            )

            col_raca_clear = COL_RACA if COL_RACA and COL_RACA in df_contratos_form.columns else detectar_coluna_form(
                df_contratos_form,
                [["raça"], ["raca"]],
            )

            col_sexo_clear = detectar_coluna_form(
                df_contratos_form,
                [["sexo"]],
            )

            col_cor_clear = detectar_coluna_form(
                df_contratos_form,
                [["cor"]],
            )

            col_microchip_clear = detectar_coluna_form(
                df_contratos_form,
                [["microchip"], ["micro", "chip"]],
            )

            col_endereco_clear = detectar_coluna_form(
                df_contratos_form,
                [["endereço"], ["endereco"], ["rua"], ["bairro"], ["cidade"]],
            )

            contrato_row = None

            # Agora o formulário pega automaticamente o Novo Lead mais recente da aba Clear.
            # Novo Lead para o formulário = linha marcada como "Pendente" quando o status vira Vendido pela Visão Geral.
            if not df_contratos_form.empty:

                col_status_venda_form = (
                    "Status Venda Pedigree"
                    if "Status Venda Pedigree" in df_contratos_form.columns
                    else detect_col(df_contratos_form, [["status", "venda", "pedigree"], ["status", "venda"]])
                )

                # Nova entrada de contrato:
                # O formulário só deve puxar vendas novas feitas na Visão Geral.
                # Quando o status é alterado no dashboard para "Vendido",
                # a função atualizar_status_venda_pedigree_clear marca:
                # Novo Formulário Pedigree = Pendente.
                col_novo_formulario_clear = (
                    "Novo Formulário Pedigree"
                    if "Novo Formulário Pedigree" in df_contratos_form.columns
                    else detect_col(
                        df_contratos_form,
                        [["novo", "formulário", "pedigree"], ["novo", "formulario", "pedigree"]]
                    )
                )

                if col_novo_formulario_clear and col_novo_formulario_clear in df_contratos_form.columns:
                    serie_novo_formulario = (
                        df_contratos_form[col_novo_formulario_clear]
                        .astype(str)
                        .apply(normalize_search_text)
                    )

                    df_novos_leads_form = df_contratos_form[
                        serie_novo_formulario.eq(normalize_search_text("Pendente"))
                    ].copy()
                else:
                    df_novos_leads_form = pd.DataFrame()

                # Segurança extra: se a linha da Clear já foi lançada na aba Pedigree,
                # ela não aparece novamente, mas outra linha do mesmo cliente pode aparecer normalmente.
                df_pedigree_existente_form = load_pedigree_data().copy()

                if not df_novos_leads_form.empty and not df_pedigree_existente_form.empty:

                    linhas_clear_ja_lancadas = set()

                    if "Linha Clear Origem" in df_pedigree_existente_form.columns:
                        linhas_clear_ja_lancadas = set(
                            df_pedigree_existente_form["Linha Clear Origem"]
                            .astype(str)
                            .str.strip()
                            .replace("", pd.NA)
                            .dropna()
                            .tolist()
                        )

                    if linhas_clear_ja_lancadas and "__linha_clear" in df_novos_leads_form.columns:
                        df_novos_leads_form = df_novos_leads_form[
                            ~df_novos_leads_form["__linha_clear"].astype(str).isin(linhas_clear_ja_lancadas)
                        ].copy()

                if "_data_compra" in df_novos_leads_form.columns:
                    df_novos_leads_form = df_novos_leads_form.sort_values(
                        by=["_data_compra", "__linha_clear"],
                        ascending=[False, False],
                    )
                elif "__linha_clear" in df_novos_leads_form.columns:
                    df_novos_leads_form = df_novos_leads_form.sort_values(
                        by="__linha_clear",
                        ascending=False,
                    )

                if not df_novos_leads_form.empty:
                    contrato_row = df_novos_leads_form.iloc[0]

                    nome_lead_auto = normalize_text(contrato_row.get(COL_NOME, "")) if COL_NOME and COL_NOME in df_contratos_form.columns else ""
                    telefone_lead_auto = format_phone_br(contrato_row.get(COL_TEL, "")) if COL_TEL and COL_TEL in df_contratos_form.columns else ""

                    st.markdown(
                        f"""
                        <div class="live-card">
                            <div class="live-title">🆕 Novo lead carregado automaticamente</div>
                            <div class="live-sub">
                                {html.escape(nome_lead_auto or "Sem nome")} — {html.escape(telefone_lead_auto or "Sem telefone")}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("Nenhuma venda nova marcada pela Visão Geral disponível para preencher automaticamente no momento.")

            linha_clear_origem_default = normalize_text(contrato_row.get("__linha_clear", "")) if contrato_row is not None and "__linha_clear" in contrato_row.index else ""

            tutor_nome_default = normalize_text(contrato_row.get(COL_NOME, "")) if contrato_row is not None and COL_NOME and COL_NOME in df_contratos_form.columns else ""
            tutor_telefone_default = normalize_text(contrato_row.get(COL_TEL, "")) if contrato_row is not None and COL_TEL and COL_TEL in df_contratos_form.columns else ""
            tutor_cpf_default = normalize_text(contrato_row.get(COL_CPF, "")) if contrato_row is not None and COL_CPF and COL_CPF in df_contratos_form.columns else ""
            tutor_email_default = normalize_text(contrato_row.get(COL_EMAIL, "")) if contrato_row is not None and COL_EMAIL and COL_EMAIL in df_contratos_form.columns else ""
            tutor_endereco_default = valor_coluna_form(contrato_row, [col_endereco_clear]) if contrato_row is not None and col_endereco_clear else ""

            nome_pet_default = valor_coluna_form(contrato_row, [col_nome_pet_clear]) if contrato_row is not None and col_nome_pet_clear else ""
            pelagem_default = valor_coluna_form(contrato_row, [col_pelagem_clear]) if contrato_row is not None and col_pelagem_clear else ""
            raca_default = valor_coluna_form(contrato_row, [col_raca_clear]) if contrato_row is not None and col_raca_clear else ""
            sexo_default = valor_coluna_form(contrato_row, [col_sexo_clear]) if contrato_row is not None and col_sexo_clear else ""
            cor_default = valor_coluna_form(contrato_row, [col_cor_clear]) if contrato_row is not None and col_cor_clear else ""
            microchip_default = valor_coluna_form(contrato_row, [col_microchip_clear]) if contrato_row is not None and col_microchip_clear else ""

            nascimento_default = dt.date.today()

            if contrato_row is not None and col_data_nascimento_clear:
                nascimento_clear = parse_date_any(contrato_row.get(col_data_nascimento_clear, ""))
                if nascimento_clear:
                    nascimento_default = nascimento_clear

            with st.form("formulario_pedigree_novo"):
                st.markdown("#### Informações Tutor")

                col1, col2 = st.columns(2)

                with col1:
                    tutor_nome = st.text_input(
                        "Nome do tutor",
                        value=tutor_nome_default,
                    )

                    tutor_telefone = st.text_input(
                        "Telefone",
                        value=tutor_telefone_default,
                        disabled=True,
                    )

                    tutor_cpf = st.text_input(
                        "CPF",
                        value=tutor_cpf_default,
                        disabled=True,
                    )

                    tutor_email = st.text_input(
                        "E-mail",
                        value=tutor_email_default,
                        disabled=True,
                    )

                    tutor_endereco = st.text_input(
                        "Endereço completo",
                        value=tutor_endereco_default,
                        disabled=True,
                    )

                with col2:
                    status_cliente = st.selectbox("Status do Pedigree", status_opcoes)
                    transferencia = st.radio("Houve pedido de transferência?", ["Sim", "Não"], horizontal=True)
                    observacoes_status = st.text_area("Observações do status")

                st.markdown("#### Informações Cão")

                col3, col4 = st.columns(2)

                with col3:
                    cao_nome = st.text_input(
                        "Nome do pet",
                        value=nome_pet_default,
                    )

                    nascimento = st.date_input(
                        "Data de nascimento",
                        value=nascimento_default,
                    )

                    pelagem = st.text_input(
                        "Pelagem",
                        value=pelagem_default,
                        disabled=True,
                    )

                    raca = st.text_input(
                        "Raça do pet",
                        value=raca_default,
                        disabled=True,
                    )

                    sexo_opcoes = ["", "MACHO", "FÊMEA"]

                    sexo_default_norm = normalize_search_text(sexo_default)

                    if sexo_default_norm in ["macho", "masculino", "m"]:
                        sexo_default_visual = "MACHO"
                    elif sexo_default_norm in ["femea", "fêmea", "feminino", "f"]:
                        sexo_default_visual = "FÊMEA"
                    else:
                        sexo_default_visual = ""

                    sexo = st.selectbox(
                        "Sexo",
                        sexo_opcoes,
                        index=sexo_opcoes.index(sexo_default_visual) if sexo_default_visual in sexo_opcoes else 0,
                        disabled=True,
                    )

                    cor = st.text_input(
                        "Cor",
                        value=cor_default,
                        disabled=True,
                    )

                    microchip = st.text_input(
                        "Microchip",
                        value=microchip_default,
                    )

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
                        "Mês": hoje.strftime("%m/%Y"),
                        "Raça": raca,
                        "Sexo": sexo,
                        "Cor": cor,
                        "Endereço completo": tutor_endereco,
                        "Status Pedigree": status_cliente,
                        "Transferência": transferencia,
                        "Observações Status": observacoes_status,
                        "Nome Cachorro": cao_nome,
                        "Data Nascimento": nascimento.strftime("%d/%m/%Y"),
                        "Pelagem": pelagem,
                        "Microchip": microchip,
                        "Observações gerais": observacoes,
                        "Linha Clear Origem": linha_clear_origem_default,
                    }

                    try:
                        salvar_formulario_pedigree(dados_formulario)

                        if linha_clear_origem_default:
                            marcar_novo_formulario_pedigree_feito(
                                safe_int_zero(linha_clear_origem_default)
                            )

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

    # Cards e gráfico de Pedigree foram removidos desta aba.
    # Eles permanecem somente na aba Visão Geral, conforme solicitado.


elif page == "Comissão":
    st.markdown('<div class="page-title">Comissão</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Painel de acompanhamento da aba Pedigree Comissão Ju.</div>',
        unsafe_allow_html=True,
    )

    if "sync_pedigree_comissao_feito" not in st.session_state:
        st.session_state["sync_pedigree_comissao_feito"] = False

    sync_col1, sync_col2 = st.columns([1, 4])

    with sync_col1:
        sincronizar_agora = st.button("Sincronizar", use_container_width=True, key="btn_sync_pedigree_comissao")

    # Não sincroniza automaticamente ao abrir a página.
    # Use o botão Sincronizar apenas para recarregar os dados atuais da aba Pedigree Comissão Ju.
    if sincronizar_agora:
        try:
            sync_pedigrees_para_comissao()
            st.session_state["sync_pedigree_comissao_feito"] = True
            st.success("Dados da aba Pedigree Comissão Ju recarregados.")
            st.rerun()
        except Exception as e:
            st.warning(f"Não foi possível recarregar a aba de Comissão: {e}")

    df_com = load_commission_data().copy()

    if not df_com.empty:
        col_data_venda = "Data da Venda" if "Data da Venda" in df_com.columns else detect_col(df_com, [["data", "venda"]])
        col_mes_venda = "Mês da Venda" if "Mês da Venda" in df_com.columns else detect_col(df_com, [["mês", "venda"], ["mes", "venda"]])
        col_cliente = "Cliente" if "Cliente" in df_com.columns else detect_col(df_com, [["cliente"]])
        col_qtd_pedigrees = "Quantidade de Pedigrees" if "Quantidade de Pedigrees" in df_com.columns else detect_col(df_com, [["quantidade", "pedigree"], ["qtd", "pedigree"]])
        col_produtos = "Produtos" if "Produtos" in df_com.columns else detect_col(df_com, [["produto"]])
        col_mes_compra_cliente = (
            "Mês da Compra do Cliente"
            if "Mês da Compra do Cliente" in df_com.columns
            else detect_col(df_com, [["compra", "cliente"]])
        )
        col_valor = "Valor" if "Valor" in df_com.columns else detect_col(df_com, [["valor"]])
        col_vendedor = "Vendedor" if "Vendedor" in df_com.columns else detect_col(df_com, [["vendedor"]])
        col_silimario = "Silmário" if "Silmário" in df_com.columns else ("Silimario" if "Silimario" in df_com.columns else detect_col(df_com, [["silmario"], ["silimario"]]))

        df_com["_data_venda"] = df_com[col_data_venda].apply(parse_date_any) if col_data_venda else None
        df_com["_mes_key"] = df_com.apply(lambda row: build_month_key(row, col_mes_venda, col_data_venda), axis=1)
        df_com["_valor_num"] = df_com[col_valor].apply(parse_money) if col_valor else 0.0
        df_com["_silimario_num"] = df_com[col_silimario].apply(parse_money) if col_silimario else 0.0
        df_com["_produto_norm"] = df_com[col_produtos].apply(normalize_search_text) if col_produtos else ""

        # Aplica os valores históricos conferidos manualmente antes de qualquer soma/card.
        df_com = aplicar_valores_historicos_fixos(df_com, col_cliente, col_valor)

        # IMPORTANTE:
        # A função acima pode criar a coluna "Quantidade de Pedigrees" quando ela não existe na planilha.
        # Então precisamos redetectar a coluna aqui, depois dos ajustes históricos.
        # Isso garante que clientes como:
        # - Silvia Regina Leite Faganello = 2
        # - Nilbea Regina Silva = 2
        # - Mariana Sebanico Perim Bonassa = 3
        # apareçam corretamente no dashboard, mesmo que a planilha ainda esteja com 1 ou sem a coluna.
        col_qtd_pedigrees = (
            "Quantidade de Pedigrees"
            if "Quantidade de Pedigrees" in df_com.columns
            else detect_col(df_com, [["quantidade", "pedigree"], ["qtd", "pedigree"]])
        )

        comm_months = sorted([m for m in df_com["_mes_key"].dropna().unique().tolist()], key=lambda x: (x[0], x[1]))

        if not comm_months:
            comm_months = [(today.year, today.month)]

        default_comm_month = comm_months[-1]

        left_col, right_col = st.columns([1.05, 2.7])

        with left_col:
            st.markdown(
                """
                <div class="live-card">
                    <div class="live-title">Filtros da Comissão</div>
                    <div class="live-sub">Use os filtros abaixo para acompanhar os valores.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            data_referencia = st.selectbox(
                "Data de referência",
                options=comm_months,
                index=comm_months.index(default_comm_month),
                format_func=month_key_to_label,
                key="data_referencia_comissao",
            )


            st.markdown(
                """
                <div class="live-card">
                    <div class="live-title">Total de vendas por produto</div>
                    <div class="live-sub">Contagem pelo produto selecionado na planilha.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            df_produtos_mes = df_com[df_com["_mes_key"] == data_referencia].copy()
            produto = df_produtos_mes["_produto_norm"]

            qtd_pedigree_trans = int(
                (
                    produto.str.contains("pedigree", na=False)
                    & ~produto.str.contains("s/ troca", na=False)
                    & ~produto.str.contains("sem transferencia", na=False)
                    & ~produto.str.contains("s/ trans", na=False)
                ).sum()
            )

            qtd_airtag = int(produto.str.contains("airtag", na=False).sum())

            qtd_cert_rg = int(
                (
                    produto.str.contains("certidao", na=False)
                    & produto.str.contains("rg", na=False)
                ).sum()
            )

            qtd_somente_rg = int(
                (
                    produto.str.contains("rg", na=False)
                    & ~produto.str.contains("certidao", na=False)
                    & ~produto.str.contains("airtag", na=False)
                ).sum()
            )

            qtd_ped_sem_trans = int(
                (
                    produto.str.contains("pedigree", na=False)
                    & (
                        produto.str.contains("s/ troca", na=False)
                        | produto.str.contains("sem transferencia", na=False)
                        | produto.str.contains("s/ trans", na=False)
                    )
                ).sum()
            )

            qtd_somente_certidao = int(
                (
                    produto.str.contains("certidao", na=False)
                    & ~produto.str.contains("rg", na=False)
                    & ~produto.str.contains("airtag", na=False)
                ).sum()
            )

            st.markdown(
                f"""
                <div class="live-card">
                    <div class="live-sub"><b>Pedigree com Transferência:</b> {qtd_pedigree_trans}</div>
                    <div class="live-sub"><b>Airtag:</b> {qtd_airtag}</div>
                    <div class="live-sub"><b>Certidão e RG:</b> {qtd_cert_rg}</div>
                    <div class="live-sub"><b>Somente RG:</b> {qtd_somente_rg}</div>
                    <div class="live-sub"><b>Pedigree sem Transferência:</b> {qtd_ped_sem_trans}</div>
                    <div class="live-sub"><b>Somente Certidão:</b> {qtd_somente_certidao}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            mes_valor_cliente = st.selectbox(
                "Valor total vendido no mês",
                options=comm_months,
                index=comm_months.index(default_comm_month),
                format_func=month_key_to_label,
                key="valor_clientes_mes_comissao",
            )

            df_mes_valor = df_com[df_com["_mes_key"] == mes_valor_cliente].copy()

            # O card precisa bater exatamente com a soma da coluna Valor.
            # Por isso a soma é feita lendo a própria coluna Valor visível/atualizada,
            # e não uma métrica antiga em memória. Quando uma venda é adicionada ou
            # excluída da planilha, ao recarregar/sincronizar o total acompanha a base atual.
            if not df_mes_valor.empty and col_valor and col_valor in df_mes_valor.columns:
                valor_clientes_mes = float(df_mes_valor[col_valor].apply(parse_money).sum())
            else:
                valor_clientes_mes = 0.0

            valor_total_mes_placeholder = st.empty()

            def render_valor_total_mes_card(valor_total_mes_atual: float):
                valor_total_mes_placeholder.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-wrap">
                            <div class="metric-icon" style="background:#2e6cbf;">💰</div>
                            <div>
                                <div class="metric-label">Valor total<br>vendido no mês</div>
                                <div class="metric-value">{format_money(valor_total_mes_atual)}</div>
                                <div class="metric-sub">{month_key_to_label(mes_valor_cliente)}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            render_valor_total_mes_card(valor_clientes_mes)

        with right_col:
            selected_comm_month = data_referencia

            # Regra definida:
            # - Meses anteriores a Maio/2026: comissão calculada somente pela leitura da planilha.
            # - Maio/2026 em diante: comissão calculada pelas marcações feitas no dashboard.
            MES_DASHBOARD_INICIO = (2026, 5)
            usar_marcacoes_dashboard = selected_comm_month >= MES_DASHBOARD_INICIO

            vendedores = ["Todos"]

            if col_vendedor and col_vendedor in df_com.columns:
                vendedores += sorted(
                    [
                        v
                        for v in df_com[col_vendedor].dropna().astype(str).str.strip().unique().tolist()
                        if v
                    ]
                )

            filtro1, filtro2 = st.columns([1.2, 2.4])

            with filtro1:
                selected_vendedor = st.selectbox("Vendedor", vendedores, key="vendedor_comissao")

            with filtro2:
                busca_comissao = st.text_input(
                    "Busca rápida",
                    placeholder="Buscar por cliente, produto, vendedor...",
                )

            df_com_filtrado = df_com[df_com["_mes_key"] == selected_comm_month].copy()

            if selected_vendedor != "Todos" and col_vendedor and col_vendedor in df_com_filtrado.columns:
                df_com_filtrado = df_com_filtrado[
                    df_com_filtrado[col_vendedor].astype(str).str.strip() == selected_vendedor
                ].copy()

            if busca_comissao.strip():
                q = normalize_search_text(busca_comissao)

                busca_cols = [
                    c
                    for c in [col_cliente, col_produtos, col_vendedor, col_mes_compra_cliente]
                    if c and c in df_com_filtrado.columns
                ]

                if busca_cols:
                    mask_busca = pd.Series(False, index=df_com_filtrado.index)

                    for c in busca_cols:
                        mask_busca = mask_busca | df_com_filtrado[c].apply(normalize_search_text).str.contains(q, na=False)

                    df_com_filtrado = df_com_filtrado[mask_busca].copy()

            total_vendas = len(df_com_filtrado)
            valor_total = float(df_com_filtrado["_valor_num"].sum()) if not df_com_filtrado.empty else 0.0
            silimario_total = float(df_com_filtrado["_silimario_num"].sum()) if not df_com_filtrado.empty else 0.0
            ticket_medio = valor_total / total_vendas if total_vendas else 0.0

            if not df_com_filtrado.empty and col_produtos and col_produtos in df_com_filtrado.columns:
                produtos_unicos = df_com_filtrado[col_produtos].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
            else:
                produtos_unicos = 0

            # A comissão da Jullia é calculada pela base inteira do mês selecionado.
            # A caixa abaixo é preenchida depois do editor, assim ela atualiza ao marcar/desmarcar produtos.
            df_com_mes_calculo_jullia = df_com[df_com["_mes_key"] == selected_comm_month].copy()
            comissao_card_placeholder = st.empty()
            regra_card_placeholder = st.empty()

            def render_card_comissao_jullia(df_base_calculo):
                dados_jullia_render = calcular_comissao_jullia(
                    df_base_calculo,
                    col_produtos,
                    col_valor,
                    col_vendedor,
                )

                comissao_fixa_mes = comissao_historica_fixa(selected_comm_month)

                if comissao_fixa_mes is not None and selected_comm_month < (2026, 5):
                    comissao_jullia_render = float(comissao_fixa_mes)
                    percentual_jullia_render = dados_jullia_render["percentual_jullia"]
                    qtd_jullia_validas_render = dados_jullia_render["qtd_vendas_jullia_validas"]
                    total_validas_mes_render = dados_jullia_render["total_vendas_validas_mes"]
                    faixa_jullia_render = "Comissão histórica fixa conferida manualmente"
                else:
                    comissao_jullia_render = dados_jullia_render["comissao_jullia"]
                    percentual_jullia_render = dados_jullia_render["percentual_jullia"]
                    qtd_jullia_validas_render = dados_jullia_render["qtd_vendas_jullia_validas"]
                    total_validas_mes_render = dados_jullia_render["total_vendas_validas_mes"]
                    faixa_jullia_render = dados_jullia_render["faixa"]

                comissao_card_placeholder.markdown(
                    f"""
                    <div class="metric-card" style="min-height:126px; display:flex; align-items:center;">
                        <div class="metric-wrap">
                            <div class="metric-icon" style="background:#2e6cbf;">💰</div>
                            <div>
                                <div class="metric-label">Comissão Jullia</div>
                                <div class="metric-value">{format_money(comissao_jullia_render)}</div>
                                <div class="metric-sub">{qtd_jullia_validas_render} de {total_validas_mes_render} vendas válidas • {percentual_jullia_render:.1%}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                regra_card_placeholder.markdown(
                    f"""
                    <div class="live-card" style="margin-top:1rem;">
                        <div class="live-title">Regra aplicada</div>
                        <div class="live-sub">
                            {faixa_jullia_render}. {"Janeiro a Abril/2026 usam o valor fechado manualmente. Maio/2026 em diante usa as marcações do dashboard." if comissao_fixa_mes is not None and selected_comm_month < (2026, 5) else "Base: todas as vendas do mês com produto escolhido, menos Pedigree sem transferência."}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown(
                """
                <div class="live-card">
                    <div class="live-title">📄 Lista de vendas da comissão</div>
                    <div class="live-sub">Base filtrada da aba Pedigree Comissão Ju.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            cols_show = [
                c
                for c in [
                    col_data_venda,
                    col_mes_venda,
                    col_cliente,
                    col_produtos,
                    col_mes_compra_cliente,
                    col_valor,
                    col_vendedor,
                    col_silimario,
                ]
                if c and c in df_com_filtrado.columns
            ]

            if not df_com_filtrado.empty and cols_show:
                df_editor = df_com_filtrado.copy()

                if col_produtos and col_produtos in df_editor.columns:
                    produto_series = df_editor[col_produtos].fillna("").astype(str)
                else:
                    produto_series = pd.Series([""] * len(df_editor), index=df_editor.index)

                checks_df = produto_series.apply(checks_por_produto).apply(pd.Series)

                if "__row_number" not in df_editor.columns:
                    df_editor["__row_number"] = df_editor.index + 2

                df_editor_view = pd.DataFrame({
                    "Linha": df_editor["__row_number"].fillna(0).astype(int),
                    "Data da Venda": df_editor[col_data_venda] if col_data_venda and col_data_venda in df_editor.columns else "",
                    "Mês da Venda": df_editor[col_mes_venda] if col_mes_venda and col_mes_venda in df_editor.columns else "",
                    "Cliente": df_editor[col_cliente] if col_cliente and col_cliente in df_editor.columns else "",
                    "Quantidade de Pedigrees": df_editor[col_qtd_pedigrees].apply(safe_int_zero).replace(0, 1) if col_qtd_pedigrees and col_qtd_pedigrees in df_editor.columns else 1,
                    "Pedigree Transferência": checks_df["Pedigree Transferência"].astype(bool),
                    "Sem Transferência": checks_df["Sem Transferência"].astype(bool),
                    "Correios": checks_df["Correios"].astype(bool) if "Correios" in checks_df.columns else checks_df["Pedigree Transferência"].astype(bool),
                    "RG": checks_df["RG"].astype(bool),
                    "Certidão": checks_df["Certidão"].astype(bool),
                    "Airtag": checks_df["Airtag"].astype(bool),
                    "Valor": "",
                    "Vendedor": df_editor[col_vendedor] if col_vendedor and col_vendedor in df_editor.columns else "",
                })

                editor_key = f"editor_checks_comissao_{selected_comm_month}_{selected_vendedor}_{busca_comissao}"

                # Estado próprio por linha. Isso evita o problema de selecionar um checkbox
                # e perder as outras marcações da mesma linha no rerun do Streamlit.
                selecoes_key = "selecoes_comissao_por_linha"
                if selecoes_key not in st.session_state:
                    st.session_state[selecoes_key] = {}

                checkbox_cols = [
                    "Pedigree Transferência",
                    "Sem Transferência",
                    "Correios",
                    "RG",
                    "Certidão",
                    "Airtag",
                ]

                for idx_init, row_init in df_editor_view.iterrows():
                    linha_init = str(safe_int_zero(row_init.get("Linha", 0)))
                    if linha_init in st.session_state[selecoes_key]:
                        estado_linha = st.session_state[selecoes_key][linha_init]

                        # Restaura a quantidade digitada anteriormente.
                        # Sem isso, o Streamlit voltava para 1 e parecia que a conta não mudava.
                        if "Quantidade de Pedigrees" in estado_linha:
                            df_editor_view.at[idx_init, "Quantidade de Pedigrees"] = safe_int_zero(estado_linha.get("Quantidade de Pedigrees", 1)) or 1

                        for col_chk in checkbox_cols:
                            df_editor_view.at[idx_init, col_chk] = bool(estado_linha.get(col_chk, False))

                def recalcular_linha_editor(row_editor):
                    ped_trans_calc = checkbox_marcado(row_editor.get("Pedigree Transferência", False))
                    ped_sem_calc = checkbox_marcado(row_editor.get("Sem Transferência", False))
                    correios_calc = checkbox_marcado(row_editor.get("Correios", False))
                    rg_calc = checkbox_marcado(row_editor.get("RG", False))
                    certidao_calc = checkbox_marcado(row_editor.get("Certidão", False))
                    airtag_calc = checkbox_marcado(row_editor.get("Airtag", False))
                    qtd_calc = safe_int_zero(row_editor.get("Quantidade de Pedigrees", 1)) or 1

                    # Permite múltiplas escolhas simultâneas.
                    # Sem Transferência não é frete; o frete obrigatório já entra fixo quando Transferência está marcada.

                    produto_calc = montar_produto_por_checks(
                        ped_trans_calc,
                        ped_sem_calc,
                        rg_calc,
                        certidao_calc,
                        airtag_calc,
                    )

                    return format_money(calcular_valor_por_checks(ped_trans_calc, ped_sem_calc, correios_calc, rg_calc, certidao_calc, airtag_calc, qtd_calc))

                df_editor_view["Valor"] = df_editor_view.apply(recalcular_linha_editor, axis=1)

                st.markdown(
                    f"""
                    <div class="live-sub" style="margin-top:0.2rem; margin-bottom:0.8rem;">
                        {"Marque os produtos desejados e informe a Quantidade de Pedigrees. Para inserir uma nova venda, adicione uma linha no final preenchendo Data da Venda, Mês da Venda e Cliente. Depois clique em Calcular prévia / salvar novas linhas." if usar_marcacoes_dashboard else "Mês histórico: você pode ajustar Quantidade de Pedigrees/Produtos no dashboard e salvar direto na planilha; a comissão final do mês continua usando os valores históricos conferidos."}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # IMPORTANTE:
                # O st.data_editor fora de formulário faz o Streamlit rodar a página inteira
                # a cada checkbox marcado. Isso fazia a grade voltar para o começo.
                # Dentro do st.form, você pode marcar várias opções/linhas primeiro;
                # a página só recalcula quando clicar em "Calcular prévia".
                with st.form(key=f"form_{editor_key}", clear_on_submit=False):
                    edited_df = st.data_editor(
                        df_editor_view,
                        use_container_width=True,
                        hide_index=True,
                        height=430,
                        column_config={
                            "Linha": st.column_config.NumberColumn("Linha", disabled=True),
                            "Data da Venda": st.column_config.TextColumn("Data da Venda"),
                            "Mês da Venda": st.column_config.TextColumn("Mês da Venda"),
                            "Cliente": st.column_config.TextColumn("Cliente"),
                            "Quantidade de Pedigrees": st.column_config.NumberColumn("Quantidade de Pedigrees", min_value=1, step=1),
                            "Pedigree Transferência": st.column_config.CheckboxColumn("Pedigree Transferência"),
                            "Sem Transferência": st.column_config.CheckboxColumn("Sem Transferência"),
                            "Correios": st.column_config.CheckboxColumn("Correios"),
                            "RG": st.column_config.CheckboxColumn("RG"),
                            "Certidão": st.column_config.CheckboxColumn("Certidão"),
                            "Airtag": st.column_config.CheckboxColumn("Airtag"),
                            "Valor": st.column_config.TextColumn("Valor", disabled=True),
                            "Vendedor": st.column_config.TextColumn("Vendedor", disabled=True),
                        },
                        key=editor_key,
                        disabled=["Valor", "Vendedor"],
                        num_rows="dynamic",
                    )

                    aplicar_previa = st.form_submit_button(
                        "Calcular prévia da comissão",
                        use_container_width=True,
                    )

                # Atualiza o estado próprio com TODAS as marcações retornadas pelo editor
                # somente quando o usuário terminar de marcar e clicar no botão.
                # Assim a tabela não fica voltando para o começo a cada clique.
                if aplicar_previa:
                    novas_linhas_para_salvar = []
                    edicoes_linhas_para_salvar = []

                    for _, row_state_editor in edited_df.iterrows():
                        linha_state_num = safe_int_zero(row_state_editor.get("Linha", 0))
                        linha_state = str(linha_state_num)

                        data_linha = normalize_text(row_state_editor.get("Data da Venda", ""))
                        mes_linha = normalize_text(row_state_editor.get("Mês da Venda", ""))
                        cliente_linha = normalize_text(row_state_editor.get("Cliente", ""))
                        qtd_pedigrees_linha = safe_int_zero(row_state_editor.get("Quantidade de Pedigrees", 1)) or 1

                        ped_trans_linha = checkbox_marcado(row_state_editor.get("Pedigree Transferência", False))
                        ped_sem_linha = checkbox_marcado(row_state_editor.get("Sem Transferência", False))
                        correios_linha = checkbox_marcado(row_state_editor.get("Correios", False))
                        rg_linha = checkbox_marcado(row_state_editor.get("RG", False))
                        certidao_linha = checkbox_marcado(row_state_editor.get("Certidão", False))
                        airtag_linha = checkbox_marcado(row_state_editor.get("Airtag", False))

                        produto_linha = montar_produto_com_correios(
                            ped_trans_linha,
                            ped_sem_linha,
                            correios_linha,
                            rg_linha,
                            certidao_linha,
                            airtag_linha,
                        )
                        valor_linha = calcular_valor_por_checks(
                            ped_trans_linha,
                            ped_sem_linha,
                            correios_linha,
                            rg_linha,
                            certidao_linha,
                            airtag_linha,
                            qtd_pedigrees_linha,
                        )

                        if linha_state != "0":
                            estado_linha_atual = {
                                col_chk: checkbox_marcado(row_state_editor.get(col_chk, False))
                                for col_chk in checkbox_cols
                            }
                            estado_linha_atual["Quantidade de Pedigrees"] = qtd_pedigrees_linha
                            st.session_state[selecoes_key][linha_state] = estado_linha_atual

                            # Salva diretamente na planilha a quantidade, produtos e valor calculado.
                            # Isso resolve os casos de clientes com 2 ou mais pedigrees na mesma venda.
                            if qtd_pedigrees_linha >= 2 or produto_linha or data_linha or mes_linha or cliente_linha:
                                edicoes_linhas_para_salvar.append({
                                    "Linha": linha_state_num,
                                    "Data da Venda": data_linha,
                                    "Mês da Venda": mes_linha,
                                    "Cliente": cliente_linha,
                                    "Quantidade de Pedigrees": qtd_pedigrees_linha,
                                    "Produtos": produto_linha,
                                    "Mês da Compra do Cliente": mes_linha,
                                    "Valor": format_money(valor_linha),
                                    "Vendedor": normalize_text(row_state_editor.get("Vendedor", "Jullia")) or "Jullia",
                                })
                        else:
                            # Linha nova criada no editor. Só salva quando tiver pelo menos Data/Mês/Cliente ou algum produto marcado.
                            if data_linha or mes_linha or cliente_linha or produto_linha:
                                novas_linhas_para_salvar.append({
                                    "Data da Venda": data_linha,
                                    "Mês da Venda": mes_linha,
                                    "Cliente": cliente_linha,
                                    "Quantidade de Pedigrees": qtd_pedigrees_linha,
                                    "Produtos": produto_linha,
                                    "Mês da Compra do Cliente": mes_linha,
                                    "Valor": format_money(valor_linha),
                                    "Vendedor": "Jullia",
                                })

                    try:
                        qtd_editadas = salvar_edicoes_linhas_comissao(edicoes_linhas_para_salvar)
                        qtd_salvas = salvar_novas_linhas_comissao(novas_linhas_para_salvar) if novas_linhas_para_salvar else 0

                        if qtd_editadas or qtd_salvas:
                            st.success(f"{qtd_editadas} linha(s) atualizada(s) e {qtd_salvas} nova(s) venda(s) adicionada(s) na aba Pedigree Comissão Ju.")
                        else:
                            st.info("Prévia recalculada. Nenhuma linha nova ou alteração para salvar.")

                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar alterações na planilha: {e}")
                else:
                    # Sem submit, usa a versão inicial/persistida para renderizar a prévia atual.
                    # Isso evita salvar alterações parciais que ainda estão sendo marcadas na tela.
                    pass

                # Prévia ao vivo da comissão:
                # monta uma base nova com o que está marcado no editor, sem depender da planilha salvar primeiro.
                df_com_mes_preview = df_com_mes_calculo_jullia.copy()

                if "__row_number" not in df_com_mes_preview.columns:
                    df_com_mes_preview["__row_number"] = df_com_mes_preview.index + 2

                linhas_editadas_preview = []

                for _, row_edit_preview in (edited_df if usar_marcacoes_dashboard else pd.DataFrame()).iterrows():
                    row_number_preview = safe_int_zero(row_edit_preview.get("Linha", 0))

                    ped_trans_preview = checkbox_marcado(row_edit_preview.get("Pedigree Transferência", False))
                    ped_sem_preview = checkbox_marcado(row_edit_preview.get("Sem Transferência", False))
                    correios_preview = checkbox_marcado(row_edit_preview.get("Correios", False))
                    rg_preview = checkbox_marcado(row_edit_preview.get("RG", False))
                    certidao_preview = checkbox_marcado(row_edit_preview.get("Certidão", False))
                    airtag_preview = checkbox_marcado(row_edit_preview.get("Airtag", False))
                    qtd_pedigrees_preview = safe_int_zero(row_edit_preview.get("Quantidade de Pedigrees", 1)) or 1

                    # Permite múltiplas escolhas simultâneas.
                    # Sem Transferência não é frete. Se Transferência e Sem Transferência ficarem marcados juntos, a Transferência vence e não soma R$ 35,80 duas vezes.

                    produto_preview = montar_produto_com_correios(
                        ped_trans_preview,
                        ped_sem_preview,
                        correios_preview,
                        rg_preview,
                        certidao_preview,
                        airtag_preview,
                    )

                    valor_preview = calcular_valor_por_checks(ped_trans_preview, ped_sem_preview, correios_preview, rg_preview, certidao_preview, airtag_preview, qtd_pedigrees_preview)

                    if row_number_preview > 0:
                        linhas_editadas_preview.append(row_number_preview)

                        mask_preview = df_com_mes_preview["__row_number"].astype(int) == row_number_preview

                        if mask_preview.any():
                            if col_produtos and col_produtos in df_com_mes_preview.columns:
                                df_com_mes_preview.loc[mask_preview, col_produtos] = produto_preview

                            if col_valor and col_valor in df_com_mes_preview.columns:
                                df_com_mes_preview.loc[mask_preview, col_valor] = format_money(valor_preview)

                            # Garante que o card Comissão Jullia conte a quantidade digitada.
                            if "Quantidade de Pedigrees" not in df_com_mes_preview.columns:
                                df_com_mes_preview["Quantidade de Pedigrees"] = 1
                            df_com_mes_preview.loc[mask_preview, "Quantidade de Pedigrees"] = qtd_pedigrees_preview

                            if col_vendedor and col_vendedor in df_com_mes_preview.columns:
                                df_com_mes_preview.loc[mask_preview, col_vendedor] = normalize_text(row_edit_preview.get("Vendedor", "Jullia"))

                # Atualiza também o card lateral de Valor Total Vendido no Mês
                # usando exatamente a soma da coluna Valor depois da prévia/edição.
                # Assim, se uma linha for adicionada, alterada ou excluída da base,
                # o total fica sempre igual à soma dos valores exibidos.
                if selected_comm_month == mes_valor_cliente:
                    if col_valor and col_valor in df_com_mes_preview.columns and not df_com_mes_preview.empty:
                        valor_total_mes_preview = float(df_com_mes_preview[col_valor].apply(parse_money).sum())
                    else:
                        valor_total_mes_preview = 0.0
                    render_valor_total_mes_card(valor_total_mes_preview)

                render_card_comissao_jullia(df_com_mes_preview)

                if usar_marcacoes_dashboard:
                    st.info("Marque tudo primeiro e depois clique em Calcular prévia / salvar novas linhas. Linhas novas são gravadas sempre abaixo da última linha escrita.")
                else:
                    st.info("Mês histórico: clientes com mais de 1 pedigree podem ser corrigidos no dashboard e gravados direto na planilha.")
            else:
                render_card_comissao_jullia(df_com_mes_calculo_jullia)
                st.info("Nenhuma venda encontrada com os filtros selecionados.")

    else:
        st.warning("A aba Pedigree Comissão Ju está vazia ou não foi encontrada.")
