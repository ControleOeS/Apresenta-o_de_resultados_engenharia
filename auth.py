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
