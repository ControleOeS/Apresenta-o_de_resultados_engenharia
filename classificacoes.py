"""Classificação manual de Centro de Custo -> categoria, persistida no
Dropbox (mesma conta do DASH_DIRETORIA) — passou a ser assim em 2026-10-21
pra sobreviver a reinício/redeploy na nuvem (Streamlit Community Cloud não
tem disco persistente) e ficar igual pra qualquer um que abrir o link, em
vez de "por computador". Chave sempre o código do Centro de Custo (estável
entre Realizado e Previsto) — o nome descritivo só é guardado junto para
exibição/busca."""

from config import DROPBOX_CATEGORIAS, DROPBOX_CLASSIFICACOES
from dropbox_io import baixar_json, salvar_json


def carregar_categorias() -> list[str]:
    return baixar_json(DROPBOX_CATEGORIAS, [])


def salvar_categorias(categorias: list[str]) -> None:
    salvar_json(DROPBOX_CATEGORIAS, sorted(set(categorias)))


def adicionar_categoria(nova: str) -> list[str]:
    categorias = carregar_categorias()
    nova = nova.strip()
    if nova and nova not in categorias:
        categorias.append(nova)
        salvar_categorias(categorias)
    return categorias


def remover_categoria(categoria: str) -> list[str]:
    categorias = [c for c in carregar_categorias() if c != categoria]
    salvar_categorias(categorias)
    return categorias


# Classificações fixas — sempre prevalecem sobre o que estiver salvo no
# arquivo e não podem ser alteradas pela página "Classificar Centros de
# Custo" (nem aparecem lá como editáveis). "AJUSTE" fixado em Backlog Ativo
# a pedido do usuário (2026-10-21): vinha caindo em "Outros" e não deve ser
# reclassificado nunca, por mais que alguém tente editar.
CLASSIFICACOES_FIXAS: dict[str, dict[str, str]] = {
    "AJUSTE": {"nome": "AJUSTE", "categoria": "Backlog Ativo"},
}


def carregar_classificacoes() -> dict[str, dict[str, str]]:
    """Retorna {codigo_cc: {"nome": ..., "categoria": ...}}."""
    mapa = dict(baixar_json(DROPBOX_CLASSIFICACOES, {}))
    mapa.update(CLASSIFICACOES_FIXAS)
    return mapa


def salvar_classificacoes(mapa: dict[str, dict[str, str]]) -> None:
    mapa = dict(mapa)
    mapa.update(CLASSIFICACOES_FIXAS)
    salvar_json(DROPBOX_CLASSIFICACOES, mapa)


def categoria_por_codigo_cc(mapa: dict[str, dict[str, str]]) -> dict[str, str]:
    """Achata para {codigo_cc: categoria} — formato direto pra usar em merge/map."""
    return {codigo: info["categoria"] for codigo, info in mapa.items() if info.get("categoria")}
