""""Forecast de Oportunidades" — cenário alternativo ESTÁTICO de Receita
Bruta/Margem Bruta pro Forecast, lido direto da aba "Forecast super
otimista" do mesmo Excel sincronizado pelo DASH_DIRETORIA
(sync_forecast_oportunidades.py de lá, mesma conta Dropbox — ver
dropbox_auth.py). Só leitura: diferente do Forecast normal desta página
(forecast.py, preenchimento manual salvo em DROPBOX_FORECAST), este nunca
é editado por aqui — muda só se alguém editar o Excel e rodar o sync de
novo no DASH_DIRETORIA. Duplicado (não importado) do forecast_oportunidades.py
do DASH_DIRETORIA, pela mesma regra de independência do resto deste
projeto (ver docstring de dados.py) — pedido do usuário, 2026-11-18.

A aba tem duas tabelas linha a linha (Classificação/Complexo x Jan..Dez),
"Receita Bruta por Cliente" e "Lucro Bruto por Cliente", no mesmo formato
da página "Forecast" desta Apresentação de Resultados. O parser abaixo acha
as seções pelo texto do título/cabeçalho (não por número de linha fixo, pra
não quebrar se a planilha for reorganizada) e reconcilia a soma das linhas
individuais contra as linhas "TOTAL - ..." da própria aba antes de
confiar no resultado — qualquer divergência acima de R$1 interrompe o
carregamento (ver _parse_secao)."""

import datetime
import json
from io import BytesIO

import pandas as pd
import requests
import streamlit as st

from dropbox_auth import get_access_token

DROPBOX_PATH = "/FORECAST - SUPERUS - SETEMBRO.xlsx"
SHEET = "Forecast super otimista"

# Mesma regra do Forecast normal (forecast.py: imposto_pct_linha) e do
# DASH_DIRETORIA: Imposto 0% pra linha de Indenização, 10% pras demais.
IMPOSTO_PCT = 0.10

_TOLERANCIA_RECONCILIACAO = 1.0  # R$1 — folga só pra arredondamento de ponto flutuante


def _imposto_pct_linha(complexo: str) -> float:
    return 0.0 if "indeniza" in (complexo or "").lower() else IMPOSTO_PCT


