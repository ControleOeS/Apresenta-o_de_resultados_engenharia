import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dados import (
    LINHAS_DRE_DEF,
    LINHAS_MARGEM,
    MESES_PT,
    calcular_dre,
    calcular_previsto_com_fallback_despesa,
    carregar_previsto,
    carregar_previsto_refinado,
    carregar_realizado_2025_mensal,
    carregar_realizado_superus,
    carregar_meta_mensal,
    carregar_refinado_detalhado,
    dre_2025_periodo,
    revisao_vigente_no_mes,
    tabela_dimensao_centro_de_custo,
)
from estilo import (
    VERDE_DERIVADO_HEADER,
    VERDE_DERIVADO_TINT,
    VERDE_ESCURO,
    VERDE_ORCADO,
    VERMELHO,
    render_banner,
    render_caixa_narrativa,
    render_tabela_com_faixa,
)
from formatting import format_brl_compacto, format_brl_md, format_pct, format_pct_av
from exportar_pdf import gerar_pdf, localizar_navegador, porta_do_servidor_atual
from forecast import dados_forecast_salvo, fechar_dre_ano, meses_forecast, revisao_atual_forecast, validar_lucro_bruto
from narrativa import gerar_analise
from analise_complexos import AnaliseComplexos
from graficos_complexos import grafico_pizza_duas_fatias, grafico_pizza_status
from analise_categoria import (
    custo_por_categoria_previsto,
    custo_por_categoria_realizado,
    custo_por_cc_previsto,
    custo_por_cc_realizado,
    despesa_por_categoria_previsto,
    despesa_por_categoria_realizado,
    despesa_por_cc_previsto,
    despesa_por_cc_realizado,
    imposto_por_categoria_previsto,
    imposto_por_categoria_realizado,
    imposto_por_cc_previsto,
    imposto_por_cc_realizado,
    receita_por_categoria_previsto,
    receita_por_categoria_realizado,
    receita_por_cc_previsto,
    receita_por_cc_realizado,
)
from graficos_categoria import grafico_categoria_empilhado
from auth import mostrar_banner_ambiente, require_password

st.set_page_config(page_title="Apresentação de Resultados", page_icon="📊", layout="wide")
require_password()
mostrar_banner_ambiente()

st.markdown(
    """
    <style>
    @media print {
        [data-testid="stSidebar"], [data-testid="stHeader"],
        [data-testid="stToolbar"], #MainMenu, footer { display: none !important; }
        .block-container { max-width: 100% !important; padding: 0 1rem !important; }
        /* break-before/break-inside não funcionam de forma confiável dentro
        de containers flex (o layout padrão do Streamlit) — força bloco só
        na impressão, senão a quebra de página força uma página extra em
        branco antes do conteúdo seguinte. */
        [data-testid="stVerticalBlock"], [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stMain"], [data-testid="stAppViewBlockContainer"] { display: block !important; }
        .quebra-pagina { break-before: page; }
        .tabela-dre-wrapper { break-inside: avoid; }
        /* Detalhamento mês a mês da tabela Acumulado: útil interativo (tem
        scroll horizontal na tela), mas em paisagem A4 não cabe junto com
        Acumulado/Orçado/Δ/Acumulado 2025/Δ 25x26 sem cortar colunas fora
        da página — escondido só no PDF, igual ao padrão da apresentação
        de referência (que também só mostra os totais, sem detalhe mensal
        dentro do Acumulado). */
        .col-mes-detalhe { display: none; }
    }
    @page { size: A4 landscape; margin: 8mm; }
    </style>
    """,
    unsafe_allow_html=True,
)

df_real = carregar_realizado_superus()
df_previsto = carregar_previsto()
df_refinado = carregar_previsto_refinado()
df_refinado_detalhado = carregar_refinado_detalhado()
tabela_dimensao = tabela_dimensao_centro_de_custo()

