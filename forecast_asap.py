"""Simulador de Forecast da ASAP — mesmo modelo da Superus (forecast.py),
versão simplificada: só a fonte manual (sem "Forecast de Oportunidades"/
"Forecast com Desmob", que são cenários específicos de clientes/obras da
Superus/Vale, confirmado com o usuário, 2026-11-24) e sem Despesa
fragmentada por Revisão (a ASAP tem cascata completa em cada arquivo de
Previsto — ver previsto_asap.py). Arquivo salvo à parte no Dropbox
(DROPBOX_FORECAST_ASAP), nunca o mesmo da Superus.

Reaproveita de forecast.py tudo que já é genérico (fechar_linha,
calcular_dre_forecast_mes, chave_linha, lucro_bruto_padrao,
imposto_pct_linha, validar_lucro_bruto) — só o que dependia do Previsto/
Dropbox específico da Superus foi reescrito aqui."""

import pandas as pd

from config import DROPBOX_FORECAST_ASAP
from dropbox_io import baixar_json, salvar_json
from forecast import calcular_dre_forecast_mes, chave_linha, imposto_pct_linha
from previsto_asap import calcular_previsto_efetivo_asap

# Semente da grade de Receita Bruta Mensal da ASAP — transcrita pelo usuário
# de uma tabela "Forecast – Receita 2026" (Cliente x mês), 2026-11-24. Só
# usada como ponto de partida na primeira abertura (igual à Superus); dali
# em diante o preenchimento salvo manda. "pode ignorar a questão da
# margem" (usuário) — só a Receita Bruta tem semente; o Lucro Bruto
# continua pré-preenchido via lucro_bruto_padrao (20% padrão), igual à
# Superus.
#
# PREMISSA (não confirmada explicitamente, sinalizada ao usuário): os
# valores transcritos (ex.: LATAM ~2184 em Jan) são pequenos demais pra ser
# R$ puro num cliente desse porte (a LATAM sozinha já é o maior Centro de
# Custo do Realizado da ASAP) — tratados aqui como R$ MIL, mesma convenção
# já usada em outro arquivo deste projeto (META ANO SUPERUS.xlsx, ver
# config.py: "valores em R$ mil"). Confirmar com o usuário se os números
# batendo errado por 1000x aparecerem na DRE.
LINHAS_RECEITA_SEED_ASAP = [
    ("Backlog", "ASAP REFEIÇÕES", [10_000, 16_000, 13_000, 25_000, 7_000, 18_000, None, 46_000, 11_000, 4_000, None, None]),
    ("Backlog", "AZUL", [98_000, 98_000, 148_000, 92_000, 102_000, 92_000, 77_000, 108_000, 122_000, 218_000, 187_000, 187_000]),
    ("Backlog", "DAN HERBERT", [100_000, 177_000, 71_000, 178_000, 185_000, 109_000, 116_000, 165_000, 99_000, 9_000, None, None]),
    ("Backlog", "GOVERNAMENTAIS", [18_000, 11_000, 35_000, 32_000, 72_000, 45_000, 68_000, 83_000, 41_000, 72_000, 42_000, 42_000]),
    ("Backlog", "GREEN GARDEN", [None, None, None, None, None, None, None, 21_000, 65_000, 46_000, 51_000, 51_000]),
    ("Backlog", "LATAM", [2_184_000, 2_297_000, 1_970_000, 2_354_000, 2_265_000, 2_146_000, 2_295_000, 2_334_000, 2_231_000, 2_335_000, 2_434_000, 3_800_000]),
    ("Backlog", "LATAM INTER - BUENOS AIRES", [192_000, 155_000, 5_000, None, None, None, None, None, None, None, None, None]),
    ("Backlog", "LATAM INTER - SCL", [62_000, 61_000, 144_000, None, 66_000, 60_000, 98_000, None, 172_000, 164_000, 67_000, 65_000]),
    ("Backlog", "PRESIDÊNCIA", [110_000, 176_000, 198_000, 117_000, 190_000, 193_000, 130_000, 210_000, 253_000, 179_000, 237_000, 121_000]),
    ("Backlog", "SALAS VIP, LOJAS (BACKLOG)", [53_000, 54_000, 19_000, 51_000, 52_000, 38_000, 49_000, 35_000, 36_000, 36_000, 34_000, 34_000]),
    ("Comercial", "SMART RAMPS", [None, None, None, None, None, None, None, None, None, None, 1_750_000, None]),
    ("Comercial", "ASAP REFEIÇÕES - CNF", [None] * 12),
    ("Comercial", "LATAM CNF", [None, None, None, None, None, None, None, None, None, None, None, 440_000]),
    ("Comercial", "OPERAÇÕES GUARULHOS", [None] * 12),
    ("Comercial", "RESTAURANTE GOL", [None] * 12),
    ("Comercial", "SALA VIP – CNF", [None] * 12),
]


