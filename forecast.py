"""Simulador de Forecast (páginas 6/7 da apresentação de referência).

Receita Bruta Mensal (página 7): tabela 100% manual, com as mesmas linhas/
classificação da apresentação de referência (2026-08, Cenário Otimista) —
ver LINHAS_RECEITA_SEED. Usada só como ponto de partida na primeira
abertura (sem nada salvo ainda); dali em diante o preenchimento salvo
(qualquer mês, inclusive histórico) manda, e o usuário edita os valores,
os nomes dos projetos e adiciona/remove linhas à vontade — não depende
mais de Centro de Custo nem da Revisão/Orçado (por pedido explícito do
usuário, 2026-10-20).

Lucro Bruto: tabela no mesmo modelo da Receita Bruta Mensal (mesmas
linhas/Classificação, mesmo Complexo, espelhando sempre a lista atual da
Receita — ver _chave_linha), só pros meses sem Realizado ainda. Com
Imposto de IMPOSTO_FORECAST_PCT (10%) da Receita Bruta — 0% pra qualquer
linha com "Indenização" no nome (confirmado pelo usuário, 2026-10-20: não
tem a tributação normal de Receita — ver imposto_pct_linha) — o Custo de
cada linha é calculado matematicamente a partir do Lucro Bruto preenchido:

    Receita Líquida (linha) = Receita Bruta (linha) × (1 - Imposto da linha)
    Custo (linha)           = Lucro Bruto (linha) - Receita Líquida (linha)   (sempre ≤ 0)

A DRE soma Receita Bruta/Custo/Lucro Bruto de todas as linhas do mês.

Dali pra baixo (Despesa Administrativa/Financeira/Imposto de Renda, até
Lucro Líquido) vem da Revisão "em vigor" no mês seguinte ao último
Realizado fechado (revisao_atual_forecast + despesa_dre_mes) — pedido
explícito do usuário, 2026-10-20: Realizado fechado até Agosto -> Despesa
de Setembro em diante usa REV02 (janela já começou em Julho); fechado até
Setembro -> usa REV03 (janela começa em Outubro, o mês seguinte).

Preenchimento salvo num único arquivo JSON no Dropbox — ver DROPBOX_FORECAST
em config.py."""

import pandas as pd

from config import DROPBOX_FORECAST
from dados import calcular_dre, calcular_previsto_com_fallback_despesa, revisao_vigente_no_mes
from dropbox_io import baixar_json, salvar_json

CENARIO_FORECAST = "Otimista"
IMPOSTO_FORECAST_PCT = 0.10

# Margem Bruta % padrão pra pré-preencher o Lucro Bruto de uma linha
# quando ainda não foi salvo nada pra ela — editável livremente depois,
# só poupa o usuário de digitar tudo do zero.
MARGEM_PADRAO_PCT = 20.0

# Tolerância numérica pra validação de Custo ≤ 0 (evita falso-positivo por
# arredondamento de ponto flutuante em Margem Bruta % = 100,000001%).
_EPSILON = 0.01


def imposto_pct_linha(complexo: str) -> float:
    """Imposto da linha — 0% pra Indenização (confirmado pelo usuário,
    2026-10-20: lançamento indenizatório não tem a tributação normal de
    Receita), IMPOSTO_FORECAST_PCT (10%) pras demais."""
    if "indeniza" in (complexo or "").lower():
        return 0.0
    return IMPOSTO_FORECAST_PCT

