"""Paleta e componentes visuais. A paleta-base (Superus) foi extraída da
apresentação de referência ("Apresentação de Resultados - Superus Holding -
Agosto.26 - v1.pdf") via amostragem de pixel nas imagens embutidas do PDF —
ver assets_extraidos/. A partir de 2026-11-24, as 4 abas (Superus/ASAP/O&S/
Grupo) passaram a usar a identidade visual OFICIAL de cada empresa (pedido
do usuário: "tudo que está na aba da empresa selecionada deve seguir a
paleta de cores que eu já te forneci no app dash diretoria") — ver
PALETA_POR_SEGMENTO abaixo."""

import base64
from pathlib import Path

PASTA_ASSETS = Path(__file__).parent / "assets"

VERMELHO = "#FF0000"  # variações negativas / setas de queda — universal, não muda por empresa
BRANCO = "#FFFFFF"


def _imagem_base64(nome_arquivo: str) -> str:
    caminho = PASTA_ASSETS / nome_arquivo
    return base64.b64encode(caminho.read_bytes()).decode("ascii")


def hex_para_rgb(cor_hex: str) -> tuple[int, int, int]:
    cor_hex = cor_hex.lstrip("#")
    return tuple(int(cor_hex[i : i + 2], 16) for i in (0, 2, 4))


def mesclar(cor_hex: str, outra_hex: str, fator: float) -> str:
    """Mistura cor_hex com outra_hex: fator=0 -> cor_hex puro, fator=1 ->
    outra_hex puro. Usado só pra DERIVAR os tons secundários de cada
    paleta (ver _derivar_paleta) — nunca pras 2 cores oficiais confirmadas
    (cor_escura/cor_destaque), essas vêm prontas do manual de marca de
    cada empresa."""
    r1, g1, b1 = hex_para_rgb(cor_hex)
    r2, g2, b2 = hex_para_rgb(outra_hex)
    r = round(r1 + fator * (r2 - r1))
    g = round(g1 + fator * (g2 - g1))
    b = round(b1 + fator * (b2 - b1))
    return f"#{r:02X}{g:02X}{b:02X}"


def _derivar_paleta(cor_escura: str, cor_destaque: str, logo_nome_arquivo: str) -> dict:
    """`cor_escura`/`cor_destaque` são as 2 cores oficiais de cada empresa,
    confirmadas pelo usuário em 2026-11-05 a partir do manual de marca de
    cada uma (mesmos valores usados em
    DASH_DIRETORIA/pages/4_Carrossel_Meta.py IDENTIDADE_VISUAL — "cor" ali
    = cor_destaque, "cor_card" = cor_escura). Os demais tons (gradiente do
    banner, header/corpo da caixa narrativa, header/tint das colunas
    derivadas A.V.%/Δ) NÃO são confirmados marca a marca — são só uma
    extrapolação consistente (mesma fórmula/fatores pras 4 empresas),
    calibrada pra reproduzir de perto os tons que já existiam hardcoded
    pra Superus antes desta mudança (#729672/#D4E4B8/#5B6B58/#EDF0E7)."""
    return {
        "cor_escura": cor_escura,
        "cor_destaque": cor_destaque,
        "logo_nome_arquivo": logo_nome_arquivo,
        "gradiente_banner": (
            f"linear-gradient(90deg, {cor_escura} 0%, "
            f"{mesclar(cor_escura, cor_destaque, 0.45)} 45%, "
            f"{mesclar(cor_escura, cor_destaque, 0.75)} 75%, "
            f"{cor_destaque} 100%)"
        ),
        "gradiente_faixa": f"linear-gradient(90deg, {cor_escura}, {mesclar(cor_escura, cor_destaque, 0.25)})",
        "box_header": mesclar(cor_escura, cor_destaque, 0.55),
        "box_corpo": mesclar(cor_destaque, BRANCO, 0.78),
        "derivado_header": mesclar(cor_escura, "#808080", 0.45),
        "derivado_tint": mesclar(cor_escura, BRANCO, 0.93),
    }


# As 2 cores de cada linha = oficiais/confirmadas (ver docstring de
# _derivar_paleta); o resto do dict é derivado, não confirmado marca a marca.
PALETA_SUPERUS = _derivar_paleta("#24372C", "#98C13B", "logo_acpl_superus.png")
PALETA_ASAP = _derivar_paleta("#0027BE", "#1641FF", "logo_asap.png")
PALETA_OES = _derivar_paleta("#00465A", "#C8EB28", "oes_logo_preto.png")
# "Grupo" (Superus+ASAP, sem O&S) usa a mesma cor_escura/cor_destaque da
# Superus Engenharia (a Holding compartilha a identidade visual da
# Superus no manual de marca, só a logo muda) — ver
# DASH_DIRETORIA/pages/4_Carrossel_Meta.py, "Holding S/ LocServs".
PALETA_GRUPO = _derivar_paleta("#24372C", "#98C13B", "logo_grupo_superus.png")

