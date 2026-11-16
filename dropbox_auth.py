import os

import requests
import streamlit as st


def _get_secret(key: str) -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ[key]


# Comprovado por profiling (2026-11-11, item 32): get_access_token() não
# tinha cache nenhum, então toda chamada a token_e_rev()/token_e_revs()/
# salvar_json() buscava um token novo via POST ao Dropbox (até 7 vezes numa
# única troca de filtro) mesmo o token anterior ainda sendo válido (tokens
# de refresh_token do Dropbox duram ~4h). TTL de 30min fica bem dentro
# dessa janela de validade.
@st.cache_data(ttl=1800, show_spinner=False)
def get_access_token() -> str:
    resp = requests.post(
        "https://api.dropboxapi.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": _get_secret("DROPBOX_REFRESH_TOKEN"),
            "client_id": _get_secret("DROPBOX_APP_KEY"),
            "client_secret": _get_secret("DROPBOX_APP_SECRET"),
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