with st.sidebar:
    st.header("Filtros")
    meses_disponiveis = sorted(df_real["Mes"].dropna().unique().tolist())
    mes_param = st.query_params.get("mes")
    indice_mes_padrao = len(meses_disponiveis) - 1
    if mes_param:
        datas_iso = [d.strftime("%Y-%m-%d") for d in meses_disponiveis]
        if mes_param in datas_iso:
            indice_mes_padrao = datas_iso.index(mes_param)
    mes_ref = st.selectbox(
        "Mês de referência",
        meses_disponiveis,
        index=indice_mes_padrao,
        format_func=lambda d: f"{MESES_PT[d.month]}/{d.year}",
    )
    revisoes = sorted(set(df_previsto["Revisão"].unique().tolist()) | set(df_refinado["Revisão"].unique().tolist()))
    revisao_param = st.query_params.get("revisao")
    # Abre já na Revisão que previa de verdade o mês padrão (último Realizado
    # fechado) — ex: fechado até Setembro -> REV02 (REV03 só previa de Out
    # em diante) — em vez de sempre a Revisão mais recente, pra abrir pronto
    # pra consumir sem precisar trocar manualmente (pedido do usuário,
    # 2026-10-21).
    mes_padrao = meses_disponiveis[indice_mes_padrao]
    indice_revisao_padrao = revisoes.index(revisao_vigente_no_mes(mes_padrao.month, revisoes))
    if revisao_param in revisoes:
        indice_revisao_padrao = revisoes.index(revisao_param)
    revisao_sel = st.selectbox("Revisão", revisoes, index=indice_revisao_padrao)
    cenario_sel = "Otimista"

    st.query_params["mes"] = mes_ref.strftime("%Y-%m-%d")
    st.query_params["revisao"] = revisao_sel

    st.divider()
    # Exportar PDF abre um Chrome/Edge local via CDP — não existe num
    # servidor Linux na nuvem (Streamlit Cloud), então o botão some sozinho
    # lá (localizar_navegador não acha nada) em vez de aparecer e dar erro
    # quando clicado. Continua funcionando normal rodando local.
    navegador_disponivel = True
    try:
        localizar_navegador()
    except FileNotFoundError:
        navegador_disponivel = False

    if navegador_disponivel and st.button("📄 Exportar PDF", use_container_width=True):
        with st.spinner("Gerando PDF..."):
            porta = porta_do_servidor_atual()
            url_exportacao = (
                f"http://localhost:{porta}/?mes={mes_ref.strftime('%Y-%m-%d')}&revisao={revisao_sel}"
            )
            try:
                pdf_bytes = gerar_pdf(url_exportacao)
                st.session_state["pdf_gerado"] = pdf_bytes
            except Exception as e:
                st.error(f"Não foi possível gerar o PDF: {e}")

    if "pdf_gerado" in st.session_state:
        st.download_button(
            "⬇️ Baixar PDF",
            data=st.session_state["pdf_gerado"],
            file_name=f"Apresentacao_Resultados_{mes_ref.strftime('%Y-%m')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

ano = mes_ref.year
mes_ini_ano = pd.Timestamp(year=ano, month=1, day=1)
nome_mes = MESES_PT[mes_ref.month].upper()

st.markdown(
    render_banner(
        "APRESENTAÇÃO DE RESULTADOS",
        f"Superus Holding · Revisão {revisao_sel} · Cenário {cenario_sel}",
    ),
    unsafe_allow_html=True,
)

dre_mes_real = calcular_dre(df_real[df_real["Mes"] == mes_ref])
dre_acum_real = calcular_dre(df_real[(df_real["Mes"] >= mes_ini_ano) & (df_real["Mes"] <= mes_ref)])

realizado_2025_mensal = carregar_realizado_2025_mensal()
dre_mes_2025 = dre_2025_periodo(realizado_2025_mensal, mes_ref, mes_ref)
dre_acum_2025 = dre_2025_periodo(realizado_2025_mensal, mes_ini_ano, mes_ref)

dre_mes_orc, despesa_provisoria_mes = calcular_previsto_com_fallback_despesa(
    df_previsto, df_refinado, revisao_sel, cenario_sel, mes_ref, mes_ref, df_real
)
dre_acum_orc, despesa_provisoria_acum = calcular_previsto_com_fallback_despesa(
    df_previsto, df_refinado, revisao_sel, cenario_sel, mes_ini_ano, mes_ref, df_real
)
dre_mes_orc = dre_mes_orc or {}
dre_acum_orc = dre_acum_orc or {}
despesa_provisoria = despesa_provisoria_mes or despesa_provisoria_acum

# ------------------------------------------------------------------
# KPIs
# ------------------------------------------------------------------
st.header("KPIs")


def _variacao_pct(real, orc):
    if real is None or orc is None or not orc:
        return None
    return (real - orc) / abs(orc)


def _grafico_kpi(nome: str, campo: str, campo_margem_base: str | None = None) -> tuple[go.Figure, str]:
    rotulos = ["Mês Orç.", "Mês Real.", "Acum. Orç.", "Acum. Real."]
    valores = [dre_mes_orc.get(campo), dre_mes_real.get(campo), dre_acum_orc.get(campo), dre_acum_real.get(campo)]
    cores = [VERDE_ORCADO, VERDE_ESCURO, VERDE_ORCADO, VERDE_ESCURO]
    textos = [format_brl_compacto(v) for v in valores]
    cores_texto = [VERMELHO if (v or 0) < 0 else "#1A1A1A" for v in valores]

    var_mes = _variacao_pct(dre_mes_real.get(campo), dre_mes_orc.get(campo))
    var_acum = _variacao_pct(dre_acum_real.get(campo), dre_acum_orc.get(campo))

    valores_validos = [v for v in valores if v is not None]
    maior = max(valores_validos) if valores_validos else 0
    menor = min(valores_validos) if valores_validos else 0
    # Folga proporcional ao alcance total do gráfico (não ao valor da própria
    # barra) — senão uma barra negativa minúscula perto de barras grandes
    # ganha uma margem ínfima e o rótulo cola no eixo X.
    alcance = maior - min(menor, 0) or abs(maior) or 1
    y_topo = maior + alcance * 0.22
    y_base = min(menor, 0) - alcance * 0.18

    fig = go.Figure(
        go.Bar(
            x=rotulos,
            y=valores,
            marker_color=cores,
            text=textos,
            textposition="outside",
            textfont=dict(color=cores_texto, size=13, weight=700),
            cliponaxis=False,
        )
    )

    anotacoes = []
    for var, x_real, x_orc in [(var_mes, "Mês Real.", "Mês Orç."), (var_acum, "Acum. Real.", "Acum. Orç.")]:
        if var is None:
            continue
        cor_var = VERMELHO if var < 0 else "#1C7C3E"
        anotacoes.append(
            dict(
                x=x_real,
                y=y_topo,
                text=f"{'▲' if var >= 0 else '▼'} {var * 100:+.1f}%",
                showarrow=False,
                font=dict(color=cor_var, size=13, weight=700),
            )
        )

    fig.update_layout(
        title=dict(text=nome, font=dict(size=16, color="#1A1A1A")),
        height=380,
        separators=",.",
        margin=dict(t=70, b=40),
        xaxis=dict(
            tickfont=dict(size=12, color="#1A1A1A", weight=600),
            showgrid=False,
        ),
        yaxis=dict(
            title=dict(text="Valor (R$)", font=dict(size=12, color="#444")),
            tickprefix="R$ ",
            tickformat=",.2s",
            tickfont=dict(size=11, color="#444"),
            gridcolor="#E8E8E4",
            zerolinecolor="#CCCCCC",
            range=[y_base, y_topo],
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        showlegend=False,
        annotations=anotacoes,
    )

    legenda_margem = ""
    if campo_margem_base:
        base_mes_orc, base_mes_real = dre_mes_orc.get(campo_margem_base), dre_mes_real.get(campo_margem_base)
        base_acum_orc, base_acum_real = dre_acum_orc.get(campo_margem_base), dre_acum_real.get(campo_margem_base)
        m1 = format_pct_av(dre_mes_orc.get(campo), base_mes_orc)
        m2 = format_pct_av(dre_mes_real.get(campo), base_mes_real)
        m3 = format_pct_av(dre_acum_orc.get(campo), base_acum_orc)
        m4 = format_pct_av(dre_acum_real.get(campo), base_acum_real)
        legenda_margem = f"Margem — Mês Orç. {m1} · Mês Real. {m2} · Acum. Orç. {m3} · Acum. Real. {m4}"

    return fig, legenda_margem


c1, c2 = st.columns(2)
fig, _ = _grafico_kpi("Receita Bruta", "receita_bruta")
c1.plotly_chart(fig, use_container_width=True)
fig, legenda = _grafico_kpi("Lucro Bruto", "margem_bruta", campo_margem_base="receita_bruta")
c2.plotly_chart(fig, use_container_width=True)
if legenda:
    c2.caption(legenda)

c3, c4 = st.columns(2)
fig, legenda = _grafico_kpi("EBITDA", "ebitda", campo_margem_base="receita_bruta")
c3.plotly_chart(fig, use_container_width=True)
if legenda:
    c3.caption(legenda)
fig, legenda = _grafico_kpi("LAIR", "lair", campo_margem_base="receita_bruta")
c4.plotly_chart(fig, use_container_width=True)
if legenda:
    c4.caption(legenda)

st.divider()

# ------------------------------------------------------------------
# DRE — Mês e Acumulado (duas tabelas empilhadas, faixa lateral verde,
# grupos de coluna verde-escuro para valores reportados / cinza para
# colunas derivadas, mês a mês no Acumulado — fiel à página 5 da
# apresentação de referência, incluindo "Realizado 2025"/"25x26" (fonte:
# RESULTADOS 2025.xlsx, ver carregar_realizado_2025_mensal em dados.py).
# ------------------------------------------------------------------
st.markdown("<div class='quebra-pagina'></div>", unsafe_allow_html=True)
st.header("DRE — Mês e Acumulado")

base_av_mes = dre_mes_real.get("receita_bruta")
base_av_acum = dre_acum_real.get("receita_bruta")
base_av_2025_mes = dre_mes_2025.get("receita_bruta") if dre_mes_2025 else None
base_av_2025_acum = dre_acum_2025.get("receita_bruta") if dre_acum_2025 else None

TH_VALOR = f"padding:6px 10px; text-align:right; background-color:{VERDE_ESCURO}; color:white; font-weight:700; white-space:nowrap;"
TH_DERIVADO = f"padding:6px 10px; text-align:right; background-color:{VERDE_DERIVADO_HEADER}; color:white; font-weight:700; white-space:nowrap;"
TH_GRUPO_VALOR = f"text-align:center; padding:6px; background-color:{VERDE_ESCURO}; color:white; font-weight:700;"
TH_GRUPO_DERIVADO = f"text-align:center; padding:6px; background-color:{VERDE_DERIVADO_HEADER}; color:white; font-weight:700;"
TH_ROTULO = f"text-align:left; padding:6px 12px; background-color:{VERDE_ESCURO}; color:white;"


def _td(conteudo, extra="", classe="") -> str:
    return f"<td class='{classe}' style='padding:6px 10px; text-align:right; white-space:nowrap; {extra}'>{conteudo}</td>"


def _td_valor(valor, extra="", classe="") -> str:
    cor = f"color:{VERMELHO};" if (valor or 0) < 0 else ""
    return _td(format_brl_md(valor), extra + cor, classe)


def _celula_av(valor, base, disponivel=True, extra="") -> str:
    texto = format_pct_av(valor, base) if disponivel else "N/D"
    return _td(texto, f"background-color:{VERDE_DERIVADO_TINT};" + extra)


def _espacador_th() -> str:
    # Gap físico (~10% da largura de uma célula) pra separar blocos de
    # colunas de verdade, sem nenhuma cor (branco sólido, não "transparent"
    # — o fundo por trás não é garantido branco) — pedido do usuário,
    # 2026-10-21.
    return "<th style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></th>"


def _espacador_td() -> str:
    return "<td style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></td>"


def _celulas_delta(real, orc, destaque: bool) -> str:
    delta = (real - orc) if orc is not None else None
    ah = _variacao_pct(real, orc)
    if destaque:
        cor = "#FF7A7A" if (delta or 0) < 0 else "#FFFFFF"
        estilo = f"background-color:{VERDE_ESCURO}; color:{cor};"
    else:
        cor = VERMELHO if (delta or 0) < 0 else "#1C7C3E"
        estilo = f"color:{cor}; background-color:{VERDE_DERIVADO_TINT};"
    texto_delta = format_brl_md(delta) if delta is not None else "N/D"
    texto_ah = format_pct(ah) if ah is not None else "N/D"
    return _td(texto_delta, estilo) + _td(texto_ah, estilo)


# --- Tabela do Mês ---------------------------------------------------
linhas_mes_html = []
for nome, campo, destaque in LINHAS_DRE_DEF:
    real_mes = dre_mes_real[campo]
    orc_mes = dre_mes_orc.get(campo)
    real_2025_mes = dre_mes_2025.get(campo) if dre_mes_2025 else None
    estilo_linha = "font-weight:700; background-color:#EAF2E0;" if destaque else "background-color:#FFFFFF;"
    linhas_mes_html.append(
        f"<tr style='{estilo_linha}'>"
        f"<td style='padding:6px 12px; white-space:nowrap;'>{nome}</td>"
        + _td_valor(real_mes)
        + _celula_av(real_mes, base_av_mes)
        + _td_valor(orc_mes)
        + _celula_av(orc_mes, base_av_mes, disponivel=orc_mes is not None)
        + _celulas_delta(real_mes, orc_mes, destaque)
        + _td_valor(real_2025_mes)
        + _celula_av(real_2025_mes, base_av_2025_mes, disponivel=real_2025_mes is not None)
        + _celulas_delta(real_mes, real_2025_mes, destaque)
        + "</tr>"
    )
    if campo in LINHAS_MARGEM:
        m_real = format_pct_av(real_mes, base_av_mes)
        m_orc = format_pct_av(orc_mes, base_av_mes) if orc_mes is not None else "N/D"
        m_2025 = format_pct_av(real_2025_mes, base_av_2025_mes) if real_2025_mes is not None else "N/D"
        linhas_mes_html.append(
            "<tr style='font-style:italic; color:#555; background-color:#F7F9F4;'>"
            f"<td style='padding:4px 12px 4px 24px;'>{LINHAS_MARGEM[campo]}</td>"
            + _td(m_real) + _td("") + _td(m_orc) + _td("") + _td("") + _td("")
            + _td(m_2025) + _td("") + _td("") + _td("")
            + "</tr>"
        )

tabela_mes_html = (
    # Sem width:100% de propósito — essa tabela tem bem menos colunas que a
    # Acumulado (que precisa ser larga pro detalhamento mês a mês); se
    # esticasse pra ocupar a mesma largura do container, as colunas ficariam
    # com vãos enormes e sem proporção com a tabela de baixo.
    "<table style='border-collapse:collapse; font-size:0.85rem; color:#1a1a1a;'>"
    "<tr><th></th>"
    f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Realizado</th>"
    f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Orçado 2026</th>"
    f"<th colspan='2' style='{TH_GRUPO_DERIVADO}'>Real. x Orç.</th>"
    f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Realizado 2025</th>"
    f"<th colspan='2' style='{TH_GRUPO_DERIVADO}'>25x26</th>"
    "</tr>"
    f"<tr><th style='{TH_ROTULO}'>DRE - Engenharia</th>"
    f"<th style='{TH_VALOR}'>{nome_mes}/{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
    f"<th style='{TH_VALOR}'>{nome_mes}/{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
    f"<th style='{TH_DERIVADO}'>▲</th><th style='{TH_DERIVADO}'>A.H.%</th>"
    f"<th style='{TH_VALOR}'>{nome_mes}/{str(ano - 1)[2:]}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
    f"<th style='{TH_DERIVADO}'>▲</th><th style='{TH_DERIVADO}'>A.H.%</th>"
    "</tr>"
    + "".join(linhas_mes_html)
    + "</table>"
)

st.markdown(
    f"<div class='tabela-dre-wrapper'>{render_tabela_com_faixa(f'{nome_mes}/{ano}', tabela_mes_html)}</div>",
    unsafe_allow_html=True,
)

# --- Tabela do Acumulado (com detalhamento mês a mês do Realizado) --
meses_do_ano = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= mes_ref]
dre_por_mes = {m: calcular_dre(df_real[df_real["Mes"] == m]) for m in meses_do_ano}

linhas_acum_html = []
for nome, campo, destaque in LINHAS_DRE_DEF:
    real_acum = dre_acum_real[campo]
    orc_acum = dre_acum_orc.get(campo)
    real_2025_acum = dre_acum_2025.get(campo) if dre_acum_2025 else None
    estilo_linha = "font-weight:700; background-color:#EAF2E0;" if destaque else "background-color:#FFFFFF;"
    celulas_meses = "".join(_td_valor(dre_por_mes[m][campo], classe="col-mes-detalhe") for m in meses_do_ano)
    linhas_acum_html.append(
        f"<tr style='{estilo_linha}'>"
        f"<td style='padding:6px 12px; white-space:nowrap;'>{nome}</td>"
        + celulas_meses
        + _espacador_td()
        + _td_valor(real_acum)
        + _celula_av(real_acum, base_av_acum)
        + _td_valor(orc_acum)
        + _celula_av(orc_acum, base_av_acum, disponivel=orc_acum is not None)
        + _celulas_delta(real_acum, orc_acum, destaque)
        + _td_valor(real_2025_acum)
        + _celula_av(real_2025_acum, base_av_2025_acum, disponivel=real_2025_acum is not None)
        + _celulas_delta(real_acum, real_2025_acum, destaque)
        + "</tr>"
    )
    if campo in LINHAS_MARGEM:
        celulas_margem_meses = "".join(
            _td(format_pct_av(dre_por_mes[m][campo], dre_por_mes[m].get("receita_bruta")), classe="col-mes-detalhe")
            for m in meses_do_ano
        )
        m_real = format_pct_av(real_acum, base_av_acum)
        m_orc = format_pct_av(orc_acum, base_av_acum) if orc_acum is not None else "N/D"
        m_2025 = format_pct_av(real_2025_acum, base_av_2025_acum) if real_2025_acum is not None else "N/D"
        linhas_acum_html.append(
            "<tr style='font-style:italic; color:#555; background-color:#F7F9F4;'>"
            f"<td style='padding:4px 12px 4px 24px;'>{LINHAS_MARGEM[campo]}</td>"
            + celulas_margem_meses
            + _espacador_td()
            + _td(m_real) + _td("") + _td(m_orc) + _td("") + _td("") + _td("")
            + _td(m_2025) + _td("") + _td("") + _td("")
            + "</tr>"
        )

cabecalho_meses = "".join(
    f"<th class='col-mes-detalhe' style='{TH_VALOR}'>{MESES_PT[m.month]}/{str(m.year)[2:]}</th>" for m in meses_do_ano
)

tabela_acum_html = (
    "<table style='width:100%; border-collapse:collapse; font-size:0.85rem; color:#1a1a1a;'>"
    "<tr><th></th>"
    f"<th class='col-mes-detalhe' colspan='{max(len(meses_do_ano), 1)}' style='{TH_GRUPO_VALOR}'>Realizado</th>"
    "<th></th>"
    f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Acumulado</th>"
    f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Orçado</th>"
    f"<th colspan='2' style='{TH_GRUPO_DERIVADO}'>Real. x Orç.</th>"
    f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Acumulado 2025</th>"
    f"<th colspan='2' style='{TH_GRUPO_DERIVADO}'>25x26</th>"
    "</tr>"
    f"<tr><th style='{TH_ROTULO}'>DRE - Engenharia</th>"
    + cabecalho_meses
    + _espacador_th()
    + f"<th style='{TH_VALOR}'>{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
    + f"<th style='{TH_VALOR}'>{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
    + f"<th style='{TH_DERIVADO}'>▲</th><th style='{TH_DERIVADO}'>A.H.%</th>"
    + f"<th style='{TH_VALOR}'>{ano - 1}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
    + f"<th style='{TH_DERIVADO}'>▲</th><th style='{TH_DERIVADO}'>A.H.%</th>"
    "</tr>"
    + "".join(linhas_acum_html)
    + "</table>"
)

st.markdown(
    f"<div class='tabela-dre-wrapper'>{render_tabela_com_faixa(f'ACUMULADO/{ano}', tabela_acum_html)}</div>",
    unsafe_allow_html=True,
)

if revisao_sel == "REV03" and despesa_provisoria:
    st.caption(
        "⚠️ Orçado de Despesa da REV03: Jan-Set/26 espelham o próprio Realizado (sem Δ) — a "
        "REV03 não prevê esses meses, já tinham acontecido quando ela foi fechada (igual ao "
        "DASH_DIRETORIA). De Out/26 em diante (a janela que a REV03 prevê de verdade), Despesa "
        "Administrativa e Financeira já vêm completas do orçamento próprio dela "
        "(ONEPAGE_REV03.xlsx), com Δ real contra o Realizado; só o Imposto de Renda desses meses "
        "**ainda é emprestado da REV01**, até chegar uma fonte própria."
    )
elif revisao_sel == "REV02" and despesa_provisoria:
    st.caption(
        "⚠️ Orçado de Despesa da REV02: Jan-Jun/26 espelham o próprio Realizado (sem Δ) — a "
        "REV02 não prevê esses meses, já tinham acontecido quando ela foi fechada. De Jul/26 em "
        "diante (a janela que a REV02 prevê de verdade), a Despesa (Administrativa + Comercial + "
        "Operação) já vem completa do orçamento próprio dela (DESPESA REV02.xlsx), com Δ real "
        "contra o Realizado; só a Despesa Financeira e o Imposto de Renda desses meses **ainda "
        "são emprestados da REV01**, até chegar uma fonte própria."
    )
elif despesa_provisoria:
    st.caption(
        f"⚠️ A {revisao_sel} ainda não tem Despesa Administrativa/Financeira própria lançada — "
        "Receita/Custo/Margem Bruta já são dessa revisão, mas Despesa/EBITDA/LAIR/Lucro Líquido "
        "abaixo são **provisórios, emprestados da REV01**, até a Despesa real da "
        f"{revisao_sel} chegar."
    )
elif dre_mes_orc.get("despesa_adm") is None:
    st.caption(
        "⚠️ Despesa Administrativa/Financeira, EBITDA, LAIR, Imposto de Renda e Lucro Líquido aparecem "
        "como N/D para essa Revisão/Cenário — ainda não temos uma base de Previsto completa até Lucro "
        "Líquido para ela (hoje só REV00 e REV01-Otimista têm essa cascata)."
    )

st.divider()

# ------------------------------------------------------------------
# DRE — Forecast (ano inteiro: Realizado fechado + Forecast preenchido na
# página "Forecast" — sempre o último estado SALVO lá, não depende de
# estar com a página aberta). Some abaixo do Acumulado de propósito,
# pedido do usuário pra fechar a visão do ano completo na página
# principal antes de divulgar o link.
# ------------------------------------------------------------------
st.header(f"DRE — Forecast {ano}")

meses_fc_app = meses_forecast(df_real, ano)
if not meses_fc_app:
    st.success(f"Todos os meses de {ano} já têm Realizado fechado — nada em aberto pra prever.")
else:
    revisao_atual_forecast_app = revisao_atual_forecast(df_real, revisoes, ano)
    ultimo_mes_real_app = df_real.loc[df_real["Mes"].dt.year == ano, "Mes"].max()
    meses_realizado_app = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= ultimo_mes_real_app]

    receita_por_linha_mes_app, lucro_por_linha_mes_app, nomes_linha_app = dados_forecast_salvo(meses_fc_app)
    erros_forecast_app = []
    for mes in meses_fc_app:
        chave_mes = mes.strftime("%Y-%m")
        erros_forecast_app += validar_lucro_bruto(
            receita_por_linha_mes_app[chave_mes], lucro_por_linha_mes_app[chave_mes], nomes_linha_app,
            f"{MESES_PT[mes.month]}/{str(mes.year)[2:]}",
        )

    if erros_forecast_app:
        st.warning(
            "⚠️ O Forecast salvo ainda tem pendência de preenchimento — corrija na página **Forecast** "
            "pra essa DRE aparecer aqui:\n\n" + "\n".join(f"- {e}" for e in erros_forecast_app)
        )
    else:
        dre_forecast_por_mes = fechar_dre_ano(
            df_real, df_previsto, df_refinado, revisao_atual_forecast_app,
            meses_realizado_app, meses_fc_app, receita_por_linha_mes_app, lucro_por_linha_mes_app, nomes_linha_app,
        )
        dre_forecast_total_ano = {campo: sum(dre_forecast_por_mes[m][campo] for m in dre_forecast_por_mes) for _, campo, _ in LINHAS_DRE_DEF}
        base_av_forecast_ano = dre_forecast_total_ano["receita_bruta"]

        # Meta Otimista (META ANO SUPERUS.xlsx) — só como colunas de
        # referência (Meta + Δ Forecast-Meta) no fim da mesma tabela, não
        # entra em nenhum cálculo. Colunas mais estreitas que a DRE Mês/
        # Acumulado acima (tabela com mais colunas, Jan-Dez + Total + Meta +
        # Δ) — usa helpers próprios (_td_fc/_td_valor_fc) em vez dos globais
        # _td/_td_valor, pra não estreitar a tabela Mês/Acumulado também.
        meta_mensal_app = carregar_meta_mensal("Otimista")
        meta_total_ano_app = {
            campo: sum(meta_mensal_app[m.month][campo] for m in dre_forecast_por_mes) for _, campo, _ in LINHAS_DRE_DEF
        }
        TH_VALOR_FC = f"padding:6px 6px; text-align:right; background-color:{VERDE_ESCURO}; color:white; font-weight:700; white-space:nowrap;"
        TH_META = f"padding:6px 6px; text-align:right; background-color:#5B7B4A; color:white; font-weight:700; white-space:nowrap;"
        TH_DELTA = TH_META

        def _td_fc(conteudo, extra="") -> str:
            return f"<td style='padding:4px 6px; text-align:right; white-space:nowrap; {extra}'>{conteudo}</td>"

        def _td_valor_fc(valor, extra="") -> str:
            cor = f"color:{VERMELHO};" if (valor or 0) < 0 else ""
            return _td_fc(format_brl_md(valor), extra + cor)

        linhas_forecast_html = []
        for nome, campo, destaque in LINHAS_DRE_DEF:
            estilo_linha = "font-weight:700; background-color:#EAF2E0;" if destaque else "background-color:#FFFFFF;"
            celulas = "".join(_td_valor_fc(dre_forecast_por_mes[m][campo]) for m in dre_forecast_por_mes)
            celula_total = _td_valor_fc(dre_forecast_total_ano[campo])
            celula_meta = _td_valor_fc(meta_total_ano_app[campo])
            celula_delta = _td_valor_fc(dre_forecast_total_ano[campo] - meta_total_ano_app[campo])
            linhas_forecast_html.append(
                f"<tr style='{estilo_linha}'><td style='padding:6px 10px; white-space:nowrap;'>{nome}</td>"
                f"{celulas}{celula_total}{_espacador_td()}{celula_meta}{celula_delta}</tr>"
            )
            if campo in LINHAS_MARGEM:
                celulas_pct = "".join(
                    _td_fc(format_pct_av(dre_forecast_por_mes[m][campo], dre_forecast_por_mes[m]["receita_bruta"]))
                    for m in dre_forecast_por_mes
                )
                celula_pct_total = _td_fc(format_pct_av(dre_forecast_total_ano[campo], base_av_forecast_ano))
                pct_meta = (
                    meta_total_ano_app[campo] / meta_total_ano_app["receita_bruta"]
                    if meta_total_ano_app["receita_bruta"]
                    else None
                )
                pct_forecast = dre_forecast_total_ano[campo] / base_av_forecast_ano if base_av_forecast_ano else None
                celula_pct_meta = _td_fc(format_pct_av(meta_total_ano_app[campo], meta_total_ano_app["receita_bruta"]))
                delta_pp = None if pct_meta is None or pct_forecast is None else pct_forecast - pct_meta
                celula_pct_delta = _td_fc(format_pct(delta_pp))
                linhas_forecast_html.append(
                    "<tr style='font-style:italic; color:#555; background-color:#F7F9F4;'>"
                    f"<td style='padding:4px 10px 4px 20px;'>{LINHAS_MARGEM[campo]}</td>"
                    f"{celulas_pct}{celula_pct_total}{_espacador_td()}{celula_pct_meta}{celula_pct_delta}</tr>"
                )

        cabecalho_forecast = "".join(
            f"<th style='{TH_VALOR_FC}'>{MESES_PT[m.month]}/{str(m.year)[2:]}</th>" for m in dre_forecast_por_mes
        )
        tabela_forecast_html = (
            "<table style='width:100%; border-collapse:collapse; font-size:0.8rem; color:#1a1a1a;'>"
            f"<tr><th style='{TH_ROTULO}'>DRE - Engenharia</th>{cabecalho_forecast}<th style='{TH_VALOR_FC}'>Total {ano}</th>"
            f"{_espacador_th()}<th style='{TH_META}'>Meta Otimista</th><th style='{TH_DELTA}'>Δ Forecast-Meta</th></tr>"
            + "".join(linhas_forecast_html)
            + "</table>"
        )
        st.markdown(
            f"<div class='tabela-dre-wrapper'>{render_tabela_com_faixa(f'FORECAST {ano}', tabela_forecast_html, largura_total=True)}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Jan-{MESES_PT[meses_realizado_app[-1].month]}/{ano} = Realizado fechado; "
            f"{MESES_PT[meses_fc_app[0].month]}-{MESES_PT[meses_fc_app[-1].month]}/{ano} = Forecast "
            "(preenchido na página **Forecast**, Revisão em vigor "
            f"**{revisao_atual_forecast_app}** pra Despesa). **Meta Otimista/Δ** = DRE anual alvo "
            "(META ANO SUPERUS.xlsx, Cenário Otimista) pro ano inteiro, só como referência — não "
            "entra em nenhum cálculo; Δ = Forecast menos Meta."
        )

