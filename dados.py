from io import BytesIO

import pandas as pd
import streamlit as st

from config import (
    COLIGADAS_SUPERUS,
    DROPBOX_DESPESA_REV02,
    DROPBOX_META_SUPERUS,
    DROPBOX_ONEPAGE_REV03,
    DROPBOX_PREVISTO_REV00_MOD,
    DROPBOX_PREVISTO_REV00_OTI,
    DROPBOX_PREVISTO_REV01_OTI,
    DROPBOX_REALIZADO,
    DROPBOX_REFINADO_ENGENHARIAS,
    DROPBOX_RESULTADO_2025,
)
from dropbox_io import download, token_e_rev, token_e_revs

MESES_COLUNA = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
MES_NUMERO = {nome: i + 1 for i, nome in enumerate(MESES_COLUNA)}
MESES_PT = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}

# Definição das linhas da DRE (rótulo, campo, destaque-de-subtotal) —
# compartilhada entre a página principal e o Forecast, pra manter a mesma
# tabela/estilo nos dois lugares.
LINHAS_DRE_DEF = [
    ("Receita Bruta", "receita_bruta", False),
    ("(-) Impostos", "imposto", False),
    ("(=) Receita Líquida", "receita_liquida", True),
    ("(-) Custo", "custo", False),
    ("(=) Lucro Bruto", "margem_bruta", True),
    ("(-) Despesas Administrativas", "despesa_adm", False),
    ("(=) EBITDA", "ebitda", True),
    ("(-) Despesa Financeira", "despesa_financeira", False),
    ("(=) LAIR", "lair", True),
    ("(-) Imposto de Renda", "imposto_renda", False),
    ("(=) Lucro Líquido", "lucro_liquido", True),
]

# Linhas de margem (%) exibidas logo abaixo de cada subtotal, igual à
# apresentação de referência (Margem Bruta %, Margem EBITDA %, Margem LAIR %).
LINHAS_MARGEM = {
    "margem_bruta": "Margem Bruta %",
    "ebitda": "Margem EBITDA %",
    "lair": "Margem LAIR %",
}

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


@st.cache_data(show_spinner="Lendo Realizado do Dropbox...")
def _ler_realizado(_token: str, cache_key: str) -> pd.DataFrame:
    content = download(_token, DROPBOX_REALIZADO)
    df = pd.read_excel(BytesIO(content), sheet_name="Planilha1", engine="calamine")
    df["Mes"] = df["Data"].values.astype("datetime64[M]")
    return df


def carregar_realizado() -> pd.DataFrame:
    token, rev = token_e_rev(DROPBOX_REALIZADO)
    return _ler_realizado(token, rev)


def carregar_realizado_superus() -> pd.DataFrame:
    df = carregar_realizado()
    return df[df["Coligada"].isin(COLIGADAS_SUPERUS)]


@st.cache_data(show_spinner="Lendo Realizado 2025 do Dropbox...")
def _ler_realizado_2025_mensal(_token: str, cache_key: str) -> pd.DataFrame:
    """DRE mensal 2025 (Jan-Dez) pronta — RESULTADOS 2025.xlsx, aba "Superus
    Moderado" (Realizado é igual em todos os Cenários dessa planilha, não
    varia — confirmado pelo usuário). Usada só pra comparação Real. 2026 x
    Real. 2025 na DRE Mês/Acumulado (app.py).

    As linhas de rótulo ficam na própria coluna ao lado do bloco mensal
    (não na coluna A, que é de outro bloco da aba) — índice de linha fixo,
    confirmado inspecionando o arquivo em 2026-10-20:
      2 Receita Bruta, 3 Impostos, 4 Receita Líquida, 5 Custo Total,
      6 Lucro Bruto, 8 Despesa Total, 9 Ebitda, 11 Outros Itens não
      Operacionais, 13 Despesa Financeira, 16 IRPJ/CSLL, 17 Lucro Líquido
    (linhas 7/10/15 são as de Margem %, puladas). "Outros Itens não
    Operacionais" entra somado dentro de despesa_financeira — a cascata
    desse app não tem uma linha própria pra isso (mesma simplificação do
    Realizado 2026, que também não discrimina Outros)."""
    content = download(_token, DROPBOX_RESULTADO_2025)
    df = pd.read_excel(BytesIO(content), sheet_name="Superus Moderado", engine="calamine", header=None)
    colunas = list(range(43, 55))
    meses = [pd.Timestamp(year=2025, month=m, day=1) for m in range(1, 13)]

    def _linha(indice: int) -> pd.Series:
        return pd.Series(df.iloc[indice, colunas].astype(float).values, index=meses)

    resultado = pd.DataFrame(
        {
            "receita_bruta": _linha(2),
            "imposto": _linha(3),
            "receita_liquida": _linha(4),
            "custo": _linha(5),
            "margem_bruta": _linha(6),
            "despesa_adm": _linha(8),
            "ebitda": _linha(9),
            "imposto_renda": _linha(16),
            "lucro_liquido": _linha(17),
        }
    )
    resultado["despesa_financeira"] = _linha(11) + _linha(13)
    resultado["lair"] = resultado["ebitda"] + resultado["despesa_financeira"]
    resultado.index.name = "Mes"
    return resultado