# Linhas da Receita Bruta Mensal, transcritas direto da página 7 da
# apresentação de referência (jan-dez/26, Cenário Otimista) — mesma
# Classificação/ordem/agrupamento do PDF. Só usada como semente na
# primeira abertura (ver carregar_linhas_receita); todo o resto do ano é
# resultado de o usuário ter editado em cima disso. Meses: Jan,Fev,Mar,
# Abr,Mai,Jun,Jul,Ago,Set,Out,Nov,Dez.
LINHAS_RECEITA_SEED = [
    ("BackLog", "BackLog Ativo + Inativo", [9140583, 10851224, 10239773, 12822938, 10780638, 11488553, 12140209, 10525888, 11615703, 9018710, 8452924, 3118888]),
    ("Capex A Vender", "Capex A Vender", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3041350]),
    ("Plano de Guerra", "Antecipação de Receita", [0, 376311, 469625, 0, 394485, 0, 0, 0, 0, 0, 0, 3798000]),
    ("Plano de Guerra", "Custo", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    ("Plano de Guerra", "Indenização", [0, 0, 0, 643589, 900000, 0, 0, 569386, 0, 0, 300000, 300000]),
    ("Super Meta A Vender", "Reajuste Retroativo", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1099000]),
    ("Indenizações", "Supermeta", [0, 0, 0, 0, 0, 0, 0, 0, 0, 3897065, 3897065, 3274513]),
    ("BackLog Novo", "ALBRÁS RETROFIT INSTRUMENTAÇÃO BARCARENA", [0, 0, 0, 0, 0, 0, 243934, 482720, 782720, 185491, 0, 0]),
    ("BackLog Novo", "CAPEX CMOC DIAGNÓSTICO EM PONTE ROLANTE", [0, 0, 0, 0, 0, 0, 0, 109900, 0, 0, 0, 0]),
    ("BackLog Novo", "DOW REFRATÁRIOS PA", [0, 110387, 145025, 82886, 82920, 124141, 141728, 115226, 124141, 124141, 124141, 124141]),
    ("BackLog Novo", "DOW SOLDA BREU BRANCO", [0, 23624, 47246, 47250, 47248, 47248, 55567, 45698, 47248, 47248, 47248, 47248]),
    ("BackLog Novo", "HYDRO ALBRÁS ANDAIMES PA", [0, 0, 0, 0, 0, 0, 0, 0, 162215, 199620, 237025, 237025]),
    ("BackLog Novo", "HYDRO ALBRÁS MANUTENÇÃO DE TELHADOS PA", [0, 0, 0, 0, 0, 0, 0, 0, 532755, 532755, 532755, 532755]),
    ("BackLog Novo", "HYDRO ALUNORTE ACESSO E ISOLAMENTO PA", [0, 0, 1541308, 2322613, 2317677, 3145710, 3138046, 3261112, 3196630, 3196630, 3196630, 3196630]),
    ("BackLog Novo", "HYDRO ALUNORTE CORREIAS PA", [0, 0, 0, 0, 0, 248820, 804814, 117887, 0, 0, 0, 0]),
    ("BackLog Novo", "HYDRO ALUNORTE SINDIQUIMICOS PA", [0, 0, 0, 0, 34092, 0, 309066, 94475, 39125, 0, 0, 0]),
    ("BackLog Novo", "LARGO ANDAIMES BA", [155627, 137849, 163388, 190446, 202999, 116037, 176376, 146984, 158048, 158048, 153088, 158048]),
    ("BackLog Novo", "METRO BH", [0, 0, 0, 598735, 218399, 0, -370440, 0, 0, 0, 0, 0]),
    ("BackLog Novo", "VALE ALPINISMO ITABIRA", [0, 0, 0, 0, 0, 269830, 184841, 197149, 197149, 197149, 197149, 197149]),
    ("BackLog Novo", "VALE ALPINISMO MARIANA", [0, 0, 0, 193040, 316712, 155962, 220885, 150634, 150634, 150634, 150634, 150634]),
    ("BackLog Novo", "VALE ANDAIMES BRUCUTU MG", [0, 0, 0, 0, 0, 66885, 577286, 378521, 471692, 589615, 589615, 0]),
    ("BackLog Novo", "VALE ANDAIMES VARGEM GRANDE", [0, 0, 0, 0, 1068189, 695139, 729219, 1889268, 1644678, 1693813, 0, 0]),
    ("BackLog Novo", "VALE INTEGRIDADE NOVA LIMA", [0, 0, 0, 0, 0, 0, 0, 0, 847550, 1147550, 1247550, 1247550]),
    ("BackLog Novo", "VALE SOLDADORES ITABIRA", [20037, 363245, 233608, 242206, 242320, 248904, 242973, 235430, 244732, 253274, 253274, 253274]),
    ("BackLog Novo", "VALE SOLDADORES PARAOPEBA", [0, 189680, 96066, 122972, 115881, 101610, 114132, 105976, 107239, 114132, 114132, 114132]),
    ("BackLog Novo", "VLI ELETROMECÂNICA ES", [126237, 952319, 523519, 504985, 523381, 329520, 370129, 428348, 428348, 428348, 428348, 428348]),
    ("Funil de vendas", "CAPEX - ANGLOGOLD LAMEGO - LAVADOR", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 336726, 1234660]),
    ("Funil de vendas", "CAPEX - ANGLOGOLD LAMEGO - OFICINA DE PNEUS", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 576741, 1297666]),
    ("Funil de vendas", "CAPEX - ANGLOGOLD LAMEGO - SALAS DAS OFICINAS", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 365576, 1340446]),
    ("Funil de vendas", "CAPEX - EUROCHEM SÃO LUÍS - TELHADOS E REC", [0, 0, 0, 0, 0, 0, 0, 0, 0, 300000, 1200000, 0]),
    ("Funil de vendas", "CAPEX - HYDRO ALBRÁS - INSTALAÇÃO MEDIDOR DE VAZÃO", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 359253]),
    ("Funil de vendas", "CAPEX - HYDRO ALBRÁS - MONTAGEM CHAMINÉ", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 600000]),
    ("Funil de vendas", "CAPEX - HYDRO ALBRÁS - TELHADO ROLL ON", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 400600, 959840]),
    ("Funil de vendas", "CAPEX - TERNIUM - OBRAS CIVIS COMPLEMENTARES", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1000000, 1000000]),
    ("Funil de vendas", "CAPEX - TERNIUM - SISTEMA DE REUSO DOS OUTLETS 6", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1000000, 1000000]),
    ("Funil de vendas", "CAPEX HYDRO ALBRÁS - MONTAGEM DE LAJES", [0, 0, 0, 0, 0, 0, 0, 0, 200000, 0, 410000, 842000]),
    ("Funil de vendas", "HYDRO PARAGOMINAS - CALDEIRARIA", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2817031, 910000]),
    ("Funil de vendas", "SPOT", [0, 0, 0, 0, 0, 0, 0, 0, 0, 653678, 653678, 653678]),
    ("Funil de vendas", "Vale Base Metals Sossego - Eletromecânica", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    ("Funil de vendas", "Vale BID Nacional B - Pelotização Porto Maranhão", [0, 0, 0, 0, 0, 0, 0, 0, 360000, 0, 3000000, 2100000]),
    ("Funil de vendas", "Vale Nacional Andaimes A - Mina de Brucutu", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2232000, 1650000]),
]