st.divider()

# ------------------------------------------------------------------
# Receita e Despesa por Categoria (Centro de Custo classificado)
# ------------------------------------------------------------------
st.markdown("<div class='quebra-pagina'></div>", unsafe_allow_html=True)
st.header("Receita e Despesa por Categoria")
st.caption(
    "Quebra por categoria de Centro de Custo, a partir da classificação feita em "
    "\"Classificar Centros de Custo\". Categorias usadas numa categoria mas que "
    "cobrem um Centro de Custo ainda sem classificação aparecem como "
    "\"Não classificado\"."
)


receita_real_mes_cat = receita_por_categoria_realizado(df_real, mes_ref, mes_ref)
receita_real_acum_cat = receita_por_categoria_realizado(df_real, mes_ini_ano, mes_ref)
receita_orc_mes_cat = receita_por_categoria_previsto(df_refinado_detalhado, revisao_sel, cenario_sel, mes_ref, mes_ref)
receita_orc_acum_cat = receita_por_categoria_previsto(df_refinado_detalhado, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)

def _config_colunas_moeda(*nomes) -> dict:
    # format="localized" usa o idioma do NAVEGADOR de quem acessa (não do
    # servidor) pra decidir separador de milhar/decimal — pra um usuário com
    # o navegador em pt-BR já sai com ponto de milhar, igual ao resto do
    # app. Crucial: mantém o valor como número de verdade, então clicar no
    # cabeçalho pra ordenar ordena pelo VALOR, não pelo texto formatado
    # (era isso que causava "969.336" vir antes de "84.184").
    return {nome: st.column_config.NumberColumn(nome, format="localized") for nome in nomes}