def carregar_realizado_2025_mensal() -> pd.DataFrame:
    token, rev = token_e_rev(DROPBOX_RESULTADO_2025)
    return _ler_realizado_2025_mensal(token, rev)


def dre_2025_periodo(mensal_2025: pd.DataFrame, mes_ini_2026, mes_fim_2026) -> dict | None:
    """Soma a DRE 2025 pronta no mesmo recorte de mês/ano (dia fixo em 1)
    do período 2026 informado — ex: mes_ini/fim 2026-01/2026-09 vira
    2025-01/2025-09. None se o recorte cair fora do que existe (não
    deveria acontecer, a aba tem o ano inteiro)."""
    mes_ini_2025 = pd.Timestamp(year=2025, month=pd.Timestamp(mes_ini_2026).month, day=1)
    mes_fim_2025 = pd.Timestamp(year=2025, month=pd.Timestamp(mes_fim_2026).month, day=1)
    sub = mensal_2025[(mensal_2025.index >= mes_ini_2025) & (mensal_2025.index <= mes_fim_2025)]
    if sub.empty:
        return None
    return sub.sum().to_dict()


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


def _ler_previsto_rev00(content: bytes, sheet_name: str, cenario: str) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content), sheet_name=sheet_name, engine="calamine")
    df = df.rename(columns={"Unnamed: 0": "Codigo", "Cód. Centro de custo": "CC"})
    for mes in MESES_COLUNA:
        df[mes] = pd.to_numeric(df[mes], errors="coerce").fillna(0)
    df["Cenário"] = cenario
    df["Revisão"] = "REV00"
    longo = df.melt(
        id_vars=["Codigo", "Coligada", "CC", "Centro de Custo", "Cenário", "Revisão"],
        value_vars=MESES_COLUNA,
        var_name="MesNome",
        value_name="Valor",
    )
    longo["Mes"] = longo["MesNome"].map(MES_NUMERO).apply(lambda m: pd.Timestamp(year=2026, month=m, day=1))
    return longo[["Codigo", "Coligada", "CC", "Centro de Custo", "Cenário", "Revisão", "Mes", "Valor"]]


def _ler_previsto_rev01(content: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content), sheet_name="BASE_PREVISTO", engine="calamine")
    df = df.rename(columns={"Cód. Centro de custo": "CC"})
    df["Codigo"] = df["Fato Contábil"].map(_FATO_CONTABIL_PARA_CODIGO_REV01)
    df["Cenário"] = "Otimista"
    df["Revisão"] = "REV01"
    for mes in MESES_COLUNA:
        df[mes] = pd.to_numeric(df[mes], errors="coerce").fillna(0)
    longo = df.melt(
        id_vars=["Codigo", "Coligada", "CC", "Centro de Custo", "Cenário", "Revisão"],
        value_vars=MESES_COLUNA,
        var_name="MesNome",
        value_name="Valor",
    )
    longo["Mes"] = longo["MesNome"].map(MES_NUMERO).apply(lambda m: pd.Timestamp(year=2026, month=m, day=1))
    return longo[["Codigo", "Coligada", "CC", "Centro de Custo", "Cenário", "Revisão", "Mes", "Valor"]]


@st.cache_data(show_spinner="Lendo Previsto do Dropbox...")
def _ler_previsto(_token: str, cache_key: str) -> pd.DataFrame:
    partes = [
        _ler_previsto_rev00(download(_token, DROPBOX_PREVISTO_REV00_MOD), "BASE_MOD", "Moderado"),
        _ler_previsto_rev00(download(_token, DROPBOX_PREVISTO_REV00_OTI), "BASE_OTIM", "Otimista"),
        _ler_previsto_rev01(download(_token, DROPBOX_PREVISTO_REV01_OTI)),
    ]
    return pd.concat(partes, ignore_index=True)


def carregar_previsto() -> pd.DataFrame:
    """Previsto da Superus (ACPL + Superus Holding + Superus Engenharia) —
    só REV00 (Moderado/Otimista) e REV01 (só Otimista) têm a cascata
    completa até Lucro Líquido. REV02/REV03 ainda não têm uma fonte
    equivalente (ver nota em config.py) — não incluídas aqui ainda."""
    token, rev = token_e_revs([DROPBOX_PREVISTO_REV00_MOD, DROPBOX_PREVISTO_REV00_OTI, DROPBOX_PREVISTO_REV01_OTI])
    return _ler_previsto(token, rev)


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


