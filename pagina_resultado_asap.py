"""Aba "Resultado" da ASAP — KPIs + DRE Mês/Acumulado (resultado_comum.py),
igual à Superus. Escopo reduzido em relação à Superus nesta primeira
versão (2026-11-24): sem Curva S, Análise por Categoria/CC, Análise de
Complexos e Exportar PDF — essas seções são deliberadamente deixadas de
fora por enquanto (dependem de conceitos específicos da Superus, como
"Complexo" nomeado à mão e a classificação de Centro de Custo já em uso
lá), não um esquecimento. "Realizado ano anterior" fica N/D (não existe
RESULTADOS 2025.xlsx equivalente pra ASAP)."""

import pandas as pd
import streamlit as st

from config import COLIGADAS_ASAP
from dados import MESES_PT, calcular_dre, carregar_realizado_por_coligadas
from estilo import render_banner
from previsto_asap import calcular_previsto_efetivo_asap, carregar_previsto_asap
from resultado_comum import renderizar_dre_mes_e_acumulado, renderizar_kpis


def render() -> None:
    df_real = carregar_realizado_por_coligadas(COLIGADAS_ASAP)
    df_previsto = carregar_previsto_asap()

    with st.sidebar:
        st.header("Filtros — ASAP")
        meses_disponiveis = sorted(df_real["Mes"].dropna().unique().tolist())
        mes_ref = st.selectbox(
            "Mês de referência", meses_disponiveis, index=len(meses_disponiveis) - 1,
            format_func=lambda d: f"{MESES_PT[d.month]}/{d.year}", key="asap_mes_ref",
        )
        revisoes = sorted(df_previsto["Revisão"].unique().tolist())
        revisao_sel = st.selectbox("Revisão", revisoes, index=len(revisoes) - 1, key="asap_revisao_sel")
        cenario_sel = "Otimista"
        if "REV03" not in revisoes:
            st.caption("⚠️ A ASAP ainda não tem base de Previsto para a REV03.")

    ano = mes_ref.year
    mes_ini_ano = pd.Timestamp(year=ano, month=1, day=1)
    nome_mes = MESES_PT[mes_ref.month].upper()

    st.markdown(
        render_banner("APRESENTAÇÃO DE RESULTADOS", f"ASAP · Revisão {revisao_sel} · Cenário {cenario_sel}"),
        unsafe_allow_html=True,
    )
    _ultimo_mes_real = df_real["Mes"].max()
    st.caption(f"último mês com Realizado fechado: {MESES_PT[_ultimo_mes_real.month]}/{_ultimo_mes_real.year}")

    dre_mes_real = calcular_dre(df_real[df_real["Mes"] == mes_ref])
    dre_acum_real = calcular_dre(df_real[(df_real["Mes"] >= mes_ini_ano) & (df_real["Mes"] <= mes_ref)])

    dre_mes_orc = calcular_previsto_efetivo_asap(df_real, df_previsto, revisao_sel, cenario_sel, mes_ref, mes_ref) or {}
    dre_acum_orc = calcular_previsto_efetivo_asap(df_real, df_previsto, revisao_sel, cenario_sel, mes_ini_ano, mes_ref) or {}
    if not dre_acum_orc:
        st.warning(f"⚠️ A {revisao_sel} não tem base de Previsto para a ASAP — Orçado aparece como N/D.")

    renderizar_kpis(dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc)
    st.divider()

    meses_do_ano = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= mes_ref]
    dre_por_mes = {m: calcular_dre(df_real[df_real["Mes"] == m]) for m in meses_do_ano}

    renderizar_dre_mes_e_acumulado(
        "ASAP", ano, nome_mes, dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc, dre_por_mes, meses_do_ano,
    )
