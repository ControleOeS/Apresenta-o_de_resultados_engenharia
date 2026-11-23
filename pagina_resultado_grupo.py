"""Aba "Resultado" do Grupo — Superus + ASAP somados campo a campo, O&S
EXCLUÍDA (pedido explícito do usuário, 2026-11-24: "respeitando a regra que
não podemos duplicar a despesa e a receita da O&S... vamos somar Superus e
ASAP no resultado grupo"). A Receita da O&S é o rateio de despesa cobrado
de ASAP/Superus pelos próprios serviços administrativos dela — somá-la
direto contaria a mesma coisa duas vezes (uma como Receita da O&S, outra já
embutida na Despesa de quem paga), mesma regra já usada no DASH_DIRETORIA
(coligadas_dos_grupos/coligada_os_excluida).

Só essa aba (sem Forecast/Classificar Centro de Custo — é um resultado
derivado, não tem Forecast manual próprio nem faz sentido ter a sua
própria classificação de Centro de Custo). N/D sempre que QUALQUER um dos
dois lados (Superus ou ASAP) não tiver o campo disponível pra aquela
Revisão/período — nunca uma soma parcial silenciosa."""

import pandas as pd
import streamlit as st

from config import COLIGADAS_ASAP, COLIGADAS_GRUPO, COLIGADAS_SUPERUS
from dados import (
    MESES_PT,
    calcular_dre,
    calcular_previsto_com_fallback_despesa,
    carregar_previsto,
    carregar_previsto_refinado,
    carregar_realizado_por_coligadas,
)
from estilo import render_banner
from previsto_asap import calcular_previsto_efetivo_asap, carregar_previsto_asap
from resultado_comum import renderizar_dre_mes_e_acumulado, renderizar_kpis

CAMPOS_SOMA = [
    "receita_bruta", "imposto", "receita_liquida", "custo", "margem_bruta",
    "despesa_adm", "ebitda", "despesa_financeira", "lair", "imposto_renda", "lucro_liquido",
]


def _somar_com_propagacao_none(a: dict | None, b: dict | None) -> dict | None:
    if not a or not b:
        return None
    resultado = {}
    for campo in CAMPOS_SOMA:
        va, vb = a.get(campo), b.get(campo)
        resultado[campo] = None if va is None or vb is None else va + vb
    return resultado


