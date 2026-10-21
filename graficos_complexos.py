"""Gráficos de pizza da Análise de Complexos (págs. 10/11 da apresentação
de referência) — contagem de complexos (não R$) por status ou por
condição binária (Acima/Abaixo do previsto, Positivo/Negativo)."""

import plotly.graph_objects as go

CORES_STATUS = {
    "Backlog Ativo": "#1C3024",
    "Backlog Inativo": "#6B6B63",
    "Backlog Novo Mobilizado": "#6AA62C",
    "Backlog Novo Em Mobilização": "#C8D9A0",
}
COR_POSITIVA = "#1C3024"
COR_NEGATIVA = "#D9D2C0"


def _pizza(titulo, rotulos, valores, cores) -> go.Figure:
    total = sum(valores) or 1
    textos = [f"{v}; {v / total * 100:.0f}%" for v in valores]
    cores_texto = ["#1A1A1A" if c == COR_NEGATIVA else "#FFFFFF" for c in cores]
    fig = go.Figure(
        go.Pie(
            labels=rotulos,
            values=valores,
            marker=dict(colors=cores, line=dict(color="#FFFFFF", width=2)),
            text=textos,
            textinfo="text",
            textposition="inside",
            textfont=dict(size=13, weight=700),
            insidetextfont=dict(color=cores_texto),
            sort=False,
            direction="clockwise",
        )
    )
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=14, color="#1A1A1A")),
        showlegend=True,
        legend=dict(font=dict(size=11)),
        height=380,
        margin=dict(t=60, b=20, l=10, r=10),
        paper_bgcolor="#FFFFFF",
    )
    return fig


def grafico_pizza_status(titulo: str, contagem: dict[str, int]) -> go.Figure:
    rotulos = [r for r in CORES_STATUS if contagem.get(r, 0) > 0]
    valores = [contagem[r] for r in rotulos]
    cores = [CORES_STATUS[r] for r in rotulos]
    return _pizza(titulo, rotulos, valores, cores)


def grafico_pizza_duas_fatias(titulo: str, rotulo_pos: str, n_pos: int, rotulo_neg: str, n_neg: int) -> go.Figure:
    return _pizza(titulo, [rotulo_pos, rotulo_neg], [n_pos, n_neg], [COR_POSITIVA, COR_NEGATIVA])
