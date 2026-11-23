"""Previsto da ASAP (Coligada 14) — REV00/REV01 (BASE_PREVISTO, esquema de
código numérico nativo 1-7) e REV02 (DREDin, esquema diferente, remapeado
pro mesmo canônico abaixo). Portado do DASH_DIRETORIA (mesma conta Dropbox,
mesmos arquivos, mesmas regras já confirmadas pelo usuário lá) — ver
[[project_refinado_engenharias]] na memória do projeto. Adicionado em
2026-11-24, pedido do usuário ("crie outras três abas... uma para ASAP").

Ao contrário da Superus (REV02/REV03 fragmentam Receita/Custo de um lado —
Refinado Engenharias — e Despesa de outro — DESPESA REV02/ONEPAGE_REV03 —,
exigindo um "fallback" mês a mês entre fontes), cada arquivo da ASAP já tem
a cascata INTEIRA (Receita...Lucro Líquido) num só lugar — não precisa de
nenhum "calcular_previsto_com_fallback_despesa" equivalente aqui.

Código canônico (igual ao nativo de REV00/REV01, native em "Unnamed: 0" da
aba BASE_PREVISTO — confirmado por inspeção direta do arquivo, 2026-11-24):
1=Receita Bruta, 2=Impostos, 3=Custo, [4,5]=Despesa Administrativa (4=Despesas
Administrativas, 5=Depreciação/Amortização), 6=Despesa Financeira,
7=IRPJ/CSLL. Sinal: Receita positiva, resto já negativo (dedução=negativo) —
sem flip de sinal, igual ao REV00 da Engenharia."""

import pandas as pd
import streamlit as st

from config import (
    DROPBOX_ASAP_REV00_MOD,
    DROPBOX_ASAP_REV00_OTI,
    DROPBOX_ASAP_REV01_MOD,
    DROPBOX_ASAP_REV01_OTI,
    DROPBOX_ASAP_REV02_MOD,
    DROPBOX_ASAP_REV02_OTI,
)
from dados import MES_NUMERO, MESES_COLUNA, calcular_dre, mes_corte_revisao, normalizar_codigo_cc
from dropbox_io import download, token_e_revs
from io import BytesIO

CODIGO_RECEITA_BRUTA = 1
CODIGO_IMPOSTO = 2
CODIGO_CUSTO = 3
CODIGOS_DESPESA_ADM = [4, 5]
CODIGO_DESPESA_FINANCEIRA = 6
CODIGO_IMPOSTO_RENDA = 7

CAMPOS_PREVISTO_ASAP = [
    "receita_bruta", "imposto", "receita_liquida", "custo", "margem_bruta",
    "despesa_adm", "ebitda", "despesa_financeira", "lair", "imposto_renda", "lucro_liquido",
]


def _ler_rev00_rev01(content: bytes, revisao: str, cenario: str) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content), sheet_name="BASE_PREVISTO", engine="calamine")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={"Unnamed: 0": "Codigo", "Cód. Centro de custo": "CC"})
    df = df.dropna(subset=["Coligada"])
    df["CC"] = df["CC"].map(normalizar_codigo_cc)
    for mes in MESES_COLUNA:
        df[mes] = pd.to_numeric(df[mes], errors="coerce").fillna(0)
    df["Cenário"] = cenario
    df["Revisão"] = revisao
    longo = df.melt(
        id_vars=["Codigo", "CC", "Centro de Custo", "Cenário", "Revisão"],
        value_vars=MESES_COLUNA, var_name="MesNome", value_name="Valor",
    )
    longo["Mes"] = longo["MesNome"].map(MES_NUMERO).apply(lambda m: pd.Timestamp(year=2026, month=m, day=1))
    return longo[["Codigo", "CC", "Centro de Custo", "Cenário", "Revisão", "Mes", "Valor"]]