def _tabela_discreta_categoria(serie_real_mes, serie_orc_mes, serie_real_acum, serie_orc_acum) -> pd.DataFrame:
    categorias = sorted(
        set(serie_real_mes.index)
        | set(serie_orc_mes.index if serie_orc_mes is not None else [])
        | set(serie_real_acum.index)
        | set(serie_orc_acum.index if serie_orc_acum is not None else []),
        key=lambda c: -(serie_real_acum.get(c, 0) or 0),
    )

    def _v(serie, cat):
        return float("nan") if serie is None else float(serie.get(cat, 0.0))

    linhas = [
        {
            "Categoria": cat,
            f"Orçado {nome_mes}/{ano}": _v(serie_orc_mes, cat),
            f"Realizado {nome_mes}/{ano}": _v(serie_real_mes, cat),
            f"Orçado Acum. {ano}": _v(serie_orc_acum, cat),
            f"Realizado Acum. {ano}": _v(serie_real_acum, cat),
        }
        for cat in categorias
    ]
    return pd.DataFrame(linhas)


def _tabela_cc_da_categoria(categoria, detalhe_real_mes, detalhe_orc_mes, detalhe_real_acum, detalhe_orc_acum) -> pd.DataFrame:
    """Uma linha por Centro de Custo dentro da categoria, com os 4 valores."""

    def _filtra(df):
        # Agrupa por nome (soma) — dois Códigos de Centro de Custo distintos
        # às vezes compartilham o mesmo nome descritivo, o que quebraria uma
        # busca direta por nome (índice duplicado).
        if df is None or df.empty:
            return pd.Series(dtype=float)
        sub = df.loc[df["Categoria"] == categoria]
        return sub.groupby("Centro de Custo")["Valor"].sum()

    f_real_mes, f_orc_mes = _filtra(detalhe_real_mes), _filtra(detalhe_orc_mes)
    f_real_acum, f_orc_acum = _filtra(detalhe_real_acum), _filtra(detalhe_orc_acum)

    ccs = sorted(
        set(f_real_mes.index) | set(f_orc_mes.index) | set(f_real_acum.index) | set(f_orc_acum.index),
        key=lambda cc: -abs(f_real_acum.get(cc, 0.0)),
    )

    def _v(serie, cc, disponivel):
        if not disponivel:
            return float("nan")
        return float(serie.get(cc, 0.0))

    tem_orc_mes = detalhe_orc_mes is not None
    tem_orc_acum = detalhe_orc_acum is not None
    linhas = [
        {
            "Centro de Custo": cc,
            f"Orçado {nome_mes}/{ano}": _v(f_orc_mes, cc, tem_orc_mes),
            f"Realizado {nome_mes}/{ano}": _v(f_real_mes, cc, True),
            f"Orçado Acum. {ano}": _v(f_orc_acum, cc, tem_orc_acum),
            f"Realizado Acum. {ano}": _v(f_real_acum, cc, True),
        }
        for cc in ccs
    ]
    return pd.DataFrame(linhas)


