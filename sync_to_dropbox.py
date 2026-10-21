"""Upload manual (sem agendamento no Task Scheduler) dos arquivos que são
só desse projeto — não compartilhados com o DASH_DIRETORIA. Rode de novo
sempre que atualizar RESULTADOS 2025.xlsx, DESPESA REV02.xlsx ou
META ANO SUPERUS.xlsx na pasta local; os outros 6 arquivos que o app usa já
são sincronizados pelo DASH_DIRETORIA (mesma conta Dropbox)."""

from pathlib import Path

from dotenv import load_dotenv

from config import (
    ARQUIVO_DESPESA_REV02,
    ARQUIVO_META_SUPERUS,
    ARQUIVO_RESULTADO_2025,
    DROPBOX_DESPESA_REV02,
    DROPBOX_META_SUPERUS,
    DROPBOX_RESULTADO_2025,
)
from dropbox_auth import get_access_token
from dropbox_io import upload

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

ARQUIVOS = [
    (ARQUIVO_RESULTADO_2025, DROPBOX_RESULTADO_2025),
    (ARQUIVO_DESPESA_REV02, DROPBOX_DESPESA_REV02),
    (ARQUIVO_META_SUPERUS, DROPBOX_META_SUPERUS),
]


def sync():
    token = get_access_token()
    for local_path, dropbox_path in ARQUIVOS:
        with open(local_path, "rb") as f:
            content = f.read()
        upload(token, dropbox_path, content)
        print(f"Upload OK: {dropbox_path} ({len(content)} bytes)")


if __name__ == "__main__":
    sync()