# Só essa Classificação entra no bucket "Funil de Vendas" do resumo final
# (Total - Operação + Plano de Guerra / Total - Funil de Vendas) — todo o
# resto cai em "Operação + Plano de Guerra", igual à apresentação de
# referência.
CLASSIFICACAO_FUNIL_VENDAS = "funil de vendas"


def meses_forecast(df_real: pd.DataFrame, ano: int) -> list[pd.Timestamp]:
    """Meses de `ano` que ainda não têm Realizado fechado."""
    meses_ano = df_real.loc[df_real["Mes"].dt.year == ano, "Mes"]
    ultimo_real = meses_ano.max() if not meses_ano.empty else None
    inicio = pd.Timestamp(year=ano, month=1, day=1) if ultimo_real is None else ultimo_real + pd.DateOffset(months=1)
    fim = pd.Timestamp(year=ano, month=12, day=1)
    if inicio > fim:
        return []
    return list(pd.date_range(inicio, fim, freq="MS"))


def revisao_atual_forecast(df_real: pd.DataFrame, revisoes_disponiveis: list[str], ano: int) -> str:
    """Revisão "em vigor" pro mês seguinte ao último Realizado fechado —
    usada tanto pra pré-preencher a Margem Bruta % padrão quanto pra trazer
    a Despesa (Administrativa/Financeira/Imposto de Renda) da DRE do
    Forecast. A mais recente cujo próprio período de previsão
    (MESES_SUBSTITUIR_POR_REV) já começou a valer: Realizado fechado até
    Agosto -> REV02 (janela começa Julho); fechado até Setembro -> REV03
    (janela começa Outubro, mês seguinte)."""
    meses_ano = df_real.loc[df_real["Mes"].dt.year == ano, "Mes"]
    ultimo_real = meses_ano.max() if not meses_ano.empty else None
    proximo_mes = 1 if ultimo_real is None else ultimo_real.month + 1
    return revisao_vigente_no_mes(proximo_mes, revisoes_disponiveis)


def _vazio() -> dict:
    return {"linhas_receita": None, "lucro_bruto": {}}


def carregar_forecast() -> dict:
    """{"linhas_receita": [{"classificacao":, "complexo":, "valores": [12 floats]}, ...] | None,
         "lucro_bruto": {"classificacao||complexo": {"2026-10": valor, ...}, ...}}.
    linhas_receita None -> ainda não foi salvo nada, quem chama usa
    LINHAS_RECEITA_SEED."""
    dado = baixar_json(DROPBOX_FORECAST, None)
    if dado is None:
        return _vazio()
    dado.setdefault("linhas_receita", None)
    dado.setdefault("lucro_bruto", {})
    return dado


