import pandas as pd
import streamlit as st

from config import (
    ARQUIVO_PREVISTO_REV00_MOD,
    ARQUIVO_PREVISTO_REV00_OTI,
    ARQUIVO_PREVISTO_REV01_OTI,
    ARQUIVO_REALIZADO,
    COLIGADAS_SUPERUS,
)

MESES_COLUNA = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
MES_NUMERO = {nome: i + 1 for i, nome in enumerate(MESES_COLUNA)}
MESES_PT = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}

CAMPOS_DRE = [
    "receita_bruta",
    "imposto",
    "receita_liquida",
    "custo",
    "margem_bruta",
    "despesa_adm",
    "ebitda",
    "despesa_financeira",
    "lair",
    "imposto_renda",
    "lucro_liquido",
]

# Classificação Nível 1 do Realizado — mesmo esquema confirmado no
# DASH_DIRETORIA (1=Receita, 2=Imposto, 3=Custo, 5/6/7=Despesa
# Administrativa, 8=Outros não operacionais, 9=Despesa Financeira,
# 10=Imposto de Renda).
NIVEL_RECEITA_BRUTA = [1]
NIVEL_IMPOSTO = [2]
NIVEL_CUSTO = [3]
NIVEL_DESPESA_ADM = [5, 6, 7]
NIVEL_OUTROS = [8]
NIVEL_DESPESA_FINANCEIRA = [9]
NIVEL_IMPOSTO_RENDA = [10]


def _soma_nivel(df: pd.DataFrame, niveis: list[int]) -> float:
    return df.loc[df["Nível 1"].isin(niveis), "Valor"].sum()


def calcular_dre(df: pd.DataFrame) -> dict:
    receita_bruta = _soma_nivel(df, NIVEL_RECEITA_BRUTA)
    imposto = _soma_nivel(df, NIVEL_IMPOSTO)
    receita_liquida = receita_bruta + imposto
    custo = _soma_nivel(df, NIVEL_CUSTO)
    margem_bruta = receita_liquida + custo
    despesa_adm = _soma_nivel(df, NIVEL_DESPESA_ADM)
    ebitda = margem_bruta + despesa_adm
    outros = _soma_nivel(df, NIVEL_OUTROS)
    ebit = ebitda + outros
    despesa_financeira = _soma_nivel(df, NIVEL_DESPESA_FINANCEIRA)
    lair = ebit + despesa_financeira
    imposto_renda = _soma_nivel(df, NIVEL_IMPOSTO_RENDA)
    lucro_liquido = lair + imposto_renda
    return {
        "receita_bruta": receita_bruta,
        "imposto": imposto,
        "receita_liquida": receita_liquida,
        "custo": custo,
        "margem_bruta": margem_bruta,
        "despesa_adm": despesa_adm,
        "ebitda": ebitda,
        "despesa_financeira": despesa_financeira,
        "lair": lair,
        "imposto_renda": imposto_renda,
        "lucro_liquido": lucro_liquido,
    }


def calcular_dre_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for mes, grupo in df.groupby("Mes"):
        linha = calcular_dre(grupo)
        linha["Mes"] = mes
        linhas.append(linha)
    if not linhas:
        return pd.DataFrame(columns=CAMPOS_DRE + ["Mes"])
    return pd.DataFrame(linhas)


@st.cache_data(show_spinner="Lendo Realizado...")
def carregar_realizado() -> pd.DataFrame:
    df = pd.read_excel(ARQUIVO_REALIZADO, sheet_name="Planilha1", engine="calamine")
    df["Mes"] = df["Data"].values.astype("datetime64[M]")
    return df


def carregar_realizado_superus() -> pd.DataFrame:
    df = carregar_realizado()
    return df[df["Coligada"].isin(COLIGADAS_SUPERUS)]


# Esquema de códigos canônico da base refinada da Engenharia: 1=Receita
# Bruta, 2=Impostos, 3=Custo, 4=Comerciais, 5=Custo Fixo Operacional,
# 6=Administrativas/Gerais Insumos, 7=Depreciação/Amortização (4,5,6,7 juntos
# = Despesa Administrativa), 8=Despesa Financeira, 9=IRPJ/CSLL — confirmado
# junto com o usuário (mesmo esquema usado no DASH_DIRETORIA).
CODIGO_RECEITA_BRUTA = 1
CODIGO_IMPOSTO = 2
CODIGO_CUSTO = 3
CODIGOS_DESPESA_ADM = [4, 5, 6, 7]
CODIGO_DESPESA_FINANCEIRA = 8
CODIGO_IMPOSTO_RENDA = 9

# A REV01 (sheet BASE_PREVISTO do arquivo _OT_REV01) não tem a coluna de
# código numérico — classifica pelo texto do "Fato Contábil" em vez disso.
_FATO_CONTABIL_PARA_CODIGO_REV01 = {
    "Prestação de Serviços (ENG. ACESSO)": 1,
    "Impostos Sobre Prestação de Serviços (ENG. ACESSO)": 2,
    "Custo Serviço Prestado (ENG. ACESSO) OUTROS CUSTOS DIRETOS": 3,
    "Comerciais (ENG. ACESSO) MDO": 4,
    "Custo Fixo operacional (ENG. ACESSO) MDO": 5,
    "Gerais INSUMOS": 6,
    "Despesa Financeira": 8,
    "IRPJ/CSLL": 9,
}


