"""Gráfico de barras empilhadas por categoria (Receita Bruta / Despesa /
Lucro Bruto por Categoria), fiel ao desenho das páginas 8/9/12 da
apresentação de referência: 2 barras (Orçado x Realizado), cada uma
empilhada por categoria, com uma caixa de total acima de cada barra.
Cores amostradas diretamente da apresentação (BackLog Ativo = mais
escuro, Funil de Vendas = mais claro)."""

import plotly.graph_objects as go

from estilo import VERDE_ESCURO, VERMELHO

# Rampa escuro -> claro amostrada da apresentação de referência (BackLog
# Ativo #1C3024, BackLog Novo #6AA62C, Funil de Vendas #C8E09B) — os tons
# intermediários/adicionais são interpolados linearmente entre esses.
_PONTOS_RAMPA = [
    (0x1C, 0x30, 0x24),  # escuro (BackLog Ativo)
    (0x6A, 0xA6, 0x2C),  # medio (BackLog Novo)
    (0xC8, 0xE0, 0x9B),  # claro (Funil de Vendas)
]


def _cor_em(t: float) -> str:
    """t em [0,1] -> hex interpolado nos 3 pontos amostrados da apresentação."""
    segmentos = len(_PONTOS_RAMPA) - 1
    pos = t * segmentos
    i = min(int(pos), segmentos - 1)
    frac = pos - i
    a, b = _PONTOS_RAMPA[i], _PONTOS_RAMPA[i + 1]
    rgb = tuple(int(a[k] + (b[k] - a[k]) * frac) for k in range(3))
    return "#%02X%02X%02X" % rgb


def _cores_categoria(n: int) -> list[str]:
    if n <= 1:
        return [_cor_em(0)]
    return [_cor_em(i / (n - 1)) for i in range(n)]


_COR_DEMAIS = "#9E9E9E"  # cinza neutro — nunca usado na rampa principal, não colide


def mapa_cores_categorias(categorias_conhecidas: list[str]) -> dict[str, str]:
    """Categoria -> cor FIXA, numa ordem estável (alfabética, a mesma lista
    pra qualquer gráfico) — antes a cor seguia a posição no ranking de
    valor de CADA gráfico, então a mesma categoria virava cor diferente
    entre o bloco do Mês e o do Acumulado (item 26, 2026-11-11). Passe a
    MESMA lista completa (analise_categoria.todas_categorias_conhecidas())
    em todo gráfico, não só as categorias que aparecem naquele recorte."""
    ordenadas = sorted(categorias_conhecidas)
    cores = _cores_categoria(len(ordenadas)) if ordenadas else []
    return dict(zip(ordenadas, cores))


def _cor_texto_legivel(cor_hex: str) -> str:
    """Branco em fundo escuro, texto escuro em fundo claro — luminância
    relativa simples. Evita o problema de rótulo branco sumindo nas fatias
    mais claras da rampa."""
    r, g, b = int(cor_hex[1:3], 16), int(cor_hex[3:5], 16), int(cor_hex[5:7], 16)
    luminancia = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#1A1A1A" if luminancia > 140 else "#FFFFFF"


# Fatia precisa representar pelo menos esse % da barra (em módulo) pra
# ganhar rótulo — abaixo disso o texto não cabe e o Plotly ou encolhe até
# ficar ilegível ou sobrepõe as fatias vizinhas. Testado ao vivo (não só
# na exportação estática) antes de fixar esse valor.
_LIMIAR_ROTULO = 0.07


# Fatia com participação (em módulo, em qualquer uma das barras) abaixo
# disso entra em "Demais" — até 13 categorias em tons próximos da mesma
# rampa ficavam indistinguíveis e sem rótulo; o detalhe completo continua
# na tabela/expander de cada categoria (item 28, 2026-11-11). Esse
# agrupamento é só visual — não muda nenhuma série usada fora do gráfico.
_LIMIAR_AGRUPAR_DEMAIS = 0.02