def _vazio() -> dict:
    return {"linhas_receita": None, "lucro_bruto": {}}


def carregar_forecast_asap() -> dict:
    dado = baixar_json(DROPBOX_FORECAST_ASAP, None)
    if dado is None:
        return _vazio()
    dado.setdefault("linhas_receita", None)
    dado.setdefault("lucro_bruto", {})
    return dado


def salvar_forecast_asap(dado: dict) -> None:
    salvar_json(DROPBOX_FORECAST_ASAP, dado)


def despesa_dre_mes_asap(df_previsto_asap: pd.DataFrame, df_real_asap: pd.DataFrame, revisao: str, mes: pd.Timestamp) -> dict:
    """Despesa Administrativa/Financeira/Imposto de Renda do mês, vindas da
    Revisão "em vigor" da ASAP — mesma ideia de forecast.despesa_dre_mes,
    mas usando calcular_previsto_efetivo_asap (cascata completa, sem
    fallback fragmentado)."""
    totais = calcular_previsto_efetivo_asap(df_real_asap, df_previsto_asap, revisao, "Otimista", mes, mes)
    totais = totais or {}
    return {
        "despesa_adm": totais.get("despesa_adm") or 0.0,
        "despesa_financeira": totais.get("despesa_financeira") or 0.0,
        "imposto_renda": totais.get("imposto_renda") or 0.0,
    }


def fechar_dre_ano_asap(
    df_real_asap: pd.DataFrame,
    df_previsto_asap: pd.DataFrame,
    revisao_atual: str,
    meses_realizado: list[pd.Timestamp],
    meses_fc: list[pd.Timestamp],
    receita_por_linha_mes: dict,
    lucro_por_linha_mes: dict,
    nomes_linha: dict,
) -> dict[pd.Timestamp, dict]:
    """Equivalente a forecast.fechar_dre_ano, sem o seletor de fonte (só a
    manual) — Despesa sempre da Revisão "em vigor" da própria ASAP."""
    from dados import calcular_dre

    dre_por_mes = {}
    for mes in meses_realizado:
        dre_por_mes[mes] = calcular_dre(df_real_asap[df_real_asap["Mes"] == mes])

    for mes in meses_fc:
        chave_mes = mes.strftime("%Y-%m")
        linhas_receita_lucro = [
            (receita_bruta, lucro_por_linha_mes[chave_mes].get(chave) or 0.0, imposto_pct_linha(nomes_linha.get(chave)))
            for chave, receita_bruta in receita_por_linha_mes[chave_mes].items()
        ]
        dre_mes = calcular_dre_forecast_mes(linhas_receita_lucro)
        despesa = despesa_dre_mes_asap(df_previsto_asap, df_real_asap, revisao_atual, mes)
        dre_mes["despesa_adm"] = despesa["despesa_adm"]
        dre_mes["ebitda"] = dre_mes["margem_bruta"] + despesa["despesa_adm"]
        dre_mes["despesa_financeira"] = despesa["despesa_financeira"]
        dre_mes["lair"] = dre_mes["ebitda"] + despesa["despesa_financeira"]
        dre_mes["imposto_renda"] = despesa["imposto_renda"]
        dre_mes["lucro_liquido"] = dre_mes["lair"] + despesa["imposto_renda"]
        dre_por_mes[mes] = dre_mes

    return dre_por_mes


def dados_forecast_salvo_asap(meses_fc: list[pd.Timestamp]) -> tuple[dict, dict, dict]:
    forecast_salvo = carregar_forecast_asap()
    linhas = forecast_salvo.get("linhas_receita")
    if linhas is None:
        linhas = [{"classificacao": c, "complexo": p, "valores": list(v)} for c, p, v in LINHAS_RECEITA_SEED_ASAP]
    lucro_salvo = forecast_salvo.get("lucro_bruto", {})

    receita_por_linha_mes = {mes.strftime("%Y-%m"): {} for mes in meses_fc}
    lucro_por_linha_mes = {mes.strftime("%Y-%m"): {} for mes in meses_fc}
    nomes_linha = {}

    for linha in linhas:
        classificacao = linha.get("classificacao") or ""
        complexo = linha.get("complexo") or ""
        if not classificacao.strip() and not complexo.strip():
            continue
        chave = chave_linha(classificacao, complexo)
        nomes_linha[chave] = complexo or classificacao
        valores = linha.get("valores") or [None] * 12
        for mes in meses_fc:
            chave_mes = mes.strftime("%Y-%m")
            valor_receita = valores[mes.month - 1] if mes.month - 1 < len(valores) else None
            receita_por_linha_mes[chave_mes][chave] = 0.0 if valor_receita is None else float(valor_receita)
            lucro_por_linha_mes[chave_mes][chave] = lucro_salvo.get(chave, {}).get(chave_mes)

    return receita_por_linha_mes, lucro_por_linha_mes, nomes_linha
