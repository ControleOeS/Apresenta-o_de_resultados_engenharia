"""Aba "Forecast" da ASAP — mesmo modelo da Superus (pagina_forecast.py),
simplificado: só a fonte manual, sem o seletor "Forecast de Oportunidades"/
"Forecast com Desmob" (cenários específicos da Superus/Vale, confirmado
com o usuário que não se aplicam à ASAP, 2026-11-24). Grade salva à parte
no Dropbox (DROPBOX_FORECAST_ASAP, ver forecast_asap.py) — nunca compartilha
arquivo com a Superus."""

import pandas as pd
import streamlit as st

from config import COLIGADAS_ASAP
from dados import LINHAS_DRE_DEF, MESES_PT, carregar_realizado_por_coligadas
from estilo import VERDE_ESCURO, VERMELHO, render_tabela_com_faixa
from formatting import format_brl_md
from forecast import chave_linha, fechar_linha, imposto_pct_linha, lucro_bruto_padrao, meses_forecast, validar_lucro_bruto
from forecast_asap import (
    LINHAS_RECEITA_SEED_ASAP,
    carregar_forecast_asap,
    despesa_dre_mes_asap,
    fechar_dre_ano_asap,
    salvar_forecast_asap,
)
from previsto_asap import carregar_previsto_asap
from dados import revisao_vigente_no_mes


