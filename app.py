"""Ponto de entrada do app — bootstrap de autenticação + navegação por
segmento. Hoje só existe "Superus" (as 3 abas que antes eram páginas
separadas: Resultado/app.py, Classificar Centro de Custo e Forecast),
organizadas em st.tabs() dentro de uma única entrada de navegação —
pedido do usuário, 2026-11-23, preparando o app pra quando ASAP/O&S
ganharem sua própria entrada de navegação no mesmo molde (cada uma com
sua própria caixa de abas)."""

import streamlit as st

from auth import mostrar_banner_ambiente, require_password

import pagina_classificar_cc
import pagina_forecast
import pagina_resultado

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


navegacao = st.navigation([st.Page(pagina_superus, title="Superus", icon="📊")])
navegacao.run()