def chave_linha(classificacao: str, complexo: str) -> str:
    """Chave estável pra guardar o Lucro Bruto de uma linha — espelha
    sempre a linha correspondente da Receita Bruta Mensal (mesmo
    Classificação+Complexo); renomear a linha lá perde a ligação com o
    Lucro Bruto já salvo (mesmo comportamento de uma Pivot Table)."""
    return f"{classificacao}||{complexo}"


def salvar_forecast(dado: dict) -> None:
    salvar_json(DROPBOX_FORECAST, dado)


def despesa_dre_mes(
    df_previsto: pd.DataFrame, df_refinado: pd.DataFrame, df_real: pd.DataFrame, revisao: str, mes: pd.Timestamp
) -> dict:
    """Despesa Administrativa/Financeira/Imposto de Renda do mês, vindas da
    Revisão "em vigor" (revisao_atual_forecast) — mesma cascata usada no
    resto do app (calcular_previsto_com_fallback_despesa): meses fora da
    janela de previsão da própria Revisão espelham o Realizado (Δ=0), meses
    dentro da janela usam a Despesa própria da Revisão (REV02/REV03) ou a
    cascata cheia (REV00/REV01)."""
    totais, _ = calcular_previsto_com_fallback_despesa(df_previsto, df_refinado, revisao, CENARIO_FORECAST, mes, mes, df_real)
    totais = totais or {}
    return {
        "despesa_adm": totais.get("despesa_adm") or 0.0,
        "despesa_financeira": totais.get("despesa_financeira") or 0.0,
        "imposto_renda": totais.get("imposto_renda") or 0.0,
    }


def lucro_bruto_padrao(receita_bruta: float, complexo: str = "") -> float:
    """Lucro Bruto default de uma linha — MARGEM_PADRAO_PCT sobre a Receita
    Líquida da própria linha (Imposto da linha já descontado — ver
    imposto_pct_linha)."""
    receita_liquida = receita_bruta * (1 - imposto_pct_linha(complexo))
    return round(receita_liquida * (MARGEM_PADRAO_PCT / 100), 2)


def fechar_linha(receita_bruta: float, lucro_bruto: float, imposto_pct: float = IMPOSTO_FORECAST_PCT) -> dict:
    """Fecha Receita Bruta -> Custo -> Lucro Bruto de UMA linha — Lucro
    Bruto vem direto do preenchimento manual (não é mais uma % aplicada, é
    o valor em R$ da própria linha). `imposto_pct` é por linha (ver
    imposto_pct_linha — Indenização não paga Imposto)."""
    imposto = -receita_bruta * imposto_pct
    receita_liquida = receita_bruta + imposto
    custo = lucro_bruto - receita_liquida
    return {
        "receita_bruta": receita_bruta,
        "imposto": imposto,
        "receita_liquida": receita_liquida,
        "custo": custo,
        "margem_bruta": lucro_bruto,
    }


def custo_invalido_linha(receita_bruta: float, lucro_bruto: float, imposto_pct: float = IMPOSTO_FORECAST_PCT) -> bool:
    """True se esse Lucro Bruto fecha um Custo > 0 pra essa linha (Lucro
    Bruto maior do que a própria Receita Líquida da linha) — sempre
    inválido, Custo é uma dedução e não pode virar crédito."""
    return fechar_linha(receita_bruta, lucro_bruto, imposto_pct)["custo"] > _EPSILON


def calcular_dre_forecast_mes(linhas_receita_lucro_imposto: list[tuple[float, float, float]]) -> dict:
    """Fecha a DRE do mês somando Receita Bruta/Imposto/Receita Líquida/
    Custo/Lucro Bruto de todas as linhas — `linhas_receita_lucro_imposto` é
    uma lista de (receita_bruta, lucro_bruto, imposto_pct) por linha (linha
    com Lucro Bruto não preenchido entra como 0, já filtrado por quem
    chama)."""
    campos = ["receita_bruta", "imposto", "receita_liquida", "custo", "margem_bruta"]
    total = dict.fromkeys(campos, 0.0)
    for receita_bruta, lucro_bruto, imposto_pct in linhas_receita_lucro_imposto:
        linha = fechar_linha(receita_bruta, lucro_bruto, imposto_pct)
        for campo in campos:
            total[campo] += linha[campo]
    return total