def _render_categoria_com_drilldown(
    serie_real_mes, serie_orc_mes, serie_real_acum, serie_orc_acum,
    detalhe_real_mes, detalhe_orc_mes, detalhe_real_acum, detalhe_orc_acum,
):
    colunas_moeda = _config_colunas_moeda(
        f"Orçado {nome_mes}/{ano}", f"Realizado {nome_mes}/{ano}",
        f"Orçado Acum. {ano}", f"Realizado Acum. {ano}",
    )
    st.dataframe(
        _tabela_discreta_categoria(serie_real_mes, serie_orc_mes, serie_real_acum, serie_orc_acum),
        hide_index=True,
        use_container_width=True,
        column_config=colunas_moeda,
    )
    categorias = sorted(
        set(serie_real_mes.index)
        | set(serie_orc_mes.index if serie_orc_mes is not None else [])
        | set(serie_real_acum.index)
        | set(serie_orc_acum.index if serie_orc_acum is not None else []),
        key=lambda c: -(serie_real_acum.get(c, 0) or 0),
    )
    st.caption("Abra uma categoria abaixo pra ver os Centros de Custo que a compõem:")
    for cat in categorias:
        with st.expander(f"🔎 {cat}"):
            st.dataframe(
                _tabela_cc_da_categoria(cat, detalhe_real_mes, detalhe_orc_mes, detalhe_real_acum, detalhe_orc_acum),
                hide_index=True,
                use_container_width=True,
                column_config=colunas_moeda,
            )


