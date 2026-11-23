"""Previsto da O&S (Coligada 11) — só REV00 (completa, aba DRE_DIN,
classificada por texto do "Fato Contábil") e REV02 (aba ConsolidadoPrevisto,
lista de despesas por tarefa, sem Receita/Custo/Despesa Financeira
discriminados). Não existe REV01/REV03 pra O&S. Portado do DASH_DIRETORIA
(mesma conta Dropbox, mesmos arquivos, mesmas regras já confirmadas pelo
usuário lá) — ver [[project_refinado_engenharias]] na memória do projeto.
Adicionado em 2026-11-24.

A O&S genuinamente não tem Imposto nem IRPJ/CSLL (confirmado pelo usuário,
sua Receita é inteiramente o rateio de despesa cobrado de ASAP/Superus) —
por isso esses dois campos aqui são SEMPRE 0.0 real, nunca None."""

import pandas as pd
import streamlit as st

from config import DROPBOX_OES_REV00_MOD, DROPBOX_OES_REV00_OTI, DROPBOX_OES_REV02_MOD, DROPBOX_OES_REV02_OTI
from dados import calcular_dre, mes_corte_revisao, normalizar_codigo_cc
from dropbox_io import download, token_e_revs
from io import BytesIO

CAMPOS_PREVISTO_OES = [
    "receita_bruta", "imposto", "receita_liquida", "custo", "margem_bruta",
    "despesa_adm", "ebitda", "despesa_financeira", "lair", "imposto_renda", "lucro_liquido",
]

MESES_OES_REV00 = {
    "Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
    "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12,
}
MESES_NOME_REV02_OES = {"jul/26": 7, "ago/26": 8, "set/26": 9, "out/26": 10, "nov/26": 11, "dez/26": 12}


def _categoria_rev00_oes(fato_contabil: str) -> str:
    """Classifica pelo PREFIXO do texto — "Receita Com..."/"Custo
    Serviço..."/"Despesa Financeira", senão é alguma variante de
    "Administrativas ..." (13º, Encargos, Insumos, MDO, Provisões) ->
    Despesa Administrativa. Confirmado por inspeção direta do arquivo,
    2026-11-24 (15 textos distintos, só essas 4 famílias)."""
    texto = str(fato_contabil)
    if texto.startswith("Receita"):
        return "receita_bruta"
    if texto.startswith("Custo"):
        return "custo"
    if texto.startswith("Despesa Financeira"):
        return "despesa_financeira"
    return "despesa_adm"


@st.cache_data(show_spinner="Lendo Previsto O&S REV00 do Dropbox...")
def _ler_rev00(_token: str, path: str, cache_key: str) -> pd.DataFrame:
    content = download(_token, path)
    df = pd.read_excel(BytesIO(content), sheet_name="DRE_DIN", engine="calamine")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=["Coligada"])
    df["Categoria"] = df["Fato Contábil"].map(_categoria_rev00_oes)
    if "Cód. Centro de custo" in df.columns:
        df["CC"] = df["Cód. Centro de custo"].map(normalizar_codigo_cc)
    linhas = []
    for nome_mes, numero in MESES_OES_REV00.items():
        if nome_mes not in df.columns:
            continue
        mes = pd.Timestamp(year=2026, month=numero, day=1)
        soma_por_categoria = df.groupby("Categoria")[nome_mes].sum()
        linhas.append({"Mes": mes, **soma_por_categoria.to_dict()})
    resultado = pd.DataFrame(linhas).set_index("Mes")
    for campo in ["receita_bruta", "custo", "despesa_financeira", "despesa_adm"]:
        if campo not in resultado.columns:
            resultado[campo] = 0.0
    return resultado


def carregar_previsto_oes_rev00(cenario: str) -> pd.DataFrame:
    """Uma linha por mês (Jan-Dez), colunas receita_bruta/custo/
    despesa_financeira/despesa_adm (R$, convenção dedução=negativo já na
    origem — confirmado, sem flip de sinal)."""
    path = DROPBOX_OES_REV00_MOD if cenario == "Moderado" else DROPBOX_OES_REV00_OTI
    token, rev = token_e_revs([path])
    return _ler_rev00(token, path, rev)


@st.cache_data(show_spinner="Lendo Previsto O&S REV02 do Dropbox...")
def _ler_rev02(_token: str, path: str, cache_key: str) -> pd.Series:
    content = download(_token, path)
    df = pd.read_excel(BytesIO(content), sheet_name="ConsolidadoPrevisto", engine="calamine", header=1)
    df.columns = [str(c).strip() for c in df.columns]
    valores = {}
    for nome_mes, numero in MESES_NOME_REV02_OES.items():
        if nome_mes not in df.columns:
            continue
        valores[pd.Timestamp(year=2026, month=numero, day=1)] = df[nome_mes].sum()
    return pd.Series(valores)


