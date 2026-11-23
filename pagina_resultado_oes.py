"""Aba "Resultado" da O&S — só essa aba (sem Forecast/Classificar Centro de
Custo, pedido do usuário, 2026-11-24). Mesmo escopo reduzido da ASAP (sem
Curva S/Categoria/Complexos/PDF, ver pagina_resultado_asap.py). Só existe
Previsto REV00/REV02 pra O&S — REV01/REV03 aparecem como N/D."""

import pandas as pd
import streamlit as st

from config import COLIGADAS_OES
from dados import MESES_PT, calcular_dre, carregar_realizado_por_coligadas
from estilo import render_banner
from previsto_oes import calcular_previsto_efetivo_oes
from resultado_comum import renderizar_dre_mes_e_acumulado, renderizar_kpis

REVISOES_OES = ["REV00", "REV02"]


def render() -> None:
    df_real = carregar_realizado_por_coligadas(COLIGADAS_OES)

    with st.sidebar:
        st.header("Filtros — O&S")
        meses_disponiveis = sorted(df_real["Mes"].dropna().unique().tolist())
        mes_ref = st.selectbox(
            "Mês de referência", meses_disponiveis, index=len(meses_disponiveis) - 1,
            format_func=lambda d: f"{MESES_PT[d.month]}/{d.year}", key="oes_mes_ref",
        )
        revisao_sel = st.selectbox("Revisão", REVISOES_OES, index=len(REVISOES_OES) - 1, key="oes_revisao_sel")
        cenario_sel = "Otimista"
        st.caption("⚠️ A O&S só tem base de Previsto própria para REV00 e REV02 — REV01/REV03 não existem pra ela.")

    ano = mes_ref.year
    mes_ini_ano = pd.Timestamp(year=ano, month=1, day=1)
    nome_mes = MESES_PT[mes_ref.month].upper()

    st.markdown(
        render_banner("APRESENTAÇÃO DE RESULTADOS", f"O&amp;S · Revisão {revisao_sel} · Cenário {cenario_sel}"),
        unsafe_allow_html=True,
    )
    _ultimo_mes_real = df_real["Mes"].max()
    st.caption(f"último mês com Realizado fechado: {MESES_PT[_ultimo_mes_real.month]}/{_ultimo_mes_real.year}")
    st.caption(
        "A Receita da O&S é inteiramente o rateio de despesa cobrado da ASAP/Superus pelos próprios "
        "serviços administrativos — por isso ela não entra no resultado do \"Grupo\" (evita contar a "
        "mesma coisa duas vezes). Não tem Imposto nem Imposto de Renda (entram como zero, não N/D)."
    )

    dre_mes_real = calcular_dre(df_real[df_real["Mes"] == mes_ref])
    dre_acum_real = calcular_dre(df_real[(df_real["Mes"] >= mes_ini_ano) & (df_real["Mes"] <= mes_ref)])

    dre_mes_orc = calcular_previsto_efetivo_oes(df_real, revisao_sel, cenario_sel, mes_ref, mes_ref) or {}
    dre_acum_orc = calcular_previsto_efetivo_oes(df_real, revisao_sel, cenario_sel, mes_ini_ano, mes_ref) or {}
    if not dre_acum_orc:
        st.warning(f"⚠️ A {revisao_sel} não tem base de Previsto para a O&S — Orçado aparece como N/D.")

    renderizar_kpis(dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc)
    st.divider()

    meses_do_ano = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= mes_ref]
    dre_por_mes = {m: calcular_dre(df_real[df_real["Mes"] == m]) for m in meses_do_ano}

    renderizar_dre_mes_e_acumulado(
        "O&S", ano, nome_mes, dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc, dre_por_mes, meses_do_ano,
    )
