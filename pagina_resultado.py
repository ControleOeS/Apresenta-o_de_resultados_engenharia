"""Aba "Resultado" da Superus — conteúdo que antes era o app.py inteiro
(virou uma aba dentro da página "Superus" em app.py, pra caber lado a lado
com "Classificar Centro de Custo" e "Forecast" — pedido do usuário,
2026-11-23, preparando o app pra futuramente ter ASAP/O&S como outras
seções no mesmo molde)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dados import (
    LINHAS_DRE_DEF,
    LINHAS_MARGEM,
    MESES_PT,
    calcular_dre,
    calcular_dre_por_mes,
    calcular_previsto_com_fallback_despesa,
    carregar_previsto,
    carregar_previsto_refinado,
    carregar_realizado_2025_mensal,
    carregar_realizado_superus,
    carregar_refinado_detalhado,
    dre_2025_periodo,
    last_update,
    mapear_nomes_centro_custo,
    MESES_SUBSTITUIR_POR_REV,
    mes_corte_revisao,
    previsto_mensal_ano,
    revisao_vigente_no_mes,
    tabela_dimensao_centro_de_custo,
)
from estilo import (
    VERDE_DERIVADO_HEADER,
    VERDE_DERIVADO_TINT,
    VERDE_ESCURO,
    VERDE_ORCADO,
    VERMELHO,
    render_banner,
    render_caixa_narrativa,
    render_tabela_com_faixa,
)
from formatting import format_brl_compacto, format_brl_md, format_pct, format_pct_av, format_pp
from exportar_pdf import gerar_pdf, localizar_navegador, porta_do_servidor_atual
from forecast import (
    FONTE_FORECAST_DESMOB,
    FONTE_FORECAST_OPORTUNIDADES,
    FONTE_FORECAST_PADRAO,
    FONTES_FORECAST,
    chaves_desmob,
    dados_forecast_salvo,
    fechar_dre_ano,
    meses_forecast,
    revisao_atual_forecast,
    validar_lucro_bruto,
)
from narrativa import gerar_analise
from analise_complexos import MESES_NOVO_MOBILIZADO, construir_analise_complexos
from graficos_complexos import grafico_pizza_duas_fatias, grafico_pizza_status
from analise_categoria import (
    custo_por_categoria_previsto,
    custo_por_categoria_realizado,
    custo_por_cc_previsto,
    custo_por_cc_realizado,
    despesa_por_categoria_previsto,
    despesa_por_categoria_realizado,
    despesa_por_cc_previsto,
    despesa_por_cc_realizado,
    imposto_por_categoria_previsto,
    imposto_por_categoria_realizado,
    imposto_por_cc_previsto,
    imposto_por_cc_realizado,
    receita_por_categoria_previsto,
    receita_por_categoria_realizado,
    receita_por_cc_previsto,
    receita_por_cc_realizado,
    todas_categorias_conhecidas,
)
from graficos_categoria import grafico_categoria_empilhado, mapa_cores_categorias
from resultado_comum import renderizar_dre_mes_e_acumulado, renderizar_kpis


def render() -> None:


    # Guarda os query params (?mes=...&revisao=...) em session_state ANTES do
    # gate de login — se reabrir um link assim cai na tela "Acesso Restrito" e,
    # pelo relato do usuário, os filtros voltam ao padrão depois de logar (item
    # 31, 2026-11-11). Fallback de leitura, não mexe na senha (st.secrets) nem
    # adiciona nenhuma persistência de sessão nova.
    if st.query_params.get("mes"):
        st.session_state["_qp_mes"] = st.query_params.get("mes")
    if st.query_params.get("revisao"):
        st.session_state["_qp_revisao"] = st.query_params.get("revisao")


    st.markdown(
        """
        <style>
        @media print {
            [data-testid="stSidebar"], [data-testid="stHeader"],
            [data-testid="stToolbar"], #MainMenu, footer { display: none !important; }
            .block-container { max-width: 100% !important; padding: 0 1rem !important; }
            /* break-before/break-inside não funcionam de forma confiável dentro
            de containers flex (o layout padrão do Streamlit) — força bloco só
            na impressão, senão a quebra de página força uma página extra em
            branco antes do conteúdo seguinte. */
            [data-testid="stVerticalBlock"], [data-testid="stVerticalBlockBorderWrapper"],
            [data-testid="stMain"], [data-testid="stAppViewBlockContainer"] { display: block !important; }
            .quebra-pagina { break-before: page; }
            .tabela-dre-wrapper { break-inside: avoid; }
            /* Detalhamento mês a mês da tabela Acumulado: útil interativo (tem
            scroll horizontal na tela), mas em paisagem A4 não cabe junto com
            Acumulado/Orçado/Δ/Acumulado 2025/Δ 25x26 sem cortar colunas fora
            da página — escondido só no PDF, igual ao padrão da apresentação
            de referência (que também só mostra os totais, sem detalhe mensal
            dentro do Acumulado). */
            .col-mes-detalhe { display: none; }
        }
        @page { size: A4 landscape; margin: 8mm; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    df_real = carregar_realizado_superus()
    df_previsto = carregar_previsto()
    df_refinado = carregar_previsto_refinado()
    df_refinado_detalhado = carregar_refinado_detalhado()
    tabela_dimensao = tabela_dimensao_centro_de_custo()
    nomes_centro_custo = mapear_nomes_centro_custo(df_real)

    with st.sidebar:
        st.header("Filtros")
        meses_disponiveis = sorted(df_real["Mes"].dropna().unique().tolist())
        mes_param = st.query_params.get("mes") or st.session_state.get("_qp_mes")
        indice_mes_padrao = len(meses_disponiveis) - 1
        if mes_param:
            datas_iso = [d.strftime("%Y-%m-%d") for d in meses_disponiveis]
            if mes_param in datas_iso:
                indice_mes_padrao = datas_iso.index(mes_param)
        mes_ref = st.selectbox(
            "Mês de referência",
            meses_disponiveis,
            index=indice_mes_padrao,
            format_func=lambda d: f"{MESES_PT[d.month]}/{d.year}",
        )
        revisoes = sorted(set(df_previsto["Revisão"].unique().tolist()) | set(df_refinado["Revisão"].unique().tolist()))
        revisao_param = st.query_params.get("revisao") or st.session_state.get("_qp_revisao")
        # Abre já na Revisão que previa de verdade o mês padrão (último Realizado
        # fechado) — ex: fechado até Setembro -> REV02 (REV03 só previa de Out
        # em diante) — em vez de sempre a Revisão mais recente, pra abrir pronto
        # pra consumir sem precisar trocar manualmente (pedido do usuário,
        # 2026-10-21).
        mes_padrao = meses_disponiveis[indice_mes_padrao]
        indice_revisao_padrao = revisoes.index(revisao_vigente_no_mes(mes_padrao.month, revisoes))
        if revisao_param in revisoes:
            indice_revisao_padrao = revisoes.index(revisao_param)
        revisao_sel = st.selectbox("Revisão", revisoes, index=indice_revisao_padrao)
        cenario_sel = "Otimista"

        # Mesmo modelo/rótulo do filtro já existente no DASH_DIRETORIA — pedido
        # do usuário, 2026-11-19. Sem seleção (padrão) = sem filtro, mostra
        # tudo. Só filtra o Realizado (KPIs, DRE Mês/Acumulado, Curva S, DRE
        # Forecast, Análise por Categoria/CC, Análise de Complexos) — o
        # Orçado/Previsto não tem granularidade de Centro de Custo (mesma
        # limitação de lá: Δ Real-vs-Orçado com filtro ativo compara Real
        # filtrado contra Orçado total).
        centros_custo = sorted(df_real["Cod. Centro de Custo"].dropna().unique().tolist())
        centros_custo_sel = st.multiselect(
            "Cod. Centro de Custo", centros_custo,
            format_func=lambda c: f"{c} — {nomes_centro_custo[c]}" if nomes_centro_custo.get(c) else c,
        )

        with st.expander("ℹ️ Qual Revisão escolher?"):
            st.caption(
                "Cada Revisão só prevê de verdade a partir de um certo mês — antes "
                "disso, ela só espelha o Realizado (sem Δ, não é um Orçado de "
                "verdade pra esse período)."
            )
            _ano_filtro = mes_ref.year
            _revisoes_ordenadas = sorted(MESES_SUBSTITUIR_POR_REV.items(), key=lambda kv: kv[1])
            _linhas_periodo = []
            for _i, (_rev, _meses_sub) in enumerate(_revisoes_ordenadas):
                _mes_ini = _meses_sub + 1
                _mes_fim = _revisoes_ordenadas[_i + 1][1] if _i + 1 < len(_revisoes_ordenadas) else 12
                if _mes_ini > _mes_fim or _rev not in revisoes:
                    continue
                _periodo = (
                    f"{MESES_PT[_mes_ini]}/{str(_ano_filtro)[2:]}"
                    if _mes_ini == _mes_fim
                    else f"{MESES_PT[_mes_ini]}-{MESES_PT[_mes_fim]}/{str(_ano_filtro)[2:]}"
                )
                _linhas_periodo.append({"Revisão": _rev, "Prevê de verdade": _periodo})
            st.dataframe(pd.DataFrame(_linhas_periodo), hide_index=True, use_container_width=True)

        st.query_params["mes"] = mes_ref.strftime("%Y-%m-%d")
        st.query_params["revisao"] = revisao_sel

        st.divider()
        # Exportar PDF abre um Chrome/Edge local via CDP — não existe num
        # servidor Linux na nuvem (Streamlit Cloud), então o botão some sozinho
        # lá (localizar_navegador não acha nada) em vez de aparecer e dar erro
        # quando clicado. Continua funcionando normal rodando local.
        navegador_disponivel = True
        try:
            localizar_navegador()
        except FileNotFoundError:
            navegador_disponivel = False

        if navegador_disponivel and st.button("📄 Exportar PDF", use_container_width=True):
            with st.spinner("Gerando PDF..."):
                porta = porta_do_servidor_atual()
                url_exportacao = (
                    f"http://localhost:{porta}/?mes={mes_ref.strftime('%Y-%m-%d')}&revisao={revisao_sel}"
                )
                try:
                    pdf_bytes = gerar_pdf(url_exportacao)
                    st.session_state["pdf_gerado"] = pdf_bytes
                except Exception as e:
                    st.error(f"Não foi possível gerar o PDF: {e}")

        if "pdf_gerado" in st.session_state:
            st.download_button(
                "⬇️ Baixar PDF",
                data=st.session_state["pdf_gerado"],
                file_name=f"Apresentacao_Resultados_{mes_ref.strftime('%Y-%m')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    ano = mes_ref.year
    mes_ini_ano = pd.Timestamp(year=ano, month=1, day=1)
    nome_mes = MESES_PT[mes_ref.month].upper()

    # df_real_filtrado = o que o filtro "Cod. Centro de Custo" da barra lateral
    # realmente filtra — todo o Realizado exibido daqui pra baixo (KPIs, DRE
    # Mês/Acumulado, Curva S, DRE Forecast, Análise por Categoria/CC, Análise
    # de Complexos). df_real (sem filtro) continua usado pra decidir limites de
    # data/Revisão (último mês fechado, janela de Forecast, Revisão "em
    # vigor") e como fallback interno do Orçado (calcular_previsto_com_fallback_despesa/
    # previsto_mensal_ano/despesa_dre_mes) — o Orçado não tem granularidade de
    # Centro de Custo, então ele nunca encolhe com esse filtro, igual ao
    # DASH_DIRETORIA.
    df_real_filtrado = df_real[df_real["Cod. Centro de Custo"].isin(centros_custo_sel)] if centros_custo_sel else df_real

    st.markdown(
        render_banner(
            "APRESENTAÇÃO DE RESULTADOS",
            f"Superus Engenharia · Revisão {revisao_sel} · Cenário {cenario_sel}",
        ),
        unsafe_allow_html=True,
    )
    _ultimo_mes_real = df_real["Mes"].max()
    st.caption(
        f"Dados atualizados em {last_update()} · último mês com Realizado fechado: "
        f"{MESES_PT[_ultimo_mes_real.month]}/{_ultimo_mes_real.year}"
    )
    if centros_custo_sel:
        st.caption(
            f"🔎 Filtro de Centro de Custo ativo ({len(centros_custo_sel)} selecionado"
            f"{'s' if len(centros_custo_sel) != 1 else ''}) — afeta só o Realizado; o Orçado/Previsto "
            "não tem granularidade de Centro de Custo e continua no total."
        )

    dre_mes_real = calcular_dre(df_real_filtrado[df_real_filtrado["Mes"] == mes_ref])
    dre_acum_real = calcular_dre(df_real_filtrado[(df_real_filtrado["Mes"] >= mes_ini_ano) & (df_real_filtrado["Mes"] <= mes_ref)])

    realizado_2025_mensal = carregar_realizado_2025_mensal()
    dre_mes_2025 = dre_2025_periodo(realizado_2025_mensal, mes_ref, mes_ref)
    dre_acum_2025 = dre_2025_periodo(realizado_2025_mensal, mes_ini_ano, mes_ref)

    dre_mes_orc, despesa_provisoria_mes = calcular_previsto_com_fallback_despesa(
        df_previsto, df_refinado, revisao_sel, cenario_sel, mes_ref, mes_ref, df_real
    )
    dre_acum_orc, despesa_provisoria_acum = calcular_previsto_com_fallback_despesa(
        df_previsto, df_refinado, revisao_sel, cenario_sel, mes_ini_ano, mes_ref, df_real
    )
    dre_mes_orc = dre_mes_orc or {}
    dre_acum_orc = dre_acum_orc or {}
    despesa_provisoria = despesa_provisoria_mes or despesa_provisoria_acum

    # Aviso genérico quando o Mês de referência inteiro está fora da janela que
    # a Revisão escolhida realmente prevê (ex.: Jan/26+REV02, Set/26+REV03) — o
    # Orçado inteiro (não só Despesa) espelha o Realizado aí, Δ=0 em tudo. Antes
    # só existia um aviso específico de Despesa pra REV02/REV03 (abaixo) — esse
    # cobre o caso geral, pra qualquer Revisão (item 6, 2026-11-11).
    if mes_ref < mes_corte_revisao(revisao_sel, ano):
        revisao_indicada = revisao_vigente_no_mes(mes_ref.month, revisoes)
        janelas = {"REV00": "Jan-Mar", "REV01": "Abr-Jun", "REV02": "Jul-Set", "REV03": "Out-Dez"}
        st.warning(
            f"⚠️ A {revisao_sel} só prevê {janelas.get(revisao_sel, '?')}/{str(ano)[2:]}; para "
            f"{MESES_PT[mes_ref.month]}/{str(ano)[2:]} o Orçado espelha o Realizado (Δ=0 em tudo). "
            f"Revisão indicada para este mês: {revisao_indicada}."
        )

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------
    renderizar_kpis(dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc)

    st.divider()

    # ------------------------------------------------------------------
    # DRE — Mês e Acumulado (renderização compartilhada com ASAP/O&S/Grupo,
    # ver resultado_comum.py — inclui "Realizado 2025"/"25x26" (fonte:
    # RESULTADOS 2025.xlsx, ver carregar_realizado_2025_mensal em dados.py),
    # exclusivo da Superus por enquanto.
    # ------------------------------------------------------------------
    st.markdown("<div class='quebra-pagina'></div>", unsafe_allow_html=True)

    meses_do_ano = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= mes_ref]
    dre_por_mes = {m: calcular_dre(df_real_filtrado[df_real_filtrado["Mes"] == m]) for m in meses_do_ano}

    renderizar_dre_mes_e_acumulado(
        "Superus Engenharia", ano, nome_mes, dre_mes_real, dre_mes_orc, dre_acum_real, dre_acum_orc,
        dre_por_mes, meses_do_ano, dre_mes_2025=dre_mes_2025, dre_acum_2025=dre_acum_2025,
    )

    # Reaproveitados mais abaixo pela seção "DRE — Forecast" (mesmo estilo de
    # espaçador/rótulo das tabelas acima, que agora vivem em resultado_comum.py).
    TH_ROTULO = f"text-align:left; padding:6px 10px; background-color:{VERDE_ESCURO}; color:white; position:sticky; left:0; z-index:2;"

    def _espacador_th() -> str:
        return "<th style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></th>"

    def _espacador_td() -> str:
        return "<td style='padding:0; width:10px; background-color:#FFFFFF; border:none;'></td>"

    if revisao_sel == "REV03" and despesa_provisoria:
        st.caption(
            "⚠️ Orçado de Despesa da REV03: Jan-Set/26 espelham o próprio Realizado (sem Δ) — a "
            "REV03 não prevê esses meses, já tinham acontecido quando ela foi fechada (igual ao "
            "DASH_DIRETORIA). De Out/26 em diante (a janela que a REV03 prevê de verdade), Despesa "
            "Administrativa e Financeira já vêm completas do orçamento próprio dela "
            "(ONEPAGE_REV03.xlsx), com Δ real contra o Realizado; só o Imposto de Renda desses meses "
            "**ainda é emprestado da REV01**, até chegar uma fonte própria."
        )
    elif revisao_sel == "REV02" and despesa_provisoria:
        st.caption(
            "⚠️ Orçado de Despesa da REV02: Jan-Jun/26 espelham o próprio Realizado (sem Δ) — a "
            "REV02 não prevê esses meses, já tinham acontecido quando ela foi fechada. De Jul/26 em "
            "diante (a janela que a REV02 prevê de verdade), a Despesa (Administrativa + Comercial + "
            "Operação) já vem completa do orçamento próprio dela (DESPESA REV02.xlsx), com Δ real "
            "contra o Realizado; só a Despesa Financeira e o Imposto de Renda desses meses **ainda "
            "são emprestados da REV01**, até chegar uma fonte própria."
        )
    elif despesa_provisoria:
        st.caption(
            f"⚠️ A {revisao_sel} ainda não tem Despesa Administrativa/Financeira própria lançada — "
            "Receita/Custo/Margem Bruta já são dessa revisão, mas Despesa/EBITDA/LAIR/Lucro Líquido "
            "abaixo são **provisórios, emprestados da REV01**, até a Despesa real da "
            f"{revisao_sel} chegar."
        )
    elif dre_mes_orc.get("despesa_adm") is None:
        st.caption(
            "⚠️ Despesa Administrativa/Financeira, EBITDA, LAIR, Imposto de Renda e Lucro Líquido aparecem "
            "como N/D para essa Revisão/Cenário — ainda não temos uma base de Previsto completa até Lucro "
            "Líquido para ela (hoje só REV00 e REV01-Otimista têm essa cascata)."
        )

    st.divider()

    # ------------------------------------------------------------------
    # Fonte da Receita Bruta/Margem Bruta pra qualquer visão com Forecast desta
    # página (Curva S com base "Forecast" logo abaixo + tabela "DRE — Forecast"
    # mais adiante) — mesmo seletor/rótulos já existentes no DASH_DIRETORIA.
    # "Forecast" = preenchimento manual salvo na página "Forecast" (padrão,
    # comportamento de sempre); "Forecast de Oportunidades" = cenário
    # alternativo e estático, sincronizado à parte (forecast_oportunidades.py)
    # — pedido do usuário, 2026-11-18.
    # ------------------------------------------------------------------
    if meses_forecast(df_real, ano):
        fonte_forecast = st.radio(
            "Fonte da Receita Bruta/Margem Bruta do Forecast",
            FONTES_FORECAST,
            key="app_fonte_forecast",
            horizontal=True,
        )
        if fonte_forecast == FONTE_FORECAST_OPORTUNIDADES:
            st.caption(
                "Forecast de Oportunidades = cenário alternativo e **estático** (aba \"Forecast super "
                "otimista\" de um Excel à parte, sincronizado pelo DASH_DIRETORIA) — só muda se alguém "
                "editar aquele arquivo e rodar o sync de novo; não dá pra editar por aqui. Despesa "
                "Administrativa/Financeira continuam vindo da Revisão \"em vigor\", igual ao Forecast "
                "normal."
            )
        elif fonte_forecast == FONTE_FORECAST_DESMOB:
            st.caption(
                "Forecast com Desmob = o preenchimento manual do Forecast, mas **considerando a "
                "desmobilização da Vale Integridade e da Vale Soldadores Itabira** — Receita Bruta/Lucro "
                "Bruto desses dois Complexos zerados nos meses de Forecast, mais R$1,6 milhão de Custo de "
                "desmobilização lançado em Dezembro (sem Receita associada). Despesa Administrativa/"
                "Financeira continuam vindo da Revisão \"em vigor\", igual ao Forecast normal."
            )
    else:
        fonte_forecast = FONTE_FORECAST_PADRAO

    # ------------------------------------------------------------------
    # Curva S — Orçado x Realizado Acumulado (ano inteiro, independe do Mês de
    # referência filtrado na barra lateral) — mesma visão já existente no
    # DASH_DIRETORIA, com as duas curvas de Orçado (Moderado/Otimista) — o
    # resto da apresentação usa só o Cenário Otimista (cenario_sel fixo), mas
    # a Curva S mostra os dois igual ao DASH_DIRETORIA.
    # ------------------------------------------------------------------
    st.header("Curva S — Orçado x Realizado Acumulado")
    st.caption(
        "Acumulado mês a mês ao longo do ano inteiro — o Orçado mostra o ano inteiro "
        "independente do Mês de referência filtrado na barra lateral (Realizado "
        "comparado ao Orçado efetivo de cada Cenário, Moderado e Otimista, na Revisão "
        "selecionada); o Realizado é cortado nesse Mês de referência (ver nota abaixo), "
        "para a linha do DRE escolhida abaixo."
    )

    col_curva_s_linha, col_curva_s_base = st.columns([2, 1])
    _opcoes_curva_s = [nome for nome, _, _ in LINHAS_DRE_DEF]
    linha_curva_s_sel = col_curva_s_linha.selectbox(
        "Linha do DRE",
        _opcoes_curva_s,
        index=_opcoes_curva_s.index("(=) Lucro Bruto"),
        key="curva_s_linha",
    )
    campo_curva_s = next(campo for nome, campo, _ in LINHAS_DRE_DEF if nome == linha_curva_s_sel)

    base_curva_s_sel = col_curva_s_base.radio(
        "Linha de referência",
        ["Realizado", "Forecast"],
        key="curva_s_base",
        horizontal=True,
    )
    if base_curva_s_sel == "Forecast":
        col_curva_s_base.caption(
            "Realizado fechado + Forecast preenchido na página \"Forecast\" (último estado salvo) pro resto do ano."
        )
    else:
        col_curva_s_base.caption(f"Só o Realizado, até {MESES_PT[mes_ref.month]}/{mes_ref.year} (Mês de referência).")

    COR_ORCADO_MODERADO = "#00465C"  # ponta esquerda do GRADIENTE_BANNER — distingue do verde do Otimista

    # Linhas de dedução (convenção de sinal negativo) que o usuário prefere ver
    # subindo (valor absoluto) na Curva S — mais fácil comparar magnitude entre
    # Realizado/Orçado do que com a curva descendo. Sinal original preservado
    # só no tooltip (via customdata). Confirmado pelo usuário, 2026-11-11 (item
    # 12) — lista literal pedida, não generalizada pra outras linhas de
    # dedução (ex.: Imposto de Renda fica como estava, sinal original plotado).
    CAMPOS_CURVA_S_ABSOLUTO = {"custo", "imposto", "despesa_adm", "despesa_financeira"}


    def _ticks_bonitos(valor_min: float, valor_max: float, n: int = 5) -> list[float]:
        """Posições de tick "redondas" e igualmente espaçadas (algoritmo clássico
        de "nice numbers" — degrau arredondado pra 1/2/5×10^k), igual ao que o
        tickformat automático do Plotly faria — mas aqui calculado à mão porque
        precisamos interceptar o texto de cada tick (format_brl_compacto em vez
        do sufixo em inglês do Plotly, item 13)."""
        import math

        if valor_max == valor_min:
            return [valor_min]
        alcance_bruto = (valor_max - valor_min) / max(n - 1, 1)
        magnitude = 10 ** math.floor(math.log10(abs(alcance_bruto)))
        passo_normalizado = alcance_bruto / magnitude
        if passo_normalizado < 1.5:
            passo = magnitude
        elif passo_normalizado < 3:
            passo = 2 * magnitude
        elif passo_normalizado < 7:
            passo = 5 * magnitude
        else:
            passo = 10 * magnitude
        primeiro = math.floor(valor_min / passo) * passo
        ultimo = math.ceil(valor_max / passo) * passo
        n_ticks = int(round((ultimo - primeiro) / passo)) + 1
        return [primeiro + i * passo for i in range(n_ticks)]


    def _ticktext_compacta(valores) -> list[str]:
        """Rótulo de eixo na mesma função de formatação dos rótulos de dado
        (format_brl_compacto) — "Mi"/"mil" em vez do tickformat nativo do
        Plotly (",.2s", que produz "50M" em inglês); "0" em vez de "0,0" no
        zero (item 13, 2026-11-11)."""
        textos = []
        for v in valores:
            if v == 0:
                textos.append("0")
            else:
                textos.append(format_brl_compacto(v))
        return textos


    def _grafico_curva_s(
        df_real_mensal: pd.DataFrame,
        df_orc_mensal_moderado: pd.DataFrame,
        df_orc_mensal_otimista: pd.DataFrame,
        campo: str,
        nome_linha: str,
        ano_cs: int,
        nome_real: str = "Realizado",
    ) -> tuple[go.Figure, list[str]]:
        meses_ano_cs = list(pd.date_range(f"{ano_cs}-01-01", f"{ano_cs}-12-01", freq="MS"))
        fig = go.Figure()
        em_valor_absoluto = campo in CAMPOS_CURVA_S_ABSOLUTO
        # Com sinal original preservado via customdata, o hover mostra o valor
        # de verdade mesmo quando a curva plota o módulo (item 12).
        hover = "%{x|%b/%Y}<br>%{fullData.name}: R$ %{customdata:,.2f}<extra></extra>"
        avisos: list[str] = []
        todos_os_valores: list[float] = []

        if not df_real_mensal.empty and campo in df_real_mensal.columns:
            serie_real = df_real_mensal.set_index("Mes")[campo].reindex(meses_ano_cs)
            acumulado_real = serie_real.cumsum().dropna()
            if not acumulado_real.empty:
                valores_plotados = acumulado_real.abs().values if em_valor_absoluto else acumulado_real.values
                todos_os_valores.extend(valores_plotados)
                fig.add_trace(
                    go.Scatter(
                        x=acumulado_real.index,
                        y=valores_plotados,
                        customdata=acumulado_real.values,
                        mode="lines+markers",
                        name=nome_real,
                        line=dict(color=VERDE_ESCURO, width=4),
                        hovertemplate=hover,
                    )
                )

        for df_orc_mensal, nome_serie, cor, tracejado in [
            (df_orc_mensal_moderado, "Orçado Moderado", COR_ORCADO_MODERADO, "dot"),
            (df_orc_mensal_otimista, "Orçado Otimista", VERDE_ORCADO, "dash"),
        ]:
            if df_orc_mensal.empty or campo not in df_orc_mensal.columns or df_orc_mensal[campo].isna().all():
                avisos.append(f"{nome_serie}: sem base de Previsto disponível para \"{nome_linha}\" nesta Revisão.")
                continue
            serie_orc = df_orc_mensal.set_index("Mes")[campo].reindex(meses_ano_cs)
            if serie_orc.isna().any():
                avisos.append(f"{nome_serie}: N/D para \"{nome_linha}\" em pelo menos um mês do ano — curva não exibida.")
                continue
            acumulado_orc = serie_orc.cumsum()
            valores_plotados = acumulado_orc.abs().values if em_valor_absoluto else acumulado_orc.values
            todos_os_valores.extend(valores_plotados)
            fig.add_trace(
                go.Scatter(
                    x=acumulado_orc.index,
                    y=valores_plotados,
                    customdata=acumulado_orc.values,
                    mode="lines+markers",
                    name=nome_serie,
                    line=dict(color=cor, width=2, dash=tracejado),
                    hovertemplate=hover,
                )
            )

        fig.update_layout(
            separators=",.",
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            height=420,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(t=30, b=10, l=70, r=10),
        )
        # Eixo X: os 12 meses em pt-BR (item 11) — tickformat nativo do Plotly
        # usa locale em inglês e escolhe o passo automaticamente (de 2 em 2
        # meses quando não cabem os 12).
        fig.update_xaxes(
            tickvals=meses_ano_cs,
            ticktext=[f"{MESES_PT[m.month]}/{str(m.year)[2:]}" for m in meses_ano_cs],
            showgrid=False,
        )
        if todos_os_valores:
            y_ticks = _ticks_bonitos(min(0, min(todos_os_valores)), max(0, max(todos_os_valores)))
            fig.update_yaxes(
                tickvals=y_ticks,
                ticktext=_ticktext_compacta(y_ticks),
                zeroline=True, zerolinewidth=2, zerolinecolor="#CCCCCC",
            )
        else:
            fig.update_yaxes(zeroline=True, zerolinewidth=2, zerolinecolor="#CCCCCC")
        return fig, avisos


    if base_curva_s_sel == "Forecast":
        meses_fc_cs = meses_forecast(df_real, ano)
        if not meses_fc_cs:
            # Ano já fechado inteiro no Realizado — nada de Forecast pra misturar.
            df_real_mensal_cs = calcular_dre_por_mes(df_real_filtrado[df_real_filtrado["Mes"].dt.year == ano])
        else:
            revisao_atual_forecast_cs = revisao_atual_forecast(df_real, revisoes, ano)
            meses_realizado_cs = sorted(m for m in df_real["Mes"].dropna().unique() if pd.Timestamp(m).year == ano)
            receita_por_linha_mes_cs, lucro_por_linha_mes_cs, nomes_linha_cs = dados_forecast_salvo(meses_fc_cs)
            dre_por_mes_cs = fechar_dre_ano(
                df_real_filtrado, df_previsto, df_refinado, revisao_atual_forecast_cs,
                meses_realizado_cs, meses_fc_cs, receita_por_linha_mes_cs, lucro_por_linha_mes_cs, nomes_linha_cs,
                fonte_forecast=fonte_forecast, df_real_despesa=df_real,
            )
            df_real_mensal_cs = pd.DataFrame([dict(dre, Mes=mes) for mes, dre in dre_por_mes_cs.items()])
        nome_real_cs = "Realizado + Forecast"
    else:
        df_real_mensal_cs = calcular_dre_por_mes(df_real_filtrado[(df_real_filtrado["Mes"].dt.year == ano) & (df_real_filtrado["Mes"] <= mes_ref)])
        nome_real_cs = "Realizado"

    df_orc_mensal_moderado_cs = previsto_mensal_ano(df_previsto, df_refinado, df_real, revisao_sel, "Moderado", ano)
    df_orc_mensal_otimista_cs = previsto_mensal_ano(df_previsto, df_refinado, df_real, revisao_sel, "Otimista", ano)

    fig_curva_s, avisos_curva_s = _grafico_curva_s(
        df_real_mensal_cs, df_orc_mensal_moderado_cs, df_orc_mensal_otimista_cs, campo_curva_s, linha_curva_s_sel, ano,
        nome_real=nome_real_cs,
    )
    st.plotly_chart(fig_curva_s, use_container_width=True)
    for aviso in avisos_curva_s:
        st.caption(f"⚠️ {aviso}")

    st.divider()

    # ------------------------------------------------------------------
    # DRE — Forecast (ano inteiro: Realizado fechado + Forecast preenchido na
    # página "Forecast" — sempre o último estado SALVO lá, não depende de
    # estar com a página aberta). Some abaixo do Acumulado de propósito,
    # pedido do usuário pra fechar a visão do ano completo na página
    # principal antes de divulgar o link.
    # ------------------------------------------------------------------
    st.header(f"DRE — Forecast {ano}")

    meses_fc_app = meses_forecast(df_real, ano)
    if not meses_fc_app:
        st.success(f"Todos os meses de {ano} já têm Realizado fechado — nada em aberto pra prever.")
    else:
        revisao_atual_forecast_app = revisao_atual_forecast(df_real, revisoes, ano)
        ultimo_mes_real_app = df_real.loc[df_real["Mes"].dt.year == ano, "Mes"].max()
        meses_realizado_app = [m for m in sorted(df_real["Mes"].dropna().unique()) if m.year == ano and m <= ultimo_mes_real_app]

        receita_por_linha_mes_app, lucro_por_linha_mes_app, nomes_linha_app = dados_forecast_salvo(meses_fc_app)
        # "Forecast com Desmob" também usa o preenchimento manual (só exclui os
        # Complexos desmobilizados) — essas linhas não precisam de Lucro Bruto
        # preenchido nesse cenário, já que não entram na DRE de qualquer forma.
        linhas_desmob_app = chaves_desmob(nomes_linha_app) if fonte_forecast == FONTE_FORECAST_DESMOB else set()
        erros_forecast_app = []
        for mes in meses_fc_app:
            chave_mes = mes.strftime("%Y-%m")
            receita_validar_app = {
                chave: valor for chave, valor in receita_por_linha_mes_app[chave_mes].items() if chave not in linhas_desmob_app
            }
            erros_forecast_app += validar_lucro_bruto(
                receita_validar_app, lucro_por_linha_mes_app[chave_mes], nomes_linha_app,
                f"{MESES_PT[mes.month]}/{str(mes.year)[2:]}",
            )

        # Pendência de preenchimento do Forecast manual só bloqueia a DRE
        # quando a fonte escolhida depende dele (Forecast normal ou com Desmob)
        # — com "Forecast de Oportunidades" selecionado, a Receita/Margem Bruta
        # não depende dele (vem do cenário estático), então a pendência não
        # impede nada.
        if fonte_forecast != FONTE_FORECAST_OPORTUNIDADES and erros_forecast_app:
            st.warning(
                "⚠️ O Forecast salvo ainda tem pendência de preenchimento — corrija na página **Forecast** "
                "pra essa DRE aparecer aqui:\n\n" + "\n".join(f"- {e}" for e in erros_forecast_app)
            )
        else:
            dre_forecast_por_mes = fechar_dre_ano(
                df_real_filtrado, df_previsto, df_refinado, revisao_atual_forecast_app,
                meses_realizado_app, meses_fc_app, receita_por_linha_mes_app, lucro_por_linha_mes_app, nomes_linha_app,
                fonte_forecast=fonte_forecast, df_real_despesa=df_real,
            )
            dre_forecast_total_ano = {campo: sum(dre_forecast_por_mes[m][campo] for m in dre_forecast_por_mes) for _, campo, _ in LINHAS_DRE_DEF}
            base_av_forecast_ano = dre_forecast_total_ano["receita_liquida"]

            # Meta 2026 — mesmo alvo fixo (DRE "Total 2026" aprovada) usado na
            # aba Forecast (ver pagina_forecast.py, 2026-11-26: "essa é a
            # meta" + conta de chegada pro LAIR/Lucro Líquido, que o print do
            # usuário não fechava sozinho). Deixou de acompanhar o Orçado
            # (Cenário Otimista) da Revisão em vigor automaticamente (regra
            # antiga, 2026-11-18) — repetido aqui em vez de importado de
            # pagina_forecast.py pra não criar acoplamento entre as duas
            # páginas por causa de uma tabela que já é, por si só, quase-
            # duplicada (ver comentário da tabela_forecast_html abaixo).
            meta_total_ano_app = {
                "receita_bruta": 252_412_454.0,
                "imposto": -22_177_268.0,
                "receita_liquida": 230_235_186.0,
                "custo": -175_660_008.0,
                "margem_bruta": 54_575_178.0,
                "despesa_adm": -22_017_454.0,
                "ebitda": 32_557_724.0,
                "despesa_financeira": -9_051_005.0,
                "lair": 23_506_719.0,
                "imposto_renda": -7_650_665.0,
                "lucro_liquido": 15_856_054.0,
            }

            # Realizado 2025 — comparação direta com o Forecast 2026 (ano
            # inteiro), mesma fonte já usada na DRE Mês/Acumulado acima
            # (RESULTADOS 2025.xlsx, carregar_realizado_2025_mensal em
            # dados.py). Pedido do usuário, 2026-11-18.
            dre_2025_total_app = dre_2025_periodo(
                realizado_2025_mensal, mes_ini_ano, pd.Timestamp(year=ano, month=12, day=1)
            )
            TH_VALOR_FC = f"padding:6px 6px; text-align:right; background-color:{VERDE_ESCURO}; color:white; font-weight:700; white-space:nowrap;"
            TH_META = f"padding:6px 6px; text-align:right; background-color:#5B7B4A; color:white; font-weight:700; white-space:nowrap;"
            TH_DELTA = TH_META

            def _td_fc(conteudo, extra="") -> str:
                return f"<td style='padding:4px 6px; text-align:right; white-space:nowrap; {extra}'>{conteudo}</td>"

            def _td_valor_fc(valor, extra="") -> str:
                cor = f"color:{VERMELHO};" if (valor or 0) < 0 else ""
                return _td_fc(format_brl_md(valor), extra + cor)

            linhas_forecast_html = []
            for nome, campo, destaque in LINHAS_DRE_DEF:
                cor_fundo_linha = "#EAF2E0" if destaque else "#FFFFFF"
                estilo_linha = f"font-weight:700; background-color:{cor_fundo_linha};" if destaque else f"background-color:{cor_fundo_linha};"
                valor_meta = meta_total_ano_app[campo]
                valor_2025 = dre_2025_total_app.get(campo) if dre_2025_total_app else None
                celulas = "".join(_td_valor_fc(dre_forecast_por_mes[m][campo]) for m in dre_forecast_por_mes)
                celula_total = _td_valor_fc(dre_forecast_total_ano[campo])
                celula_meta = _td_valor_fc(valor_meta)
                celula_delta = _td_valor_fc(None if valor_meta is None else dre_forecast_total_ano[campo] - valor_meta)
                celula_2025 = _td_valor_fc(valor_2025)
                celula_delta_2025 = _td_valor_fc(None if valor_2025 is None else dre_forecast_total_ano[campo] - valor_2025)
                linhas_forecast_html.append(
                    f"<tr style='{estilo_linha}'><td style='padding:6px 10px; white-space:nowrap; position:sticky; left:0; z-index:1; background-color:{cor_fundo_linha};'>{nome}</td>"
                    f"{celulas}{celula_total}{_espacador_td()}{celula_meta}{celula_delta}{_espacador_td()}{celula_2025}{celula_delta_2025}</tr>"
                )
                if campo in LINHAS_MARGEM:
                    celulas_pct = "".join(
                        _td_fc(
                            format_pct_av(dre_forecast_por_mes[m][campo], dre_forecast_por_mes[m]["receita_liquida"], manter_sinal=True),
                            f"color:{VERMELHO};" if dre_forecast_por_mes[m][campo] < 0 else "",
                        )
                        for m in dre_forecast_por_mes
                    )
                    celula_pct_total = _td_fc(
                        format_pct_av(dre_forecast_total_ano[campo], base_av_forecast_ano, manter_sinal=True),
                        f"color:{VERMELHO};" if dre_forecast_total_ano[campo] < 0 else "",
                    )
                    base_meta = meta_total_ano_app["receita_liquida"]
                    pct_meta = valor_meta / base_meta if valor_meta is not None and base_meta else None
                    pct_forecast = dre_forecast_total_ano[campo] / base_av_forecast_ano if base_av_forecast_ano else None
                    celula_pct_meta = _td_fc(
                        format_pct_av(valor_meta, base_meta, manter_sinal=True),
                        f"color:{VERMELHO};" if (valor_meta or 0) < 0 else "",
                    )
                    delta_pp = None if pct_meta is None or pct_forecast is None else pct_forecast - pct_meta
                    celula_pct_delta = _td_fc(format_pp(delta_pp))
                    base_2025 = dre_2025_total_app.get("receita_liquida") if dre_2025_total_app else None
                    pct_2025 = valor_2025 / base_2025 if valor_2025 is not None and base_2025 else None
                    celula_pct_2025 = _td_fc(
                        format_pct_av(valor_2025, base_2025, manter_sinal=True),
                        f"color:{VERMELHO};" if (valor_2025 or 0) < 0 else "",
                    )
                    delta_pp_2025 = None if pct_2025 is None or pct_forecast is None else pct_forecast - pct_2025
                    celula_pct_delta_2025 = _td_fc(format_pp(delta_pp_2025))
                    linhas_forecast_html.append(
                        "<tr style='font-style:italic; color:#555; background-color:#F7F9F4;'>"
                        f"<td style='padding:4px 10px 4px 20px; position:sticky; left:0; z-index:1; background-color:#F7F9F4;'>{LINHAS_MARGEM[campo]}</td>"
                        f"{celulas_pct}{celula_pct_total}{_espacador_td()}{celula_pct_meta}{celula_pct_delta}"
                        f"{_espacador_td()}{celula_pct_2025}{celula_pct_delta_2025}</tr>"
                    )

            cabecalho_forecast = "".join(
                f"<th style='{TH_VALOR_FC}'>{MESES_PT[m.month]}/{str(m.year)[2:]}</th>" for m in dre_forecast_por_mes
            )
            tabela_forecast_html = (
                "<table style='width:100%; border-collapse:collapse; font-size:0.8rem; color:#1a1a1a;'>"
                f"<tr><th style='{TH_ROTULO}'>DRE - Superus Engenharia</th>{cabecalho_forecast}<th style='{TH_VALOR_FC}'>Total {ano}</th>"
                f"{_espacador_th()}<th style='{TH_META}'>Meta</th><th style='{TH_DELTA}'>Δ Forecast-Meta</th>"
                f"{_espacador_th()}<th style='{TH_META}'>Realizado {ano - 1}</th><th style='{TH_DELTA}'>Δ Forecast-Real.{str(ano - 1)[2:]}</th></tr>"
                + "".join(linhas_forecast_html)
                + "</table>"
            )
            st.markdown(
                f"<div class='tabela-dre-wrapper'>{render_tabela_com_faixa(f'FORECAST {ano} (em R$)', tabela_forecast_html, largura_total=True)}</div>",
                unsafe_allow_html=True,
            )
            _fonte_forecast_legenda = {
                FONTE_FORECAST_OPORTUNIDADES: "Forecast de Oportunidades (cenário estático à parte)",
                FONTE_FORECAST_DESMOB: (
                    "Forecast com Desmob (preenchido na página **Forecast**, considerando a "
                    "desmobilização da Vale Integridade e da Vale Soldadores Itabira, com R$1,6 milhão de "
                    "Custo de desmobilização em Dezembro)"
                ),
            }.get(fonte_forecast, "Forecast (preenchido na página **Forecast**)")
            st.caption(
                f"Jan-{MESES_PT[meses_realizado_app[-1].month]}/{ano} = Realizado fechado; "
                f"{MESES_PT[meses_fc_app[0].month]}-{MESES_PT[meses_fc_app[-1].month]}/{ano} = "
                f"{_fonte_forecast_legenda}, Revisão em vigor "
                f"**{revisao_atual_forecast_app}** pra Despesa. **Meta/Δ** = meta oficial fixa aprovada "
                "pro ano inteiro (não acompanha mais a Revisão automaticamente); não entra em "
                f"nenhum cálculo do Forecast; Δ = Forecast menos Meta. **Realizado {ano - 1}/Δ** = DRE "
                f"fechada de {ano - 1} (RESULTADOS {ano - 1}.xlsx), ano inteiro, só comparativo; Δ = "
                f"Forecast {ano} menos Realizado {ano - 1}."
            )

    st.divider()

    # ------------------------------------------------------------------
    # Receita e Despesa por Categoria (Centro de Custo classificado)
    # ------------------------------------------------------------------
    st.markdown("<div class='quebra-pagina'></div>", unsafe_allow_html=True)
    st.header("Receita e Despesa por Categoria")
    st.caption(
        "Quebra por categoria de Centro de Custo, a partir da classificação feita em "
        "\"Classificar Centros de Custo\". Centros de Custo ainda sem classificação "
        "aparecem como \"Não classificado\"."
    )


    receita_real_mes_cat = receita_por_categoria_realizado(df_real_filtrado, mes_ref, mes_ref)
    receita_real_acum_cat = receita_por_categoria_realizado(df_real_filtrado, mes_ini_ano, mes_ref)
    receita_orc_mes_cat = receita_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao_sel, cenario_sel, mes_ref, mes_ref)
    receita_orc_acum_cat = receita_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)

    def _config_colunas_com_textuais(colunas_numericas: list[str], colunas_textuais: set[str]) -> dict:
        # format="localized" usa o idioma do NAVEGADOR de quem acessa (não do
        # servidor) pra decidir separador de milhar/decimal — pra um usuário com
        # o navegador em pt-BR já sai com ponto de milhar, igual ao resto do
        # app. Crucial: mantém o valor como número de verdade, então clicar no
        # cabeçalho pra ordenar ordena pelo VALOR, não pelo texto formatado
        # (era isso que causava "969.336" vir antes de "84.184").
        #
        # Colunas em `colunas_textuais` viram TextColumn em vez de NumberColumn
        # — pedido do usuário, 2026-10-23: uma coluna 100% N/D (nenhuma fonte de
        # Orçado pra essa Revisão/granularidade) como NumberColumn("localized")
        # renderizava "None" na tela em vez de ficar em branco (bug visual do
        # componente), então colunas assim viram texto puro ("N/D").
        config = {}
        for nome in colunas_numericas:
            if nome in colunas_textuais:
                config[nome] = st.column_config.TextColumn(nome)
            else:
                # step=1 força exibição inteira (sem casas decimais) mantendo o
                # separador localizado — não afeta o valor numérico de verdade
                # usado pra ordenar (doc do NumberColumn: "step... ensures a
                # consistent number of digits after the decimal"). Sem isso,
                # valores apareciam com 0 a 3 casas decimais soltas (item 14,
                # 2026-11-11).
                config[nome] = st.column_config.NumberColumn(nome, format="localized", step=1)
        return config


    def _tabela_discreta_categoria(serie_real_mes, serie_orc_mes, serie_real_acum, serie_orc_acum) -> pd.DataFrame:
        categorias = sorted(
            set(serie_real_mes.index)
            | set(serie_orc_mes.index if serie_orc_mes is not None else [])
            | set(serie_real_acum.index)
            | set(serie_orc_acum.index if serie_orc_acum is not None else []),
            key=lambda c: -(serie_real_acum.get(c, 0) or 0),
        )

        def _v(serie, cat):
            return "N/D" if serie is None else float(serie.get(cat, 0.0))

        linhas = [
            {
                "Categoria": cat,
                f"Orçado {nome_mes}/{ano}": _v(serie_orc_mes, cat),
                f"Realizado {nome_mes}/{ano}": _v(serie_real_mes, cat),
                f"Orçado Acum. {ano}": _v(serie_orc_acum, cat),
                f"Realizado Acum. {ano}": _v(serie_real_acum, cat),
            }
            for cat in categorias
        ]
        return pd.DataFrame(linhas)


    def _tabela_cc_da_categoria(categoria, detalhe_real_mes, detalhe_orc_mes, detalhe_real_acum, detalhe_orc_acum) -> pd.DataFrame:
        """Uma linha por Centro de Custo (por Código) dentro da categoria, com os 4 valores.

        Concilia Orçado x Realizado pelo CÓDIGO do Centro de Custo, não mais
        pelo nome — Orçado e Realizado às vezes grafam o mesmo Centro de Custo
        de um jeito ligeiramente diferente (abreviação, acento, maiúscula), o
        que fazia a busca por nome cair em duas linhas separadas em vez de
        conciliar na mesma linha. O Código já vem confiável dos dois lados em
        todo detalhamento (_detalhar/_detalhar_serie em analise_categoria.py);
        pra Despesa REV02 especificamente, o Código é resolvido a partir do
        de-para de nomes já existente (ver _despesa_por_cc_rev02 em
        analise_categoria.py — o de-para em si não foi alterado)."""

        def _filtra(df):
            if df is None or df.empty:
                return pd.Series(dtype=float)
            sub = df.loc[df["Categoria"] == categoria].copy()
            sub["Codigo"] = sub["Codigo"].astype(str).str.strip()
            return sub.groupby("Codigo")["Valor"].sum()

        def _nomes(df):
            # Alguns lançamentos do Realizado vêm sem "Centro de Custo" preenchido
            # (vira "(sem nome)" lá em _detalhar) mesmo quando o mesmo Código tem
            # nome real em outros lançamentos — sem essa priorização, o
            # drop_duplicates abaixo podia pegar justo a variante "(sem nome)"
            # pro Código (ordenação alfabética: "(" vem antes de letra). Regra:
            # só usa "(sem nome)" quando o Código não tem NENHUM nome real.
            if df is None or df.empty:
                return {}
            sub = df.loc[df["Categoria"] == categoria].copy()
            sub["Codigo"] = sub["Codigo"].astype(str).str.strip()
            sub["_tem_nome"] = sub["Centro de Custo"] != "(sem nome)"
            sub = sub.sort_values("_tem_nome", ascending=False)
            return sub.drop_duplicates("Codigo").set_index("Codigo")["Centro de Custo"].to_dict()

        f_real_mes, f_orc_mes = _filtra(detalhe_real_mes), _filtra(detalhe_orc_mes)
        f_real_acum, f_orc_acum = _filtra(detalhe_real_acum), _filtra(detalhe_orc_acum)

        # Nome de exibição: prioriza o Orçado (pedido do usuário, 2026-10-28) —
        # cai pro nome do Realizado só quando o Código não existe no Orçado.
        nomes = {}
        for d in (detalhe_real_mes, detalhe_real_acum, detalhe_orc_mes, detalhe_orc_acum):
            nomes.update(_nomes(d))

        ccs = sorted(
            set(f_real_mes.index) | set(f_orc_mes.index) | set(f_real_acum.index) | set(f_orc_acum.index),
            key=lambda cc: -abs(f_real_acum.get(cc, 0.0)),
        )

        def _v(serie, cc, disponivel):
            if not disponivel:
                return "N/D"
            return float(serie.get(cc, 0.0))

        tem_orc_mes = detalhe_orc_mes is not None
        tem_orc_acum = detalhe_orc_acum is not None
        linhas = [
            {
                "Código": cc,
                "Centro de Custo": nomes.get(cc, cc),
                f"Orçado {nome_mes}/{ano}": _v(f_orc_mes, cc, tem_orc_mes),
                f"Realizado {nome_mes}/{ano}": _v(f_real_mes, cc, True),
                f"Orçado Acum. {ano}": _v(f_orc_acum, cc, tem_orc_acum),
                f"Realizado Acum. {ano}": _v(f_real_acum, cc, True),
            }
            for cc in ccs
        ]
        return pd.DataFrame(linhas)


    def _render_categoria_com_drilldown(
        serie_real_mes, serie_orc_mes, serie_real_acum, serie_orc_acum,
        detalhe_real_mes, detalhe_orc_mes, detalhe_real_acum, detalhe_orc_acum,
    ):
        nomes_colunas = [
            f"Orçado {nome_mes}/{ano}", f"Realizado {nome_mes}/{ano}",
            f"Orçado Acum. {ano}", f"Realizado Acum. {ano}",
        ]
        colunas_textuais_cat = {
            nome for nome, disponivel in [
                (f"Orçado {nome_mes}/{ano}", serie_orc_mes is not None),
                (f"Orçado Acum. {ano}", serie_orc_acum is not None),
            ] if not disponivel
        }
        st.dataframe(
            _tabela_discreta_categoria(serie_real_mes, serie_orc_mes, serie_real_acum, serie_orc_acum),
            hide_index=True,
            use_container_width=True,
            column_config=_config_colunas_com_textuais(nomes_colunas, colunas_textuais_cat),
        )
        categorias = sorted(
            set(serie_real_mes.index)
            | set(serie_orc_mes.index if serie_orc_mes is not None else [])
            | set(serie_real_acum.index)
            | set(serie_orc_acum.index if serie_orc_acum is not None else []),
            key=lambda c: -(serie_real_acum.get(c, 0) or 0),
        )
        st.caption("Abra uma categoria abaixo pra ver os Centros de Custo que a compõem:")
        if detalhe_orc_mes is None or detalhe_orc_acum is None:
            st.caption(
                "⚠️ Essa Revisão não tem Orçado detalhado por Centro de Custo (só no agregado da "
                "categoria, na tabela acima) — por isso aparece \"N/D\" no detalhamento abaixo."
            )
        colunas_textuais_cc = {
            nome for nome, disponivel in [
                (f"Orçado {nome_mes}/{ano}", detalhe_orc_mes is not None),
                (f"Orçado Acum. {ano}", detalhe_orc_acum is not None),
            ] if not disponivel
        }
        colunas_moeda_cc = _config_colunas_com_textuais(nomes_colunas, colunas_textuais_cc)
        for cat in categorias:
            with st.expander(f"🔎 {cat}"):
                st.dataframe(
                    _tabela_cc_da_categoria(cat, detalhe_real_mes, detalhe_orc_mes, detalhe_real_acum, detalhe_orc_acum),
                    hide_index=True,
                    use_container_width=True,
                    column_config=colunas_moeda_cc,
                )



    # Cor fixa por categoria (item 26) — calculada uma vez com a lista
    # canônica inteira, reaproveitada nos 3 blocos (Receita/Lucro Bruto/
    # Despesa) × (Mês/Acumulado), não recalculada por gráfico.
    mapa_cores_cat = mapa_cores_categorias(todas_categorias_conhecidas())

    st.subheader("Receita Bruta por Categoria (em R$)")
    col_rec_mes, col_rec_acum = st.columns(2)
    col_rec_mes.plotly_chart(
        grafico_categoria_empilhado(
            f"Receita Bruta (em R$) — {nome_mes}/{ano}", receita_orc_mes_cat, receita_real_mes_cat, format_brl_compacto, mapa_cores_cat
        ),
        use_container_width=True,
    )
    col_rec_acum.plotly_chart(
        grafico_categoria_empilhado(
            f"Receita Bruta (em R$) — Acumulado {ano}", receita_orc_acum_cat, receita_real_acum_cat, format_brl_compacto, mapa_cores_cat
        ),
        use_container_width=True,
    )
    col_rec_mes.markdown(
        render_caixa_narrativa(
            f"ANÁLISE DE {nome_mes}/{ano}",
            gerar_analise(
                "Receita Bruta", f"{nome_mes}/{ano}",
                dre_mes_real["receita_bruta"], dre_mes_orc.get("receita_bruta"),
                receita_real_mes_cat, receita_orc_mes_cat, favoravel_se_maior=True,
            ),
        ),
        unsafe_allow_html=True,
    )
    col_rec_acum.markdown(
        render_caixa_narrativa(
            "ANÁLISE DE ACUMULADO",
            gerar_analise(
                "Receita Bruta", f"Acumulado {ano}",
                dre_acum_real["receita_bruta"], dre_acum_orc.get("receita_bruta"),
                receita_real_acum_cat, receita_orc_acum_cat, favoravel_se_maior=True,
            ),
        ),
        unsafe_allow_html=True,
    )
    receita_detalhe_real_mes = receita_por_cc_realizado(df_real_filtrado, mes_ref, mes_ref)
    receita_detalhe_real_acum = receita_por_cc_realizado(df_real_filtrado, mes_ini_ano, mes_ref)
    receita_detalhe_orc_mes = receita_por_cc_previsto(df_previsto, df_refinado_detalhado, df_real, tabela_dimensao, revisao_sel, cenario_sel, mes_ref, mes_ref)
    receita_detalhe_orc_acum = receita_por_cc_previsto(df_previsto, df_refinado_detalhado, df_real, tabela_dimensao, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)

    with st.expander("Ver valores em tabela (Receita Bruta por Categoria)"):
        _render_categoria_com_drilldown(
            receita_real_mes_cat, receita_orc_mes_cat, receita_real_acum_cat, receita_orc_acum_cat,
            receita_detalhe_real_mes, receita_detalhe_orc_mes, receita_detalhe_real_acum, receita_detalhe_orc_acum,
        )

    # ------------------------------------------------------------------
    # Lucro Bruto por Categoria (= Receita Bruta por Categoria - Custo por
    # Categoria, mesma classificação) — página 9 da apresentação de referência.
    # ------------------------------------------------------------------
    def _soma_serie_opcional(a, b):
        return None if a is None or b is None else a.add(b, fill_value=0.0)


    def _combinar_detalhe(a, b):
        if a is None or b is None:
            return None
        return pd.concat([a, b], ignore_index=True).groupby(["Categoria", "Codigo", "Centro de Custo"], as_index=False)["Valor"].sum()


    # Lucro Bruto = Receita Líquida (Bruta + Imposto) + Custo — mesma definição
    # da DRE (margem_bruta), não só Receita Bruta + Custo.
    custo_real_mes_cat = custo_por_categoria_realizado(df_real_filtrado, mes_ref, mes_ref)
    custo_real_acum_cat = custo_por_categoria_realizado(df_real_filtrado, mes_ini_ano, mes_ref)
    custo_orc_mes_cat = custo_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao_sel, cenario_sel, mes_ref, mes_ref)
    custo_orc_acum_cat = custo_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)
    imposto_real_mes_cat = imposto_por_categoria_realizado(df_real_filtrado, mes_ref, mes_ref)
    imposto_real_acum_cat = imposto_por_categoria_realizado(df_real_filtrado, mes_ini_ano, mes_ref)
    imposto_orc_mes_cat = imposto_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao_sel, cenario_sel, mes_ref, mes_ref)
    imposto_orc_acum_cat = imposto_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)

    lucro_real_mes_cat = receita_real_mes_cat.add(imposto_real_mes_cat, fill_value=0.0).add(custo_real_mes_cat, fill_value=0.0)
    lucro_real_acum_cat = receita_real_acum_cat.add(imposto_real_acum_cat, fill_value=0.0).add(custo_real_acum_cat, fill_value=0.0)
    lucro_orc_mes_cat = _soma_serie_opcional(_soma_serie_opcional(receita_orc_mes_cat, imposto_orc_mes_cat), custo_orc_mes_cat)
    lucro_orc_acum_cat = _soma_serie_opcional(_soma_serie_opcional(receita_orc_acum_cat, imposto_orc_acum_cat), custo_orc_acum_cat)

    st.subheader("Lucro Bruto por Categoria (em R$)")
    col_lb_mes, col_lb_acum = st.columns(2)
    col_lb_mes.plotly_chart(
        grafico_categoria_empilhado(
            f"Lucro Bruto (em R$) — {nome_mes}/{ano}", lucro_orc_mes_cat, lucro_real_mes_cat, format_brl_compacto, mapa_cores_cat
        ),
        use_container_width=True,
    )
    col_lb_acum.plotly_chart(
        grafico_categoria_empilhado(
            f"Lucro Bruto (em R$) — Acumulado {ano}", lucro_orc_acum_cat, lucro_real_acum_cat, format_brl_compacto, mapa_cores_cat
        ),
        use_container_width=True,
    )
    col_lb_mes.markdown(
        render_caixa_narrativa(
            f"ANÁLISE DE {nome_mes}/{ano}",
            gerar_analise(
                "Lucro Bruto", f"{nome_mes}/{ano}",
                lucro_real_mes_cat.sum(), lucro_orc_mes_cat.sum() if lucro_orc_mes_cat is not None else None,
                lucro_real_mes_cat, lucro_orc_mes_cat, favoravel_se_maior=True,
            ),
        ),
        unsafe_allow_html=True,
    )
    col_lb_acum.markdown(
        render_caixa_narrativa(
            "ANÁLISE DE ACUMULADO",
            gerar_analise(
                "Lucro Bruto", f"Acumulado {ano}",
                lucro_real_acum_cat.sum(), lucro_orc_acum_cat.sum() if lucro_orc_acum_cat is not None else None,
                lucro_real_acum_cat, lucro_orc_acum_cat, favoravel_se_maior=True,
            ),
        ),
        unsafe_allow_html=True,
    )

    lucro_detalhe_real_mes = _combinar_detalhe(
        _combinar_detalhe(receita_detalhe_real_mes, imposto_por_cc_realizado(df_real_filtrado, mes_ref, mes_ref)),
        custo_por_cc_realizado(df_real_filtrado, mes_ref, mes_ref),
    )
    lucro_detalhe_real_acum = _combinar_detalhe(
        _combinar_detalhe(receita_detalhe_real_acum, imposto_por_cc_realizado(df_real_filtrado, mes_ini_ano, mes_ref)),
        custo_por_cc_realizado(df_real_filtrado, mes_ini_ano, mes_ref),
    )
    lucro_detalhe_orc_mes = _combinar_detalhe(
        _combinar_detalhe(
            receita_detalhe_orc_mes,
            imposto_por_cc_previsto(df_previsto, df_refinado_detalhado, df_real, tabela_dimensao, revisao_sel, cenario_sel, mes_ref, mes_ref),
        ),
        custo_por_cc_previsto(df_previsto, df_refinado_detalhado, df_real, tabela_dimensao, revisao_sel, cenario_sel, mes_ref, mes_ref),
    )
    lucro_detalhe_orc_acum = _combinar_detalhe(
        _combinar_detalhe(
            receita_detalhe_orc_acum,
            imposto_por_cc_previsto(df_previsto, df_refinado_detalhado, df_real, tabela_dimensao, revisao_sel, cenario_sel, mes_ini_ano, mes_ref),
        ),
        custo_por_cc_previsto(df_previsto, df_refinado_detalhado, df_real, tabela_dimensao, revisao_sel, cenario_sel, mes_ini_ano, mes_ref),
    )

    with st.expander("Ver valores em tabela (Lucro Bruto por Categoria)"):
        _render_categoria_com_drilldown(
            lucro_real_mes_cat, lucro_orc_mes_cat, lucro_real_acum_cat, lucro_orc_acum_cat,
            lucro_detalhe_real_mes, lucro_detalhe_orc_mes, lucro_detalhe_real_acum, lucro_detalhe_orc_acum,
        )

    # Despesa vem negativa (convenção "dedução = negativo") — inverte pra mostrar
    # magnitude positiva (igual à apresentação de referência).
    despesa_real_mes_cat = -despesa_por_categoria_realizado(df_real_filtrado, mes_ref, mes_ref)
    despesa_real_acum_cat = -despesa_por_categoria_realizado(df_real_filtrado, mes_ini_ano, mes_ref)
    despesa_orc_mes_cat = despesa_por_categoria_previsto(df_previsto, df_real, revisao_sel, cenario_sel, mes_ref, mes_ref)
    despesa_orc_acum_cat = despesa_por_categoria_previsto(df_previsto, df_real, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)
    if despesa_orc_mes_cat is not None:
        despesa_orc_mes_cat = -despesa_orc_mes_cat
    if despesa_orc_acum_cat is not None:
        despesa_orc_acum_cat = -despesa_orc_acum_cat

    st.subheader("Despesa Total por Categoria (em R$)")
    col_desp_mes, col_desp_acum = st.columns(2)
    col_desp_mes.plotly_chart(
        grafico_categoria_empilhado(
            f"Despesa Total (em R$) — {nome_mes}/{ano}", despesa_orc_mes_cat, despesa_real_mes_cat, format_brl_compacto, mapa_cores_cat
        ),
        use_container_width=True,
    )
    col_desp_acum.plotly_chart(
        grafico_categoria_empilhado(
            f"Despesa Total (em R$) — Acumulado {ano}", despesa_orc_acum_cat, despesa_real_acum_cat, format_brl_compacto, mapa_cores_cat
        ),
        use_container_width=True,
    )
    despesa_orc_mes_total = dre_mes_orc.get("despesa_adm")
    despesa_orc_acum_total = dre_acum_orc.get("despesa_adm")
    col_desp_mes.markdown(
        render_caixa_narrativa(
            f"ANÁLISE DE {nome_mes}/{ano}",
            gerar_analise(
                # Magnitude positiva (-1 * valor), igual à convenção já usada nas
                # séries de categoria acima — "Despesa real > Orçado" tem que dar
                # delta positivo (gastou mais) pra bater com favoravel_se_maior=False.
                "Despesa Administrativa", f"{nome_mes}/{ano}",
                -dre_mes_real["despesa_adm"],
                -despesa_orc_mes_total if despesa_orc_mes_total is not None else None,
                despesa_real_mes_cat, despesa_orc_mes_cat, favoravel_se_maior=False,
            ),
        ),
        unsafe_allow_html=True,
    )
    col_desp_acum.markdown(
        render_caixa_narrativa(
            "ANÁLISE DE ACUMULADO",
            gerar_analise(
                "Despesa Administrativa", f"Acumulado {ano}",
                -dre_acum_real["despesa_adm"],
                -despesa_orc_acum_total if despesa_orc_acum_total is not None else None,
                despesa_real_acum_cat, despesa_orc_acum_cat, favoravel_se_maior=False,
            ),
        ),
        unsafe_allow_html=True,
    )
    despesa_detalhe_real_mes = despesa_por_cc_realizado(df_real_filtrado, mes_ref, mes_ref).assign(Valor=lambda d: -d["Valor"])
    despesa_detalhe_real_acum = despesa_por_cc_realizado(df_real_filtrado, mes_ini_ano, mes_ref).assign(Valor=lambda d: -d["Valor"])
    despesa_detalhe_orc_mes = despesa_por_cc_previsto(df_previsto, df_real, revisao_sel, cenario_sel, mes_ref, mes_ref)
    despesa_detalhe_orc_acum = despesa_por_cc_previsto(df_previsto, df_real, revisao_sel, cenario_sel, mes_ini_ano, mes_ref)
    if despesa_detalhe_orc_mes is not None:
        despesa_detalhe_orc_mes = despesa_detalhe_orc_mes.assign(Valor=lambda d: -d["Valor"])
    if despesa_detalhe_orc_acum is not None:
        despesa_detalhe_orc_acum = despesa_detalhe_orc_acum.assign(Valor=lambda d: -d["Valor"])

    with st.expander("Ver valores em tabela (Despesa Total por Categoria)"):
        _render_categoria_com_drilldown(
            despesa_real_mes_cat, despesa_orc_mes_cat, despesa_real_acum_cat, despesa_orc_acum_cat,
            despesa_detalhe_real_mes, despesa_detalhe_orc_mes, despesa_detalhe_real_acum, despesa_detalhe_orc_acum,
        )

    # ------------------------------------------------------------------
    # Análise de Complexos (páginas 10/11 da apresentação de referência) —
    # unidade = Centro de Custo direto (não agrupado em "Complexo" comercial).
    # O agrupamento por Complexo cobria só ~32 Centro de Custo de Receita,
    # com boa parte caindo em "SEM AGRUPAMENTO"; trocado por Centro de Custo
    # puro pra maior cobertura e confiabilidade (sem agrupamento adivinhado).
    # ------------------------------------------------------------------
    st.markdown("<div class='quebra-pagina'></div>", unsafe_allow_html=True)
    st.header("Análise de Complexos")

    analise_cpx = construir_analise_complexos(
        df_real_filtrado, df_refinado_detalhado, tabela_dimensao, mes_ref, mes_ini_ano, revisao_sel, cenario_sel
    )
    status_cpx = analise_cpx.status_todos()
    st.caption(f"Cobre todo Centro de Custo que já apareceu em Receita Bruta (Realizado ou Orçado) — {len(status_cpx)} ao todo.")
    if analise_cpx.janela_sem_historico():
        st.info(
            f"ℹ️ Nos primeiros {MESES_NOVO_MOBILIZADO} meses em que esta base tem dado (a partir de Jan/2026), "
            "todo complexo ativo aparece como \"Novo Mobilizado\" — não existe histórico de 2025 por Centro de "
            "Custo nesta base (só uma DRE 2025 já agregada, sem essa granularidade) pra distinguir de \"Ativo\"."
        )

    # "Complexos Totais" não varia entre o bloco do Mês e o do Acumulado (vem
    # de status_cpx, calculado uma vez só acima) — mostrado uma única vez,
    # fora de _render_complexos_periodo (antes se repetia idêntico nos dois
    # blocos, item 4, 2026-11-11).
    from collections import Counter

    st.plotly_chart(
        grafico_pizza_status(f"Complexos Totais: {len(status_cpx)}", Counter(status_cpx.values())),
        use_container_width=True,
    )


    def _lista_nomeada(ccs) -> str:
        return " + ".join(analise_cpx.nome(c) for c in sorted(ccs, key=analise_cpx.nome)) if ccs else "nenhum"


    def _render_complexos_periodo(badge: str, serie_receita_real, serie_receita_orc, serie_lucro_real, serie_lucro_orc):
        operando = analise_cpx.complexos_operando()

        receita_acima = [c for c in operando if c in serie_receita_orc.index and serie_receita_real.get(c, 0) > serie_receita_orc.get(c, 0)]
        receita_avaliaveis = [c for c in operando if c in serie_receita_orc.index]
        receita_abaixo = [c for c in receita_avaliaveis if c not in receita_acima]

        lucro_positivo = [c for c in operando if serie_lucro_real.get(c, 0) > 0]
        lucro_negativo = [c for c in operando if c not in lucro_positivo]

        lucro_acima = [c for c in operando if c in serie_lucro_orc.index and serie_lucro_real.get(c, 0) > serie_lucro_orc.get(c, 0)]
        lucro_avaliaveis = [c for c in operando if c in serie_lucro_orc.index]
        lucro_abaixo = [c for c in lucro_avaliaveis if c not in lucro_acima]

        # Título = soma das fatias DAQUELA pizza (não mais len(operando) fixo
        # pras 3 — item 4, 2026-11-11). Quando a pizza cobre só um subconjunto
        # de `operando` (nem todo complexo ativo tem orçado comparável nesse
        # recorte), um subtítulo explica quantos ficaram de fora.
        col1, col2, col3 = st.columns(3)
        col1.plotly_chart(
            grafico_pizza_duas_fatias(
                f"Receita Bruta — {badge}: {len(receita_avaliaveis)}",
                "Receita Bruta Acima do Previsto", len(receita_acima),
                "Receita Bruta Abaixo do Previsto", len(receita_abaixo),
            ),
            use_container_width=True,
        )
        if len(receita_avaliaveis) < len(operando):
            col1.caption(f"{len(receita_avaliaveis)} de {len(operando)} complexos ativos — {len(operando) - len(receita_avaliaveis)} sem orçamento de Receita Bruta no período.")
        col2.plotly_chart(
            grafico_pizza_duas_fatias(
                f"Lucro Bruto Realizado — {badge}: {len(operando)}",
                "Lucro Bruto Realizado Positivo", len(lucro_positivo),
                "Lucro Bruto Realizado Negativo", len(lucro_negativo),
            ),
            use_container_width=True,
        )
        col3.plotly_chart(
            grafico_pizza_duas_fatias(
                f"Lucro Bruto x Orçado — {badge}: {len(lucro_avaliaveis)}",
                "Lucro Bruto Acima do Previsto", len(lucro_acima),
                "Lucro Bruto Abaixo do Previsto", len(lucro_abaixo),
            ),
            use_container_width=True,
        )
        if len(lucro_avaliaveis) < len(operando):
            col3.caption(f"{len(lucro_avaliaveis)} de {len(operando)} complexos ativos — {len(operando) - len(lucro_avaliaveis)} sem orçamento de Lucro Bruto no período.")
        st.markdown(
            f"- **Lucro Bruto Realizado Negativo** ({len(lucro_negativo)}): {_lista_nomeada(lucro_negativo)}.\n"
            f"- **Lucro Bruto Acima do Previsto** ({len(lucro_acima)}): {_lista_nomeada(lucro_acima)}."
        )


    st.subheader(f"{nome_mes}/{ano}")
    _render_complexos_periodo(
        f"{nome_mes}/{ano}",
        analise_cpx.receita_real_mes, analise_cpx.receita_orc_mes,
        analise_cpx.lucro_real_mes, analise_cpx.lucro_orc_mes,
    )

    st.subheader(f"Acumulado {ano}")
    _render_complexos_periodo(
        f"{ano}",
        analise_cpx.receita_real_acum, analise_cpx.receita_orc_acum,
        analise_cpx.lucro_real_acum, analise_cpx.lucro_orc_acum,
    )

