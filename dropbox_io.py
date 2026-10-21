"""Helpers de baixo nível pra ler/gravar arquivos no Dropbox — mesma conta/
app usada pelo DASH_DIRETORIA (reaproveitada por pedido do usuário,
2026-10-21), pra poder rodar na nuvem (Streamlit Community Cloud) sem
depender do disco local. `rev` (revisão do arquivo no Dropbox) é usado como
cache_key dos loaders cacheados em dados.py — invalida sozinho quando o
arquivo muda, sem precisar de TTL."""

import json

import requests
import streamlit as st

from dropbox_auth import get_access_token


def get_metadata(token: str, path: str) -> dict:
    resp = requests.post(
        "https://api.dropboxapi.com/2/files/get_metadata",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"path": path},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def download(token: str, path: str) -> bytes:
    resp = requests.post(
        "https://content.dropboxapi.com/2/files/download",
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": path}),
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content


def upload(token: str, path: str, content: bytes) -> None:
    args = {"path": path, "mode": "overwrite", "mute": True}
    resp = requests.post(
        "https://content.dropboxapi.com/2/files/upload",
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps(args),
            "Content-Type": "application/octet-stream",
        },
        data=content,
        timeout=60,
    )
    resp.raise_for_status()


def token_e_rev(path: str) -> tuple[str, str]:
    """(token, rev) de um arquivo — rev vira cache_key de quem chama. Se o
    arquivo ainda não existe no Dropbox (primeiro save), retorna rev=""."""
    token = get_access_token()
    try:
        meta = get_metadata(token, path)
        return token, meta["rev"]
    except requests.HTTPError:
        return token, ""


@st.cache_data(show_spinner=False)
def _baixar_json_cache(_token: str, cache_key: str, path: str, padrao):
    if not cache_key:
        # Arquivo ainda não existe no Dropbox (primeiro uso) — nada salvo.
        return padrao
    content = download(_token, path)
    return json.loads(content.decode("utf-8"))


def baixar_json(path: str, padrao):
    """Lê um JSON do Dropbox (estado editável do app: classificações,
    categorias, forecast) — cacheado por rev, igual aos loaders de Excel em
    dados.py. `padrao` é o que volta se o arquivo ainda não existir lá
    (primeiro save de quem for usar)."""
    token, rev = token_e_rev(path)
    return _baixar_json_cache(token, rev, path, padrao)


def salvar_json(path: str, dados) -> None:
    token = get_access_token()
    content = json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    upload(token, path, content)


def token_e_revs(paths: list[str]) -> tuple[str, str]:
    """Igual a token_e_rev, mas combina a rev de vários arquivos num cache_key
    só — pra loaders que juntam mais de um arquivo Dropbox numa função
    cacheada só (ex: carregar_previsto, que junta REV00 Mod+Otim e REV01)."""
    token = get_access_token()
    revs = []
    for path in paths:
        try:
            revs.append(get_metadata(token, path)["rev"])
        except requests.HTTPError:
            revs.append("")
    return token, "|".join(revs)