# "Dados Refinado" (REFINADO ENGENHARIAS 2026 - BI BRANCO OFICIAL.xlsx) —
# fonte transacional com REV00-REV03, mas que só alcança Margem Bruta:
# nenhuma Revisão aí tem Despesa Administrativa/Financeira (confirmado
# inspecionando o arquivo em 2026-10-14). Fórmula de Receita/Imposto/Custo
# replicada do DASH_DIRETORIA (mesma fonte, já reconciliada lá): o pacote
# "TOTAL" de cada um ignora a linha paralela "VENDAS"; Custo nunca usa a
# linha "CUSTO TOTAL " (não auditável — soma as 7 categorias granulares
# em vez disso). Aqui os totais vêm positivos — precisa negar Imposto/Custo.
REVISOES_REFINADO = ["REV00", "REV01", "REV02", "REV03"]
LINHAS_CUSTO_REFINADO = [
    "CUSTO COM INSUMOS",
    "CUSTO COM MAO DE OBRA",
    "CUSTO DE INDENIZAÇÃO",
    "CUSTO VENDAS",
    "CUSTOS CPC",
    "Depreciação de ativo (+)",
    "LOCAÇÃO DE EQUIPAMENTOS",
]


@st.cache_data(show_spinner="Baixando Refinado Engenharias do Dropbox (arquivo grande)...")
def _baixar_refinado_bytes(_token: str, cache_key: str) -> bytes:
    # Cache à parte só do download (arquivo de ~74MB) — compartilhado entre
    # carregar_refinado_detalhado e tabela_dimensao_centro_de_custo, que lêem
    # abas diferentes do MESMO arquivo; sem isso, baixaria o arquivo inteiro
    # duas vezes toda vez que a rev mudar.
    return download(_token, DROPBOX_REFINADO_ENGENHARIAS)


@st.cache_data(show_spinner="Lendo Refinado Engenharias (REV00-REV03)...")
def _ler_refinado_detalhado(_token: str, cache_key: str) -> pd.DataFrame:
    content = _baixar_refinado_bytes(_token, cache_key)
    df = pd.read_excel(
        BytesIO(content),
        sheet_name="Dados Refinado",
        engine="calamine",
        usecols=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        names=["Classificacao", "Revisao", "CC", "Complexo", "Area", "Gerencia", "Cenario", "Analise", "Mes", "Valor"],
        header=0,
    )
    return df[df["Revisao"].isin(REVISOES_REFINADO)]


def carregar_refinado_detalhado() -> pd.DataFrame:
    """Fonte bruta (uma linha por Revisão/Cenário/Mês/Centro de Custo/
    Análise) da base Refinado Engenharias — preserva o Centro de Custo,
    ao contrário de carregar_previsto_refinado() (que agrega direto pro
    total da DRE). Usada pra Análise de Complexos e quebras por Categoria
    nas Revisões REV02/REV03: o df_previsto "antigo" só tem CC-level pra
    REV00/REV01 (ex: só 29 Centro de Custo de Receita na REV01, contra 57
    no Realizado); essa fonte cobre as 4 Revisões com granularidade de CC
    (ex: 57 Centro de Custo de Receita na REV03, batendo com o Realizado)."""
    token, rev = token_e_rev(DROPBOX_REFINADO_ENGENHARIAS)
    return _ler_refinado_detalhado(token, rev)


ANALISES_RECEITA_REFINADO = ["RECEITA TOTAL BRUTA", "RECEITA VENDAS"]
ANALISES_IMPOSTO_REFINADO = ["TOTAL DE IMPOSTOS", "IMPOSTO VENDAS"]


def _por_cc_refinado(df_detalhado: pd.DataFrame, analises: list[str], revisao: str, cenario: str, mes_ini, mes_fim, negar: bool) -> pd.Series:
    sub = df_detalhado[
        (df_detalhado["Revisao"] == revisao)
        & (df_detalhado["Cenario"] == cenario)
        & (df_detalhado["Analise"].isin(analises))
        & (df_detalhado["Mes"] >= mes_ini)
        & (df_detalhado["Mes"] <= mes_fim)
    ]
    serie = sub.groupby("CC")["Valor"].sum()
    return -serie if negar else serie


