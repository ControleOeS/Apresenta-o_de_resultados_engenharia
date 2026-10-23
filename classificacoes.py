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
#
# Os demais (2026-10-23) são "códigos-bucket" da aba "Tabelas dimensão" do
# Refinado Engenharias — texto no lugar de um código numérico de verdade
# (JURIDICO, PLR, SEM RATEIO, CATERING ASAP, DIRETORIA COMERCIAL,
# GERENTES REGIONAIS, ESTOQUE - BALDIM, DESMOBILIZADO), só usados no
# Orçado/Previsto. Nunca aparecem na página "Classificar Centros de Custo"
# pra edição (ela só lista códigos de Realizado/Previsto "antigo", não os
# do Refinado) — ficam fixos aqui, por instrução direta do usuário.
# "01962.S01GO" é um código numérico de verdade que aponta pro mesmo nome
# "GERENTES REGIONAIS" na tabela dimensão — mesma categoria, por
# consistência. "PLR" fica na categoria "PLR" de propósito (não uma das
# categorias de Despesa normais) — mesma categoria que o Realizado já usa
# pros Centro de Custo com "PLR " no nome (ver _marcar_plr_pelo_nome em
# analise_categoria.py), pra ficar igual entre Previsto e Realizado.
CLASSIFICACOES_FIXAS: dict[str, dict[str, str]] = {
    "AJUSTE": {"nome": "AJUSTE", "categoria": "Backlog Ativo"},
    "JURIDICO": {"nome": "JURIDICO", "categoria": "Não operacional"},
    "PLR": {"nome": "PLR GESTORES", "categoria": "PLR"},
    "SEM RATEIO": {"nome": "SEM RATEIO", "categoria": "Outros"},
    "CATERING ASAP": {"nome": "CATERING ASAP", "categoria": "Backlog Inativo"},
    "DIRETORIA COMERCIAL": {"nome": "COMISSÃO - COMERCIAL", "categoria": "Despesa - Comercial"},
    "GERENTES REGIONAIS": {"nome": "GERENTES REGIONAIS", "categoria": "Não operacional"},
    "01962.S01GO": {"nome": "GERENTES REGIONAIS", "categoria": "Não operacional"},
    "ESTOQUE - BALDIM": {"nome": "ESTOQUE - BALDIM", "categoria": "Estoque"},
    "DESMOBILIZADO": {"nome": "CMOC", "categoria": "Backlog Inativo"},
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
