"""Simulador de Forecast (páginas 6/7 da apresentação de referência) —
ver docstring de forecast.py pra regra de negócio completa."""

import pandas as pd
import streamlit as st

from dados import (
    LINHAS_DRE_DEF,
    LINHAS_MARGEM,
    MESES_PT,
    NIVEL_DESPESA_FINANCEIRA,
    NIVEL_IMPOSTO_RENDA,
    NIVEL_OUTROS,
    carregar_previsto,
    carregar_previsto_refinado,
    carregar_realizado_2025_mensal,
    carregar_realizado_superus,
    dre_2025_periodo,
    previsto_mensal_ano,
)
from estilo import VERDE_ESCURO, VERMELHO, render_tabela_com_faixa
from formatting import format_brl_md, format_pct_av, format_pp
from forecast import (
    CLASSIFICACAO_FUNIL_VENDAS,
    LINHAS_RECEITA_SEED,
    carregar_forecast,
    chave_linha,
    fechar_dre_ano,
    fechar_linha,
    gerar_excel_export,
    imposto_pct_linha,
    lucro_bruto_padrao,
    meses_forecast,
    revisao_atual_forecast,
    salvar_forecast,
    validar_lucro_bruto,
)
from analise_categoria import (
    _detalhar,
    custo_por_cc_realizado,
    despesa_por_cc_realizado,
    imposto_por_cc_realizado,
    receita_por_cc_realizado,
)
from auth import mostrar_banner_ambiente, pedir_senha_edicao_forecast, pode_editar_forecast, require_password

st.set_page_config(page_title="Forecast", page_icon="🔮", layout="wide")
require_password()
mostrar_banner_ambiente()
st.title("Simulador de Forecast")
st.caption(
    "Receita Bruta Mensal — mesmas linhas da apresentação de referência. Só os meses sem Realizado "
    "fechado ainda ficam editáveis (não faz sentido prever um resultado que já está posto); "
    "renomeie projetos e adicione ou exclua linhas à vontade (ícone no fim de cada linha / botão "
    "'+' no rodapé da tabela). Preencha também a Margem Bruta % dos meses em aberto pra fechar o "
    "Custo/Lucro Bruto na DRE. Fica tudo salvo no Dropbox."
)

pedir_senha_edicao_forecast()
edicao_liberada = pode_editar_forecast()
if not edicao_liberada:
    st.info("👁️ Modo somente visualização — digite a senha de edição acima pra editar e salvar.")

df_real = carregar_realizado_superus()
df_previsto = carregar_previsto()
df_refinado = carregar_previsto_refinado()
realizado_2025_mensal = carregar_realizado_2025_mensal()

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
    # Nome de coluna de tabela não renderiza Markdown — "*Forecast*" aparecia
    # com os asteriscos literais na tela (item 16, 2026-11-11).
    sufixo = " (Forecast)" if mes in meses_fc else ""
    return f"{MESES_PT[mes.month]}/{str(mes.year)[2:]}{sufixo}"


rotulos_meses = [_rotulo_mes(mes) for mes in todos_meses_ano]

forecast_salvo = carregar_forecast()

