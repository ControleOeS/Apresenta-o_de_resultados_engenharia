"""Quebra Receita/Despesa por categoria (BackLog Ativo/Novo/Inativo, Funil
de Vendas, Despesa - Operação/Comercial/Administrativo etc.), usando a
classificação manual de Centro de Custo feita na página "Classificar
Centros de Custo" — ver classificacoes.py."""

import pandas as pd

from classificacoes import carregar_classificacoes
from dados import (
    CATEGORIA_DESPESA_ADMINISTRATIVO,
    CATEGORIA_DESPESA_COMERCIAL,
    CATEGORIA_DESPESA_OPERACAO,
    CATEGORIA_DESPESA_PLR,
    CODIGOS_DESPESA_ADM,
    NIVEL_CUSTO,
    NIVEL_DESPESA_ADM,
    NIVEL_IMPOSTO,
    NIVEL_RECEITA_BRUTA,
    custo_por_cc_refinado,
    despesa_por_categoria_rev02_mensal,
    despesa_por_categoria_rev03_mensal,
    despesa_por_cc_rev02_mensal,
    imposto_por_cc_refinado,
    mes_corte_revisao,
    receita_por_cc_refinado,
)

NAO_CLASSIFICADO = "Não classificado"

# A apresentação de referência só tem 3 categorias de Despesa (Operação/
# Comercial/Administrativo) + PLR à parte — mas a classificação manual de
# Centro de Custo (pensada pra cobrir Receita também) tem categorias como
# "Capex"/"Não operacional"/"Backlog Inativo" que, pra Despesa
# especificamente, são só uma fração pequena e deveriam cair em
# Administrativo pra bater com o padrão da referência (confirmado com o
# usuário, 2026-10-20).
_CATEGORIAS_DESPESA_VALIDAS = {CATEGORIA_DESPESA_ADMINISTRATIVO, CATEGORIA_DESPESA_COMERCIAL, CATEGORIA_DESPESA_OPERACAO}

# PLR no Realizado: o usuário renomeou os Centro de Custo dedicados a PLR
# pra começar com "PLR " (ex: "PLR DOP", "PLR COMERCIAL") especificamente
# pra isolar isso (antes só achávamos provisão de ano anterior, não o
# valor corrente — não dava pra confiar). Esse nome manda mais que
# qualquer categoria salva na classificação manual pra esses CCs.
_PREFIXO_PLR_REALIZADO = "PLR "


def _marcar_plr_pelo_nome(df: pd.DataFrame, coluna_nome: str) -> pd.Series:
    return df[coluna_nome].astype(str).str.upper().str.startswith(_PREFIXO_PLR_REALIZADO)


def _dobrar_para_administrativo(serie: pd.Series) -> pd.Series:
    if serie.empty:
        return serie
    serie = serie.rename(
        index=lambda c: c if c in _CATEGORIAS_DESPESA_VALIDAS else CATEGORIA_DESPESA_ADMINISTRATIVO
    )
    return serie.groupby(level=0).sum()


def _mapa_categoria_por_codigo() -> dict[str, str]:
    classificacoes = carregar_classificacoes()
    return {codigo: info["categoria"] for codigo, info in classificacoes.items() if info.get("categoria")}


def _agrupar(df: pd.DataFrame, coluna_cc: str) -> pd.Series:
    mapa = _mapa_categoria_por_codigo()
    if df.empty:
        return pd.Series(dtype=float)
    sub = df.copy()
    sub["Categoria"] = sub[coluna_cc].astype(str).map(mapa).fillna(NAO_CLASSIFICADO)
    return sub.groupby("Categoria")["Valor"].sum()


def _agrupar_serie(serie_cc: pd.Series) -> pd.Series:
    """Igual a _agrupar, mas pra uma série já indexada por Código de
    Centro de Custo (ex: vinda do Refinado Engenharias) em vez de um
    DataFrame linha a linha."""
    mapa = _mapa_categoria_por_codigo()
    if serie_cc.empty:
        return pd.Series(dtype=float)
    df = serie_cc.rename("Valor").reset_index()
    df.columns = ["Codigo", "Valor"]
    df["Categoria"] = df["Codigo"].astype(str).map(mapa).fillna(NAO_CLASSIFICADO)
    return df.groupby("Categoria")["Valor"].sum()


def receita_por_categoria_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.Series:
    sub = df_real[
        df_real["Nível 1"].isin(NIVEL_RECEITA_BRUTA) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)
    ]
    return _agrupar(sub, "Cod. Centro de Custo")


