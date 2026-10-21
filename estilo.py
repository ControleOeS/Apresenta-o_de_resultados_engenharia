"""Paleta e componentes visuais extraídos da apresentação de referência
("Apresentação de Resultados - Superus Holding - Agosto.26 - v1.pdf") via
amostragem de pixel nas imagens embutidas do PDF — ver assets_extraidos/."""

import base64
from pathlib import Path

PASTA_ASSETS = Path(__file__).parent / "assets"

# Gradiente do banner superior (amostrado em p1_img0.jpeg, esquerda -> direita)
GRADIENTE_BANNER = "linear-gradient(90deg, #00465C 0%, #336F4F 45%, #6FA140 75%, #ABD42E 100%)"

VERDE_ESCURO = "#1C3024"  # barras "Realizado" / badges de seção / header da tabela
VERDE_ORCADO = "#6AA62C"  # barras "Orçado"
VERDE_BOX_HEADER = "#729672"  # header das caixas de resumo narrativo
VERDE_BOX_CORPO = "#D4E4B8"  # corpo das caixas de resumo narrativo
# Colunas "derivadas" (A.V.%, Δ, A.H.%) — em vez de um cinza neutro (que
# destoa da paleta verde e cria manchas visuais sobre o fundo verde-pálido
# das linhas de subtotal), um tom sálvia na mesma família do verde-escuro:
# mais escuro para o cabeçalho (texto branco), bem claro pro fundo das
# células (quase imperceptível, só o suficiente pra agrupar visualmente).
VERDE_DERIVADO_HEADER = "#5B6B58"
VERDE_DERIVADO_TINT = "#EDF0E7"
VERMELHO = "#FF0000"  # variações negativas / setas de queda
BRANCO = "#FFFFFF"


def _imagem_base64(nome_arquivo: str) -> str:
    caminho = PASTA_ASSETS / nome_arquivo
    return base64.b64encode(caminho.read_bytes()).decode("ascii")


def render_banner(titulo: str, subtitulo: str = "") -> str:
    """Banner com gradiente teal->verde-limão e a logo ACPL+Superus (versão
    colorida, fundo claro — igual à usada na capa da apresentação de
    referência) num cartão branco à direita."""
    logo = _imagem_base64("logo_acpl_superus.png")
    subtitulo_html = f"<div style='color:#EAF5E5; font-size:0.95rem; margin-top:4px;'>{subtitulo}</div>" if subtitulo else ""
    return f"""
<div style='background:{GRADIENTE_BANNER}; border-radius:10px; padding:22px 28px;
            display:flex; align-items:center; justify-content:space-between; margin-bottom:18px;'>
  <div>
    <div style='color:{BRANCO}; font-size:1.6rem; font-weight:700; letter-spacing:0.3px;'>{titulo}</div>
    {subtitulo_html}
  </div>
  <div style='display:flex; align-items:center; background:{BRANCO};
              border-radius:8px; padding:8px 18px;'>
    <img src='data:image/png;base64,{logo}' style='height:40px;'>
  </div>
</div>
"""


def render_caixa_narrativa(titulo: str, texto_html: str) -> str:
    """Caixa de resumo narrativo duas-tons (header + corpo), tipo 'ANÁLISE
    DE AGOSTO/26' da apresentação de referência — cores amostradas de lá."""
    return f"""
<div style='border-radius:6px; overflow:hidden; margin-bottom:12px;'>
  <div style='background:{VERDE_BOX_HEADER}; color:{BRANCO}; font-weight:700;
              font-size:0.82rem; letter-spacing:0.3px; padding:6px 14px;'>
    {titulo}
  </div>
  <div style='background:{VERDE_BOX_CORPO}; color:#1a1a1a; font-size:0.88rem;
              line-height:1.5; padding:12px 14px;'>
    {texto_html}
  </div>
</div>
"""


def render_tabela_com_faixa(texto_faixa: str, tabela_html: str, largura_total: bool = False) -> str:
    """Faixa verde-escura ACIMA da tabela (tipo 'AGOSTO/26'/'ACUMULADO/26') —
    ocupa a largura toda em vez de uma coluna lateral, pra sobrar mais
    espaço horizontal pra tabela (evita scroll lateral com o detalhamento
    mês a mês do Acumulado).

    `largura_total=True` força o bloco (faixa + tabela) a ocupar 100% do
    container, mesmo que a tabela por dentro seja mais estreita que isso —
    use nas tabelas com muita coluna (Forecast+Meta) que devem sempre
    esticar até o fim do texto abaixo, painel lateral aberto ou fechado
    (pedido do usuário, 2026-10-21). Sem isso, `width:100%` na tabela por
    dentro não tem efeito nenhum: o div externo (display:inline-block)
    encolhe pro tamanho do conteúdo, e 100% de um container que encolheu
    não estica nada."""
    # display:inline-block + max-width:100% faz o bloco inteiro (faixa +
    # tabela) encolher pro tamanho natural do conteúdo quando a tabela é
    # estreita (Mês) e só ocupar a largura toda quando precisa mesmo
    # (Acumulado, com o detalhamento mês a mês) — sem isso a faixa ficava
    # sempre esticada 100% mesmo quando a tabela de baixo era bem menor.
    display = "block" if largura_total else "inline-block"
    return f"""
<div style='display:{display}; max-width:100%; margin-bottom:10px;'>
  <div style='background:linear-gradient(90deg, {VERDE_ESCURO}, #2E5339); color:{BRANCO};
              font-size:1.05rem; font-weight:700; padding:8px 16px; border-radius:6px;
              margin-bottom:8px; box-shadow:0 2px 4px rgba(0,0,0,0.15);'>
    {texto_faixa}
  </div>
  <div style='overflow-x:auto;'>
    {tabela_html}
  </div>
</div>
"""