PALETA_POR_SEGMENTO = {
    "Superus": PALETA_SUPERUS,
    "ASAP": PALETA_ASAP,
    "O&S": PALETA_OES,
    "Grupo": PALETA_GRUPO,
}

# Aliases pro nome antigo (módulo inteiro, incl. forecast.py/
# graficos_categoria.py/graficos_complexos.py/pagina_resultado.py, usava
# essas constantes fixas direto) — continuam existindo, só que agora
# apontam pros valores OFICIAIS da Superus (antes eram uma amostragem
# aproximada do PDF de referência: #1C3024/#6AA62C viram #24372C/#98C13B).
# Nenhum desses arquivos precisou mudar: são todos conteúdo exclusivo da
# aba Superus hoje (Curva S, Análise por Categoria/Complexos, Forecast),
# então a paleta fixa = a paleta da Superus já é o comportamento certo.
GRADIENTE_BANNER = PALETA_SUPERUS["gradiente_banner"]
VERDE_ESCURO = PALETA_SUPERUS["cor_escura"]
VERDE_ORCADO = PALETA_SUPERUS["cor_destaque"]
VERDE_BOX_HEADER = PALETA_SUPERUS["box_header"]
VERDE_BOX_CORPO = PALETA_SUPERUS["box_corpo"]
VERDE_DERIVADO_HEADER = PALETA_SUPERUS["derivado_header"]
VERDE_DERIVADO_TINT = PALETA_SUPERUS["derivado_tint"]


def render_banner(titulo: str, subtitulo: str = "", paleta: dict | None = None) -> str:
    """Banner com o gradiente e a logo da empresa (num cartão branco à
    direita) da paleta passada — por padrão a da Superus (igual à usada na
    capa da apresentação de referência); ASAP/O&S/Grupo passam sua própria
    paleta (PALETA_ASAP/PALETA_OES/PALETA_GRUPO, mesmas logos já usadas no
    DASH_DIRETORIA — pedido do usuário, 2026-11-24, "identidade visual de
    cada empresa nas abas", estendido em seguida pra cor de fundo/gráficos
    também). logo_grupo_superus.png (dentro de PALETA_GRUPO) é a logo
    "Grupo Superus" do DASH_DIRETORIA — não confirmado 1:1 com o recorte
    "Grupo" deste app (Superus+ASAP, sem O&S), mas é a única logo de grupo
    disponível."""
    paleta = paleta or PALETA_SUPERUS
    logo = _imagem_base64(paleta["logo_nome_arquivo"])
    subtitulo_html = f"<div style='color:#EAF5E5; font-size:0.95rem; margin-top:4px;'>{subtitulo}</div>" if subtitulo else ""
    return f"""
<div style='background:{paleta["gradiente_banner"]}; border-radius:10px; padding:22px 28px;
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


def render_caixa_narrativa(titulo: str, texto_html: str, paleta: dict | None = None) -> str:
    """Caixa de resumo narrativo duas-tons (header + corpo), tipo 'ANÁLISE
    DE AGOSTO/26' da apresentação de referência — cores amostradas de lá
    (Superus) ou derivadas da paleta de cada empresa (ver _derivar_paleta).
    Só a Superus usa esta função hoje (narrativa do Forecast/KPIs) — o
    parâmetro paleta existe pra quando ASAP/O&S/Grupo ganharem seção
    equivalente, sem precisar mexer aqui de novo."""
    paleta = paleta or PALETA_SUPERUS
    return f"""
<div style='border-radius:6px; overflow:hidden; margin-bottom:12px;'>
  <div style='background:{paleta["box_header"]}; color:{BRANCO}; font-weight:700;
              font-size:0.82rem; letter-spacing:0.3px; padding:6px 14px;'>
    {titulo}
  </div>
  <div style='background:{paleta["box_corpo"]}; color:#1a1a1a; font-size:0.88rem;
              line-height:1.5; padding:12px 14px;'>
    {texto_html}
  </div>
</div>
"""


def render_tabela_com_faixa(texto_faixa: str, tabela_html: str, largura_total: bool = False, paleta: dict | None = None) -> str:
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
    paleta = paleta or PALETA_SUPERUS
    display = "block" if largura_total else "inline-block"
    return f"""
<div style='display:{display}; max-width:100%; margin-bottom:10px;'>
  <div style='background:{paleta["gradiente_faixa"]}; color:{BRANCO};
              font-size:1.05rem; font-weight:700; padding:8px 16px; border-radius:6px;
              margin-bottom:8px; box-shadow:0 2px 4px rgba(0,0,0,0.15);'>
    {texto_faixa}
  </div>
  <div style='overflow-x:auto;'>
    {tabela_html}
  </div>
</div>
"""