# ------------------------------------------------------------------
# Receita Bruta Mensal — mesmas linhas da página 7 de referência (semente
# só na primeira abertura; depois disso é sempre o que foi salvo).
# ------------------------------------------------------------------
st.header("Receita Bruta Mensal (em R$)")
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
    num_rows="dynamic" if edicao_liberada else "fixed",
    column_order=colunas_visiveis,
    # Mês com Realizado já fechado não é editável aqui — não faz sentido
    # "prever" um resultado que já está posto. Só os meses em aberto
    # (meses_fc) ficam liberados pra preenchimento. Ficam ocultos por
    # padrão (checkbox acima) pra não poluir a tela. Sem a senha de edição
    # do Forecast, a tabela toda fica travada (só visualização).
    disabled=True if not edicao_liberada else [*rotulos_realizado, f"Total {ano}", "AV%"],
    column_config={
        "Classificação": st.column_config.TextColumn("Classificação", width="medium", pinned=True),
        "Complexo": st.column_config.TextColumn("Complexo", width="large", pinned=True),
        # Sem casa decimal, sem indicador de moeda (fica só no título "(em
        # R$)" da seção) e com separador de milhar — "," é a única opção de
        # agrupamento que o data_editor do Streamlit aceita hoje (sem
        # suporte nativo a locale pt-BR; as tabelas de DRE/Resumo abaixo,
        # que não são editáveis, continuam no padrão brasileiro com ponto).
        **{col: st.column_config.NumberColumn(col, format="%,d", step=1000, width="small") for col in rotulos_meses},
        f"Total {ano}": st.column_config.NumberColumn(f"Total {ano}", format="%,d", step=1, width="small"),
        "AV%": st.column_config.NumberColumn("AV%", format="percent", width="small"),
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
# position:sticky: 1a coluna fixa na rolagem horizontal (item 29).
TH_ROTULO = f"text-align:left; padding:6px 12px; background-color:{VERDE_ESCURO}; color:white; position:sticky; left:0; z-index:2;"


def _linha_resumo_html(rotulo: str, valores: list[float]) -> str:
    celulas = "".join(
        f"<td style='padding:4px 8px; text-align:right; white-space:nowrap; font-size:0.78rem;'>{format_brl_md(v)}</td>"
        for v in valores
    )
    total_linha = sum(valores)
    av = format_pct_av(total_linha, total_geral_ano)
    return (
        f"<tr style='font-weight:700; background-color:#DCE8CB;'><td style='padding:4px 10px; white-space:nowrap; font-size:0.8rem; position:sticky; left:0; z-index:1; background-color:#DCE8CB;'>{rotulo}</td>"
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
st.markdown(f"<div style='overflow-x:auto;'>{tabela_resumo_html}</div>", unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------
# Lucro Bruto — mesmo modelo de tabela da Receita Bruta Mensal (mesmas
# linhas, espelhadas ao vivo do editor acima), só pros meses em aberto.
# Custo é calculado automaticamente (Imposto de 10%, 0% pra Indenização).
# ------------------------------------------------------------------
st.header("Lucro Bruto (em R$)")
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
# Coluna que mistura float e None (linha "Super Meta" sem Receita Bruta no
# mês, ver lucro_bruto_padrao acima) fica com dtype object — o grid do
# data_editor mostra um None de coluna-objeto como texto literal "None"
# (um NaN de coluna float fica em branco). Cast pra float converte None
# em NaN automaticamente — só exibição, não mexe na leitura/salvamento
# (que já trata pd.isna() corretamente). Item 15, 2026-11-11.
for _col in rotulos_fc:
    if _col in tabela_lucro.columns:
        tabela_lucro[_col] = tabela_lucro[_col].astype(float)
editado_lucro = st.data_editor(
    tabela_lucro,
    hide_index=True,
    use_container_width=True,
    disabled=True if not edicao_liberada else ["Classificação", "Complexo"],
    column_config={
        "Classificação": st.column_config.TextColumn("Classificação", width="medium", pinned=True),
        "Complexo": st.column_config.TextColumn("Complexo", width="large", pinned=True),
        **{col: st.column_config.NumberColumn(col, format="%,d", step=1000, width="small") for col in rotulos_fc},
    },
    key="editor_lucro_bruto",
)

if edicao_liberada and st.button("💾 Salvar Forecast", type="primary"):
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
base_av_ano = dre_total_ano["receita_liquida"]

# Meta Otimista — trocado de META ANO SUPERUS.xlsx (meta estática) pro
# Orçado (Cenário Otimista) da Revisão "em vigor" (mesma Revisão usada pra
# Despesa no Forecast), ano inteiro — pedido do usuário, 2026-11-18. Campo
# sem base nenhuma pra algum mês vira None no total, nunca soma parcial.
orc_mensal_otimista = previsto_mensal_ano(df_previsto, df_refinado, df_real, revisao_atual, "Otimista", ano)
meta_total_ano = {
    campo: (None if orc_mensal_otimista[campo].isna().any() else float(orc_mensal_otimista[campo].sum()))
    for _, campo, _ in LINHAS_DRE_DEF
}

# Realizado do ano anterior — comparação direta com o Forecast do ano
# corrente (ano inteiro), mesma fonte usada na DRE Mês/Acumulado do "app"
# (RESULTADOS {ano-1}.xlsx, carregar_realizado_2025_mensal em dados.py).
# Pedido do usuário, 2026-11-18.
dre_ano_anterior_total = dre_2025_periodo(
    realizado_2025_mensal, pd.Timestamp(year=ano, month=1, day=1), pd.Timestamp(year=ano, month=12, day=1)
)

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
    cor_fundo_linha = "#EAF2E0" if destaque else "#FFFFFF"
    estilo_linha = f"font-weight:700; background-color:{cor_fundo_linha};" if destaque else f"background-color:{cor_fundo_linha};"
    valor_meta = meta_total_ano[campo]
    valor_ano_anterior = dre_ano_anterior_total.get(campo) if dre_ano_anterior_total else None
    celulas = "".join(_td_valor(dre_por_mes[mes][campo]) for mes in dre_por_mes)
    celula_total = _td_valor(dre_total_ano[campo])
    celula_meta = _td_valor(valor_meta)
    celula_delta = _td_valor(None if valor_meta is None else dre_total_ano[campo] - valor_meta)
    celula_ano_anterior = _td_valor(valor_ano_anterior)
    celula_delta_ano_anterior = _td_valor(None if valor_ano_anterior is None else dre_total_ano[campo] - valor_ano_anterior)
    linhas_html.append(
        f"<tr style='{estilo_linha}'><td style='padding:6px 10px; white-space:nowrap; position:sticky; left:0; z-index:1; background-color:{cor_fundo_linha};'>{nome}</td>"
        f"{celulas}{celula_total}{_espacador_td()}{celula_meta}{celula_delta}"
        f"{_espacador_td()}{celula_ano_anterior}{celula_delta_ano_anterior}</tr>"
    )
    if campo in LINHAS_MARGEM:
        def _td_pct(valor, base) -> str:
            cor = f"color:{VERMELHO};" if (valor or 0) < 0 else ""
            return f"<td style='padding:4px 6px; text-align:right; {cor}'>{format_pct_av(valor, base, manter_sinal=True)}</td>"

        celulas_pct = "".join(
            _td_pct(dre_por_mes[mes][campo], dre_por_mes[mes]["receita_liquida"]) for mes in dre_por_mes
        )
        celula_pct_total = _td_pct(dre_total_ano[campo], base_av_ano)
        base_meta = meta_total_ano["receita_liquida"]
        pct_meta = valor_meta / base_meta if valor_meta is not None and base_meta else None
        pct_forecast = dre_total_ano[campo] / base_av_ano if base_av_ano else None
        celula_pct_meta = _td_pct(valor_meta, base_meta)
        delta_pp = None if pct_meta is None or pct_forecast is None else pct_forecast - pct_meta
        celula_pct_delta = f"<td style='padding:4px 6px; text-align:right;'>{format_pp(delta_pp)}</td>"
        base_ano_anterior = dre_ano_anterior_total.get("receita_liquida") if dre_ano_anterior_total else None
        pct_ano_anterior = (
            valor_ano_anterior / base_ano_anterior if valor_ano_anterior is not None and base_ano_anterior else None
        )
        celula_pct_ano_anterior = _td_pct(valor_ano_anterior, base_ano_anterior)
        delta_pp_ano_anterior = (
            None if pct_ano_anterior is None or pct_forecast is None else pct_forecast - pct_ano_anterior
        )
        celula_pct_delta_ano_anterior = f"<td style='padding:4px 6px; text-align:right;'>{format_pp(delta_pp_ano_anterior)}</td>"
        linhas_html.append(
            "<tr style='font-style:italic; color:#555; background-color:#F7F9F4;'>"
            f"<td style='padding:4px 10px 4px 20px; position:sticky; left:0; z-index:1; background-color:#F7F9F4;'>{LINHAS_MARGEM[campo]}</td>"
            f"{celulas_pct}{celula_pct_total}{_espacador_td()}{celula_pct_meta}{celula_pct_delta}"
            f"{_espacador_td()}{celula_pct_ano_anterior}{celula_pct_delta_ano_anterior}</tr>"
        )

cabecalho_meses = "".join(f"<th style='{TH_VALOR}'>{MESES_PT[mes.month]}/{str(mes.year)[2:]}</th>" for mes in dre_por_mes)
tabela_dre_html = (
    "<table style='width:100%; border-collapse:collapse; font-size:0.8rem; color:#1a1a1a;'>"
    f"<tr><th style='{TH_ROTULO}'>DRE - Superus Engenharia</th>{cabecalho_meses}<th style='{TH_VALOR}'>Total {ano}</th>"
    f"{_espacador_th()}<th style='{TH_META}'>Meta Otimista</th><th style='{TH_DELTA}'>Δ Forecast-Meta</th>"
    f"{_espacador_th()}<th style='{TH_META}'>Realizado {ano - 1}</th><th style='{TH_DELTA}'>Δ Forecast-Real.{str(ano - 1)[2:]}</th></tr>"
    + "".join(linhas_html)
    + "</table>"
)

st.markdown(
    render_tabela_com_faixa(f"Jan-{MESES_PT[meses_fc[-1].month]}/{ano} (em R$)", tabela_dre_html, largura_total=True),
    unsafe_allow_html=True,
)

st.caption(
    "Os gráficos de histórico 2022-2025 (parte de baixo da página 6) continuam bloqueados — essa "
    "base só tem 2026. **Meta Otimista/Δ** = Orçado (Cenário Otimista) da Revisão em vigor "
    f"(**{revisao_atual}**) pro ano inteiro — acompanha automaticamente a Revisão mais recente "
    "conforme o ano avança; não entra em nenhum cálculo do Forecast; Δ = Forecast menos Meta. "
    f"**Realizado {ano - 1}/Δ** = DRE fechada de {ano - 1} (RESULTADOS {ano - 1}.xlsx), ano inteiro, "
    f"só comparativo; Δ = Forecast {ano} menos Realizado {ano - 1}."
)

# ------------------------------------------------------------------
# Exportar Excel — snapshot completo do que está na tela agora: Receita
# Bruta Mensal e Lucro Bruto (linha a linha), o detalhamento linha a linha
# do Forecast (Receita/Imposto/Receita Líquida/Custo/Lucro Bruto por mês
# em aberto), o detalhamento do Realizado por Centro de Custo (meses já
# fechados) e a DRE consolidada (Realizado + Forecast, mês a mês). Só
# leitura: não mexe em nada salvo no Dropbox.
# ------------------------------------------------------------------
st.divider()

df_receita_exp = editado[["Classificação", "Complexo"] + rotulos_meses + [f"Total {ano}", "AV%"]].copy()

# Lucro Bruto só sai pros meses em aberto (rotulos_fc) — tentamos estender
# pros meses já fechados usando o nome do "Complexo" pra achar o Centro de
# Custo correspondente no Realizado, mas não bate: o nome digitado no
# Forecast é uma versão resumida/digitada à mão (ex. "HYDRO ALUNORTE
# ACESSO E ISOLAMENTO PA") e o Centro de Custo real do Realizado tem outra
# grafia (ex. "HYDRO ALUNORTE - ACESSO E ISOLAMENTO - BARCARENA- PA") — 0
# de 37 linhas batem exatamente, e casar por aproximação seria chute (o
# que não é aceitável pra dado financeiro). Até existir um de-para
# confiável Complexo -> Centro de Custo, os meses fechados ficam de fora
# em vez de sair com valor errado ou em branco fingindo ser dado real.
df_lucro_exp = editado_lucro[["Classificação", "Complexo"] + rotulos_fc].copy()

# Detalhamento linha a linha do Forecast (só meses em aberto — mesmas
# linhas/valores já usados na validação/DRE acima).
detalhe_forecast_linhas = []
for _, linha in editado.iterrows():
    classificacao = linha.get("Classificação")
    complexo = linha.get("Complexo")
    if (pd.isna(classificacao) or not str(classificacao).strip()) and (pd.isna(complexo) or not str(complexo).strip()):
        continue
    classificacao_str = "" if pd.isna(classificacao) else str(classificacao)
    complexo_str = "" if pd.isna(complexo) else str(complexo)
    chave = chave_linha(classificacao_str, complexo_str)
    imposto_pct = imposto_pct_linha(complexo_str)
    for mes in meses_fc:
        chave_mes = _chave_mes(mes)
        receita_bruta_linha = receita_por_linha_mes[chave_mes].get(chave) or 0.0
        lucro_bruto_linha = lucro_por_linha_mes[chave_mes].get(chave)
        if not receita_bruta_linha or lucro_bruto_linha is None:
            continue
        fechado = fechar_linha(receita_bruta_linha, lucro_bruto_linha, imposto_pct)
        detalhe_forecast_linhas.append(
            {
                "Classificação": classificacao_str,
                "Complexo": complexo_str,
                "Mês": _rotulo_mes(mes),
                "Receita Bruta": fechado["receita_bruta"],
                "Imposto": fechado["imposto"],
                "Receita Líquida": fechado["receita_liquida"],
                "Custo": fechado["custo"],
                "Lucro Bruto": fechado["margem_bruta"],
            }
        )
df_forecast_detalhado = pd.DataFrame(
    detalhe_forecast_linhas,
    columns=["Classificação", "Complexo", "Mês", "Receita Bruta", "Imposto", "Receita Líquida", "Custo", "Lucro Bruto"],
)

# Detalhamento do Realizado por Centro de Custo (meses já fechados, antes
# do Forecast) — reaproveita as mesmas funções de categoria usadas no
# resto do app, mês a mês.
_funcoes_realizado = [
    ("Receita Bruta", lambda m: receita_por_cc_realizado(df_real, m, m)),
    ("Imposto", lambda m: imposto_por_cc_realizado(df_real, m, m)),
    ("Custo", lambda m: custo_por_cc_realizado(df_real, m, m)),
    ("Despesa Administrativa", lambda m: despesa_por_cc_realizado(df_real, m, m)),
    ("Outros", lambda m: _detalhar(df_real[df_real["Nível 1"].isin(NIVEL_OUTROS) & (df_real["Mes"] == m)], "Cod. Centro de Custo", "Centro de Custo")),
    ("Despesa Financeira", lambda m: _detalhar(df_real[df_real["Nível 1"].isin(NIVEL_DESPESA_FINANCEIRA) & (df_real["Mes"] == m)], "Cod. Centro de Custo", "Centro de Custo")),
    ("Imposto de Renda", lambda m: _detalhar(df_real[df_real["Nível 1"].isin(NIVEL_IMPOSTO_RENDA) & (df_real["Mes"] == m)], "Cod. Centro de Custo", "Centro de Custo")),
]
_partes_realizado = []
for mes in meses_realizado:
    for tipo_nome, funcao in _funcoes_realizado:
        detalhe = funcao(mes)
        if detalhe is None or detalhe.empty:
            continue
        detalhe = detalhe.copy()
        detalhe["Tipo"] = tipo_nome
        detalhe["Mês"] = _rotulo_mes(mes)
        _partes_realizado.append(detalhe)
df_realizado_detalhado = (
    pd.concat(_partes_realizado, ignore_index=True)[["Mês", "Tipo", "Categoria", "Codigo", "Centro de Custo", "Valor"]]
    if _partes_realizado
    else pd.DataFrame(columns=["Mês", "Tipo", "Categoria", "Codigo", "Centro de Custo", "Valor"])
)

linhas_dre_exp = []
for nome, campo, _ in LINHAS_DRE_DEF:
    registro = {"DRE": nome}
    for mes in dre_por_mes:
        registro[f"{MESES_PT[mes.month]}/{str(mes.year)[2:]}"] = dre_por_mes[mes][campo]
    registro[f"Total {ano}"] = dre_total_ano[campo]
    linhas_dre_exp.append(registro)
df_dre_exp = pd.DataFrame(linhas_dre_exp)

excel_bytes = gerar_excel_export(
    {
        "Receita Bruta Mensal": df_receita_exp,
        "Lucro Bruto": df_lucro_exp,
        "Forecast Detalhado": df_forecast_detalhado,
        "Realizado Detalhado": df_realizado_detalhado,
        "DRE": df_dre_exp,
    },
    colunas_percentual={"Receita Bruta Mensal": ["AV%"]},
)
st.download_button(
    "📥 Exportar Forecast em Excel",
    data=excel_bytes,
    file_name=f"forecast_{ano}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help=(
        "Receita Bruta Mensal / Lucro Bruto: linhas do Forecast (ano todo). "
        "Forecast Detalhado: Receita/Imposto/Receita Líquida/Custo/Lucro Bruto linha a linha, "
        "só meses em aberto. Realizado Detalhado: mesma quebra por Centro de Custo, mês a mês, "
        "pros meses já fechados. DRE: consolidado mensal (Realizado + Forecast)."
    ),
)
