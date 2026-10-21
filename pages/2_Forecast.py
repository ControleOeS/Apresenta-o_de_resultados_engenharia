"""Simulador de Forecast (páginas 6/7 da apresentação de referência) —
ver docstring de forecast.py pra regra de negócio completa."""

import pandas as pd
import streamlit as st

from dados import (
    LINHAS_DRE_DEF,
    LINHAS_MARGEM,
    MESES_PT,
    carregar_meta_mensal,
    carregar_previsto,
    carregar_previsto_refinado,
    carregar_realizado_superus,
)
from estilo import VERDE_ESCURO, VERMELHO, render_tabela_com_faixa
from formatting import format_brl_md, format_pct, format_pct_av
from forecast import (
    CLASSIFICACAO_FUNIL_VENDAS,
    LINHAS_RECEITA_SEED,
    carregar_forecast,
    chave_linha,
    fechar_dre_ano,
    lucro_bruto_padrao,
    meses_forecast,
    revisao_atual_forecast,
    salvar_forecast,
    validar_lucro_bruto,
)
from auth import mostrar_banner_ambiente, require_password

st.set_page_config(page_title="Forecast", page_icon="🔮", layout="wide")
require_password()
mostrar_banner_ambiente()
st.title("Simulador de Forecast")
st.caption(
    "Receita Bruta Mensal — mesmas linhas da apresentação de referência. Só os meses sem Realizado "
    "fechado ainda ficam editáveis (não faz sentido prever um resultado que já está posto); "
    "renomeie projetos e adicione ou exclua linhas à vontade (ícone no fim de cada linha / botão "
    "'+' no rodapé da tabela). Preencha também a Margem Bruta % dos meses em aberto pra fechar o "
    "Custo/Lucro Bruto na DRE. Fica tudo salvo neste computador."
)

df_real = carregar_realizado_superus()
df_previsto = carregar_previsto()
df_refinado = carregar_previsto_refinado()

ano = int(df_real["Mes"].max().year)
meses_fc = meses_forecast(df_real, ano)

if not meses_fc:
    st.success(f"Todos os meses de {ano} já têm Realizado fechado — nada para prever por enquanto.")
    st.stop()

revisoes_disponiveis = sorted(set(df_previsto["Revisão"].unique().tolist()) | set(df_refinado["Revisão"].unique().tolist()))
revisao_atual = revisao_atual_forecast(df_real, revisoes_disponiveis, ano)
ultimo_mes_real = df_real.loc[df_real["Mes"].dt.year == ano, "Mes"].max()
meses_realizado = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= ultimo_mes_real]
todos_meses_ano = [pd.Timestamp(year=ano, month=m, day=1) for m in range(1, 13)]


def _chave_mes(mes: pd.Timestamp) -> str:
    return mes.strftime("%Y-%m")


def _rotulo_mes(mes: pd.Timestamp) -> str:
    sufixo = " *Forecast*" if mes in meses_fc else ""
    return f"{MESES_PT[mes.month]}/{str(mes.year)[2:]}{sufixo}"


rotulos_meses = [_rotulo_mes(mes) for mes in todos_meses_ano]

forecast_salvo = carregar_forecast()

# ------------------------------------------------------------------
# Receita Bruta Mensal — mesmas linhas da página 7 de referência (semente
# só na primeira abertura; depois disso é sempre o que foi salvo).
# ------------------------------------------------------------------
st.header("Receita Bruta Mensal")
st.caption("*Forecast* = mês ainda sem Realizado fechado.")

linhas_salvas = forecast_salvo.get("linhas_receita")
if linhas_salvas is None:
    linhas_atuais = [{"classificacao": c, "complexo": p, "valores": list(v)} for c, p, v in LINHAS_RECEITA_SEED]
else:
    linhas_atuais = linhas_salvas

registros = []
for linha in linhas_atuais:
    valores = linha["valores"]
    registro = {"Classificação": linha["classificacao"], "Complexo": linha["complexo"]}
    for rotulo, valor in zip(rotulos_meses, valores):
        registro[rotulo] = valor
    total_linha = sum(v for v in valores if v is not None)
    registro[f"Total {ano}"] = total_linha
    registros.append(registro)

