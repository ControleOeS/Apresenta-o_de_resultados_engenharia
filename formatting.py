import pandas as pd


def format_brl(valor: float, decimais: int = 0) -> str:
    """Valor monetário sem o prefixo 'R$' — a unidade fica só no título da
    tabela/seção ("... (em R$)"), não repetida em cada célula (pedido do
    usuário, 2026-10-23). Negativo entre parênteses, zero vira '-'."""
    if valor is None or pd.isna(valor):
        return "N/D"
    if valor == 0:
        return "-"
    texto = f"{abs(valor):,.{decimais}f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"({texto})" if valor < 0 else texto


def format_brl_compacto(valor: float) -> str:
    if valor is None or pd.isna(valor):
        return "N/D"
    if valor == 0:
        return "-"
    abs_valor = abs(valor)
    if abs_valor >= 1_000_000:
        corpo = f"{abs_valor / 1_000_000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        corpo = f"{corpo} Mi"
    elif abs_valor >= 1_000:
        corpo = f"{abs_valor / 1_000:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        corpo = f"{corpo} mil"
    else:
        corpo = f"{abs_valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"({corpo})" if valor < 0 else corpo


def format_brl_md(valor: float, decimais: int = 0) -> str:
    """Igual a format_brl — mantido por compatibilidade com quem já importa
    esse nome (não tem mais '$' pra escapar, já que o prefixo 'R$' saiu de
    toda célula; a unidade agora só aparece no título "... (em R$)")."""
    return format_brl(valor, decimais)


def format_pct(valor: float, decimais: int = 1) -> str:
    if valor is None or pd.isna(valor):
        return "N/D"
    if valor == 0:
        return "-"
    return f"{valor * 100:+.{decimais}f}%".replace(".", ",")


def format_pct_av(valor: float, base: float, decimais: int = 1, manter_sinal: bool = False) -> str:
    """Análise Vertical: valor como % de uma base (Receita Líquida).

    Por padrão (`manter_sinal=False`) sempre em valor absoluto (sem %
    negativo) — pedido do usuário, 2026-10-21: uma linha de Despesa/Custo
    já mostra que é negativa pelo valor em R$ (sinal, cor, parênteses);
    repetir o sinal no A.V.% é redundante.

    `manter_sinal=True` — linhas de RESULTADO (Receita Líquida, Lucro
    Bruto, EBITDA, LAIR, Lucro Líquido): aqui o sinal É a informação (uma
    margem negativa é um resultado negativo, não "uma dedução que já é
    negativa por natureza") — corrigido 2026-11-11 (antes o abs() era
    aplicado também nessas linhas, escondendo margens negativas)."""
    if valor is None or pd.isna(valor) or not base:
        return "-"
    if valor == 0:
        return "-"
    pct = valor / base * 100
    if manter_sinal:
        return f"{pct:+,.{decimais}f}%".replace(".", ",")
    return f"{abs(pct):,.{decimais}f}%".replace(".", ",")


def format_pp(valor: float, decimais: int = 1) -> str:
    """Diferença entre dois percentuais, em pontos percentuais — nunca
    confundir com format_pct (diferença relativa em %). Ex.: Margem A =
    10%, Margem B = 10,7% -> diferença = "+0,7 p.p.", não "+0,7%"."""
    if valor is None or pd.isna(valor):
        return "N/D"
    if valor == 0:
        return "-"
    return f"{valor * 100:+.{decimais}f} p.p.".replace(".", ",")
