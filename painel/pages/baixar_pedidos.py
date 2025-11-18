# streamlit_app.py
import streamlit as st
import pandas as pd
from io import BytesIO
import datetime
from concurrent.futures import ThreadPoolExecutor
from pages.baixar_pedidos import baixar_pedidos  # sua função

st.set_page_config(page_title="Painel BEES 🐝", layout="wide", page_icon="💵")
st.title("Painel BEES🐝")

# Executor único por processo
@st.cache_resource
def get_executor():
    return ThreadPoolExecutor(max_workers=1)

executor = get_executor()

# Estado inicial
if "future" not in st.session_state:
    st.session_state.future = None
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "error" not in st.session_state:
    st.session_state.error = None
if "status" not in st.session_state:
    st.session_state.status = "Pronto"

def task_wrapper():
    """
    Executa baixar_pedidos e retorna o resultado bruto.
    Não deve acessar st.session_state (executa em thread separada).
    """
    return baixar_pedidos()

# Botão para iniciar
if st.button("Iniciar coleta de pedidos"):
    # evita enfileirar múltiplas execuções simultâneas
    if st.session_state.future is None or st.session_state.future.done():
        st.session_state.status = "Enfileirado"
        st.session_state.error = None
        st.session_state.future = executor.submit(task_wrapper)
    else:
        st.warning("Já existe uma execução em andamento. Aguarde terminar.")

# Mostrar status
st.markdown(f"**Status:** {st.session_state.status}")
future = st.session_state.future
if future is not None:
    if future.running():
        st.session_state.status = "Executando"
        st.info("Coleta em andamento... aguarde.")
    elif future.done():
        # pega resultado sem bloquear (já está done)
        try:
            resultado = future.result()
            # processa tipos possíveis retornados pela sua função
            df = None
            if isinstance(resultado, pd.DataFrame):
                df = resultado
            elif isinstance(resultado, str):
                # caminho para arquivo
                if resultado.lower().endswith(".csv"):
                    df = pd.read_csv(resultado, encoding='utf-8-sig', dtype=str)
                else:
                    df = pd.read_excel(resultado)
            elif isinstance(resultado, (bytes, bytearray)):
                buf = BytesIO(resultado)
                try:
                    df = pd.read_excel(buf)
                except Exception:
                    buf.seek(0)
                    df = pd.read_csv(buf)
            else:
                st.info("A função retornou um tipo inesperado. Verifique o log.")

            if df is not None and not df.empty:
                st.session_state.df = df
                st.session_state.status = "Concluído"
                st.success("Coleta finalizada com sucesso.")
            else:
                st.session_state.status = "Concluído"
                st.info("Execução finalizada, mas nenhum dado foi retornado.")
        except Exception as e:
            st.session_state.error = str(e)
            st.session_state.status = "Erro"
            st.error(f"Erro durante a execução: {e}")

# Exibir DataFrame e botão de download
if not st.session_state.df.empty:
    st.subheader("Pré-visualização dos pedidos")
    st.dataframe(st.session_state.df)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        st.session_state.df.to_excel(writer, index=False, sheet_name="Pedidos")
    buffer.seek(0)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Pedidos_A_Preparar_{timestamp}.xlsx"

    st.download_button(
        label="Baixar como Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
