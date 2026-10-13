import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dados import (
    MESES_PT,
    calcular_dre,
    calcular_previsto,
    carregar_previsto,
    carregar_realizado_superus,
)
from formatting import format_brl_compacto, format_brl_md

AZUL = "#033347"  # cor primária da identidade visual O&S
VERDE_CLARO = "#8FB8A8"
VERDE = "#0ca30c"
VERMELHO = "#d03b3b"

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

st.set_page_config(page_title="Apresentação de Resultados", page_icon="📊", layout="wide")
st.title("Apresentação de Resultados — Superus")
st.caption("ACPL + Superus Holding + Superus Engenharia — projeto independente do Resultado 2026")

df_real = carregar_realizado_superus()
df_previsto = carregar_previsto()

with st.sidebar:
    st.header("Filtros")
    meses_disponiveis = sorted(df_real["Mes"].dropna().unique().tolist())
    mes_ref = st.selectbox(
        "Mês de referência",
        meses_disponiveis,
        index=len(meses_disponiveis) - 1,
        format_func=lambda d: f"{MESES_PT[d.month]}/{d.year}",
    )
    revisoes = sorted(df_previsto["Revisão"].unique().tolist())
    revisao_sel = st.selectbox("Revisão", revisoes, index=len(revisoes) - 1)
    cenarios = sorted(df_previsto[df_previsto["Revisão"] == revisao_sel]["Cenário"].unique().tolist())
    cenario_sel = st.radio(
        "Cenário", cenarios, horizontal=True, index=cenarios.index("Otimista") if "Otimista" in cenarios else 0
    )

ano = mes_ref.year
mes_ini_ano = pd.Timestamp(year=ano, month=1, day=1)

dre_mes_real = calcular_dre(df_real[df_real["Mes"] == mes_ref])
dre_acum_real = calcular_dre(df_real[(df_real["Mes"] >= mes_ini_ano) & (df_real["Mes"] <= mes_ref)])

df_previsto_rev_cen = df_previsto[(df_previsto["Revisão"] == revisao_sel)]
dre_mes_orc = calcular_previsto(df_previsto_rev_cen[df_previsto_rev_cen["Mes"] == mes_ref], cenario_sel)
dre_acum_orc = calcular_previsto(
    df_previsto_rev_cen[(df_previsto_rev_cen["Mes"] >= mes_ini_ano) & (df_previsto_rev_cen["Mes"] <= mes_ref)],
    cenario_sel,
)

st.caption(f"**{MESES_PT[mes_ref.month]}/{mes_ref.year}** · Revisão {revisao_sel} · Cenário {cenario_sel}")

# ------------------------------------------------------------------
# KPIs
# ------------------------------------------------------------------
st.header("KPIs")


def _grafico_kpi(nome: str, campo: str) -> go.Figure:
    valores = [dre_mes_orc.get(campo), dre_mes_real.get(campo), dre_acum_orc.get(campo), dre_acum_real.get(campo)]
    rotulos = ["Mês Orç.", "Mês Real.", "Acum. Orç.", "Acum. Real."]
    cores = [VERDE_CLARO, AZUL, VERDE_CLARO, AZUL]
    textos = [format_brl_compacto(v) if v is not None else "N/D" for v in valores]
    fig = go.Figure(
        go.Bar(x=rotulos, y=valores, marker_color=cores, text=textos, textposition="outside")
    )
    fig.update_layout(
        title=nome,
        height=340,
        separators=",.",
        margin=dict(t=40, b=30),
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.2s",
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="#fcfcfb",
        showlegend=False,
    )
    return fig