def _texto(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def _achar_linha(df: pd.DataFrame, coluna: int, texto_contem: str, ini: int = 0) -> int:
    for i in range(ini, len(df)):
        if texto_contem.upper() in _texto(df.iat[i, coluna]).upper():
            return i
    raise ValueError(f'Forecast de Oportunidades: não achei a linha "{texto_contem}" na aba "{SHEET}".')


def _achar_colunas_meses(df: pd.DataFrame, linha_header: int) -> list[int]:
    cols = [
        c
        for c in range(df.shape[1])
        if isinstance(df.iat[linha_header, c], (pd.Timestamp, datetime.datetime, datetime.date))
    ]
    if len(cols) != 12:
        raise ValueError(
            f"Forecast de Oportunidades: esperava 12 colunas de mês na linha de cabeçalho, achei {len(cols)}."
        )
    return cols


def _parse_secao(
    df: pd.DataFrame, linha_ini_exclusive: int, linha_fim_exclusive: int, cols_meses: list[int]
) -> tuple[list[tuple[str, list[float]]], list[tuple[str, list[float]]]]:
    """Linhas individuais (Complexo, [12 valores]) e linhas "TOTAL - ..."
    (subtotal) entre o cabeçalho da seção e `linha_fim_exclusive`."""
    individuais = []
    totais = []
    for i in range(linha_ini_exclusive + 1, linha_fim_exclusive):
        classif = _texto(df.iat[i, 1])
        complexo = _texto(df.iat[i, 2])
        if not classif and not complexo:
            continue
        rotulo = classif or complexo
        if rotulo.upper() in ("TOTAL", "RECEITA BRUTA TOTAL"):
            continue  # total geral da seção — nem individual nem subtotal parcial
        valores = [0.0 if pd.isna(df.iat[i, c]) else float(df.iat[i, c]) for c in cols_meses]
        if rotulo.upper().startswith("TOTAL -"):
            totais.append((rotulo, valores))
        else:
            individuais.append((complexo or classif, valores))
    return individuais, totais


def _reconciliar(nome_secao: str, individuais: list, totais: list) -> None:
    if not totais:
        return
    for mes in range(12):
        soma_individuais = sum(v[mes] for _, v in individuais)
        soma_totais = sum(v[mes] for _, v in totais)
        if abs(soma_individuais - soma_totais) > _TOLERANCIA_RECONCILIACAO:
            raise ValueError(
                f"Forecast de Oportunidades: divergência na seção '{nome_secao}' no mês {mes + 1} "
                f"(soma das linhas = {soma_individuais:,.2f}, soma dos subtotais 'TOTAL - ...' da "
                f"própria aba = {soma_totais:,.2f}) — a estrutura da planilha pode ter mudado, "
                f"conferir manualmente antes de confiar no Forecast de Oportunidades."
            )


def _parse_forecast_oportunidades(content: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content), sheet_name=SHEET, header=None, engine="openpyxl")

    linha_titulo_receita = _achar_linha(df, 1, "Receita Bruta por Cliente")
    linha_titulo_lucro = _achar_linha(df, 1, "Lucro Bruto por Cliente", ini=linha_titulo_receita + 1)
    linha_titulo_reconciliacao = _achar_linha(df, 2, "Lucro bruto realizado", ini=linha_titulo_lucro + 1)

    linha_header_receita = _achar_linha(df, 1, "CLASSIFICA", ini=linha_titulo_receita)
    cols_meses = _achar_colunas_meses(df, linha_header_receita)
    linha_header_lucro = _achar_linha(df, 1, "CLASSIFICA", ini=linha_titulo_lucro)

    linhas_receita, totais_receita = _parse_secao(df, linha_header_receita, linha_titulo_lucro, cols_meses)
    linhas_lucro, totais_lucro = _parse_secao(df, linha_header_lucro, linha_titulo_reconciliacao, cols_meses)

    _reconciliar("Receita Bruta por Cliente", linhas_receita, totais_receita)
    _reconciliar("Lucro Bruto por Cliente", linhas_lucro, totais_lucro)

    receita_bruta_mes = [sum(v[m] for _, v in linhas_receita) for m in range(12)]
    margem_bruta_mes = [sum(v[m] for _, v in linhas_lucro) for m in range(12)]
    imposto_mes = [
        sum(-v[m] * _imposto_pct_linha(complexo) for complexo, v in linhas_receita) for m in range(12)
    ]

    registros = []
    for m in range(12):
        receita_bruta = receita_bruta_mes[m]
        imposto = imposto_mes[m]
        receita_liquida = receita_bruta + imposto
        margem_bruta = margem_bruta_mes[m]
        custo = margem_bruta - receita_liquida
        registros.append(
            {
                "Mes": pd.Timestamp(year=2026, month=m + 1, day=1),
                "receita_bruta": receita_bruta,
                "imposto": imposto,
                "receita_liquida": receita_liquida,
                "custo": custo,
                "margem_bruta": margem_bruta,
            }
        )
    return pd.DataFrame(registros, columns=["receita_bruta", "imposto", "receita_liquida", "custo", "margem_bruta", "Mes"])


@st.cache_data(show_spinner=False)
def _baixar_e_parsear(_token: str, cache_key: str) -> pd.DataFrame:
    resp = requests.post(
        "https://content.dropboxapi.com/2/files/download",
        headers={"Authorization": f"Bearer {_token}", "Dropbox-API-Arg": json.dumps({"path": DROPBOX_PATH})},
        timeout=60,
    )
    resp.raise_for_status()
    return _parse_forecast_oportunidades(resp.content)


def carregar_forecast_oportunidades() -> pd.DataFrame:
    """Receita Bruta/Imposto/Receita Líquida/Custo/Margem Bruta pros 12
    meses de 2026, direto da aba "Forecast super otimista" — DataFrame
    vazio se o arquivo ainda não tiver sido sincronizado (pelo
    DASH_DIRETORIA, que é quem roda o sync)."""
    token = get_access_token()
    try:
        meta_resp = requests.post(
            "https://api.dropboxapi.com/2/files/get_metadata",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"path": DROPBOX_PATH},
            timeout=30,
        )
        meta_resp.raise_for_status()
        rev = meta_resp.json()["rev"]
    except requests.HTTPError:
        return pd.DataFrame(columns=["receita_bruta", "imposto", "receita_liquida", "custo", "margem_bruta", "Mes"])
    return _baixar_e_parsear(token, rev)
