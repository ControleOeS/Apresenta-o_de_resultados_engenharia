"""Renderização compartilhada de "KPIs" + "DRE — Mês e Acumulado" — extraído
de pagina_resultado.py (Superus) em 2026-11-24, pra poder ser reaproveitado
por ASAP/O&S/Grupo sem duplicar ~350 linhas de HTML/gráfico por segmento.

Só RENDERIZA dicts/DataFrames já calculados — não carrega nem calcula nada
(cada página continua responsável pela sua própria fonte de Realizado/
Previsto e pelas regras de negócio específicas do seu segmento, ex.: o
"Despesa provisória, emprestada da REV01" é uma explicação só da Superus,
então essas legendas continuam em pagina_resultado.py, não aqui)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dados import LINHAS_DRE_DEF, LINHAS_MARGEM, MESES_PT
from estilo import PALETA_SUPERUS, VERMELHO, render_tabela_com_faixa
from formatting import format_brl_compacto, format_brl_md, format_pct, format_pct_av


def _variacao_pct(real, orc):
    if real is None or orc is None or not orc:
        return None
    return (real - orc) / abs(orc)


def _grafico_kpi(
    nome: str, campo: str, dre_mes_orc, dre_mes_real, dre_acum_orc, dre_acum_real, campo_margem_base=None,
    paleta: dict | None = None, detalhe_coligadas: dict | None = None,
):
    paleta = paleta or PALETA_SUPERUS
    rotulos = ["Mês Orç.", "Mês Real.", "Acum. Orç.", "Acum. Real."]
    valores = [dre_mes_orc.get(campo), dre_mes_real.get(campo), dre_acum_orc.get(campo), dre_acum_real.get(campo)]
    cores = [paleta["cor_destaque"], paleta["cor_escura"], paleta["cor_destaque"], paleta["cor_escura"]]
    textos = [format_brl_compacto(v) for v in valores]
    cores_texto = [VERMELHO if (v or 0) < 0 else "#1A1A1A" for v in valores]

    # Só o Grupo passa `detalhe_coligadas` (Superus+ASAP somadas, pedido do
    # usuário 2026-11-24: "deixe a legenda do cursor falando o que o valor
    # daquela barra é referente a cada coligada") — as demais abas (segmento
    # único) continuam com o hover padrão do Plotly (x, y).
    hovertextos = None
    if detalhe_coligadas:
        hovertextos = []
        for i, (rotulo, chave) in enumerate(zip(rotulos, ["mes_orc", "mes_real", "acum_orc", "acum_real"])):
            linhas = [f"<b>{rotulo}</b>", f"Total: {format_brl_compacto(valores[i])}"]
            for nome_coligada, dre_coligada in detalhe_coligadas.get(chave, {}).items():
                linhas.append(f"{nome_coligada}: {format_brl_compacto(dre_coligada.get(campo))}")
            hovertextos.append("<br>".join(linhas))

    var_mes = _variacao_pct(dre_mes_real.get(campo), dre_mes_orc.get(campo))
    var_acum = _variacao_pct(dre_acum_real.get(campo), dre_acum_orc.get(campo))

    valores_validos = [v for v in valores if v is not None]
    maior = max(valores_validos) if valores_validos else 0
    menor = min(valores_validos) if valores_validos else 0
    alcance = max(maior, 0) - min(menor, 0) or abs(maior) or 1
    y_topo = max(maior, 0) + alcance * 0.22
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
            hovertext=hovertextos,
            hoverinfo="text" if hovertextos else None,
        )
    )

    anotacoes = []
    for var, x_real, x_orc in [(var_mes, "Mês Real.", "Mês Orç."), (var_acum, "Acum. Real.", "Acum. Orç.")]:
        if var is None:
            continue
        if round(var, 3) == 0:
            cor_var = "#555555"
            texto_var = "0,0%"
        else:
            cor_var = VERMELHO if var < 0 else "#1C7C3E"
            texto_var = f"{'▲' if var >= 0 else '▼'} {abs(var) * 100:.1f}%".replace(".", ",")
        anotacoes.append(
            dict(x=x_real, y=y_topo, text=texto_var, showarrow=False, font=dict(color=cor_var, size=13, weight=700))
        )

    fig.update_layout(
        title=dict(text=nome, font=dict(size=16, color="#1A1A1A")),
        height=380,
        separators=",.",
        margin=dict(t=70, b=40),
        xaxis=dict(tickfont=dict(size=12, color="#1A1A1A", weight=600), showgrid=False),
        yaxis=dict(
            title=dict(text="Valor", font=dict(size=12, color="#444")),
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
        m1 = format_pct_av(dre_mes_orc.get(campo), base_mes_orc, manter_sinal=True)
        m2 = format_pct_av(dre_mes_real.get(campo), base_mes_real, manter_sinal=True)
        m3 = format_pct_av(dre_acum_orc.get(campo), base_acum_orc, manter_sinal=True)
        m4 = format_pct_av(dre_acum_real.get(campo), base_acum_real, manter_sinal=True)
        legenda_margem = f"Margem — Mês Orç. {m1} · Mês Real. {m2} · Acum. Orç. {m3} · Acum. Real. {m4}"

    return fig, legenda_margem


def renderizar_kpis(
    dre_mes_real: dict, dre_mes_orc: dict, dre_acum_real: dict, dre_acum_orc: dict, paleta: dict | None = None,
    detalhe_coligadas: dict | None = None,
) -> None:
    """detalhe_coligadas: {"mes_orc"/"mes_real"/"acum_orc"/"acum_real": {nome: dict do
    calcular_dre daquela coligada}} — só o Grupo passa isso, pra mostrar no hover de
    cada barra quanto cada coligada (Superus/ASAP) contribuiu pro total somado."""
    paleta = paleta or PALETA_SUPERUS
    st.header("KPIs")

    c1, c2 = st.columns(2)
    fig, _ = _grafico_kpi(
        "Receita Bruta (em R$)", "receita_bruta", dre_mes_orc, dre_mes_real, dre_acum_orc, dre_acum_real,
        paleta=paleta, detalhe_coligadas=detalhe_coligadas,
    )
    c1.plotly_chart(fig, use_container_width=True)
    fig, legenda = _grafico_kpi(
        "Lucro Bruto (em R$)", "margem_bruta", dre_mes_orc, dre_mes_real, dre_acum_orc, dre_acum_real,
        campo_margem_base="receita_liquida", paleta=paleta, detalhe_coligadas=detalhe_coligadas,
    )
    c2.plotly_chart(fig, use_container_width=True)
    if legenda:
        c2.caption(legenda)

    c3, c4 = st.columns(2)
    fig, legenda = _grafico_kpi(
        "EBITDA (em R$)", "ebitda", dre_mes_orc, dre_mes_real, dre_acum_orc, dre_acum_real,
        campo_margem_base="receita_liquida", paleta=paleta, detalhe_coligadas=detalhe_coligadas,
    )
    c3.plotly_chart(fig, use_container_width=True)
    if legenda:
        c3.caption(legenda)
    fig, legenda = _grafico_kpi(
        "LAIR (em R$)", "lair", dre_mes_orc, dre_mes_real, dre_acum_orc, dre_acum_real,
        campo_margem_base="receita_liquida", paleta=paleta, detalhe_coligadas=detalhe_coligadas,
    )
    c4.plotly_chart(fig, use_container_width=True)
    if legenda:
        c4.caption(legenda)


def renderizar_dre_mes_e_acumulado(
    nome_segmento: str,
    ano: int,
    nome_mes: str,
    dre_mes_real: dict,
    dre_mes_orc: dict,
    dre_acum_real: dict,
    dre_acum_orc: dict,
    dre_por_mes: dict,
    meses_do_ano: list,
    dre_mes_2025: dict | None = None,
    dre_acum_2025: dict | None = None,
    paleta: dict | None = None,
) -> None:
    """dre_por_mes: {Timestamp do mês: dict do calcular_dre} pra cada mês já
    fechado do ano (detalhamento mês a mês da tabela Acumulado). dre_mes_2025/
    dre_acum_2025 são opcionais — None faz a coluna "Realizado {ano-1}" (e os
    dois Δ dela) aparecer como N/D, pros segmentos sem RESULTADOS {ano-1}.xlsx
    equivalente (hoje só a Superus tem). paleta: cores da empresa (ver
    estilo.PALETA_POR_SEGMENTO) — default Superus."""
    paleta = paleta or PALETA_SUPERUS
    cor_escura = paleta["cor_escura"]
    cor_derivado_header = paleta["derivado_header"]
    cor_derivado_tint = paleta["derivado_tint"]

    base_av_mes = dre_mes_real.get("receita_liquida")
    base_av_orc_mes = dre_mes_orc.get("receita_liquida")
    base_av_acum = dre_acum_real.get("receita_liquida")
    base_av_orc_acum = dre_acum_orc.get("receita_liquida")
    base_av_2025_mes = dre_mes_2025.get("receita_liquida") if dre_mes_2025 else None
    base_av_2025_acum = dre_acum_2025.get("receita_liquida") if dre_acum_2025 else None

    TH_VALOR = f"padding:6px 6px; text-align:right; background-color:{cor_escura}; color:white; font-weight:700; white-space:nowrap;"
    TH_DERIVADO = f"padding:6px 6px; text-align:right; background-color:{cor_derivado_header}; color:white; font-weight:700; white-space:nowrap;"
    TH_GRUPO_VALOR = f"text-align:center; padding:6px; background-color:{cor_escura}; color:white; font-weight:700;"
    TH_GRUPO_DERIVADO = f"text-align:center; padding:6px; background-color:{cor_derivado_header}; color:white; font-weight:700;"
    TH_ROTULO = f"text-align:left; padding:6px 10px; background-color:{cor_escura}; color:white; position:sticky; left:0; z-index:2;"

    def _td(conteudo, extra="", classe="", rowspan=None) -> str:
        atributo_rowspan = f" rowspan='{rowspan}'" if rowspan else ""
        return f"<td class='{classe}'{atributo_rowspan} style='padding:6px 6px; text-align:right; white-space:nowrap; {extra}'>{conteudo}</td>"

    def _td_valor(valor, extra="", classe="", rowspan=None) -> str:
        cor = f"color:{VERMELHO};" if (valor or 0) < 0 else ""
        return _td(format_brl_md(valor), extra + cor, classe, rowspan=rowspan)

    def _celula_av(valor, base, disponivel=True, extra="", mostrar=True, rowspan=None, destaque=False) -> str:
        if not mostrar:
            return _td("", f"background-color:{cor_derivado_tint};" + extra, rowspan=rowspan)
        texto = format_pct_av(valor, base, manter_sinal=destaque) if disponivel else "N/D"
        cor = f"color:{VERMELHO};" if destaque and disponivel and (valor or 0) < 0 else ""
        return _td(texto, f"background-color:{cor_derivado_tint};{cor}" + extra, rowspan=rowspan)

    def _espacador_th() -> str:
        return "<th style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></th>"

    def _espacador_td() -> str:
        return "<td style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></td>"

    def _celulas_delta(real, orc, destaque: bool, rowspan=None) -> str:
        delta = (real - orc) if orc is not None else None
        ah = _variacao_pct(real, orc)
        if destaque:
            cor = "#FF7A7A" if (delta or 0) < 0 else "#FFFFFF"
            estilo = f"background-color:{cor_escura}; color:{cor};"
        else:
            cor = VERMELHO if (delta or 0) < 0 else "#1C7C3E"
            estilo = f"color:{cor}; background-color:{cor_derivado_tint};"
        texto_delta = format_brl_md(delta) if delta is not None else "N/D"
        texto_ah = format_pct(ah) if ah is not None else "N/D"
        return _td(texto_delta, estilo, rowspan=rowspan) + _td(texto_ah, estilo, rowspan=rowspan)

    st.header("DRE — Mês e Acumulado")

    # --- Tabela do Mês ---------------------------------------------------
    linhas_mes_html = []
    for nome, campo, destaque in LINHAS_DRE_DEF:
        real_mes = dre_mes_real[campo]
        orc_mes = dre_mes_orc.get(campo)
        real_2025_mes = dre_mes_2025.get(campo) if dre_mes_2025 else None
        cor_fundo_linha = "#EAF2E0" if destaque else "#FFFFFF"
        estilo_linha = f"font-weight:700; background-color:{cor_fundo_linha};" if destaque else f"background-color:{cor_fundo_linha};"
        mostrar_av = campo not in ("receita_bruta", "imposto")
        linhas_mes_html.append(
            f"<tr style='{estilo_linha}'>"
            f"<td style='padding:6px 12px; white-space:nowrap; position:sticky; left:0; z-index:1; background-color:{cor_fundo_linha};'>{nome}</td>"
            + _td_valor(real_mes)
            + _celula_av(real_mes, base_av_mes, mostrar=mostrar_av, destaque=destaque)
            + _td_valor(orc_mes)
            + _celula_av(orc_mes, base_av_orc_mes, disponivel=orc_mes is not None, mostrar=mostrar_av, destaque=destaque)
            + _celulas_delta(real_mes, orc_mes, destaque)
            + _td_valor(real_2025_mes)
            + _celula_av(real_2025_mes, base_av_2025_mes, disponivel=real_2025_mes is not None, mostrar=mostrar_av, destaque=destaque)
            + _celulas_delta(real_mes, real_2025_mes, destaque)
            + "</tr>"
        )

    tabela_mes_html = (
        "<table style='border-collapse:collapse; font-size:0.85rem; color:#1a1a1a;'>"
        "<tr><th></th>"
        f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Realizado</th>"
        f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Orçado {ano}</th>"
        f"<th colspan='2' style='{TH_GRUPO_DERIVADO}'>Real. x Orç.</th>"
        f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Realizado {ano - 1}</th>"
        f"<th colspan='2' style='{TH_GRUPO_DERIVADO}'>{str(ano - 1)[2:]}x{str(ano)[2:]}</th>"
        "</tr>"
        f"<tr><th style='{TH_ROTULO}'>DRE - {nome_segmento}</th>"
        f"<th style='{TH_VALOR}'>{nome_mes}/{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
        f"<th style='{TH_VALOR}'>{nome_mes}/{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
        f"<th style='{TH_DERIVADO}'>Δ</th><th style='{TH_DERIVADO}'>A.H.%</th>"
        f"<th style='{TH_VALOR}'>{nome_mes}/{str(ano - 1)[2:]}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
        f"<th style='{TH_DERIVADO}'>Δ</th><th style='{TH_DERIVADO}'>A.H.%</th>"
        "</tr>"
        + "".join(linhas_mes_html)
        + "</table>"
    )

    st.markdown(
        f"<div class='tabela-dre-wrapper'>{render_tabela_com_faixa(f'{nome_mes}/{ano} (em R$)', tabela_mes_html, paleta=paleta)}</div>",
        unsafe_allow_html=True,
    )

    # --- Tabela do Acumulado (com detalhamento mês a mês do Realizado) --
    linhas_acum_html = []
    for nome, campo, destaque in LINHAS_DRE_DEF:
        real_acum = dre_acum_real[campo]
        orc_acum = dre_acum_orc.get(campo)
        real_2025_acum = dre_acum_2025.get(campo) if dre_acum_2025 else None
        cor_fundo_linha = "#EAF2E0" if destaque else "#FFFFFF"
        estilo_linha = f"font-weight:700; background-color:{cor_fundo_linha};" if destaque else f"background-color:{cor_fundo_linha};"
        mostrar_av = campo not in ("receita_bruta", "imposto")
        eh_margem = campo in LINHAS_MARGEM
        rs = 2 if eh_margem else None
        celulas_meses = "".join(_td_valor(dre_por_mes[m][campo], classe="col-mes-detalhe") for m in meses_do_ano)
        linhas_acum_html.append(
            f"<tr style='{estilo_linha}'>"
            f"<td style='padding:6px 12px; white-space:nowrap; position:sticky; left:0; z-index:1; background-color:{cor_fundo_linha};'>{nome}</td>"
            + celulas_meses
            + _espacador_td()
            + _td_valor(real_acum, rowspan=rs)
            + _celula_av(real_acum, base_av_acum, mostrar=mostrar_av, rowspan=rs, destaque=destaque)
            + _td_valor(orc_acum, rowspan=rs)
            + _celula_av(orc_acum, base_av_orc_acum, disponivel=orc_acum is not None, mostrar=mostrar_av, rowspan=rs, destaque=destaque)
            + _celulas_delta(real_acum, orc_acum, destaque, rowspan=rs)
            + _td_valor(real_2025_acum, rowspan=rs)
            + _celula_av(real_2025_acum, base_av_2025_acum, disponivel=real_2025_acum is not None, mostrar=mostrar_av, rowspan=rs, destaque=destaque)
            + _celulas_delta(real_acum, real_2025_acum, destaque, rowspan=rs)
            + "</tr>"
        )
        if eh_margem:
            celulas_margem_meses = "".join(
                _td(
                    format_pct_av(dre_por_mes[m][campo], dre_por_mes[m].get("receita_liquida"), manter_sinal=True),
                    extra=f"color:{VERMELHO};" if dre_por_mes[m][campo] < 0 else "",
                    classe="col-mes-detalhe",
                )
                for m in meses_do_ano
            )
            linhas_acum_html.append(
                "<tr style='font-style:italic; color:#555; background-color:#F7F9F4;'>"
                f"<td style='padding:4px 12px 4px 24px; position:sticky; left:0; z-index:1; background-color:#F7F9F4;'>{LINHAS_MARGEM[campo]}</td>"
                + celulas_margem_meses
                + _espacador_td()
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
        f"<th colspan='2' style='{TH_GRUPO_VALOR}'>Acumulado {ano - 1}</th>"
        f"<th colspan='2' style='{TH_GRUPO_DERIVADO}'>{str(ano - 1)[2:]}x{str(ano)[2:]}</th>"
        "</tr>"
        f"<tr><th style='{TH_ROTULO}'>DRE - {nome_segmento}</th>"
        + cabecalho_meses
        + _espacador_th()
        + f"<th style='{TH_VALOR}'>{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
        + f"<th style='{TH_VALOR}'>{ano}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
        + f"<th style='{TH_DERIVADO}'>Δ</th><th style='{TH_DERIVADO}'>A.H.%</th>"
        + f"<th style='{TH_VALOR}'>{ano - 1}</th><th style='{TH_DERIVADO}'>A.V.%</th>"
        + f"<th style='{TH_DERIVADO}'>Δ</th><th style='{TH_DERIVADO}'>A.H.%</th>"
        "</tr>"
        + "".join(linhas_acum_html)
        + "</table>"
    )

    st.markdown(
        f"<div class='tabela-dre-wrapper'>{render_tabela_com_faixa(f'ACUMULADO/{ano} (em R$)', tabela_acum_html, paleta=paleta)}</div>",
        unsafe_allow_html=True,
    )