def dados_forecast_salvo(meses_fc: list[pd.Timestamp]) -> tuple[dict, dict, dict]:
    """Monta (receita_por_linha_mes, lucro_por_linha_mes, nomes_linha) a
    partir do que está SALVO em disco (ver carregar_forecast) — sem
    depender de nenhum editor ao vivo. Usada pra mostrar a DRE do Forecast
    fora da página Forecast (ex: app.py), sempre com o último estado
    salvo."""
    forecast_salvo = carregar_forecast()
    linhas = forecast_salvo.get("linhas_receita")
    if linhas is None:
        linhas = [{"classificacao": c, "complexo": p, "valores": list(v)} for c, p, v in LINHAS_RECEITA_SEED]
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


def fechar_dre_ano(
    df_real: pd.DataFrame,
    df_previsto: pd.DataFrame,
    df_refinado: pd.DataFrame,
    revisao_atual: str,
    meses_realizado: list[pd.Timestamp],
    meses_fc: list[pd.Timestamp],
    receita_por_linha_mes: dict,
    lucro_por_linha_mes: dict,
    nomes_linha: dict,
) -> dict[pd.Timestamp, dict]:
    """DRE completa do ano: Realizado (meses_realizado, direto do Realizado
    fechado) + Forecast (meses_fc, Receita/Lucro Bruto linha a linha +
    Despesa da Revisão em vigor) — mesmo cálculo usado na página Forecast,
    só que reutilizável (ex: pra mostrar na página principal também).
    `nomes_linha` (chave_linha -> nome do Complexo) decide o Imposto de
    cada linha (ver imposto_pct_linha — Indenização não paga)."""
    dre_por_mes = {}
    for mes in meses_realizado:
        dre_por_mes[mes] = calcular_dre(df_real[df_real["Mes"] == mes])

    for mes in meses_fc:
        chave_mes = mes.strftime("%Y-%m")
        linhas_receita_lucro = [
            (receita_bruta, lucro_por_linha_mes[chave_mes].get(chave) or 0.0, imposto_pct_linha(nomes_linha.get(chave)))
            for chave, receita_bruta in receita_por_linha_mes[chave_mes].items()
        ]
        dre_mes = calcular_dre_forecast_mes(linhas_receita_lucro)
        despesa = despesa_dre_mes(df_previsto, df_refinado, df_real, revisao_atual, mes)
        dre_mes["despesa_adm"] = despesa["despesa_adm"]
        dre_mes["ebitda"] = dre_mes["margem_bruta"] + despesa["despesa_adm"]
        dre_mes["despesa_financeira"] = despesa["despesa_financeira"]
        dre_mes["lair"] = dre_mes["ebitda"] + despesa["despesa_financeira"]
        dre_mes["imposto_renda"] = despesa["imposto_renda"]
        dre_mes["lucro_liquido"] = dre_mes["lair"] + despesa["imposto_renda"]
        dre_por_mes[mes] = dre_mes

    return dre_por_mes


def validar_lucro_bruto(
    receita_por_linha: dict[str, float],
    lucro_por_linha: dict[str, float | None],
    nomes_linha: dict[str, str],
    rotulo_mes: str,
) -> list[str]:
    """Valida o Lucro Bruto de um mês, linha a linha — vazia quando está
    tudo certo. Linha com Receita Bruta zerada/ausente não precisa de
    Lucro Bruto preenchido (nada pra prever ali). `nomes_linha` traduz a
    chave interna (chave_linha) pro nome do Complexo, só pra mensagem."""
    erros = []
    faltando = []
    invalidas = []
    for chave, receita_bruta in receita_por_linha.items():
        if not receita_bruta:
            continue
        lucro_bruto = lucro_por_linha.get(chave)
        nome = nomes_linha.get(chave, chave)
        if lucro_bruto is None or (isinstance(lucro_bruto, float) and pd.isna(lucro_bruto)):
            faltando.append(nome)
        elif custo_invalido_linha(receita_bruta, lucro_bruto, imposto_pct_linha(nome)):
            invalidas.append(nome)
    if faltando:
        if len(faltando) > 6:
            erros.append(f"**{rotulo_mes}**: {len(faltando)} linhas sem Lucro Bruto preenchido.")
        else:
            erros.append(f"**{rotulo_mes}**: Lucro Bruto não preenchido em {', '.join(faltando)}.")
    if invalidas:
        if len(invalidas) > 6:
            erros.append(f"**{rotulo_mes}**: {len(invalidas)} linhas com Lucro Bruto maior que a Receita Líquida (Custo ficaria positivo).")
        else:
            erros.append(f"**{rotulo_mes}**: Lucro Bruto maior que a Receita Líquida (Custo ficaria positivo) em {', '.join(invalidas)}.")
    return erros