def render() -> None:
    df_real_grupo = carregar_realizado_por_coligadas(COLIGADAS_GRUPO)
    # Cada lado do Orçado precisa do Realizado SÓ DELE MESMO como fonte de
    # fallback (mês que a Revisão ainda não previa de verdade espelha o
    # Realizado daquele segmento específico, nunca o combinado) — usar
    # df_real_grupo aqui contaria o Realizado do outro segmento dentro do
    # próprio fallback, inflando o Orçado "espelhado" de cada lado.
    df_real_superus = carregar_realizado_por_coligadas(COLIGADAS_SUPERUS)
    df_real_asap = carregar_realizado_por_coligadas(COLIGADAS_ASAP)

    df_previsto_superus = carregar_previsto()
    df_refinado_superus = carregar_previsto_refinado()
    df_previsto_asap = carregar_previsto_asap()

    with st.sidebar:
        st.header("Filtros — Grupo (Superus + ASAP)")
        meses_disponiveis = sorted(df_real_grupo["Mes"].dropna().unique().tolist())
        mes_ref = st.selectbox(
            "Mês de referência", meses_disponiveis, index=len(meses_disponiveis) - 1,
            format_func=lambda d: f"{MESES_PT[d.month]}/{d.year}", key="grupo_mes_ref",
        )
        revisoes_superus = set(df_previsto_superus["Revisão"].unique()) | set(df_refinado_superus["Revisão"].unique())
        revisoes_asap = set(df_previsto_asap["Revisão"].unique())
        # Interseção, não união — uma Revisão que só a Superus tem mostraria
        # Orçado "incompleto" do lado da ASAP como se fosse zero (nunca é, vira
        # N/D por inteiro via _somar_com_propagacao_none, mas a lista de opções
        # já não oferece essa Revisão quebrada em primeiro lugar).
        revisoes = sorted(revisoes_superus & revisoes_asap)
        revisao_sel = st.selectbox("Revisão", revisoes, index=len(revisoes) - 1, key="grupo_revisao_sel")
        cenario_sel = "Otimista"
        if len(revisoes) < len(revisoes_superus):
            st.caption(
                "⚠️ Só mostra as Revisões que Superus E ASAP têm em comum — a ASAP ainda não tem base "
                "de Previsto para REV03."
            )

    ano = mes_ref.year
    mes_ini_ano = pd.Timestamp(year=ano, month=1, day=1)
    nome_mes = MESES_PT[mes_ref.month].upper()

    st.markdown(
        render_banner("APRESENTAÇÃO DE RESULTADOS", f"Grupo (Superus + ASAP) · Revisão {revisao_sel} · Cenário {cenario_sel}"),
        unsafe_allow_html=True,
    )
    _ultimo_mes_real = df_real_grupo["Mes"].max()
    st.caption(f"último mês com Realizado fechado: {MESES_PT[_ultimo_mes_real.month]}/{_ultimo_mes_real.year}")
    st.caption(
        "Grupo = Superus Engenharia + ASAP somadas campo a campo — a O&S fica de fora (a Receita dela é "
        "o rateio de despesa cobrado da própria Superus/ASAP; somar as duas pontas contaria a mesma "
        "coisa duas vezes)."
    )

    dre_mes_real = calcular_dre(df_real_grupo[df_real_grupo["Mes"] == mes_ref])
    dre_acum_real = calcular_dre(df_real_grupo[(df_real_grupo["Mes"] >= mes_ini_ano) & (df_real_grupo["Mes"] <= mes_ref)])

    # Lado Superus usa a MESMA cascata/fallback já usada na aba Resultado da
    # Superus (calcular_previsto_com_fallback_despesa) — df_real aqui é só
    # pra fallback interno (Orçado não tem granularidade de Coligada/CC
    # própria nesse cálculo, mesma regra de sempre), não precisa ser
    # filtrado especificamente pra Superus.
    dre_mes_orc_superus, _ = calcular_previsto_com_fallback_despesa(
        df_previsto_superus, df_refinado_superus, revisao_sel, cenario_sel, mes_ref, mes_ref, df_real_superus
    )
    dre_acum_orc_superus, _ = calcular_previsto_com_fallback_despesa(
        df_previsto_superus, df_refinado_superus, revisao_sel, cenario_sel, mes_ini_ano, mes_ref, df_real_superus
    )
    dre_mes_orc_asap = calcular_previsto_efetivo_asap(df_real_asap, df_previsto_asap, revisao_sel, cenario_sel, mes_ref, mes_ref)
    dre_acum_orc_asap = calcular_previsto_efetivo_asap(df_real_asap, df_previsto_asap, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)

    dre_mes_orc = _somar_com_propagacao_none(dre_mes_orc_superus, dre_mes_orc_asap) or {}
    dre_acum_orc = _somar_com_propagacao_none(dre_acum_orc_superus, dre_acum_orc_asap) or {}
    if not dre_acum_orc:
        st.warning(
            f"⚠️ A {revisao_sel} não tem base de Previsto completa pra Superus E ASAP ao mesmo tempo — "
            "Orçado do Grupo aparece como N/D (nunca uma soma parcial de só um dos dois)."
        )

    renderizar_kpis(dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc)
    st.divider()

    meses_do_ano = [m for m in sorted(df_real_grupo["Mes"].dropna().unique()) if m.year == ano and m <= mes_ref]
    dre_por_mes = {m: calcular_dre(df_real_grupo[df_real_grupo["Mes"] == m]) for m in meses_do_ano}

    renderizar_dre_mes_e_acumulado(
        "Grupo", ano, nome_mes, dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc, dre_por_mes, meses_do_ano,
    )
