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