def _ler_previsto_rev00(path, sheet_name: str, cenario: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet_name, engine="calamine")
    df = df.rename(columns={"Unnamed: 0": "Codigo", "Cód. Centro de custo": "CC"})
    for mes in MESES_COLUNA:
        df[mes] = pd.to_numeric(df[mes], errors="coerce").fillna(0)
    df["Cenário"] = cenario
    df["Revisão"] = "REV00"
    longo = df.melt(
        id_vars=["Codigo", "Coligada", "CC", "Cenário", "Revisão"],
        value_vars=MESES_COLUNA,
        var_name="MesNome",
        value_name="Valor",
    )
    longo["Mes"] = longo["MesNome"].map(MES_NUMERO).apply(lambda m: pd.Timestamp(year=2026, month=m, day=1))
    return longo[["Codigo", "Coligada", "CC", "Cenário", "Revisão", "Mes", "Valor"]]


def _ler_previsto_rev01(path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="BASE_PREVISTO", engine="calamine")
    df = df.rename(columns={"Cód. Centro de custo": "CC"})
    df["Codigo"] = df["Fato Contábil"].map(_FATO_CONTABIL_PARA_CODIGO_REV01)
    df["Cenário"] = "Otimista"
    df["Revisão"] = "REV01"
    for mes in MESES_COLUNA:
        df[mes] = pd.to_numeric(df[mes], errors="coerce").fillna(0)
    longo = df.melt(
        id_vars=["Codigo", "Coligada", "CC", "Cenário", "Revisão"],
        value_vars=MESES_COLUNA,
        var_name="MesNome",
        value_name="Valor",
    )
    longo["Mes"] = longo["MesNome"].map(MES_NUMERO).apply(lambda m: pd.Timestamp(year=2026, month=m, day=1))
    return longo[["Codigo", "Coligada", "CC", "Cenário", "Revisão", "Mes", "Valor"]]


@st.cache_data(show_spinner="Lendo Previsto...")
def carregar_previsto() -> pd.DataFrame:
    """Previsto da Superus (ACPL + Superus Holding + Superus Engenharia) —
    só REV00 (Moderado/Otimista) e REV01 (só Otimista) têm a cascata
    completa até Lucro Líquido. REV02/REV03 ainda não têm uma fonte
    equivalente (ver nota em config.py) — não incluídas aqui ainda."""
    partes = [
        _ler_previsto_rev00(ARQUIVO_PREVISTO_REV00_MOD, "BASE_MOD", "Moderado"),
        _ler_previsto_rev00(ARQUIVO_PREVISTO_REV00_OTI, "BASE_OTIM", "Otimista"),
        _ler_previsto_rev01(ARQUIVO_PREVISTO_REV01_OTI),
    ]
    return pd.concat(partes, ignore_index=True)


def calcular_previsto(df: pd.DataFrame, cenario: str) -> dict:
    sub = df[df["Cenário"] == cenario]

    def soma(codigos: int | list[int]) -> float:
        if isinstance(codigos, int):
            codigos = [codigos]
        return sub.loc[sub["Codigo"].isin(codigos), "Valor"].sum()

    def existe(codigos: int | list[int]) -> bool:
        if isinstance(codigos, int):
            codigos = [codigos]
        return bool(sub["Codigo"].isin(codigos).any())

    receita_bruta = soma(CODIGO_RECEITA_BRUTA)
    imposto = soma(CODIGO_IMPOSTO)
    receita_liquida = receita_bruta + imposto
    custo = soma(CODIGO_CUSTO)
    margem_bruta = receita_liquida + custo
    despesa_adm = soma(CODIGOS_DESPESA_ADM) if existe(CODIGOS_DESPESA_ADM) else None
    ebitda = margem_bruta + despesa_adm if despesa_adm is not None else None
    despesa_financeira = soma(CODIGO_DESPESA_FINANCEIRA) if existe(CODIGO_DESPESA_FINANCEIRA) else None
    lair = ebitda + despesa_financeira if ebitda is not None and despesa_financeira is not None else None
    imposto_renda = soma(CODIGO_IMPOSTO_RENDA) if existe(CODIGO_IMPOSTO_RENDA) else None
    lucro_liquido = lair + imposto_renda if lair is not None and imposto_renda is not None else None

    return {
        "receita_bruta": receita_bruta,
        "imposto": imposto,
        "receita_liquida": receita_liquida,
        "custo": custo,
        "margem_bruta": margem_bruta,
        "despesa_adm": despesa_adm,
        "ebitda": ebitda,
        "despesa_financeira": despesa_financeira,
        "lair": lair,
        "imposto_renda": imposto_renda,
        "lucro_liquido": lucro_liquido,
    }