def receita_por_cc_refinado(df_detalhado: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series:
    return _por_cc_refinado(df_detalhado, ANALISES_RECEITA_REFINADO, revisao, cenario, mes_ini, mes_fim, negar=False)


def custo_por_cc_refinado(df_detalhado: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series:
    return _por_cc_refinado(df_detalhado, LINHAS_CUSTO_REFINADO, revisao, cenario, mes_ini, mes_fim, negar=True)


def imposto_por_cc_refinado(df_detalhado: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series:
    return _por_cc_refinado(df_detalhado, ANALISES_IMPOSTO_REFINADO, revisao, cenario, mes_ini, mes_fim, negar=True)


@st.cache_data(show_spinner="Lendo tabela dimensão de Centro de Custo...")
def _ler_tabela_dimensao(_token: str, cache_key: str) -> pd.DataFrame:
    content = _baixar_refinado_bytes(_token, cache_key)
    df = pd.read_excel(BytesIO(content), sheet_name="Tabelas dimensão", engine="calamine", header=0)
    sub = df[["Cod. Centro de Custo", "Centro de Custo"]].copy()
    sub.columns = ["Codigo", "Centro de Custo"]
    sub = sub.dropna(subset=["Codigo"])
    sub["Codigo"] = sub["Codigo"].astype(str)
    return sub.drop_duplicates(subset="Codigo", keep="first").reset_index(drop=True)


def tabela_dimensao_centro_de_custo() -> pd.DataFrame:
    """Código <-> Nome de Centro de Custo, extraído da aba 'Tabelas
    dimensão' do Refinado Engenharias — fonte canônica de nome pra
    qualquer CC (Análise de Complexos etc.), já que nem Realizado nem
    Previsto cobrem sozinhos todo Centro de Custo conhecido."""
    token, rev = token_e_rev(DROPBOX_REFINADO_ENGENHARIAS)
    return _ler_tabela_dimensao(token, rev)


@st.cache_data(show_spinner="Calculando Refinado Engenharias agregado...")
def carregar_previsto_refinado() -> pd.DataFrame:
    df = carregar_refinado_detalhado()
    pivot = df.pivot_table(
        index=["Revisao", "Cenario", "Mes"], columns="Analise", values="Valor", aggfunc="sum", fill_value=0
    ).reset_index()

    def _col(nome: str):
        return pivot[nome] if nome in pivot.columns else 0

    resultado = pd.DataFrame(
        {
            "Revisão": pivot["Revisao"],
            "Cenário": pivot["Cenario"],
            "Mes": pivot["Mes"],
            "receita_bruta": _col("RECEITA TOTAL BRUTA") + _col("RECEITA VENDAS"),
            "imposto": -(_col("TOTAL DE IMPOSTOS") + _col("IMPOSTO VENDAS")),
            "custo": -sum(_col(c) for c in LINHAS_CUSTO_REFINADO),
        }
    )
    resultado["receita_liquida"] = resultado["receita_bruta"] + resultado["imposto"]
    resultado["margem_bruta"] = resultado["receita_liquida"] + resultado["custo"]
    return resultado


def calcular_previsto_refinado(df_refinado: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> dict | None:
    sub = df_refinado[
        (df_refinado["Revisão"] == revisao)
        & (df_refinado["Cenário"] == cenario)
        & (df_refinado["Mes"] >= mes_ini)
        & (df_refinado["Mes"] <= mes_fim)
    ]
    if sub.empty:
        return None
    return {
        "receita_bruta": sub["receita_bruta"].sum(),
        "imposto": sub["imposto"].sum(),
        "receita_liquida": sub["receita_liquida"].sum(),
        "custo": sub["custo"].sum(),
        "margem_bruta": sub["margem_bruta"].sum(),
    }


# Rótulos iguais aos 4 usados na apresentação de referência (pág. 12:
# OPERAÇÃO/COMERCIAL/ADMINISTRAÇÃO/PLR) — "PLR" não tem código/nível
# próprio, nem no Orçado (DESPESA REV02/REV03.xlsx, ver mais abaixo) nem
# no Realizado (onde o usuário renomeou os Centro de Custo dedicados a
# PLR pra começar com "PLR ", ver _marcar_plr_pelo_nome em
# analise_categoria.py — 2026-10-20).
CATEGORIA_DESPESA_ADMINISTRATIVO = "Despesa - Administrativo"
CATEGORIA_DESPESA_COMERCIAL = "Despesa - Comercial"
CATEGORIA_DESPESA_OPERACAO = "Despesa - Operação"
CATEGORIA_DESPESA_PLR = "PLR"

# Linhas "- PLR" da REV02 (aba DESPESA) — tiradas de dentro de Operação e
# Comercial pra virar a 4ª categoria, igual à apresentação de referência.
# "FILIAL PARÁ - PLR PJ" fica DE FORA desse grupo (vai pra Operação, não
# PLR) — conferido batendo valor a valor contra a apresentação de
# referência (pág. 12): com ela dentro, Operação Orçado Mês dava 504.328
# em vez dos 526.906 da referência, e PLR dava 158.148 em vez de 135.570
# — a diferença (22.578) bate exatamente com o valor dessa linha.
LINHAS_PLR_REV02 = {"DOP - PLR", "PLANEJAMENTO - PLR PJ", "SSMA - PLR PJ", "COMERCIAL - PLR"}
LINHAS_OPERACAO_REV02 = {
    "DOP", "ENGENHARIA", "PLANEJAMENTO - MDO", "PLANEJAMENTO - INSUMOS", "SSMA - INSUMOS",
    "SSMA - MDO", "SUPRIMENTOS", "GESTORES TRAINEES", "FILIAL PARÁ", "FILIAL PARÁ - PLR PJ",
}
LINHAS_COMERCIAL_REV02 = {"COMERCIAL"}
LINHAS_ADMINISTRATIVO_REV02 = {"DESPESA - O&S"}


@st.cache_data(show_spinner="Lendo Despesa REV02 do Dropbox...")
def _ler_despesa_por_categoria_rev02_mensal(_token: str, cache_key: str) -> pd.DataFrame:
    content = download(_token, DROPBOX_DESPESA_REV02)
    df = pd.read_excel(BytesIO(content), sheet_name="DESPESA", engine="calamine")

    def _soma(linhas: set[str], coluna: str) -> float:
        return df.loc[df["CENTRO DE CUSTO"].isin(linhas), coluna].sum()

    linhas_por_mes = {}
    for nome, numero in MESES_NOME_REV02.items():
        if nome not in df.columns:
            continue
        mes = pd.Timestamp(year=2026, month=numero, day=1)
        linhas_por_mes[mes] = {
            CATEGORIA_DESPESA_ADMINISTRATIVO: _soma(LINHAS_ADMINISTRATIVO_REV02, nome),
            CATEGORIA_DESPESA_COMERCIAL: _soma(LINHAS_COMERCIAL_REV02, nome),
            CATEGORIA_DESPESA_OPERACAO: _soma(LINHAS_OPERACAO_REV02, nome),
            CATEGORIA_DESPESA_PLR: _soma(LINHAS_PLR_REV02, nome),
        }
    return pd.DataFrame.from_dict(linhas_por_mes, orient="index")


def despesa_por_categoria_rev02_mensal() -> pd.DataFrame:
    """Administrativo ('DESPESA - O&S') / Comercial / Operação / PLR da
    REV02, por categoria, mês a mês — só tem Jul-Dez/26 (período coberto
    pelo arquivo). PLR reúne todas as linhas "- PLR" (de Operação e
    Comercial), igual à apresentação de referência. Indexado por Mes, uma
    coluna por categoria — granularidade mensal pra permitir espelhar o
    Realizado mês a mês fora da janela de previsão da Revisão (ver
    MESES_SUBSTITUIR_POR_REV / _por_categoria_com_mes_corte)."""
    token, rev = token_e_rev(DROPBOX_DESPESA_REV02)
    return _ler_despesa_por_categoria_rev02_mensal(token, rev)


# Despesa própria da REV03 — ONEPAGE_REV03.xlsx, aba "Dados Refinado"
# (mesmo arquivo que o DASH_DIRETORIA já usa; abandonamos o DESPESA
# REV03.xlsx em 2026-10-20 depois que o usuário conferiu que a Despesa
# Administrativa de lá batia errado — essa aba é a fonte de verdade,
# confirmado batendo R$ 2.059.976,64 de Despesa Administrativa de Out/26
# linha a linha com o usuário). "Análise de emissão" = "DESPESA
# ADMINISTRATIVA" vem por Centro de Custo (17 linhas, uma por
# departamento) com a própria coluna "Área" já separando Operação/
# Comercial/Administrativo — não precisa mais de um De-Para hardcoded de
# nome de Centro de Custo. "DESPESA FINANCEIRA" vem um valor só por mês
# (sem Centro de Custo). Só tem REV03 (Moderado e Otimista idênticos,
# confirmado com o usuário) e só Out-Dez/26 (janela que a REV03 prevê de
# verdade). Imposto de Renda continua sem fonte própria pra REV03 — segue
# emprestado da REV01.
ANALISE_DESPESA_ADM_REV03 = "DESPESA ADMINISTRATIVA"
ANALISE_DESPESA_FINANCEIRA_REV03 = "DESPESA FINANCEIRA"
CENARIO_PADRAO_REV03 = "Otimista"
AREA_PARA_CATEGORIA_REV03 = {
    "OPERAÇÕES": CATEGORIA_DESPESA_OPERACAO,
    "COMERCIAL": CATEGORIA_DESPESA_COMERCIAL,
    "ADMINISTRATIVO": CATEGORIA_DESPESA_ADMINISTRATIVO,
}


@st.cache_data(show_spinner="Lendo ONEPAGE REV03 do Dropbox...")
def _ler_onepage_rev03_detalhado(_token: str, cache_key: str) -> pd.DataFrame:
    content = download(_token, DROPBOX_ONEPAGE_REV03)
    df = pd.read_excel(BytesIO(content), sheet_name="Dados Refinado", engine="calamine")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={"Análise de emissão": "Analise", "Atributo": "Mes", "Área": "Area"})
    df = df[(df["Revisão"] == "REV03") & (df["Analise"].isin([ANALISE_DESPESA_ADM_REV03, ANALISE_DESPESA_FINANCEIRA_REV03]))]
    df["Mes"] = pd.to_datetime(df["Mes"]).values.astype("datetime64[M]")
    return df


def carregar_onepage_rev03_detalhado() -> pd.DataFrame:
    """Uma linha por Centro de Custo/Análise/Mês/Cenário — só a Despesa
    (Administrativa + Financeira) da REV03; Receita/Custo/Imposto dessa
    Revisão continuam vindo do Refinado Engenharias, sem mudança."""
    token, rev = token_e_rev(DROPBOX_ONEPAGE_REV03)
    return _ler_onepage_rev03_detalhado(token, rev)


def despesa_por_categoria_rev03_mensal() -> pd.DataFrame:
    """Operação/Comercial/Administrativo/PLR da REV03, por categoria, mês
    a mês — só tem Out-Dez/26 (período coberto pela fonte). PLR reúne
    todo Centro de Custo com "PLR" no nome (de Operação e Comercial),
    igual à apresentação de referência e ao mesmo critério já usado na
    REV02. Moderado e Otimista são idênticos pra Despesa (confirmado com o
    usuário) — filtra só Otimista antes de somar, pra não contar o mesmo
    Centro de Custo em dobro (um por Cenário)."""
    df = carregar_onepage_rev03_detalhado()
    sub = df[(df["Analise"] == ANALISE_DESPESA_ADM_REV03) & (df["Cenário"] == CENARIO_PADRAO_REV03)].copy()
    eh_plr = sub["CC"].astype(str).str.upper().str.contains("PLR")
    sub["Categoria"] = sub["Area"].map(AREA_PARA_CATEGORIA_REV03).fillna(CATEGORIA_DESPESA_ADMINISTRATIVO)
    sub.loc[eh_plr, "Categoria"] = CATEGORIA_DESPESA_PLR
    # ONEPAGE_REV03 guarda Despesa em positivo (confirmado pelo usuário,
    # 2026-10-21) — o resto da cascata (calcular_previsto, REV02) espera
    # Despesa negativa (ebitda = margem_bruta + despesa_adm). Força negativo
    # aqui independente do sinal de origem.
    sub["Valor"] = -sub["Valor"].abs()
    return sub.groupby(["Mes", "Categoria"])["Valor"].sum().unstack(fill_value=0.0)


def despesa_financeira_rev03_mensal() -> pd.Series:
    """Despesa Financeira própria da REV03, mês a mês — só Out-Dez/26."""
    df = carregar_onepage_rev03_detalhado()
    sub = df[(df["Analise"] == ANALISE_DESPESA_FINANCEIRA_REV03) & (df["Cenário"] == CENARIO_PADRAO_REV03)].copy()
    sub["Valor"] = -sub["Valor"].abs()
    return sub.groupby("Mes")["Valor"].sum()


def _serie_mensal_previsto(df_previsto: pd.DataFrame, revisao: str, cenario: str, codigo: int) -> pd.Series:
    sub = df_previsto[
        (df_previsto["Revisão"] == revisao) & (df_previsto["Cenário"] == cenario) & (df_previsto["Codigo"] == codigo)
    ]
    return sub.groupby("Mes")["Valor"].sum()


# Despesa própria da REV02 (DESPESA REV02.xlsx, adicionada pelo usuário em
# 2026-10-20) — aba "DESPESA", já vem com subtotais prontos: "DESPESA -
# O&S" = rateio da holding = 100% Despesa Administrativa (confirmado com
# o usuário); "COMERCIAL"+"COMERCIAL - PLR" = Despesa Comercial (ainda
# não discriminada por departamento, ok); "TOTAL - OPERAÇÃO" = Despesa
# Operação. Pra DRE principal só precisamos do total mesmo (as 3 somadas
# = linha "DESPESA TOTAL", que já vem pronta no arquivo). Só cobre
# Jul-Dez-26 — exatamente os meses que a REV02 prevê de verdade
# (MESES_SUBSTITUIR_POR_REV, igual ao DASH_DIRETORIA).
MESES_NOME_REV02 = {"JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}


@st.cache_data(show_spinner="Lendo Despesa REV02 do Dropbox...")
def _ler_despesa_rev02_mensal(_token: str, cache_key: str) -> pd.Series:
    content = download(_token, DROPBOX_DESPESA_REV02)
    df = pd.read_excel(BytesIO(content), sheet_name="DESPESA", engine="calamine")
    linha = df.loc[df["CENTRO DE CUSTO"] == "DESPESA TOTAL"]
    return pd.Series(
        {pd.Timestamp(year=2026, month=numero, day=1): linha[nome].sum() for nome, numero in MESES_NOME_REV02.items() if nome in linha.columns}
    )


def carregar_despesa_rev02_mensal() -> pd.Series:
    """'DESPESA TOTAL' (Administrativa+Comercial+Operação já somadas) por
    mês — só Jul-Dez-26. Vale pros dois Cenários (mesma convenção da
    REV03, confirmada com o usuário)."""
    token, rev = token_e_rev(DROPBOX_DESPESA_REV02)
    return _ler_despesa_rev02_mensal(token, rev)


def _despesa_total_mensal_rev03() -> pd.Series:
    """Despesa Administrativa total (Operação+Comercial+Administrativo+PLR
    juntos) da REV03, mês a mês — direto do ONEPAGE_REV03.xlsx, já soma
    todos os Centro de Custo de "DESPESA ADMINISTRATIVA" (17 linhas por
    mês). Não precisa mais de nada emprestado da REV01 pra essa parte."""
    df = despesa_por_categoria_rev03_mensal()
    return df.sum(axis=1)


# Quantos meses iniciais do ano cada Revisão NÃO prevê de verdade (porque
# já tinham acontecido quando a revisão foi fechada) — mesmo esquema do
# DASH_DIRETORIA (confirmado pelo usuário): REV00 prevê o ano inteiro;
# cada revisão seguinte "perde" um trimestre pro realizado. O corte é por
# REVISÃO, não por "o mês já fechou" — senão um mês dentro da própria
# janela de previsão da revisão (ex: Jul/Ago na REV02) ficaria sempre com
# Δ=0, escondendo a variação real que é o ponto inteiro de orçar.
MESES_SUBSTITUIR_POR_REV = {"REV00": 0, "REV01": 3, "REV02": 6, "REV03": 9}


def mes_corte_revisao(revisao: str, ano: int) -> pd.Timestamp:
    """Primeiro mês do ano que a Revisão já previa de verdade (ver
    MESES_SUBSTITUIR_POR_REV) — meses antes desse corte espelham o
    Realizado (Δ=0), meses a partir dele usam a fonte de Orçado própria da
    Revisão."""
    meses_substituidos = MESES_SUBSTITUIR_POR_REV.get(revisao, 0)
    if meses_substituidos < 12:
        return pd.Timestamp(year=ano, month=meses_substituidos + 1, day=1)
    return pd.Timestamp(year=ano + 1, month=1, day=1)


def revisao_vigente_no_mes(mes: int, revisoes_disponiveis: list[str]) -> str:
    """Revisão cuja janela de previsão (MESES_SUBSTITUIR_POR_REV) já cobria
    esse mês quando ele ainda era forecast — Jul-Set/26 -> REV02, Out-Dez/26
    -> REV03, etc. Usada pra abrir o app já com a Revisão certa
    pré-selecionada pro mês padrão (último Realizado fechado), em vez de
    sempre a mais recente — pedido do usuário, 2026-10-21: "o app já deve
    abrir pronto pra ser consumido"."""
    candidatas = [r for r in revisoes_disponiveis if MESES_SUBSTITUIR_POR_REV.get(r, 0) + 1 <= mes]
    if not candidatas:
        return min(revisoes_disponiveis, key=lambda r: MESES_SUBSTITUIR_POR_REV.get(r, 0))
    return max(candidatas, key=lambda r: MESES_SUBSTITUIR_POR_REV.get(r, 0))


def _despesa_mensal_com_fonte_nova(
    df_real: pd.DataFrame,
    df_previsto: pd.DataFrame,
    revisao: str,
    cenario: str,
    mes_ini,
    mes_fim,
    despesa_adm_mensal_nova: pd.Series,
    despesa_financeira_mensal_nova: pd.Series | None = None,
) -> dict:
    """Despesa Administrativa/Financeira/IR, mês a mês: meses anteriores à
    janela de previsão da Revisão (MESES_SUBSTITUIR_POR_REV) espelham o
    próprio Realizado (a revisão não tinha orçado pra eles — já tinham
    acontecido); meses dentro da janela usam `despesa_adm_mensal_nova` pra
    Despesa Administrativa, mesmo que já tenham Realizado (é exatamente
    aí que queremos ver o Real x Orç. de verdade). Despesa Financeira usa
    `despesa_financeira_mensal_nova` quando informada (REV03, fonte
    própria no ONEPAGE_REV03.xlsx); senão (REV02, ainda sem fonte própria)
    segue emprestada da REV01. Imposto de Renda segue 100% emprestado da
    REV01 pras duas, sem fonte própria ainda."""
    mes_corte = mes_corte_revisao(revisao, pd.Timestamp(mes_fim).year)

    financeira_rev01 = _serie_mensal_previsto(df_previsto, "REV01", cenario, CODIGO_DESPESA_FINANCEIRA)
    ir_rev01 = _serie_mensal_previsto(df_previsto, "REV01", cenario, CODIGO_IMPOSTO_RENDA)

    despesa_adm = despesa_financeira = imposto_renda = 0.0
    algum_mes_provisorio = False
    for mes in pd.date_range(mes_ini, mes_fim, freq="MS"):
        if mes < mes_corte:
            dre_mes = calcular_dre(df_real[df_real["Mes"] == mes])
            despesa_adm += dre_mes["despesa_adm"]
            despesa_financeira += dre_mes["despesa_financeira"]
            imposto_renda += dre_mes["imposto_renda"]
            continue
        despesa_adm += despesa_adm_mensal_nova.get(mes, 0.0)
        if despesa_financeira_mensal_nova is not None:
            despesa_financeira += despesa_financeira_mensal_nova.get(mes, 0.0)
        else:
            despesa_financeira += financeira_rev01.get(mes, 0.0)
        imposto_renda += ir_rev01.get(mes, 0.0)
        algum_mes_provisorio = True

    return {
        "despesa_adm": despesa_adm,
        "despesa_financeira": despesa_financeira,
        "imposto_renda": imposto_renda,
        "provisorio": algum_mes_provisorio,
    }


def calcular_previsto_com_fallback_despesa(
    df_previsto: pd.DataFrame,
    df_refinado: pd.DataFrame,
    revisao: str,
    cenario: str,
    mes_ini,
    mes_fim,
    df_real: pd.DataFrame | None = None,
) -> tuple[dict | None, bool]:
    """Retorna (totais, despesa_e_provisoria).

    REV00/REV01 usam a cascata cheia normal (já têm Despesa própria). REV02
    e REV03 usam a Despesa própria (DESPESA REV02.xlsx/DESPESA REV03.xlsx)
    combinada mês a mês com o Realizado pros meses já fechados — ver
    _despesa_mensal_com_fonte_nova. Despesa Financeira/Imposto de Renda
    seguem emprestados da REV01 pros dois (nenhuma das duas tem fonte
    própria pra isso ainda).
    """
    if revisao in ("REV00", "REV01"):
        sub = df_previsto[
            (df_previsto["Revisão"] == revisao) & (df_previsto["Mes"] >= mes_ini) & (df_previsto["Mes"] <= mes_fim)
        ]
        return calcular_previsto(sub, cenario), False

    base = calcular_previsto_refinado(df_refinado, revisao, cenario, mes_ini, mes_fim)
    if base is None:
        return None, False

    if revisao == "REV03" and df_real is not None:
        fonte_nova = _despesa_total_mensal_rev03()
        fonte_financeira_nova = despesa_financeira_rev03_mensal()
        despesa = _despesa_mensal_com_fonte_nova(
            df_real, df_previsto, revisao, cenario, mes_ini, mes_fim, fonte_nova, fonte_financeira_nova
        )
        provisorio = despesa["provisorio"]
    elif revisao == "REV02" and df_real is not None:
        fonte_nova = carregar_despesa_rev02_mensal()
        despesa = _despesa_mensal_com_fonte_nova(df_real, df_previsto, revisao, cenario, mes_ini, mes_fim, fonte_nova)
        provisorio = despesa["provisorio"]
    else:
        sub_rev01 = df_previsto[
            (df_previsto["Revisão"] == "REV01") & (df_previsto["Mes"] >= mes_ini) & (df_previsto["Mes"] <= mes_fim)
        ]
        despesa = calcular_previsto(sub_rev01, cenario)
        provisorio = True

    resultado = dict(base)
    resultado["despesa_adm"] = despesa.get("despesa_adm")
    resultado["ebitda"] = (
        base["margem_bruta"] + resultado["despesa_adm"] if resultado["despesa_adm"] is not None else None
    )
    resultado["despesa_financeira"] = despesa.get("despesa_financeira")
    resultado["lair"] = (
        resultado["ebitda"] + resultado["despesa_financeira"]
        if resultado["ebitda"] is not None and resultado["despesa_financeira"] is not None
        else None
    )
    resultado["imposto_renda"] = despesa.get("imposto_renda")
    resultado["lucro_liquido"] = (
        resultado["lair"] + resultado["imposto_renda"]
        if resultado["lair"] is not None and resultado["imposto_renda"] is not None
        else None
    )
    return resultado, provisorio


# Meta Ano Superus (META ANO SUPERUS.xlsx) — DRE anual alvo, valores em R$
# mil, uma aba por cenário. Linha->campo reconciliado com LINHAS_DRE_DEF:
# "Despesas Fixas" = despesa_adm; "Depreciação/Amortização" +
# "Receitas/Despesas Financeiras" somadas = despesa_financeira (nosso
# esquema não tem uma linha própria de EBIT/Depreciação entre EBITDA e
# LAIR, diferente do arquivo — essa soma bate exatamente com o LAIR do
# arquivo, conferido linha a linha em 2026-10-21). Só usado como
# comparativo na DRE do Forecast — nunca entra em nenhum cálculo.
_LINHA_META_POR_CAMPO = {
    "receita_bruta": "(+) Receita Bruta",
    "imposto": "(-) Imposto sobre Receita",
    "receita_liquida": "(=) Receita Líquida",
    "custo": "(-) Custos Variáveis",
    "margem_bruta": "(=) Lucro Bruto",
    "despesa_adm": "(-) Despesas Fixas",
    "ebitda": "(=) EBITDA",
    "lair": "(=) LAIR",
    "imposto_renda": "(-) IRPJ/CSLL",
    "lucro_liquido": "(=) Lucro Líquido",
}
_LINHA_META_DEPRECIACAO = "(-) Depreciação/ Amortização"
_LINHA_META_FINANCEIRA = "(+/-) Receitas/ Despesas Financeiras"


@st.cache_data(show_spinner="Lendo Meta Ano Superus do Dropbox...")
def _ler_meta_mensal(_token: str, cache_key: str, cenario: str) -> dict[int, dict]:
    content = download(_token, DROPBOX_META_SUPERUS)
    df = pd.read_excel(BytesIO(content), sheet_name=cenario, engine="calamine", header=None)
    rotulos = df[0].astype(str).str.strip()

    def _linha(rotulo: str) -> pd.Series:
        idx = rotulos[rotulos == rotulo].index
        if len(idx) == 0:
            return pd.Series([0.0] * 12)
        return df.loc[idx[0], 1:12].astype(float) * 1000

    campos = {campo: _linha(rotulo) for campo, rotulo in _LINHA_META_POR_CAMPO.items()}
    despesa_financeira = _linha(_LINHA_META_DEPRECIACAO) + _linha(_LINHA_META_FINANCEIRA)

    return {
        mes: {
            **{campo: serie.iloc[mes - 1] for campo, serie in campos.items()},
            "despesa_financeira": despesa_financeira.iloc[mes - 1],
        }
        for mes in range(1, 13)
    }


def carregar_meta_mensal(cenario: str = "Otimista") -> dict[int, dict]:
    """{mes_numero: {campo_dre: valor}} pro cenário pedido (aba do arquivo),
    valores já em R$ (convertidos de R$ mil)."""
    token, rev = token_e_rev(DROPBOX_META_SUPERUS)
    return _ler_meta_mensal(token, rev, cenario)