st.subheader("Receita Bruta por Categoria")
col_rec_mes, col_rec_acum = st.columns(2)
col_rec_mes.plotly_chart(
    grafico_categoria_empilhado(
        f"Receita Bruta (R$/Mil) — {nome_mes}/{ano}", receita_orc_mes_cat, receita_real_mes_cat, format_brl_compacto
    ),
    use_container_width=True,
)
col_rec_acum.plotly_chart(
    grafico_categoria_empilhado(
        f"Receita Bruta (R$/Mil) — Acumulado {ano}", receita_orc_acum_cat, receita_real_acum_cat, format_brl_compacto
    ),
    use_container_width=True,
)
col_rec_mes.markdown(
    render_caixa_narrativa(
        f"ANÁLISE DE {nome_mes}/{ano}",
        gerar_analise(
            "Receita Bruta", f"{nome_mes}/{ano}",
            dre_mes_real["receita_bruta"], dre_mes_orc.get("receita_bruta"),
            receita_real_mes_cat, receita_orc_mes_cat, favoravel_se_maior=True,
        ),
    ),
    unsafe_allow_html=True,
)
col_rec_acum.markdown(
    render_caixa_narrativa(
        "ANÁLISE DE ACUMULADO",
        gerar_analise(
            "Receita Bruta Acumulada", f"Acumulado {ano}",
            dre_acum_real["receita_bruta"], dre_acum_orc.get("receita_bruta"),
            receita_real_acum_cat, receita_orc_acum_cat, favoravel_se_maior=True,
        ),
    ),
    unsafe_allow_html=True,
)
receita_detalhe_real_mes = receita_por_cc_realizado(df_real, mes_ref, mes_ref)
receita_detalhe_real_acum = receita_por_cc_realizado(df_real, mes_ini_ano, mes_ref)
receita_detalhe_orc_mes = receita_por_cc_previsto(df_refinado_detalhado, tabela_dimensao, revisao_sel, cenario_sel, mes_ref, mes_ref)
receita_detalhe_orc_acum = receita_por_cc_previsto(df_refinado_detalhado, tabela_dimensao, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)

with st.expander("Ver valores em tabela (Receita Bruta por Categoria)"):
    _render_categoria_com_drilldown(
        receita_real_mes_cat, receita_orc_mes_cat, receita_real_acum_cat, receita_orc_acum_cat,
        receita_detalhe_real_mes, receita_detalhe_orc_mes, receita_detalhe_real_acum, receita_detalhe_orc_acum,
    )