def despesa_por_categoria_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.Series:
    sub = df_real[
        df_real["Nível 1"].isin(NIVEL_DESPESA_ADM) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)
    ]
    eh_plr = _marcar_plr_pelo_nome(sub, "Centro de Custo")
    resultado = _dobrar_para_administrativo(_agrupar(sub[~eh_plr], "Cod. Centro de Custo"))
    if eh_plr.any():
        resultado = resultado.add(pd.Series({CATEGORIA_DESPESA_PLR: sub.loc[eh_plr, "Valor"].sum()}), fill_value=0.0)
    return resultado


def custo_por_categoria_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.Series:
    sub = df_real[df_real["Nível 1"].isin(NIVEL_CUSTO) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)]
    return _agrupar(sub, "Cod. Centro de Custo")


def imposto_por_categoria_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.Series:
    sub = df_real[df_real["Nível 1"].isin(NIVEL_IMPOSTO) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)]
    return _agrupar(sub, "Cod. Centro de Custo")


def _por_categoria_previsto(df_previsto: pd.DataFrame, codigos, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series | None:
    sub = df_previsto[
        df_previsto["Codigo"].isin(codigos)
        & (df_previsto["Revisão"] == revisao)
        & (df_previsto["Cenário"] == cenario)
        & (df_previsto["Mes"] >= mes_ini)
        & (df_previsto["Mes"] <= mes_fim)
    ]
    if sub.empty:
        return None
    return _agrupar(sub, "CC")


# Receita/Custo/Imposto vêm do Refinado Engenharias (cobre as 4 Revisões —
# REV00 a REV03 — com Centro de Custo), não do df_previsto "antigo" (só
# tem REV00/REV01). Despesa continua no df_previsto: o Refinado não tem
# Despesa Administrativa/Financeira por Centro de Custo (confirmado
# inspecionando o arquivo em 2026-10-14) — REV02/REV03 ficam sem Despesa
# por Categoria até essa fonte existir.
def receita_por_categoria_previsto(df_refinado_detalhado: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series | None:
    serie = receita_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini, mes_fim)
    return _agrupar_serie(serie) if not serie.empty else None


def _despesa_por_categoria_com_mes_corte(df_real: pd.DataFrame, mensal_nova: pd.DataFrame, revisao: str, mes_ini, mes_fim) -> pd.Series:
    """Mês a mês: antes do corte de previsão da Revisão (mes_corte_revisao,
    mesma regra usada no DRE agregado em dados.py) espelha o Realizado por
    categoria — Δ=0, a Revisão não previa esse mês de verdade ainda; a
    partir do corte usa a fonte de Orçado própria da Revisão
    (`mensal_nova`, indexada por Mes/coluna por categoria). Sem isso, um
    Acumulado misturava "sem dado" (meses fora do arquivo) com "igual ao
    Realizado" de forma inconsistente, inflando artificialmente a
    divergência Orç. x Real do período todo."""
    mes_corte = mes_corte_revisao(revisao, pd.Timestamp(mes_fim).year)
    total = pd.Series(dtype=float)
    for mes in pd.date_range(mes_ini, mes_fim, freq="MS"):
        if mes < mes_corte:
            serie_mes = despesa_por_categoria_realizado(df_real, mes, mes)
        elif mes in mensal_nova.index:
            serie_mes = mensal_nova.loc[mes]
        else:
            continue
        total = total.add(serie_mes, fill_value=0.0)
    return total


def despesa_por_categoria_previsto(df_previsto: pd.DataFrame, df_real: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series | None:
    # REV02/REV03 têm fonte própria (arquivos de Despesa por departamento,
    # ver dados.py), só cobrindo a partir da janela de previsão real da
    # Revisão — meses anteriores espelham o Realizado por categoria (ver
    # _despesa_por_categoria_com_mes_corte). O df_previsto "antigo" só
    # cobre REV00/REV01.
    if revisao == "REV02":
        serie = _despesa_por_categoria_com_mes_corte(df_real, despesa_por_categoria_rev02_mensal(), revisao, mes_ini, mes_fim)
        return serie if not serie.empty else None
    if revisao == "REV03":
        serie = _despesa_por_categoria_com_mes_corte(df_real, despesa_por_categoria_rev03_mensal(), revisao, mes_ini, mes_fim)
        return serie if not serie.empty else None
    return _por_categoria_previsto(df_previsto, CODIGOS_DESPESA_ADM, revisao, cenario, mes_ini, mes_fim)


def custo_por_categoria_previsto(df_refinado_detalhado: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series | None:
    serie = custo_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini, mes_fim)
    return _agrupar_serie(serie) if not serie.empty else None


def imposto_por_categoria_previsto(df_refinado_detalhado: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.Series | None:
    serie = imposto_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini, mes_fim)
    return _agrupar_serie(serie) if not serie.empty else None


# ------------------------------------------------------------------
# Detalhamento por Centro de Custo (drill-down) — mesma lógica acima, mas
# sem agregar por categoria: uma linha por Centro de Custo, com a
# categoria dele junto, pra permitir abrir cada categoria e ver os CCs
# que a compõem.
# ------------------------------------------------------------------


def _detalhar(df: pd.DataFrame, coluna_codigo: str, coluna_nome: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Categoria", "Codigo", "Centro de Custo", "Valor"])
    # Cuidado: pandas.groupby descarta (por padrão) qualquer linha com NaN em
    # alguma das chaves — algumas linhas têm Código de Centro de Custo ou o
    # nome descritivo vazio, e isso fazia a soma do detalhamento ficar menor
    # que o total agregado (achado reconciliando os dois: "Não classificado"
    # aparecia zerado no detalhe mas não no agregado).
    mapa = _mapa_categoria_por_codigo()
    sub = df.copy()
    sub[coluna_codigo] = sub[coluna_codigo].astype(str)
    sub[coluna_nome] = sub[coluna_nome].fillna("(sem nome)")
    agrupado = sub.groupby([coluna_codigo, coluna_nome], dropna=False)["Valor"].sum().reset_index()
    agrupado.columns = ["Codigo", "Centro de Custo", "Valor"]
    agrupado["Categoria"] = agrupado["Codigo"].map(mapa).fillna(NAO_CLASSIFICADO)
    return agrupado[["Categoria", "Codigo", "Centro de Custo", "Valor"]]


def receita_por_cc_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.DataFrame:
    sub = df_real[
        df_real["Nível 1"].isin(NIVEL_RECEITA_BRUTA) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)
    ]
    return _detalhar(sub, "Cod. Centro de Custo", "Centro de Custo")


def despesa_por_cc_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.DataFrame:
    sub = df_real[
        df_real["Nível 1"].isin(NIVEL_DESPESA_ADM) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)
    ]
    detalhe = _detalhar(sub, "Cod. Centro de Custo", "Centro de Custo")
    if not detalhe.empty:
        eh_plr = _marcar_plr_pelo_nome(detalhe, "Centro de Custo")
        detalhe["Categoria"] = [
            CATEGORIA_DESPESA_PLR if plr else (c if c in _CATEGORIAS_DESPESA_VALIDAS else CATEGORIA_DESPESA_ADMINISTRATIVO)
            for c, plr in zip(detalhe["Categoria"], eh_plr)
        ]
    return detalhe


def custo_por_cc_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.DataFrame:
    sub = df_real[df_real["Nível 1"].isin(NIVEL_CUSTO) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)]
    return _detalhar(sub, "Cod. Centro de Custo", "Centro de Custo")


