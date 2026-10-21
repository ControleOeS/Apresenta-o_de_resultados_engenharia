import pandas as pd
import streamlit as st

from classificacoes import (
    CLASSIFICACOES_FIXAS,
    adicionar_categoria,
    carregar_categorias,
    carregar_classificacoes,
    remover_categoria,
    salvar_classificacoes,
)
from dados import carregar_previsto, carregar_realizado_superus
from auth import mostrar_banner_ambiente, require_password

st.set_page_config(page_title="Classificar Centros de Custo", page_icon="🏷️", layout="wide")
require_password()
mostrar_banner_ambiente()
st.title("Classificar Centros de Custo")
st.caption(
    "Associe cada Centro de Custo a uma categoria — de Receita (BackLog Ativo, BackLog "
    "Novo, Funil de Vendas...) ou de Despesa/SGA (Operação, Comercial, Administração...). "
    "Fica salvo neste computador (não depende de deixar o app aberto) e passa a ser usado "
    "pelas análises por categoria."
)

SEM_CATEGORIA = "— sem categoria —"

classificacoes = carregar_classificacoes()
categorias = carregar_categorias()
# Categorias usadas em classificações antigas que não estejam na lista oficial
# (ex: salvas antes dessa lista existir) continuam aparecendo como opção.
categorias_em_uso = {info["categoria"] for info in classificacoes.values() if info.get("categoria")}
opcoes_categoria = [SEM_CATEGORIA] + sorted(set(categorias) | categorias_em_uso)

with st.expander("⚙️ Gerenciar categorias", expanded=not categorias):
    with st.form("form_nova_categoria", clear_on_submit=True):
        col_nova, col_botao = st.columns([3, 1])
        nova_categoria = col_nova.text_input(
            "Nova categoria",
            label_visibility="collapsed",
            placeholder="Ex: BackLog Ativo, Funil de Vendas, Operação...",
        )
        enviado = col_botao.form_submit_button("➕ Adicionar", use_container_width=True)
    if enviado and nova_categoria.strip():
        adicionar_categoria(nova_categoria)
        st.rerun()

    if categorias:
        st.caption("Categorias cadastradas:")
        for cat in categorias:
            col_nome, col_remover = st.columns([5, 1])
            col_nome.write(cat)
            if col_remover.button("🗑️", key=f"remover_{cat}", help=f"Remover '{cat}'"):
                remover_categoria(cat)
                st.rerun()
    else:
        st.caption("Nenhuma categoria cadastrada ainda — crie a primeira acima.")

st.divider()

df_real = carregar_realizado_superus()
df_previsto = carregar_previsto()

reais = df_real[["Cod. Centro de Custo", "Centro de Custo"]].dropna().copy()
reais.columns = ["codigo", "nome"]
reais["codigo"] = reais["codigo"].astype(str)

prevs = df_previsto[["CC", "Centro de Custo"]].dropna().copy()
prevs.columns = ["codigo", "nome"]
prevs["codigo"] = prevs["codigo"].astype(str)

todos = (
    pd.concat([reais, prevs], ignore_index=True)
    .drop_duplicates(subset="codigo")
    .sort_values("nome")
    .reset_index(drop=True)
)
# Classificações fixas (ex: AJUSTE -> Backlog Ativo) não aparecem aqui — não
# dá pra editar o que é fixo (ver classificacoes.CLASSIFICACOES_FIXAS).
todos = todos[~todos["codigo"].isin(CLASSIFICACOES_FIXAS.keys())]

busca = st.text_input("🔎 Buscar Centro de Custo (nome ou código)", "")
if busca:
    filtro = (
        todos["nome"].str.contains(busca, case=False, na=False)
        | todos["codigo"].str.contains(busca, case=False, na=False)
    )
    visivel = todos[filtro]
else:
    visivel = todos[~todos["codigo"].isin(classificacoes.keys())]
    st.caption(
        f"Mostrando os {len(visivel)} Centros de Custo ainda sem categoria. "
        "Use a busca acima pra encontrar um específico (inclusive os já classificados)."
    )

tabela = pd.DataFrame(
    {
        "Código": visivel["codigo"].tolist(),
        "Centro de Custo": visivel["nome"].tolist(),
        "Categoria": [classificacoes.get(cod, {}).get("categoria") or SEM_CATEGORIA for cod in visivel["codigo"]],
    }
)

if not categorias:
    st.info("Cadastre pelo menos uma categoria acima (⚙️ Gerenciar categorias) antes de classificar.")
else:
    editado = st.data_editor(
        tabela,
        hide_index=True,
        use_container_width=True,
        disabled=["Código", "Centro de Custo"],
        column_config={
            "Categoria": st.column_config.SelectboxColumn(
                "Categoria", options=opcoes_categoria, required=False
            ),
        },
        key="editor_classificacao_cc",
    )

    if st.button("💾 Salvar classificações", type="primary"):
        alterados = 0
        for _, linha in editado.iterrows():
            codigo, nome, categoria = linha["Código"], linha["Centro de Custo"], linha["Categoria"]
            categoria = "" if categoria in (None, SEM_CATEGORIA) else categoria.strip()
            atual = classificacoes.get(codigo, {}).get("categoria", "")
            if categoria != atual:
                alterados += 1
            if categoria:
                classificacoes[codigo] = {"nome": nome, "categoria": categoria}
            elif codigo in classificacoes:
                del classificacoes[codigo]
        salvar_classificacoes(classificacoes)
        st.success(f"{alterados} classificação(ões) atualizada(s).")
        st.rerun()

st.divider()
with st.expander(f"Ver todas as {len(classificacoes)} classificações já salvas"):
    if classificacoes:
        df_salvas = pd.DataFrame(
            [(cod, info["nome"], info["categoria"]) for cod, info in classificacoes.items()],
            columns=["Código", "Centro de Custo", "Categoria"],
        ).sort_values("Centro de Custo")
        st.dataframe(df_salvas, hide_index=True, use_container_width=True)
    else:
        st.caption("Nenhuma classificação salva ainda.")