# REV02 (aba "DREDin") usa um esquema de código ORIGINAL diferente — Receita
# e Imposto dividem o código 1 (distinguidos só pelo texto "Imposto" no
# "Fato Contábil"); Custo = 3 (igual); Despesa Administrativa = 5 (inclui
# "Despesa Comercial" E "Despesas Administrativas" juntas, sem a distinção
# 4/5 do REV00/REV01 — não tem problema, as duas já iam pro mesmo balde
# canônico); Depreciação/Amortização = 6 (some junto à Despesa
# Administrativa, confirmado no DASH_DIRETORIA); Despesa Financeira = 7;
# IRPJ/CSLL = 8. Confirmado por inspeção direta do arquivo, 2026-11-24 —
# não é o mesmo mapeamento do REV00/REV01, remapeia pro canônico abaixo
# antes de concatenar.
_REV02_PARA_CANONICO = {3: CODIGO_CUSTO, 5: 4, 6: 5, 7: CODIGO_DESPESA_FINANCEIRA, 8: CODIGO_IMPOSTO_RENDA}


def _ler_rev02(content: bytes, cenario: str) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content), sheet_name="DREDin", engine="calamine")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={"Unnamed: 0": "CodigoOriginal", "Cód. Centro de custo": "CC"})
    # Algumas linhas do arquivo Otimista vêm com Coligada errada (15/16/19) —
    # instrução explícita do usuário (via DASH_DIRETORIA): considerar tudo
    # como Coligada 14 (ASAP), não filtrar fora.
    df = df.dropna(subset=["CodigoOriginal"])
    df["CC"] = df["CC"].map(normalizar_codigo_cc)

    eh_imposto = df["CodigoOriginal"].eq(1) & df["Fato Contábil"].astype(str).str.contains("Imposto", case=False, na=False)
    df["Codigo"] = df["CodigoOriginal"].map(_REV02_PARA_CANONICO)
    df.loc[df["CodigoOriginal"].eq(1) & ~eh_imposto, "Codigo"] = CODIGO_RECEITA_BRUTA
    df.loc[eh_imposto, "Codigo"] = CODIGO_IMPOSTO

    for mes in MESES_COLUNA:
        if mes not in df.columns:
            df[mes] = 0.0
        df[mes] = pd.to_numeric(df[mes], errors="coerce").fillna(0)
    df["Cenário"] = cenario
    df["Revisão"] = "REV02"
    longo = df.melt(
        id_vars=["Codigo", "CC", "Centro de Custo", "Cenário", "Revisão"],
        value_vars=MESES_COLUNA, var_name="MesNome", value_name="Valor",
    )
    longo["Mes"] = longo["MesNome"].map(MES_NUMERO).apply(lambda m: pd.Timestamp(year=2026, month=m, day=1))
    return longo[["Codigo", "CC", "Centro de Custo", "Cenário", "Revisão", "Mes", "Valor"]]


@st.cache_data(show_spinner="Lendo Previsto ASAP do Dropbox...")
def _ler_previsto_asap(_token: str, cache_key: str) -> pd.DataFrame:
    partes = [
        _ler_rev00_rev01(download(_token, DROPBOX_ASAP_REV00_MOD), "REV00", "Moderado"),
        _ler_rev00_rev01(download(_token, DROPBOX_ASAP_REV00_OTI), "REV00", "Otimista"),
        _ler_rev00_rev01(download(_token, DROPBOX_ASAP_REV01_MOD), "REV01", "Moderado"),
        _ler_rev00_rev01(download(_token, DROPBOX_ASAP_REV01_OTI), "REV01", "Otimista"),
        _ler_rev02(download(_token, DROPBOX_ASAP_REV02_MOD), "Moderado"),
        _ler_rev02(download(_token, DROPBOX_ASAP_REV02_OTI), "Otimista"),
    ]
    return pd.concat(partes, ignore_index=True)