total_geral_atual = sum(r[f"Total {ano}"] for r in registros) or 1
for r in registros:
    r["AV%"] = r[f"Total {ano}"] / total_geral_atual

tabela_receita = pd.DataFrame(registros)

rotulos_realizado = [_rotulo_mes(mes) for mes in meses_realizado]
rotulos_fc = [_rotulo_mes(mes) for mes in meses_fc]

mostrar_realizado = st.checkbox(
    "Mostrar meses com Realizado já fechado",
    value=False,
    help="Os meses fechados não são editáveis mesmo quando exibidos — é só pra consulta/conferência.",
)
colunas_visiveis = ["Classificação", "Complexo"] + (rotulos_realizado if mostrar_realizado else []) + rotulos_fc + [f"Total {ano}", "AV%"]

editado = st.data_editor(
    tabela_receita,
    hide_index=True,
    use_container_width=True,
    num_rows="dynamic",
    column_order=colunas_visiveis,
    # Mês com Realizado já fechado não é editável aqui — não faz sentido
    # "prever" um resultado que já está posto. Só os meses em aberto
    # (meses_fc) ficam liberados pra preenchimento. Ficam ocultos por
    # padrão (checkbox acima) pra não poluir a tela.
    disabled=[*rotulos_realizado, f"Total {ano}", "AV%"],
    column_config={
        **{col: st.column_config.NumberColumn(col, format="localized", step=1000) for col in rotulos_meses},
        f"Total {ano}": st.column_config.NumberColumn(f"Total {ano}", format="localized"),
        "AV%": st.column_config.NumberColumn("AV%", format="percent"),
    },
    key="editor_receita_mensal",
)

# ------------------------------------------------------------------
# Resumo final: Operação + Plano de Guerra x Funil de Vendas — igual ao
# quadro pequeno abaixo da tabela principal na página 7 de referência.
# ------------------------------------------------------------------
eh_funil = editado["Classificação"].astype(str).str.strip().str.lower() == CLASSIFICACAO_FUNIL_VENDAS
valores_operacao = [editado.loc[~eh_funil, rotulo].fillna(0).sum() for rotulo in rotulos_meses]
valores_funil = [editado.loc[eh_funil, rotulo].fillna(0).sum() for rotulo in rotulos_meses]
valores_total = [editado[rotulo].fillna(0).sum() for rotulo in rotulos_meses]
total_geral_ano = sum(valores_total) or 1

TH_P7 = f"padding:5px 8px; text-align:right; background-color:{VERDE_ESCURO}; color:white; font-weight:700; white-space:nowrap; font-size:0.78rem;"
TH_ROTULO = f"text-align:left; padding:6px 12px; background-color:{VERDE_ESCURO}; color:white;"


def _linha_resumo_html(rotulo: str, valores: list[float]) -> str:
    celulas = "".join(
        f"<td style='padding:4px 8px; text-align:right; white-space:nowrap; font-size:0.78rem;'>{format_brl_md(v) if v else '-'}</td>"
        for v in valores
    )
    total_linha = sum(valores)
    av = format_pct_av(total_linha, total_geral_ano)
    return (
        f"<tr style='font-weight:700; background-color:#DCE8CB;'><td style='padding:4px 10px; white-space:nowrap; font-size:0.8rem;'>{rotulo}</td>"
        f"{celulas}<td style='padding:4px 8px; text-align:right; font-weight:700; white-space:nowrap; font-size:0.78rem;'>{format_brl_md(total_linha)}</td>"
        f"<td style='padding:4px 8px; text-align:right; white-space:nowrap; font-size:0.78rem;'>{av}</td></tr>"
    )


