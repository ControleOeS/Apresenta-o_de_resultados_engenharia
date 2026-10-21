import pandas as pd


def format_brl(valor: float, decimais: int = 0) -> str:
    if valor is None or pd.isna(valor):
        return "N/D"
    texto = f"{abs(valor):,.{decimais}f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"(R$ {texto})" if valor < 0 else f"R$ {texto}"


def format_brl_compacto(valor: float) -> str:
    if valor is None or pd.isna(valor):
        return "N/D"
    abs_valor = abs(valor)
    if abs_valor >= 1_000_000:
        corpo = f"{abs_valor / 1_000_000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        corpo = f"{corpo} Mi"
    elif abs_valor >= 1_000:
        corpo = f"{abs_valor / 1_000:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        corpo = f"{corpo} mil"
    else:
        corpo = f"{abs_valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"(R$ {corpo})" if valor < 0 else f"R$ {corpo}"


def format_brl_md(valor: float, decimais: int = 0) -> str:
    """Igual a format_brl, mas com o '$' trocado pela entidade HTML &#36; —
    use sempre que o texto for inserido em HTML/markdown (st.markdown): duas
    ocorrências de 'R$' no mesmo bloco viram um par de delimitadores de
    fórmula (LaTeX) e corrompem o texto entre elas."""
    return format_brl(valor, decimais).replace("$", "&#36;")


def format_pct(valor: float, decimais: int = 1) -> str:
    if valor is None or pd.isna(valor):
        return "N/D"
    return f"{valor * 100:+.{decimais}f}%".replace(".", ",")


def format_pct_av(valor: float, base: float, decimais: int = 1) -> str:
    """Análise Vertical: valor como % de uma base (Receita Líquida). Sempre
    em valor absoluto (sem % negativo) — pedido do usuário, 2026-10-21: uma
    linha de Despesa/Custo já mostra que é negativa pelo valor em R$ (sinal,
    cor, parênteses); repetir o sinal no A.V.% é redundante."""
    if valor is None or pd.isna(valor) or not base:
        return "-"
    return f"{abs(valor / base) * 100:,.{decimais}f}%".replace(".", ",")