def carregar_previsto_asap() -> pd.DataFrame:
    """Previsto da ASAP: REV00/REV01/REV02, Moderado e Otimista — todas com
    cascata completa até Lucro Líquido. Não existe REV03 pra ASAP ainda."""
    paths = [
        DROPBOX_ASAP_REV00_MOD, DROPBOX_ASAP_REV00_OTI, DROPBOX_ASAP_REV01_MOD,
        DROPBOX_ASAP_REV01_OTI, DROPBOX_ASAP_REV02_MOD, DROPBOX_ASAP_REV02_OTI,
    ]
    token, rev = token_e_revs(paths)
    return _ler_previsto_asap(token, rev)


@st.cache_data(show_spinner=False)
def calcular_previsto_asap(df: pd.DataFrame, cenario: str) -> dict:
    """Totais de um recorte (já filtrado por Revisão/mês) do Previsto ASAP —
    cascata sempre completa (todas as Revisões têm os 7 códigos), ao
    contrário da Superus; nunca retorna None por campo faltando."""
    sub = df[df["Cenário"] == cenario]

    def soma(codigos) -> float:
        codigos = [codigos] if isinstance(codigos, int) else codigos
        return sub.loc[sub["Codigo"].isin(codigos), "Valor"].sum()

    receita_bruta = soma(CODIGO_RECEITA_BRUTA)
    imposto = soma(CODIGO_IMPOSTO)
    receita_liquida = receita_bruta + imposto
    custo = soma(CODIGO_CUSTO)
    margem_bruta = receita_liquida + custo
    despesa_adm = soma(CODIGOS_DESPESA_ADM)
    ebitda = margem_bruta + despesa_adm
    despesa_financeira = soma(CODIGO_DESPESA_FINANCEIRA)
    lair = ebitda + despesa_financeira
    imposto_renda = soma(CODIGO_IMPOSTO_RENDA)
    lucro_liquido = lair + imposto_renda

    return {
        "receita_bruta": receita_bruta, "imposto": imposto, "receita_liquida": receita_liquida,
        "custo": custo, "margem_bruta": margem_bruta, "despesa_adm": despesa_adm, "ebitda": ebitda,
        "despesa_financeira": despesa_financeira, "lair": lair, "imposto_renda": imposto_renda,
        "lucro_liquido": lucro_liquido,
    }


@st.cache_data(show_spinner=False)
def calcular_previsto_efetivo_asap(
    df_real_asap: pd.DataFrame, df_previsto_asap: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim,
) -> dict | None:
    """Blend mês a mês: ao contrário da Superus (onde só a Despesa precisa
    de fallback pro Realizado), a base da ASAP vem com TODOS os campos
    zerados nos meses que a Revisão ainda não previa de verdade quando foi
    fechada (não só Despesa) — confirmado por inspeção e já documentado no
    DASH_DIRETORIA. Por isso aqui a substituição pelo Realizado se aplica a
    TODOS os campos, sem o atalho "Previsto puro" que a Superus usa pra
    Receita/Custo/Margem Bruta. Se a Revisão não existir pra ASAP (ex.:
    REV03), retorna None — nunca um 0 fingindo "sem orçamento"."""
    if not (df_previsto_asap["Revisão"] == revisao).any():
        return None

    ano = pd.Timestamp(mes_fim).year
    mes_corte = mes_corte_revisao(revisao, ano)
    total = dict.fromkeys(CAMPOS_PREVISTO_ASAP, 0.0)
    for mes in pd.date_range(mes_ini, mes_fim, freq="MS"):
        if mes < mes_corte:
            dre_mes = calcular_dre(df_real_asap[df_real_asap["Mes"] == mes])
            for campo in CAMPOS_PREVISTO_ASAP:
                total[campo] += dre_mes[campo]
        else:
            sub_mes = df_previsto_asap[(df_previsto_asap["Revisão"] == revisao) & (df_previsto_asap["Mes"] == mes)]
            valores_mes = calcular_previsto_asap(sub_mes, cenario)
            for campo in CAMPOS_PREVISTO_ASAP:
                total[campo] += valores_mes[campo]
    return total