def imposto_por_cc_realizado(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.DataFrame:
    sub = df_real[df_real["Nível 1"].isin(NIVEL_IMPOSTO) & (df_real["Mes"] >= mes_ini) & (df_real["Mes"] <= mes_fim)]
    return _detalhar(sub, "Cod. Centro de Custo", "Centro de Custo")


def _por_cc_previsto(df_previsto: pd.DataFrame, codigos, revisao: str, cenario: str, mes_ini, mes_fim) -> pd.DataFrame | None:
    sub = df_previsto[
        df_previsto["Codigo"].isin(codigos)
        & (df_previsto["Revisão"] == revisao)
        & (df_previsto["Cenário"] == cenario)
        & (df_previsto["Mes"] >= mes_ini)
        & (df_previsto["Mes"] <= mes_fim)
    ]
    if sub.empty:
        return None
    return _detalhar(sub, "CC", "Centro de Custo")


def _detalhar_serie(serie_cc: pd.Series, tabela_dimensao: pd.DataFrame) -> pd.DataFrame:
    """Igual a _detalhar, mas pra uma série já indexada por Código de
    Centro de Custo (Refinado Engenharias) — o nome de exibição vem da
    tabela dimensão (o Refinado não carrega o nome junto na mesma linha
    que a gente já agrupou)."""
    mapa_categoria = _mapa_categoria_por_codigo()
    if serie_cc.empty:
        return pd.DataFrame(columns=["Categoria", "Codigo", "Centro de Custo", "Valor"])
    mapa_nome = tabela_dimensao.set_index("Codigo")["Centro de Custo"].to_dict()
    df = serie_cc.rename("Valor").reset_index()
    df.columns = ["Codigo", "Valor"]
    df["Codigo"] = df["Codigo"].astype(str)
    df["Categoria"] = df["Codigo"].map(mapa_categoria).fillna(NAO_CLASSIFICADO)
    df["Centro de Custo"] = df["Codigo"].map(mapa_nome).fillna(df["Codigo"])
    return df[["Categoria", "Codigo", "Centro de Custo", "Valor"]]


def receita_por_cc_previsto(
    df_refinado_detalhado: pd.DataFrame, tabela_dimensao: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim
) -> pd.DataFrame | None:
    serie = receita_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini, mes_fim)
    return _detalhar_serie(serie, tabela_dimensao) if not serie.empty else None


