import streamlit as st


def require_password():
    if st.session_state.get("autenticado"):
        return

    st.title("Acesso Restrito")

    with st.form("login_form"):
        senha = st.text_input("Senha", type="password")
        enviado = st.form_submit_button("Entrar")

    if enviado:
        senha_correta = str(st.secrets.get("APP_PASSWORD", "")).strip()
        if senha.strip() == senha_correta:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")

    st.stop()


def pode_editar_forecast() -> bool:
    """True se a senha de edição do Forecast já foi validada nesta sessão
    (ver pedir_senha_edicao_forecast) — pedido do usuário, 2026-10-21: só
    quem souber essa segunda senha (diferente da senha geral de acesso ao
    app) pode editar/salvar o Forecast; o resto de quem acessa o app
    continua só visualizando."""
    return bool(st.session_state.get("pode_editar_forecast"))


def pedir_senha_edicao_forecast() -> None:
    """Formulário pra liberar edição/salvar do Forecast nesta sessão — ao
    contrário de require_password(), NÃO bloqueia o resto da página: quem
    não digitar a senha continua vendo o Forecast normalmente, só não
    consegue editar as tabelas nem salvar."""
    if pode_editar_forecast():
        st.success("🔓 Edição liberada nesta sessão.")
        return

    with st.expander("🔒 Habilitar edição (senha)"):
        with st.form("form_senha_edicao_forecast"):
            senha = st.text_input("Senha de edição", type="password")
            enviado = st.form_submit_button("Entrar")
        if enviado:
            senha_correta = str(st.secrets.get("FORECAST_EDIT_PASSWORD", "")).strip()
            if senha.strip() and senha.strip() == senha_correta:
                st.session_state["pode_editar_forecast"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")


def mostrar_banner_ambiente() -> None:
    """Aviso visual no topo de cada página quando o app está rodando no
    ambiente de teste (staging) — configurado via o secret AMBIENTE no painel
    do Streamlit Cloud dessa implantação específica, nunca no código. Sem
    esse secret (produção), não mostra nada."""
    ambiente = str(st.secrets.get("AMBIENTE", "")).strip().lower()
    if ambiente == "staging":
        st.warning(
            "🧪 **Ambiente de teste** — esta é a versão de testes do dashboard, "
            "não o site usado pela diretoria. Mudanças feitas aqui não afetam a produção."
        )
