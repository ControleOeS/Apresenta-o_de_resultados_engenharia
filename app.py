"""Ponto de entrada do app — bootstrap de autenticação + navegação por
segmento. "Superus" tem as 3 abas de sempre (Resultado/Classificar Centro
de Custo/Forecast); "ASAP" ganhou o mesmo molde completo (pedido do
usuário, 2026-11-24); "O&S" e "Grupo" (Superus + ASAP, O&S excluída pra
não duplicar a Receita/Despesa dela — ver pagina_resultado_grupo.py) têm
só a aba "Resultado", por decisão explícita do usuário."""

import streamlit as st

from auth import mostrar_banner_ambiente, require_password

import pagina_classificar_cc
import pagina_forecast
import pagina_forecast_asap
import pagina_resultado
import pagina_resultado_asap
import pagina_resultado_grupo
import pagina_resultado_oes

st.set_page_config(page_title="Apresentação de Resultados", page_icon="📊", layout="wide")
require_password()
mostrar_banner_ambiente()


def pagina_superus() -> None:
    tab_resultado, tab_classificar_cc, tab_forecast = st.tabs(
        ["Resultado", "Classificar Centro de Custo", "Forecast"]
    )
    with tab_resultado:
        pagina_resultado.render()
    with tab_classificar_cc:
        pagina_classificar_cc.render()
    with tab_forecast:
        pagina_forecast.render()


def pagina_asap() -> None:
    tab_resultado, tab_classificar_cc, tab_forecast = st.tabs(
        ["Resultado", "Classificar Centro de Custo", "Forecast"]
    )
    with tab_resultado:
        pagina_resultado_asap.render()
    with tab_classificar_cc:
        pagina_classificar_cc.render()
    with tab_forecast:
        pagina_forecast_asap.render()


def pagina_oes() -> None:
    pagina_resultado_oes.render()


def pagina_grupo() -> None:
    pagina_resultado_grupo.render()


navegacao = st.navigation(
    [
        st.Page(pagina_superus, title="Superus", icon="📊"),
        st.Page(pagina_asap, title="ASAP", icon="✈️"),
        st.Page(pagina_oes, title="O&S", icon="🏢"),
        st.Page(pagina_grupo, title="Grupo", icon="🧮"),
    ]
)
navegacao.run()