def _mapa_nome_para_codigo_despesa(df_real: pd.DataFrame) -> dict[str, str]:
    """Nome (Centro de Custo, normalizado) -> Código real, construído a
    partir de TODO o Realizado de Despesa (sem filtro de período, pra não
    perder nome de Centro de Custo que não teve lançamento no período
    escolhido). Usado só pra resolver o Código do Orçado REV02 (que só tem
    nome de departamento — ver MAPA_NOME_DESPESA_REV02_REALIZADO em
    dados.py), nunca os valores em si."""
    sub = df_real[df_real["Nível 1"].isin(NIVEL_DESPESA_ADM)].copy()
    sub["Centro de Custo"] = sub["Centro de Custo"].astype(str).str.strip()
    sub["Cod. Centro de Custo"] = sub["Cod. Centro de Custo"].astype(str)
    return sub.drop_duplicates("Centro de Custo").set_index("Centro de Custo")["Cod. Centro de Custo"].to_dict()


def _despesa_por_cc_rev02(df_real: pd.DataFrame, mes_ini, mes_fim) -> pd.DataFrame | None:
    df = despesa_por_cc_rev02_mensal()
    sub = df[(df["Mes"] >= mes_ini) & (df["Mes"] <= mes_fim)]
    if sub.empty:
        return None
    agrupado = sub.groupby(["Categoria", "Centro de Custo"], as_index=False)["Valor"].sum()
    # Resolve pro Código real do Realizado (via o nome já convertido pelo
    # de-para de dados.py) — sem isso o drilldown comparava Orçado e
    # Realizado por nome e os dois caíam em linhas separadas sempre que a
    # grafia não batia 100% (ver _tabela_cc_da_categoria em app.py, que
    # agora concilia por Código). Nome sem equivalente no Realizado (ex:
    # "GESTORES TRAINEES") mantém o próprio nome como pseudo-código — continua
    # aparecendo como linha só do Orçado, igual antes.
    mapa_codigo = _mapa_nome_para_codigo_despesa(df_real)
    agrupado["Codigo"] = agrupado["Centro de Custo"].map(mapa_codigo).fillna(agrupado["Centro de Custo"])
    return agrupado[["Categoria", "Codigo", "Centro de Custo", "Valor"]]


def despesa_por_cc_previsto(
    df_previsto: pd.DataFrame, df_real: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim
) -> pd.DataFrame | None:
    # REV02 (DESPESA REV02.xlsx) tem granularidade de departamento (nomes
    # convertidos pro equivalente do Realizado em despesa_por_cc_rev02_mensal,
    # ver dados.py) — não é a mesma fonte/esquema de código do df_previsto
    # "antigo" (só cobre REV00/REV01). REV03 continua sem detalhamento por
    # CC (ONEPAGE_REV03 tem granularidade de departamento mas sem
    # equivalente conferido ainda com o Realizado).
    if revisao == "REV02":
        return _despesa_por_cc_rev02(df_real, mes_ini, mes_fim)
    return _por_cc_previsto(df_previsto, CODIGOS_DESPESA_ADM, revisao, cenario, mes_ini, mes_fim)


def custo_por_cc_previsto(
    df_refinado_detalhado: pd.DataFrame, tabela_dimensao: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim
) -> pd.DataFrame | None:
    serie = custo_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini, mes_fim)
    return _detalhar_serie(serie, tabela_dimensao) if not serie.empty else None


def imposto_por_cc_previsto(
    df_refinado_detalhado: pd.DataFrame, tabela_dimensao: pd.DataFrame, revisao: str, cenario: str, mes_ini, mes_fim
) -> pd.DataFrame | None:
    serie = imposto_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini, mes_fim)
    return _detalhar_serie(serie, tabela_dimensao) if not serie.empty else None