cabecalho_resumo = "".join(f"<th style='{TH_P7}'>{rotulo}</th>" for rotulo in rotulos_meses)
tabela_resumo_html = (
    "<table style='border-collapse:collapse; font-size:0.8rem; color:#1a1a1a;'>"
    f"<tr><th style='{TH_ROTULO}'>Classificação</th>{cabecalho_resumo}<th style='{TH_P7}'>Total {ano}</th><th style='{TH_P7}'>AV%</th></tr>"
    + _linha_resumo_html("Total - Operação + Plano de Guerra", valores_operacao)
    + _linha_resumo_html("Total - Funil de Vendas", valores_funil)
    + _linha_resumo_html("Total", valores_total)
    + "</table>"
)
st.markdown(tabela_resumo_html, unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------
# Lucro Bruto — mesmo modelo de tabela da Receita Bruta Mensal (mesmas
# linhas, espelhadas ao vivo do editor acima), só pros meses em aberto.
# Custo é calculado automaticamente (Imposto de 10%, 0% pra Indenização).
# ------------------------------------------------------------------
st.header("Lucro Bruto")
st.caption(
    "Mesmas linhas da Receita Bruta Mensal acima — preencha o Lucro Bruto (R$) de cada uma nos "
    "meses em aberto; o Custo de cada linha é calculado automaticamente (Receita Líquida - Lucro "
    "Bruto, com Imposto de 10% — linhas de Indenização não pagam Imposto). Linha sem Receita Bruta "
    "no mês não precisa de Lucro Bruto. Já vem pré-preenchido com 20% de margem sobre a Receita "
    "Líquida — edite à vontade."
)

lucro_salvo = forecast_salvo.get("lucro_bruto", {})

linhas_lucro = []
for _, linha in editado.iterrows():
    classificacao = linha.get("Classificação")
    complexo = linha.get("Complexo")
    if (pd.isna(classificacao) or not str(classificacao).strip()) and (pd.isna(complexo) or not str(complexo).strip()):
        continue
    classificacao_str = "" if pd.isna(classificacao) else str(classificacao)
    complexo_str = "" if pd.isna(complexo) else str(complexo)
    chave = chave_linha(classificacao_str, complexo_str)
    registro = {"Classificação": classificacao_str, "Complexo": complexo_str}
    for mes in meses_fc:
        rotulo = _rotulo_mes(mes)
        salvo = lucro_salvo.get(chave, {}).get(_chave_mes(mes))
        if salvo is None:
            receita_bruta_linha = linha.get(rotulo)
            salvo = lucro_bruto_padrao(receita_bruta_linha, complexo_str) if receita_bruta_linha else None
        registro[rotulo] = salvo
    linhas_lucro.append(registro)

tabela_lucro = pd.DataFrame(linhas_lucro)
editado_lucro = st.data_editor(
    tabela_lucro,
    hide_index=True,
    use_container_width=True,
    disabled=["Classificação", "Complexo"],
    column_config={col: st.column_config.NumberColumn(col, format="localized", step=1000) for col in rotulos_fc},
    key="editor_lucro_bruto",
)

if st.button("💾 Salvar Forecast", type="primary"):
    novas_linhas = []
    for _, linha in editado.iterrows():
        classificacao = linha.get("Classificação")
        complexo = linha.get("Complexo")
        if (pd.isna(classificacao) or not str(classificacao).strip()) and (pd.isna(complexo) or not str(complexo).strip()):
            continue
        valores = [None if pd.isna(linha.get(r)) else float(linha.get(r)) for r in rotulos_meses]
        novas_linhas.append(
            {
                "classificacao": "" if pd.isna(classificacao) else str(classificacao),
                "complexo": "" if pd.isna(complexo) else str(complexo),
                "valores": valores,
            }
        )

    novo_lucro_bruto = {}
    for _, linha in editado_lucro.iterrows():
        chave = chave_linha(linha.get("Classificação") or "", linha.get("Complexo") or "")
        novo_lucro_bruto[chave] = {
            _chave_mes(mes): (None if pd.isna(linha.get(_rotulo_mes(mes))) else float(linha.get(_rotulo_mes(mes))))
            for mes in meses_fc
        }

    novo_forecast = carregar_forecast()
    novo_forecast["linhas_receita"] = novas_linhas
    novo_forecast["lucro_bruto"] = novo_lucro_bruto
    salvar_forecast(novo_forecast)
    st.success("Forecast salvo.")
    st.rerun()

st.divider()

# ------------------------------------------------------------------
# Validação — nenhuma DRE aparece enquanto houver erro.
# ------------------------------------------------------------------
nomes_linha = {}
receita_por_linha_mes = {}
lucro_por_linha_mes = {}
for mes in meses_fc:
    receita_por_linha_mes[_chave_mes(mes)] = {}
    lucro_por_linha_mes[_chave_mes(mes)] = {}

for _, linha in editado.iterrows():
    classificacao = linha.get("Classificação")
    complexo = linha.get("Complexo")
    if (pd.isna(classificacao) or not str(classificacao).strip()) and (pd.isna(complexo) or not str(complexo).strip()):
        continue
    classificacao_str = "" if pd.isna(classificacao) else str(classificacao)
    complexo_str = "" if pd.isna(complexo) else str(complexo)
    chave = chave_linha(classificacao_str, complexo_str)
    nomes_linha[chave] = complexo_str or classificacao_str
    for mes in meses_fc:
        valor = linha.get(_rotulo_mes(mes))
        receita_por_linha_mes[_chave_mes(mes)][chave] = 0.0 if pd.isna(valor) else float(valor)

for _, linha in editado_lucro.iterrows():
    chave = chave_linha(linha.get("Classificação") or "", linha.get("Complexo") or "")
    for mes in meses_fc:
        valor = linha.get(_rotulo_mes(mes))
        lucro_por_linha_mes[_chave_mes(mes)][chave] = None if pd.isna(valor) else float(valor)

erros = []
for mes in meses_fc:
    chave_mes = _chave_mes(mes)
    erros += validar_lucro_bruto(receita_por_linha_mes[chave_mes], lucro_por_linha_mes[chave_mes], nomes_linha, _rotulo_mes(mes))

if erros:
    st.error("⚠️ A DRE só aparece depois que o Lucro Bruto estiver certo:\n\n" + "\n".join(f"- {e}" for e in erros))
    st.stop()

# ------------------------------------------------------------------
# DRE — Realizado (Jan até o último mês fechado) + Forecast (meses em
# aberto), somando a Receita Bruta Mensal e o Lucro Bruto editados acima.
# ------------------------------------------------------------------
st.header(f"DRE — {ano}")

dre_por_mes = fechar_dre_ano(
    df_real, df_previsto, df_refinado, revisao_atual, meses_realizado, meses_fc,
    receita_por_linha_mes, lucro_por_linha_mes, nomes_linha,
)

dre_total_ano = {campo: sum(dre_por_mes[mes][campo] for mes in dre_por_mes) for _, campo, _ in LINHAS_DRE_DEF}
base_av_ano = dre_total_ano["receita_bruta"]

# Meta Otimista (META ANO SUPERUS.xlsx) — só como colunas de referência
# (Meta + Δ Forecast-Meta) no fim da mesma tabela, não entra em nenhum
# cálculo do Forecast.
meta_mensal = carregar_meta_mensal("Otimista")
meta_total_ano = {campo: sum(meta_mensal[mes.month][campo] for mes in dre_por_mes) for _, campo, _ in LINHAS_DRE_DEF}

TH_VALOR = f"padding:6px 6px; text-align:right; background-color:{VERDE_ESCURO}; color:white; font-weight:700; white-space:nowrap;"
TH_META = f"padding:6px 6px; text-align:right; background-color:#5B7B4A; color:white; font-weight:700; white-space:nowrap;"
TH_DELTA = TH_META


def _espacador_th() -> str:
    # Gap físico (~10% da largura de uma célula) pra separar o bloco Meta/Δ
    # de verdade do resto da DRE, sem nenhuma cor (branco sólido, não
    # "transparent") — pedido do usuário, 2026-10-21.
    return "<th style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></th>"


def _espacador_td() -> str:
    return "<td style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></td>"


def _td_valor(valor) -> str:
    cor = f"color:{VERMELHO};" if (valor or 0) < 0 else ""
    return f"<td style='padding:6px 6px; text-align:right; white-space:nowrap; {cor}'>{format_brl_md(valor)}</td>"


linhas_html = []
for nome, campo, destaque in LINHAS_DRE_DEF:
    estilo_linha = "font-weight:700; background-color:#EAF2E0;" if destaque else "background-color:#FFFFFF;"
    celulas = "".join(_td_valor(dre_por_mes[mes][campo]) for mes in dre_por_mes)
    celula_total = _td_valor(dre_total_ano[campo])
    celula_meta = _td_valor(meta_total_ano[campo])
    celula_delta = _td_valor(dre_total_ano[campo] - meta_total_ano[campo])
    linhas_html.append(
        f"<tr style='{estilo_linha}'><td style='padding:6px 10px; white-space:nowrap;'>{nome}</td>"
        f"{celulas}{celula_total}{_espacador_td()}{celula_meta}{celula_delta}</tr>"
    )
    if campo in LINHAS_MARGEM:
        celulas_pct = "".join(
            f"<td style='padding:4px 6px; text-align:right;'>{format_pct_av(dre_por_mes[mes][campo], dre_por_mes[mes]['receita_bruta'])}</td>"
            for mes in dre_por_mes
        )
        celula_pct_total = f"<td style='padding:4px 6px; text-align:right;'>{format_pct_av(dre_total_ano[campo], base_av_ano)}</td>"
        pct_meta = meta_total_ano[campo] / meta_total_ano["receita_bruta"] if meta_total_ano["receita_bruta"] else None
        pct_forecast = dre_total_ano[campo] / base_av_ano if base_av_ano else None
        celula_pct_meta = (
            f"<td style='padding:4px 6px; text-align:right;'>"
            f"{format_pct_av(meta_total_ano[campo], meta_total_ano['receita_bruta'])}</td>"
        )
        delta_pp = None if pct_meta is None or pct_forecast is None else pct_forecast - pct_meta
        celula_pct_delta = f"<td style='padding:4px 6px; text-align:right;'>{format_pct(delta_pp)}</td>"
        linhas_html.append(
            "<tr style='font-style:italic; color:#555; background-color:#F7F9F4;'>"
            f"<td style='padding:4px 10px 4px 20px;'>{LINHAS_MARGEM[campo]}</td>"
            f"{celulas_pct}{celula_pct_total}{_espacador_td()}{celula_pct_meta}{celula_pct_delta}</tr>"
        )

cabecalho_meses = "".join(f"<th style='{TH_VALOR}'>{MESES_PT[mes.month]}/{str(mes.year)[2:]}</th>" for mes in dre_por_mes)
tabela_dre_html = (
    "<table style='width:100%; border-collapse:collapse; font-size:0.8rem; color:#1a1a1a;'>"
    f"<tr><th style='{TH_ROTULO}'>DRE - Engenharia</th>{cabecalho_meses}<th style='{TH_VALOR}'>Total {ano}</th>"
    f"{_espacador_th()}<th style='{TH_META}'>Meta Otimista</th><th style='{TH_DELTA}'>Δ Forecast-Meta</th></tr>"
    + "".join(linhas_html)
    + "</table>"
)

st.markdown(
    render_tabela_com_faixa(f"Jan-{MESES_PT[meses_fc[-1].month]}/{ano}", tabela_dre_html, largura_total=True),
    unsafe_allow_html=True,
)

st.caption(
    "Os gráficos de histórico 2022-2025 (parte de baixo da página 6) continuam bloqueados — essa "
    "base só tem 2026. **Meta Otimista/Δ** = DRE anual alvo (META ANO SUPERUS.xlsx, Cenário "
    "Otimista) pro ano inteiro, só como referência — não entra em nenhum cálculo; Δ = Forecast "
    "menos Meta."
)