c1, c2 = st.columns(2)
c1.plotly_chart(_grafico_kpi("Receita Bruta", "receita_bruta"), use_container_width=True)
c2.plotly_chart(_grafico_kpi("Lucro Bruto", "margem_bruta"), use_container_width=True)
c3, c4 = st.columns(2)
c3.plotly_chart(_grafico_kpi("EBITDA", "ebitda"), use_container_width=True)
c4.plotly_chart(_grafico_kpi("LAIR", "lair"), use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# DRE — Mês e Acumulado
# ------------------------------------------------------------------
st.header("DRE — Mês e Acumulado")

linhas_html = []
for nome, campo, destaque in LINHAS_DRE_DEF:
    estilo = "font-weight:700; background-color:rgba(3,51,71,0.08);" if destaque else "font-weight:400;"
    real_mes = dre_mes_real[campo]
    orc_mes = dre_mes_orc.get(campo)
    real_acum = dre_acum_real[campo]
    orc_acum = dre_acum_orc.get(campo)
    delta_mes = (real_mes - orc_mes) if orc_mes is not None else None
    delta_acum = (real_acum - orc_acum) if orc_acum is not None else None
    cor_delta_mes = VERDE if (delta_mes or 0) >= 0 else VERMELHO
    cor_delta_acum = VERDE if (delta_acum or 0) >= 0 else VERMELHO
    linhas_html.append(
        f"<tr style='{estilo}'>"
        f"<td style='padding:6px 14px; white-space:nowrap;'>{nome}</td>"
        f"<td style='padding:6px 14px; text-align:right; white-space:nowrap;'>{format_brl_md(real_mes)}</td>"
        f"<td style='padding:6px 14px; text-align:right; white-space:nowrap;'>{format_brl_md(orc_mes)}</td>"
        f"<td style='padding:6px 14px; text-align:right; white-space:nowrap; color:{cor_delta_mes};'>"
        f"{format_brl_md(delta_mes)}</td>"
        f"<td style='padding:6px 14px; text-align:right; white-space:nowrap; border-left:2px solid #ccc;'>"
        f"{format_brl_md(real_acum)}</td>"
        f"<td style='padding:6px 14px; text-align:right; white-space:nowrap;'>{format_brl_md(orc_acum)}</td>"
        f"<td style='padding:6px 14px; text-align:right; white-space:nowrap; color:{cor_delta_acum};'>"
        f"{format_brl_md(delta_acum)}</td>"
        "</tr>"
    )

st.markdown(
    "<table style='width:100%; border-collapse:collapse; font-size:0.95rem;'>"
    "<tr>"
    "<th></th>"
    "<th colspan='3' style='text-align:center; padding:4px;'>Mês</th>"
    "<th colspan='3' style='text-align:center; padding:4px; border-left:2px solid #ccc;'>Acumulado</th>"
    "</tr>"
    "<tr>"
    "<th style='text-align:left; padding:6px 14px;'>Linha</th>"
    "<th style='padding:6px 14px; text-align:right;'>Realizado</th>"
    "<th style='padding:6px 14px; text-align:right;'>Orçado</th>"
    "<th style='padding:6px 14px; text-align:right;'>Δ</th>"
    "<th style='padding:6px 14px; text-align:right; border-left:2px solid #ccc;'>Realizado</th>"
    "<th style='padding:6px 14px; text-align:right;'>Orçado</th>"
    "<th style='padding:6px 14px; text-align:right;'>Δ</th>"
    "</tr>"
    + "".join(linhas_html)
    + "</table>",
    unsafe_allow_html=True,
)

if dre_mes_orc.get("despesa_adm") is None:
    st.caption(
        "⚠️ Despesa Administrativa/Financeira, EBITDA, LAIR, Imposto de Renda e Lucro Líquido aparecem "
        "como N/D para essa Revisão/Cenário — ainda não temos uma base de Previsto completa até Lucro "
        "Líquido para ela (hoje só REV00 e REV01-Otimista têm essa cascata)."
    )

with st.expander("O que ainda falta para replicar a apresentação de referência"):
    st.markdown(
        "- **Previsto REV02 completo** (Despesa até Lucro Líquido) — hoje só REV00/REV01 têm.\n"
        "- **Histórico 2022-2025** — essa base só tem 2026.\n"
        "- **Classificação por categoria de receita** (Backlog Ativo/Novo, Super Meta, Funil de "
        "Vendas, Capex a Vender, Plano de Guerra, Indenização) — não existe na base atual.\n"
        "- **Previsto granular por Complexo/projeto** — hoje só temos Previsto agregado por linha de DRE.\n"
        "- **Despesa por centro de custo/departamento** (DOP, Engenharia, Planejamento, SSMA...) e por "
        "natureza (Operação/Comercial/Administração/PLR) — hoje é uma linha única agregada.\n"
        "- **Breakdown da Despesa Financeira** (Antecipação, Tributos, Fornecedor, Tarifa).\n"
    )