def render() -> None:
    st.title("Simulador de Forecast — ASAP")
    st.caption(
        "Receita Bruta Mensal por Cliente — preencha os meses sem Realizado fechado ainda "
        "(renomeie clientes e adicione ou exclua linhas à vontade); preencha também o Lucro "
        "Bruto (R$) de cada um pra fechar a DRE. Fica tudo salvo no Dropbox, num arquivo "
        "separado do Forecast da Superus."
    )

    df_real = carregar_realizado_por_coligadas(COLIGADAS_ASAP)
    df_previsto = carregar_previsto_asap()
    ano = int(df_real["Mes"].max().year)
    meses_fc = meses_forecast(df_real, ano)

    if not meses_fc:
        st.success(f"Todos os meses de {ano} já têm Realizado fechado — nada para prever por enquanto.")
        return

    revisoes_disponiveis = sorted(df_previsto["Revisão"].unique().tolist())
    ultimo_mes_real = df_real.loc[df_real["Mes"].dt.year == ano, "Mes"].max()
    proximo_mes = 1 if pd.isna(ultimo_mes_real) else ultimo_mes_real.month + 1
    revisao_atual = revisao_vigente_no_mes(proximo_mes, revisoes_disponiveis)
    meses_realizado = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= ultimo_mes_real]
    todos_meses_ano = [pd.Timestamp(year=ano, month=m, day=1) for m in range(1, 13)]

    def _chave_mes(mes: pd.Timestamp) -> str:
        return mes.strftime("%Y-%m")

    def _rotulo_mes(mes: pd.Timestamp) -> str:
        sufixo = " (Forecast)" if mes in meses_fc else ""
        return f"{MESES_PT[mes.month]}/{str(mes.year)[2:]}{sufixo}"

    rotulos_meses = [_rotulo_mes(mes) for mes in todos_meses_ano]
    forecast_salvo = carregar_forecast_asap()

    st.header("Receita Bruta Mensal (em R$)")
    st.caption("*Forecast* = mês ainda sem Realizado fechado.")

    linhas_salvas = forecast_salvo.get("linhas_receita")
    linhas_atuais = (
        linhas_salvas if linhas_salvas is not None
        else [{"classificacao": c, "complexo": p, "valores": list(v)} for c, p, v in LINHAS_RECEITA_SEED_ASAP]
    )

    registros = []
    for linha in linhas_atuais:
        valores = linha["valores"]
        registro = {"Classificação": linha["classificacao"], "Cliente": linha["complexo"]}
        for rotulo, valor in zip(rotulos_meses, valores):
            registro[rotulo] = valor
        total_linha = sum(v for v in valores if v is not None)
        registro[f"Total {ano}"] = total_linha
        registros.append(registro)

    tabela_receita = pd.DataFrame(registros)
    rotulos_realizado = [_rotulo_mes(mes) for mes in meses_realizado]
    rotulos_fc = [_rotulo_mes(mes) for mes in meses_fc]

    mostrar_realizado = st.checkbox(
        "Mostrar meses com Realizado já fechado", value=False, key="asap_mostrar_realizado",
        help="Os meses fechados não são editáveis mesmo quando exibidos — é só pra consulta/conferência.",
    )
    colunas_visiveis = ["Classificação", "Cliente"] + (rotulos_realizado if mostrar_realizado else []) + rotulos_fc + [f"Total {ano}"]

    editado = st.data_editor(
        tabela_receita,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        column_order=colunas_visiveis,
        disabled=[*rotulos_realizado, f"Total {ano}"],
        column_config={
            "Classificação": st.column_config.TextColumn("Classificação", width="medium", pinned=True),
            "Cliente": st.column_config.TextColumn("Cliente", width="large", pinned=True),
            **{col: st.column_config.NumberColumn(col, format="%,d", step=1000, width="small") for col in rotulos_meses},
            f"Total {ano}": st.column_config.NumberColumn(f"Total {ano}", format="%,d", step=1, width="small"),
        },
        key="asap_editor_receita_mensal",
    )

    st.divider()
    st.header("Lucro Bruto (em R$)")
    st.caption(
        "Mesmas linhas da Receita Bruta Mensal acima — preencha o Lucro Bruto (R$) nos meses em "
        "aberto; o Custo é calculado automaticamente (Imposto de 10% sobre a Receita Bruta). Já "
        "vem pré-preenchido com 20% de margem sobre a Receita Líquida — edite à vontade."
    )

    lucro_salvo = forecast_salvo.get("lucro_bruto", {})
    linhas_lucro = []
    for _, linha in editado.iterrows():
        classificacao = linha.get("Classificação")
        cliente = linha.get("Cliente")
        if (pd.isna(classificacao) or not str(classificacao).strip()) and (pd.isna(cliente) or not str(cliente).strip()):
            continue
        classificacao_str = "" if pd.isna(classificacao) else str(classificacao)
        cliente_str = "" if pd.isna(cliente) else str(cliente)
        chave = chave_linha(classificacao_str, cliente_str)
        registro = {"Classificação": classificacao_str, "Cliente": cliente_str}
        for mes in meses_fc:
            rotulo = _rotulo_mes(mes)
            salvo = lucro_salvo.get(chave, {}).get(_chave_mes(mes))
            if salvo is None:
                receita_bruta_linha = linha.get(rotulo)
                salvo = lucro_bruto_padrao(receita_bruta_linha, cliente_str) if receita_bruta_linha else None
            registro[rotulo] = salvo
        linhas_lucro.append(registro)

    tabela_lucro = pd.DataFrame(linhas_lucro)
    for _col in rotulos_fc:
        if _col in tabela_lucro.columns:
            tabela_lucro[_col] = tabela_lucro[_col].astype(float)

    editado_lucro = st.data_editor(
        tabela_lucro,
        hide_index=True,
        use_container_width=True,
        disabled=["Classificação", "Cliente"],
        column_config={
            "Classificação": st.column_config.TextColumn("Classificação", width="medium", pinned=True),
            "Cliente": st.column_config.TextColumn("Cliente", width="large", pinned=True),
            **{col: st.column_config.NumberColumn(col, format="%,d", step=1000, width="small") for col in rotulos_fc},
        },
        key="asap_editor_lucro_bruto",
    )

    if st.button("💾 Salvar Forecast ASAP", type="primary"):
        novas_linhas = []
        for _, linha in editado.iterrows():
            classificacao = linha.get("Classificação")
            cliente = linha.get("Cliente")
            if (pd.isna(classificacao) or not str(classificacao).strip()) and (pd.isna(cliente) or not str(cliente).strip()):
                continue
            valores = [None if pd.isna(linha.get(r)) else float(linha.get(r)) for r in rotulos_meses]
            novas_linhas.append({
                "classificacao": "" if pd.isna(classificacao) else str(classificacao),
                "complexo": "" if pd.isna(cliente) else str(cliente),
                "valores": valores,
            })

        novo_lucro_bruto = {}
        for _, linha in editado_lucro.iterrows():
            chave = chave_linha(linha.get("Classificação") or "", linha.get("Cliente") or "")
            novo_lucro_bruto[chave] = {
                _chave_mes(mes): (None if pd.isna(linha.get(_rotulo_mes(mes))) else float(linha.get(_rotulo_mes(mes))))
                for mes in meses_fc
            }

        novo_forecast = carregar_forecast_asap()
        novo_forecast["linhas_receita"] = novas_linhas
        novo_forecast["lucro_bruto"] = novo_lucro_bruto
        salvar_forecast_asap(novo_forecast)
        st.success("Forecast da ASAP salvo.")
        st.rerun()

    st.divider()

    nomes_linha = {}
    receita_por_linha_mes = {}
    lucro_por_linha_mes = {}
    for mes in meses_fc:
        receita_por_linha_mes[_chave_mes(mes)] = {}
        lucro_por_linha_mes[_chave_mes(mes)] = {}

    for _, linha in editado.iterrows():
        classificacao = linha.get("Classificação")
        cliente = linha.get("Cliente")
        if (pd.isna(classificacao) or not str(classificacao).strip()) and (pd.isna(cliente) or not str(cliente).strip()):
            continue
        classificacao_str = "" if pd.isna(classificacao) else str(classificacao)
        cliente_str = "" if pd.isna(cliente) else str(cliente)
        chave = chave_linha(classificacao_str, cliente_str)
        nomes_linha[chave] = cliente_str or classificacao_str
        for mes in meses_fc:
            valor = linha.get(_rotulo_mes(mes))
            receita_por_linha_mes[_chave_mes(mes)][chave] = 0.0 if pd.isna(valor) else float(valor)

    for _, linha in editado_lucro.iterrows():
        chave = chave_linha(linha.get("Classificação") or "", linha.get("Cliente") or "")
        for mes in meses_fc:
            valor = linha.get(_rotulo_mes(mes))
            lucro_por_linha_mes[_chave_mes(mes)][chave] = None if pd.isna(valor) else float(valor)

    erros = []
    for mes in meses_fc:
        chave_mes = _chave_mes(mes)
        erros += validar_lucro_bruto(receita_por_linha_mes[chave_mes], lucro_por_linha_mes[chave_mes], nomes_linha, _rotulo_mes(mes))

    if erros:
        st.error("⚠️ A DRE só aparece depois que o Lucro Bruto estiver certo:\n\n" + "\n".join(f"- {e}" for e in erros))
        return

    st.header(f"DRE — ASAP {ano}")

    dre_por_mes = fechar_dre_ano_asap(
        df_real, df_previsto, revisao_atual, meses_realizado, meses_fc,
        receita_por_linha_mes, lucro_por_linha_mes, nomes_linha,
    )
    dre_total_ano = {campo: sum(dre_por_mes[mes][campo] for mes in dre_por_mes) for _, campo, _ in LINHAS_DRE_DEF}

    TH_VALOR = f"padding:6px 6px; text-align:right; background-color:{VERDE_ESCURO}; color:white; font-weight:700; white-space:nowrap;"
    TH_ROTULO = f"text-align:left; padding:6px 10px; background-color:{VERDE_ESCURO}; color:white; position:sticky; left:0; z-index:2;"

    def _td_valor(valor) -> str:
        cor = f"color:{VERMELHO};" if (valor or 0) < 0 else ""
        return f"<td style='padding:6px 6px; text-align:right; white-space:nowrap; {cor}'>{format_brl_md(valor)}</td>"

    linhas_html = []
    for nome, campo, destaque in LINHAS_DRE_DEF:
        cor_fundo_linha = "#EAF2E0" if destaque else "#FFFFFF"
        estilo_linha = f"font-weight:700; background-color:{cor_fundo_linha};" if destaque else f"background-color:{cor_fundo_linha};"
        celulas = "".join(_td_valor(dre_por_mes[mes][campo]) for mes in dre_por_mes)
        celula_total = _td_valor(dre_total_ano[campo])
        linhas_html.append(
            f"<tr style='{estilo_linha}'><td style='padding:6px 10px; white-space:nowrap; position:sticky; left:0; z-index:1; background-color:{cor_fundo_linha};'>{nome}</td>"
            f"{celulas}{celula_total}</tr>"
        )

    cabecalho_meses = "".join(f"<th style='{TH_VALOR}'>{MESES_PT[mes.month]}/{str(mes.year)[2:]}</th>" for mes in dre_por_mes)
    tabela_dre_html = (
        "<table style='width:100%; border-collapse:collapse; font-size:0.8rem; color:#1a1a1a;'>"
        f"<tr><th style='{TH_ROTULO}'>DRE - ASAP</th>{cabecalho_meses}<th style='{TH_VALOR}'>Total {ano}</th></tr>"
        + "".join(linhas_html)
        + "</table>"
    )

    st.markdown(
        render_tabela_com_faixa(f"Jan-{MESES_PT[meses_fc[-1].month]}/{ano} (em R$)", tabela_dre_html, largura_total=True),
        unsafe_allow_html=True,
    )
    st.caption(
        f"{MESES_PT[meses_fc[0].month]}-{MESES_PT[meses_fc[-1].month]}/{ano} = Forecast (Receita Bruta Mensal/"
        f"Lucro Bruto editados acima). Despesa Administrativa/Financeira/Imposto de Renda vêm da Revisão "
        f"\"em vigor\" da ASAP (**{revisao_atual}**)."
    )
