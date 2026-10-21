"""Texto automático tipo 'ANÁLISE DE AGOSTO/26' da apresentação de
referência: resume a variação Real x Orçado de uma métrica (Receita
Bruta, Despesa Total) e nomeia as categorias que mais pesaram pra cima e
pra baixo — sem IA, só o dado já calculado em analise_categoria.py
preenchendo um molde de frase. Critério confirmado com o usuário: maior
variação em R$ (absoluta), mostrando os dois lados (ofensores e
compensadores), até 3 categorias nomeadas por frase."""

from formatting import format_brl_compacto, format_brl_md

N_OFENSORES = 3


def _fmt_pct_abs(valor: float) -> str:
    return f"{abs(valor) * 100:.1f}%".replace(".", ",")


def _fmt_pct_sinal(valor: float) -> str:
    return f"{valor * 100:+.1f}%".replace(".", ",")


def _fmt_brl_sinal(valor: float) -> str:
    """Compacto com sinal explícito, sem parênteses (tipo '-1,7MM' da
    apresentação de referência) — usado dentro de um parêntese que já
    contém o '%', pra não ficar com dois estilos de negativo misturados
    (sinal no %, parênteses no R$) no mesmo item."""
    sinal = "+" if valor >= 0 else "-"
    return f"{sinal}{format_brl_compacto(abs(valor))}"


def _top_variacoes(serie_real, serie_orc, n=N_OFENSORES):
    """Lista (categoria, delta, pct) ordenada por |delta| desc — só
    categorias com Orçado <> 0 disponível (sem isso não dá pra calcular
    desvio percentual)."""
    if serie_orc is None:
        return []
    categorias = set(serie_real.index) | set(serie_orc.index)
    linhas = []
    for cat in categorias:
        real = serie_real.get(cat, 0.0) or 0.0
        orc = serie_orc.get(cat, 0.0) or 0.0
        if not orc:
            continue
        delta = real - orc
        linhas.append((cat, delta, delta / abs(orc)))
    linhas.sort(key=lambda t: -abs(t[1]))
    return linhas[:n]


def gerar_analise(
    nome_metrica: str,
    periodo_label: str,
    real_total: float,
    orc_total: float | None,
    serie_real_cat,
    serie_orc_cat,
    favoravel_se_maior: bool = True,
) -> str:
    """favoravel_se_maior=True (Receita): real > orçado é bom.
    favoravel_se_maior=False (Despesa): real > orçado é ruim (gastou mais)."""
    if not orc_total:
        return (
            f"A <b>{nome_metrica} de {periodo_label}</b> totalizou {format_brl_md(real_total)}. "
            "Orçado não disponível pra essa Revisão/Cenário — sem como calcular o desvio."
        )

    delta_total = real_total - orc_total
    direcao = "acima" if delta_total >= 0 else "abaixo"

    top = _top_variacoes(serie_real_cat, serie_orc_cat)
    desfavoraveis = [t for t in top if (t[1] >= 0) != favoravel_se_maior]
    favoraveis = [t for t in top if (t[1] >= 0) == favoravel_se_maior]

    def _item(cat, delta, pct):
        return f"<b>{cat}</b> ({_fmt_pct_sinal(pct)}, {_fmt_brl_sinal(delta)})"

    partes = []
    if desfavoraveis:
        partes.append("Ofensores: " + " e ".join(_item(*t) for t in desfavoraveis))
    if favoraveis:
        conectivo = "compensados por" if desfavoraveis else "Impulsionado por"
        partes.append(f"{conectivo} " + " e ".join(_item(*t) for t in favoraveis))
    frase_extra = (" " + "; ".join(partes) + ".") if partes else ""

    # format_brl_md já envolve negativo em parênteses sozinho — não duplicar
    # (senão vira "((R$ X))" quando o desvio é desfavorável).
    delta_texto = format_brl_md(delta_total)
    delta_texto = delta_texto if delta_texto.startswith("(") else f"({delta_texto})"
    return (
        f"A <b>{nome_metrica} de {periodo_label}</b> totalizou {format_brl_md(real_total)}, "
        f"encerrando <b>{_fmt_pct_abs(delta_total / abs(orc_total))} {direcao} do orçamento</b> "
        f"{delta_texto} de {format_brl_md(orc_total)}.{frase_extra}"
    )