def grafico_categoria_empilhado(titulo: str, serie_orc, serie_real, formatar, mapa_cores: dict[str, str]) -> go.Figure:
    """serie_orc pode ser None (ex: Orçado indisponível pra essa Revisão) —
    nesse caso só a barra Realizado aparece. Categorias podem ser negativas
    (ex: Lucro Bruto por Categoria, onde uma categoria pode dar prejuízo) —
    o eixo e os rótulos são calculados pra lidar com isso (empilhamento
    positivo pra cima, negativo pra baixo, igual o Plotly já faz nativo).

    `mapa_cores` (categoria -> cor) é fixo pro app inteiro (ver
    mapa_cores_categorias) — a mesma categoria sempre sai com a mesma cor,
    não importa o que mais apareça nesse recorte específico (item 26)."""
    tem_orc = serie_orc is not None
    categorias_brutas = sorted(
        set(serie_orc.index if tem_orc else []) | set(serie_real.index),
        key=lambda c: -(
            (serie_real.get(c, 0) or 0) + (serie_orc.get(c, 0) if tem_orc else 0)
        ),
    )
    # Categoria sem valor em NENHUMA coluna (Realizado/Orçado, Mês/Acum. já
    # filtrados por quem chama) não aparece — só polui a legenda (item 27).
    categorias = [
        c for c in categorias_brutas
        if (serie_real.get(c, 0) or 0) != 0 or (tem_orc and (serie_orc.get(c, 0) or 0) != 0)
    ]
    rotulos_x = (["Orçado", "Realizado"] if tem_orc else ["Realizado"])

    # Por barra: total assinado (pra caixa do total) e a soma em módulo das
    # fatias (pra decidir o limiar de rótulo — usar o total assinado aqui
    # quebraria o limiar quando o total líquido da barra for perto de zero
    # ou negativo, mesmo com fatias individuais grandes).
    totais = []
    totais_abs = []
    valores_por_barra = []
    for rotulo in rotulos_x:
        valores_bar = [
            (serie_orc.get(c, 0) if tem_orc and rotulo == "Orçado" else serie_real.get(c, 0)) or 0
            for c in categorias
        ]
        valores_por_barra.append(valores_bar)
        totais.append(sum(valores_bar))
        totais_abs.append(sum(abs(v) for v in valores_bar) or 1)

    # Agrupa em "Demais" quem não chega no limiar de participação em
    # NENHUMA das barras (item 28) — puramente visual, a tabela/expander
    # de cada categoria continua mostrando o detalhe completo.
    mapa_valores = {cat: [valores_bar[idx] for valores_bar in valores_por_barra] for idx, cat in enumerate(categorias)}
    participacao_maxima = {
        cat: max(abs(v) / total_abs for v, total_abs in zip(mapa_valores[cat], totais_abs))
        for cat in categorias
    }
    categorias_principais = [c for c in categorias if participacao_maxima[c] >= _LIMIAR_AGRUPAR_DEMAIS]
    categorias_pequenas = [c for c in categorias if participacao_maxima[c] < _LIMIAR_AGRUPAR_DEMAIS]
    if categorias_pequenas:
        mapa_valores["Demais"] = [sum(mapa_valores[c][b] for c in categorias_pequenas) for b in range(len(rotulos_x))]
    categorias_render = categorias_principais + (["Demais"] if categorias_pequenas else [])

    fig = go.Figure()
    for cat in categorias_render:
        cor = _COR_DEMAIS if cat == "Demais" else mapa_cores.get(cat, _cor_em(0.5))
        valores = mapa_valores[cat]
        textos = [
            formatar(v) if v and abs(v) / total_abs >= _LIMIAR_ROTULO else ""
            for v, total_abs in zip(valores, totais_abs)
        ]
        fig.add_trace(
            go.Bar(
                x=rotulos_x,
                y=valores,
                name=cat,
                marker_color=cor,
                text=textos,
                textposition="inside",
                insidetextanchor="middle",
                # "inside" (não "none"): com 4+ categorias finas adjacentes
                # (ex: Despesa com PLR), texto em tamanho fixo passa do
                # próprio segmento e invade o vizinho — aqui o Plotly só
                # encolhe quando realmente não cabe, e o limiar de 7% acima
                # já filtra os segmentos pequenos demais pra sobrar com um
                # texto legível mesmo encolhido.
                constraintext="inside",
                cliponaxis=False,
                textfont=dict(color=_cor_texto_legivel(cor), size=13, weight=700),
            )
        )

    # Topo/fundo reais do empilhamento (positivo empilha pra cima, negativo
    # pra baixo) — o eixo precisa cobrir os dois lados, não só [0, topo].
    topos_positivos = [sum(v for v in valores_bar if v > 0) for valores_bar in valores_por_barra]
    fundos_negativos = [sum(v for v in valores_bar if v < 0) for valores_bar in valores_por_barra]
    y_topo = (max(topos_positivos) if topos_positivos else 0) or 1
    y_fundo = min(fundos_negativos) if fundos_negativos else 0

    anotacoes = [
        dict(
            x=rotulo,
            y=y_topo,
            text=f"<b>{formatar(total)}</b>",
            showarrow=False,
            yshift=22,
            bgcolor="#D4E4B8",
            bordercolor=VERDE_ESCURO,
            borderwidth=1,
            borderpad=4,
            font=dict(color=VERMELHO if total < 0 else "#1A1A1A", size=13),
        )
        for rotulo, total in zip(rotulos_x, totais)
    ]

    margem_topo = y_topo * 0.22 + abs(y_fundo) * 0.05
    margem_fundo = abs(y_fundo) * 0.15 if y_fundo < 0 else 0

    fig.update_layout(
        title=dict(text=titulo, font=dict(size=15, color="#1A1A1A")),
        barmode="relative",
        bargap=0.35,
        height=460,
        margin=dict(t=70, b=100),
        yaxis=dict(visible=False, range=[y_fundo - margem_fundo, y_topo + margem_topo], zeroline=True, zerolinecolor="#CCCCCC"),
        xaxis=dict(tickfont=dict(size=12, color="#1A1A1A", weight=600)),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.1,
            xanchor="center",
            x=0.5,
            font=dict(size=10),
            tracegroupgap=4,
        ),
        annotations=anotacoes,
    )
    return fig
