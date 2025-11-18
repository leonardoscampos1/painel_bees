import streamlit as st
import pandas as pd
from io import BytesIO
import datetime
import openpyxl
from pages.baixar_pedidos import baixar_pedidos

st.set_page_config(page_title="Painel BEES 🐝", layout="wide", page_icon="💵")

st.title("Painel BEES🐝")
st.write("Bem-vindo ao painel principal")
st.markdown("Por Leonardo Campos")

# arquivo local inicial
arquivo = "Pedidos_A_Preparar_Rigarr.csv"

# inicializa df em session_state para persistir entre reruns
if "df" not in st.session_state:
    try:
        st.session_state.df = pd.read_csv(arquivo)
    except FileNotFoundError:
        st.session_state.df = pd.DataFrame()

# Botão que chama a função corretamente
if st.button("Baixar pedidos"):
    with st.spinner("Executando baixar_pedidos..."):
        try:
            resultado = baixar_pedidos()
        except Exception as e:
            st.error(f"Erro ao executar baixar_pedidos: {e}")
            resultado = None

    df_novo = None

    # Se a função retornou um DataFrame
    if isinstance(resultado, pd.DataFrame):
        df_novo = resultado

    # Se retornou um caminho para arquivo
    elif isinstance(resultado, str):
        try:
            if resultado.lower().endswith(".csv"):
                df_novo = pd.read_csv(resultado)
            else:
                df_novo = pd.read_excel(resultado)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo retornado ({resultado}): {e}")

    # Se retornou bytes (Excel ou CSV em memória)
    elif isinstance(resultado, (bytes, bytearray)):
        buf = BytesIO(resultado)
        try:
            df_novo = pd.read_excel(buf)
        except Exception:
            buf.seek(0)
            try:
                df_novo = pd.read_csv(buf)
            except Exception as e:
                st.error(f"Não foi possível interpretar os bytes retornados: {e}")

    if df_novo is not None and not df_novo.empty:
        st.session_state.df = df_novo
        st.success("Pedidos atualizados com sucesso")
    else:
        st.info("Nenhum dado novo foi carregado")

# Exibe a tabela atual (arquivo local ou resultado da função)
if st.session_state.df is None or st.session_state.df.empty:
    st.info("Nenhum pedido disponível para visualização.")
else:
    st.subheader("Pré-visualização dos pedidos")
    st.dataframe(st.session_state.df)

    # Gerar Excel em memória para download
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        st.session_state.df.to_excel(writer, index=False, sheet_name="Pedidos")
    buffer.seek(0)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Pedidos_A_Preparar_Rigarr_{timestamp}.xlsx"

    st.download_button(
        label="Baixar como Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
