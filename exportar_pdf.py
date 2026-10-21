"""Exporta a página do app para PDF usando o Chromium instalado na máquina
(Edge ou Chrome) em modo headless, via Chrome DevTools Protocol — garante
que o PDF é um retrato fiel do que está sendo exibido na tela (mesmo CSS,
mesmas cores, mesmos gráficos), em vez de uma reconstrução separada."""

import base64
import contextlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time

import psutil
import requests
import websocket

_CANDIDATOS_NAVEGADOR = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def localizar_navegador() -> str:
    for caminho in _CANDIDATOS_NAVEGADOR:
        if os.path.exists(caminho):
            return caminho
    raise FileNotFoundError(
        "Nenhum navegador Chromium (Edge/Chrome) encontrado para gerar o PDF."
    )


def porta_do_servidor_atual(porta_padrao: int = 8501) -> int:
    """Descobre em qual porta o próprio processo Streamlit está escutando —
    evita depender de uma porta fixa quando o app é iniciado de formas
    diferentes (atalho, linha de comando com --server.port, etc.)."""
    processo = psutil.Process(os.getpid())
    try:
        conexoes = processo.net_connections(kind="inet")
    except AttributeError:
        conexoes = processo.connections(kind="inet")
    for c in conexoes:
        if c.status == psutil.CONN_LISTEN:
            return c.laddr.port
    return porta_padrao


def _porta_livre() -> int:
    with contextlib.closing(socket.socket()) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def gerar_pdf(url: str, espera_segundos: float = 10.0, paisagem: bool = True) -> bytes:
    navegador = localizar_navegador()
    porta_debug = _porta_livre()
    perfil_temp = tempfile.mkdtemp(prefix="apresentacao_pdf_")
    try:
        processo = subprocess.Popen(
            [
                navegador,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-extensions",
                "--no-first-run",
                f"--user-data-dir={perfil_temp}",
                f"--remote-debugging-port={porta_debug}",
                "--remote-allow-origins=*",
                "--window-size=1600,1200",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            pagina = None
            for _ in range(50):
                try:
                    tabs = requests.get(f"http://localhost:{porta_debug}/json", timeout=1).json()
                    pagina = next((t for t in tabs if t.get("type") == "page"), None)
                    if pagina:
                        break
                except Exception:
                    pass
                time.sleep(0.2)
            if not pagina:
                raise RuntimeError("Não foi possível conectar ao navegador headless para exportar o PDF.")

            ws = websocket.create_connection(pagina["webSocketDebuggerUrl"], timeout=60)
            msg_id = 0

            def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
                while True:
                    resposta = json.loads(ws.recv())
                    if resposta.get("id") == msg_id:
                        return resposta

            send("Page.enable")
            send("Page.navigate", {"url": url})
            time.sleep(espera_segundos)
            resultado = send(
                "Page.printToPDF",
                {
                    "landscape": paisagem,
                    "printBackground": True,
                    "preferCSSPageSize": True,
                    "scale": 0.65,
                },
            )
            ws.close()
            if "result" not in resultado:
                raise RuntimeError(f"Falha ao gerar PDF: {resultado}")
            return base64.b64decode(resultado["result"]["data"])
        finally:
            processo.terminate()
            try:
                processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait(timeout=5)
            time.sleep(0.5)
    finally:
        shutil.rmtree(perfil_temp, ignore_errors=True)