def carregar_previsto_oes_rev02(cenario: str) -> pd.Series:
    """Despesa Administrativa total (R$, magnitude positiva na origem) por
    mês, só Jul-Dez/26 — o resto da cascata (Receita espelhada, Custo/
    Despesa Financeira/Imposto/IRPJ zerados) é resolvido em
    calcular_previsto_oes_rev02_mes."""
    path = DROPBOX_OES_REV02_MOD if cenario == "Moderado" else DROPBOX_OES_REV02_OTI
    token, rev = token_e_revs([path])
    return _ler_rev02(token, path, rev)


def _previsto_oes_rev00_mes(df_rev00: pd.DataFrame, mes: pd.Timestamp) -> dict:
    if mes not in df_rev00.index:
        return dict.fromkeys(CAMPOS_PREVISTO_OES, 0.0)
    linha = df_rev00.loc[mes]
    receita_bruta = float(linha.get("receita_bruta", 0.0))
    custo = float(linha.get("custo", 0.0))
    despesa_adm = float(linha.get("despesa_adm", 0.0))
    despesa_financeira = float(linha.get("despesa_financeira", 0.0))
    receita_liquida = receita_bruta  # Imposto = 0 (O&S não tem)
    margem_bruta = receita_liquida + custo
    ebitda = margem_bruta + despesa_adm
    lair = ebitda + despesa_financeira
    return {
        "receita_bruta": receita_bruta, "imposto": 0.0, "receita_liquida": receita_liquida,
        "custo": custo, "margem_bruta": margem_bruta, "despesa_adm": despesa_adm, "ebitda": ebitda,
        "despesa_financeira": despesa_financeira, "lair": lair, "imposto_renda": 0.0, "lucro_liquido": lair,
    }


def _previsto_oes_rev02_mes(serie_despesa: pd.Series, mes: pd.Timestamp) -> dict:
    """REV02: só existe Despesa Administrativa de verdade (lista de tarefas)
    — Receita Bruta é SINTETIZADA como espelho exato dessa Despesa (mesmo
    valor, sinal positivo), Custo/Despesa Financeira ficam 0 — confirmado
    pelo usuário (mesmo padrão observado na REV00: Receita ≈ soma de todas
    as despesas). Resulta em Lucro Líquido ≈ 0, por desenho."""
    despesa_adm_magnitude = float(serie_despesa.get(mes, 0.0))
    despesa_adm = -despesa_adm_magnitude
    receita_bruta = despesa_adm_magnitude
    receita_liquida = receita_bruta
    custo = 0.0
    margem_bruta = receita_liquida + custo
    ebitda = margem_bruta + despesa_adm
    despesa_financeira = 0.0
    lair = ebitda + despesa_financeira
    return {
        "receita_bruta": receita_bruta, "imposto": 0.0, "receita_liquida": receita_liquida,
        "custo": custo, "margem_bruta": margem_bruta, "despesa_adm": despesa_adm, "ebitda": ebitda,
        "despesa_financeira": despesa_financeira, "lair": lair, "imposto_renda": 0.0, "lucro_liquido": lair,
    }


@st.cache_data(show_spinner=False)
def calcular_previsto_efetivo_oes(df_real_oes: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> dict | None:
    """Blend mês a mês, igual à ASAP (substitui Realizado em TODOS os campos
    antes do corte de previsão da Revisão). Só existe REV00/REV02 pra O&S —
    qualquer outra Revisão (REV01/REV03) retorna None inteiro, nunca
    espelha o Realizado sozinha (não existe "Orçado REV01/REV03 da O&S" pra
    comparar contra)."""
    if revisao not in ("REV00", "REV02"):
        return None

    ano = pd.Timestamp(mes_fim).year
    mes_corte = mes_corte_revisao(revisao, ano)

    if revisao == "REV00":
        df_rev00 = carregar_previsto_oes_rev00(cenario)
    else:
        serie_rev02 = carregar_previsto_oes_rev02(cenario)

    total = dict.fromkeys(CAMPOS_PREVISTO_OES, 0.0)
    for mes in pd.date_range(mes_ini, mes_fim, freq="MS"):
        if mes < mes_corte:
            dre_mes = calcular_dre(df_real_oes[df_real_oes["Mes"] == mes])
        elif revisao == "REV00":
            dre_mes = _previsto_oes_rev00_mes(df_rev00, mes)
        else:
            dre_mes = _previsto_oes_rev02_mes(serie_rev02, mes)
        for campo in CAMPOS_PREVISTO_OES:
            total[campo] += dre_mes[campo]
    return total