# ------------------------------------------------------------------
# Lucro Bruto por Categoria (= Receita Bruta por Categoria - Custo por
# Categoria, mesma classificação) — página 9 da apresentação de referência.
# ------------------------------------------------------------------
def _soma_serie_opcional(a, b):
    return None if a is None or b is None else a.add(b, fill_value=0.0)


def _combinar_detalhe(a, b):
    if a is None or b is None:
        return None
    return pd.concat([a, b], ignore_index=True).groupby(["Categoria", "Codigo", "Centro de Custo"], as_index=False)["Valor"].sum()


# Lucro Bruto = Receita Líquida (Bruta + Imposto) + Custo — mesma definição
# da DRE (margem_bruta), não só Receita Bruta + Custo.
custo_real_mes_cat = custo_por_categoria_realizado(df_real, mes_ref, mes_ref)
custo_real_acum_cat = custo_por_categoria_realizado(df_real, mes_ini_ano, mes_ref)
custo_orc_mes_cat = custo_por_categoria_previsto(df_refinado_detalhado, revisao_sel, cenario_sel, mes_ref, mes_ref)
custo_orc_acum_cat = custo_por_categoria_previsto(df_refinado_detalhado, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)
imposto_real_mes_cat = imposto_por_categoria_realizado(df_real, mes_ref, mes_ref)
imposto_real_acum_cat = imposto_por_categoria_realizado(df_real, mes_ini_ano, mes_ref)
imposto_orc_mes_cat = imposto_por_categoria_previsto(df_refinado_detalhado, revisao_sel, cenario_sel, mes_ref, mes_ref)
imposto_orc_acum_cat = imposto_por_categoria_previsto(df_refinado_detalhado, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)

lucro_real_mes_cat = receita_real_mes_cat.add(imposto_real_mes_cat, fill_value=0.0).add(custo_real_mes_cat, fill_value=0.0)
lucro_real_acum_cat = receita_real_acum_cat.add(imposto_real_acum_cat, fill_value=0.0).add(custo_real_acum_cat, fill_value=0.0)
lucro_orc_mes_cat = _soma_serie_opcional(_soma_serie_opcional(receita_orc_mes_cat, imposto_orc_mes_cat), custo_orc_mes_cat)
lucro_orc_acum_cat = _soma_serie_opcional(_soma_serie_opcional(receita_orc_acum_cat, imposto_orc_acum_cat), custo_orc_acum_cat)

st.subheader("Lucro Bruto por Categoria")
col_lb_mes, col_lb_acum = st.columns(2)
col_lb_mes.plotly_chart(
    grafico_categoria_empilhado(
        f"Lucro Bruto (R$/Mil) — {nome_mes}/{ano}", lucro_orc_mes_cat, lucro_real_mes_cat, format_brl_compacto
    ),
    use_container_width=True,
)
col_lb_acum.plotly_chart(
    grafico_categoria_empilhado(
        f"Lucro Bruto (R$/Mil) — Acumulado {ano}", lucro_orc_acum_cat, lucro_real_acum_cat, format_brl_compacto
    ),
    use_container_width=True,
)
col_lb_mes.markdown(
    render_caixa_narrativa(
        f"ANÁLISE DE {nome_mes}/{ano}",
        gerar_analise(
            "Lucro Bruto", f"{nome_mes}/{ano}",
            lucro_real_mes_cat.sum(), lucro_orc_mes_cat.sum() if lucro_orc_mes_cat is not None else None,
            lucro_real_mes_cat, lucro_orc_mes_cat, favoravel_se_maior=True,
        ),
    ),
    unsafe_allow_html=True,
)
col_lb_acum.markdown(
    render_caixa_narrativa(
        "ANÁLISE DE ACUMULADO",
        gerar_analise(
            "Lucro Bruto Acumulado", f"Acumulado {ano}",
            lucro_real_acum_cat.sum(), lucro_orc_acum_cat.sum() if lucro_orc_acum_cat is not None else None,
            lucro_real_acum_cat, lucro_orc_acum_cat, favoravel_se_maior=True,
        ),
    ),
    unsafe_allow_html=True,
)

lucro_detalhe_real_mes = _combinar_detalhe(
    _combinar_detalhe(receita_detalhe_real_mes, imposto_por_cc_realizado(df_real, mes_ref, mes_ref)),
    custo_por_cc_realizado(df_real, mes_ref, mes_ref),
)
lucro_detalhe_real_acum = _combinar_detalhe(
    _combinar_detalhe(receita_detalhe_real_acum, imposto_por_cc_realizado(df_real, mes_ini_ano, mes_ref)),
    custo_por_cc_realizado(df_real, mes_ini_ano, mes_ref),
)
lucro_detalhe_orc_mes = _combinar_detalhe(
    _combinar_detalhe(
        receita_detalhe_orc_mes,
        imposto_por_cc_previsto(df_refinado_detalhado, tabela_dimensao, revisao_sel, cenario_sel, mes_ref, mes_ref),
    ),
    custo_por_cc_previsto(df_refinado_detalhado, tabela_dimensao, revisao_sel, cenario_sel, mes_ref, mes_ref),
)
lucro_detalhe_orc_acum = _combinar_detalhe(
    _combinar_detalhe(
        receita_detalhe_orc_acum,
        imposto_por_cc_previsto(df_refinado_detalhado, tabela_dimensao, revisao_sel, cenario_sel, mes_ini_ano, mes_ref),
    ),
    custo_por_cc_previsto(df_refinado_detalhado, tabela_dimensao, revisao_sel, cenario_sel, mes_ini_ano, mes_ref),
)

with st.expander("Ver valores em tabela (Lucro Bruto por Categoria)"):
    _render_categoria_com_drilldown(
        lucro_real_mes_cat, lucro_orc_mes_cat, lucro_real_acum_cat, lucro_orc_acum_cat,
        lucro_detalhe_real_mes, lucro_detalhe_orc_mes, lucro_detalhe_real_acum, lucro_detalhe_orc_acum,
    )

# Despesa vem negativa (convenção "dedução = negativo") — inverte pra mostrar
# magnitude positiva (igual à apresentação de referência).
despesa_real_mes_cat = -despesa_por_categoria_realizado(df_real, mes_ref, mes_ref)
despesa_real_acum_cat = -despesa_por_categoria_realizado(df_real, mes_ini_ano, mes_ref)
despesa_orc_mes_cat = despesa_por_categoria_previsto(df_previsto, df_real, revisao_sel, cenario_sel, mes_ref, mes_ref)
despesa_orc_acum_cat = despesa_por_categoria_previsto(df_previsto, df_real, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)
if despesa_orc_mes_cat is not None:
    despesa_orc_mes_cat = -despesa_orc_mes_cat
if despesa_orc_acum_cat is not None:
    despesa_orc_acum_cat = -despesa_orc_acum_cat

st.subheader("Despesa Administrativa por Categoria")
col_desp_mes, col_desp_acum = st.columns(2)
col_desp_mes.plotly_chart(
    grafico_categoria_empilhado(
        f"Despesa Total (R$/Mil) — {nome_mes}/{ano}", despesa_orc_mes_cat, despesa_real_mes_cat, format_brl_compacto
    ),
    use_container_width=True,
)
col_desp_acum.plotly_chart(
    grafico_categoria_empilhado(
        f"Despesa Total (R$/Mil) — Acumulado {ano}", despesa_orc_acum_cat, despesa_real_acum_cat, format_brl_compacto
    ),
    use_container_width=True,
)
despesa_orc_mes_total = dre_mes_orc.get("despesa_adm")
despesa_orc_acum_total = dre_acum_orc.get("despesa_adm")
col_desp_mes.markdown(
    render_caixa_narrativa(
        f"ANÁLISE DE {nome_mes}/{ano}",
        gerar_analise(
            # Magnitude positiva (-1 * valor), igual à convenção já usada nas
            # séries de categoria acima — "Despesa real > Orçado" tem que dar
            # delta positivo (gastou mais) pra bater com favoravel_se_maior=False.
            "Despesa Administrativa", f"{nome_mes}/{ano}",
            -dre_mes_real["despesa_adm"],
            -despesa_orc_mes_total if despesa_orc_mes_total is not None else None,
            despesa_real_mes_cat, despesa_orc_mes_cat, favoravel_se_maior=False,
        ),
    ),
    unsafe_allow_html=True,
)
col_desp_acum.markdown(
    render_caixa_narrativa(
        "ANÁLISE DE ACUMULADO",
        gerar_analise(
            "Despesa Administrativa Acumulada", f"Acumulado {ano}",
            -dre_acum_real["despesa_adm"],
            -despesa_orc_acum_total if despesa_orc_acum_total is not None else None,
            despesa_real_acum_cat, despesa_orc_acum_cat, favoravel_se_maior=False,
        ),
    ),
    unsafe_allow_html=True,
)
despesa_detalhe_real_mes = despesa_por_cc_realizado(df_real, mes_ref, mes_ref).assign(Valor=lambda d: -d["Valor"])
despesa_detalhe_real_acum = despesa_por_cc_realizado(df_real, mes_ini_ano, mes_ref).assign(Valor=lambda d: -d["Valor"])
despesa_detalhe_orc_mes = despesa_por_cc_previsto(df_previsto, revisao_sel, cenario_sel, mes_ref, mes_ref)
despesa_detalhe_orc_acum = despesa_por_cc_previsto(df_previsto, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)
if despesa_detalhe_orc_mes is not None:
    despesa_detalhe_orc_mes = despesa_detalhe_orc_mes.assign(Valor=lambda d: -d["Valor"])
if despesa_detalhe_orc_acum is not None:
    despesa_detalhe_orc_acum = despesa_detalhe_orc_acum.assign(Valor=lambda d: -d["Valor"])

with st.expander("Ver valores em tabela (Despesa Total por Categoria)"):
    _render_categoria_com_drilldown(
        despesa_real_mes_cat, despesa_orc_mes_cat, despesa_real_acum_cat, despesa_orc_acum_cat,
        despesa_detalhe_real_mes, despesa_detalhe_orc_mes, despesa_detalhe_real_acum, despesa_detalhe_orc_acum,
    )

# ------------------------------------------------------------------
# Análise de Complexos (páginas 10/11 da apresentação de referência) —
# unidade = Centro de Custo direto (não agrupado em "Complexo" comercial).
# O agrupamento por Complexo cobria só ~32 Centro de Custo de Receita,
# com boa parte caindo em "SEM AGRUPAMENTO"; trocado por Centro de Custo
# puro pra maior cobertura e confiabilidade (sem agrupamento adivinhado).
# ------------------------------------------------------------------
st.markdown("<div class='quebra-pagina'></div>", unsafe_allow_html=True)
st.header("Análise de Complexos")

analise_cpx = AnaliseComplexos(
    df_real, df_refinado_detalhado, tabela_dimensao, mes_ref, mes_ini_ano, revisao_sel, cenario_sel
)
status_cpx = analise_cpx.status_todos()
st.caption(f"Cobre todo Centro de Custo que já apareceu em Receita Bruta (Realizado ou Orçado) — {len(status_cpx)} ao todo.")


def _lista_nomeada(ccs) -> str:
    return " + ".join(analise_cpx.nome(c) for c in sorted(ccs, key=analise_cpx.nome)) if ccs else "nenhum"


def _render_complexos_periodo(badge: str, serie_receita_real, serie_receita_orc, serie_lucro_real, serie_lucro_orc):
    operando = analise_cpx.complexos_operando()

    receita_acima = [c for c in operando if c in serie_receita_orc.index and serie_receita_real.get(c, 0) > serie_receita_orc.get(c, 0)]
    receita_avaliaveis = [c for c in operando if c in serie_receita_orc.index]
    receita_abaixo = [c for c in receita_avaliaveis if c not in receita_acima]

    lucro_positivo = [c for c in operando if serie_lucro_real.get(c, 0) > 0]
    lucro_negativo = [c for c in operando if c not in lucro_positivo]

    lucro_acima = [c for c in operando if c in serie_lucro_orc.index and serie_lucro_real.get(c, 0) > serie_lucro_orc.get(c, 0)]
    lucro_avaliaveis = [c for c in operando if c in serie_lucro_orc.index]
    lucro_abaixo = [c for c in lucro_avaliaveis if c not in lucro_acima]

    from collections import Counter

    col1, col2 = st.columns(2)
    col1.plotly_chart(
        grafico_pizza_status(f"Complexos Totais {badge} -> {len(operando)}", Counter(status_cpx.values())),
        use_container_width=True,
    )
    col2.plotly_chart(
        grafico_pizza_duas_fatias(
            f"Receita Bruta — {badge} -> {len(operando)}",
            "Receita Bruta Acima do Previsto", len(receita_acima),
            "Receita Bruta Abaixo do Previsto", len(receita_abaixo),
        ),
        use_container_width=True,
    )
    col3, col4 = st.columns(2)
    col3.plotly_chart(
        grafico_pizza_duas_fatias(
            f"Lucro Bruto Realizado — {badge} -> {len(operando)}",
            "Lucro Bruto Realizado Positivo", len(lucro_positivo),
            "Lucro Bruto Realizado Negativo", len(lucro_negativo),
        ),
        use_container_width=True,
    )
    col4.plotly_chart(
        grafico_pizza_duas_fatias(
            f"Lucro Bruto x Orçado — {badge} -> {len(operando)}",
            "Lucro Bruto Acima do Previsto", len(lucro_acima),
            "Lucro Bruto Abaixo do Previsto", len(lucro_abaixo),
        ),
        use_container_width=True,
    )
    st.markdown(
        f"- **Lucro Bruto Realizado Negativo** ({len(lucro_negativo)}): {_lista_nomeada(lucro_negativo)}.\n"
        f"- **Lucro Bruto Acima do Previsto** ({len(lucro_acima)}): {_lista_nomeada(lucro_acima)}."
    )


st.subheader(f"{nome_mes}/{ano}")
_render_complexos_periodo(
    f"{nome_mes}/{ano}",
    analise_cpx.receita_real_mes, analise_cpx.receita_orc_mes,
    analise_cpx.lucro_real_mes, analise_cpx.lucro_orc_mes,
)

st.subheader(f"Acumulado {ano}")
_render_complexos_periodo(
    f"{ano}",
    analise_cpx.receita_real_acum, analise_cpx.receita_orc_acum,
    analise_cpx.lucro_real_acum, analise_cpx.lucro_orc_acum,
)
