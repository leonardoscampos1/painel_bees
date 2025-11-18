#COLETAR OS DADOS
from selenium import webdriver
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import re
import logging

url = "https://one.bees.com/order-management/active-orders"

def login(driver, wait, email, senha):  
    """Realiza o login no site do Bees."""
    logging.info("Tentando realizar o login...")
    driver.get(url)
    campo_email = wait.until(EC.element_to_be_clickable(('id', 'signInName')))
    campo_email.send_keys(email)
    botao_continue = wait.until(EC.element_to_be_clickable(('id', 'next')))
    botao_continue.click()
    campo_senha = wait.until(EC.element_to_be_clickable(('id', 'password')))
    campo_senha.send_keys(senha)
    botao_continue = wait.until(EC.element_to_be_clickable(('id', 'next')))
    botao_continue.click()
    try:
        botao_entendi = wait.until(EC.element_to_be_clickable(('xpath', '//button[text()="Entendi"]')))
        botao_entendi.click()
    except Exception:
        time.sleep(5)
    logging.info("Login realizado com sucesso.")

def coletar_dados_pedidos(driver, wait):
    order_data = []
    try:
        tbody = wait.until(
            EC.presence_of_element_located((By.XPATH, '//tbody[@role="rowgroup"]'))
        )
        for tr in tbody.find_elements(By.XPATH, './/tr'):
            try:
                order = tr.find_elements(By.XPATH, './/td[1]')[0].text.strip()
                data_pedido = tr.find_elements(By.XPATH, './/td[2]')[0].text.strip()
                data_entrega = tr.find_elements(By.XPATH, './/td[3]')[0].text.strip()
                responsavel = tr.find_elements(By.XPATH, './/td[4]')[0].text.strip()
                total_pedido = tr.find_elements(By.XPATH, './/td[5]')[0].text.strip()
                order_data.append({
                    'Numero Pedido': order,
                    'Data Pedido': data_pedido,
                    'Data Entrega': data_entrega,
                    'Responsavel': responsavel,
                    'Total Pedido': total_pedido
                })
            except IndexError:
                continue
    except Exception as e:
        pass
    return pd.DataFrame(order_data)

def navegar_paginas(driver, wait):
    """Navega por todas as páginas de pedidos e coleta os dados."""
    logging.info("Navegando pelas páginas de pedidos...")
    page_number = 1
    df_total = pd.DataFrame()

    while True:
        try:
            df = coletar_dados_pedidos(driver, wait)
            df_total = pd.concat([df_total, df], ignore_index=True)
            page_xpath = f'//li[@title="page {page_number}"]'
            try:
                next_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, page_xpath))
                )
                next_button.click()
                logging.info(f"Clicando no elemento da página {page_number} para avançar.")

                wait.until(
                    EC.presence_of_element_located((By.XPATH, '//tbody[@role="rowgroup"]'))
                )
                page_number += 1
                time.sleep(2)   

            except Exception as e:
                logging.info(f"Não há mais páginas ou o botão de navegação.")
                break

        except Exception as e:
            logging.error(f"Ocorreu um erro ao coletar dados ou na navegação geral: {e}")
            break

    return df_total

def coletar_detalhes(driver, wait, df_pedidos_ativos, pedidos_existentes, filial, max_retries=3):

    detalhes = []
    pedidos_processados = set()

    all_phone_cols = [f"Telefone {i}" for i in range(1, 3)]
    all_email_cols = [f"Email {i}" for i in range(1, 3)]
    
    for order in df_pedidos_ativos['Numero Pedido']:
        logging.info(f"Iniciando coleta de detalhes para o pedido: {order}")
        if order in pedidos_processados:
            logging.info(f"Pedido {order} já foi processado nesta sessão. Ignorando.")
            continue
        if order in pedidos_existentes:
            logging.info(f"Pedido {order} já existe no CSV. Ignorando coleta de detalhes para evitar duplicação.")
            continue

        retries = 0
        while retries < max_retries:
            try:
                logging.info(f"Acessando página do pedido: {order}")
                driver.get(f'https://one.bees.com/order-management/active-orders/{order}')
                
                wait.until(
                    EC.presence_of_element_located((By.XPATH, '//h2[contains(text(), "Pedido #")]'))
                )
                time.sleep(3)

                try:
                    vermais_button = driver.find_elements(By.XPATH,
                                                            '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[8]/div[3]/div[1]/div[4]/a')
                    if vermais_button:
                        vermais_button[0].click()
                        time.sleep(1)
                except Exception as e:
                    logging.warning(f"Erro ao clicar 'Ver Mais' para o pedido {order}: {e}")
                    pass

                data_entrega = df_pedidos_ativos[df_pedidos_ativos['Numero Pedido'] == order]['Data Entrega'].values[0]
                responsavel = df_pedidos_ativos[df_pedidos_ativos['Numero Pedido'] == order]['Responsavel'].values[0]
                total_pedido = df_pedidos_ativos[df_pedidos_ativos['Numero Pedido'] == order]['Total Pedido'].values[0]

                wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH,
                         '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[9]/div[3]/div/div/table/tbody'))
                )
                tbody_produtos = driver.find_element(By.XPATH,
                                                        '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[9]/div[3]/div/div/table/tbody')
                produtos = tbody_produtos.find_elements(By.XPATH, './/tr[@role="row"]')

                _numero_pedido = driver.find_element(By.XPATH,
                                                        '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[2]/div[1]/h2').text.strip().replace(
                    'Pedido #', '')
                cd = driver.find_element(By.XPATH,
                                            '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[4]/div[2]/p[2]').text.strip()
                status = driver.find_element(By.XPATH,
                                                '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[4]/div[1]/p[2]').text.strip()
                _data_pedido = driver.find_element(By.XPATH,
                                                    '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[8]/div[3]/div[2]/div[1]/p[2]').text.strip()
                forma_pgto = driver.find_element(By.XPATH,
                                                    '//*[@id="single-spa-application:@supplier-portal/order-management-beta-mfe"]/div/div[8]/div[3]/div[2]/div[2]/p[2]').text.strip()

                pedido_detalhe = {"Numero Pedido": _numero_pedido,
                                    "Centro de Distribuição": cd,
                                    "Status": status,
                                    "Data Pedido": _data_pedido,
                                    "Forma de Pagamento": forma_pgto,
                                    "Data Entrega": data_entrega,
                                    "Responsavel": responsavel,
                                    "Total Pedido": total_pedido}
                
                for col in all_phone_cols + all_email_cols:
                    pedido_detalhe[col] = None

                try:
                    phone_section = driver.find_element(By.XPATH,
                        '//div[@class="c-jJgXmn"]/p[contains(@class, "c-jzrCjA-iqCzBn-weight-semibold") and contains(text(), "telefone")]/ancestor::div[@class="c-jJgXmn"]')
                    
                    phone_numbers = [p.text.strip() for p in phone_section.find_elements(By.XPATH, './/p[not(contains(@class, "c-jzrCjA-iqCzBn-weight-semibold"))]')]
                    
                    for i, phone in enumerate(phone_numbers):
                        if i < len(all_phone_cols): 
                            pedido_detalhe[f"Telefone {i + 1}"] = str(phone)
                except Exception as e:
                    logging.warning(f"Não foi possível encontrar ou extrair números de telefone para o pedido {order}.")
                    pass

                if not any(pedido_detalhe[col] for col in all_phone_cols):
                    logging.info(f"Nenhum telefone encontrado para o pedido {order}.")
                    for col in all_phone_cols:
                        pedido_detalhe[col] = None
                else:
                    logging.info(f"Telefones encontrados para o pedido {order}: {[pedido_detalhe[col] for col in all_phone_cols if pedido_detalhe[col]]}")
                emails_addr = []
                try:
                    email_sections = driver.find_elements(By.XPATH,
                        '//div[@class="c-jJgXmn"]/p[contains(@class, "c-jzrCjA-iqCzBn-weight-semibold") and contains(text(), "E-mail")]/ancestor::div[@class="c-jJgXmn"]')
                    if email_sections:
                        
                        emails_addr = [p.text.strip() for p in email_sections[0].find_elements(By.XPATH, './/p[not(contains(@class, "c-jzrCjA-iqCzBn-weight-semibold"))]')]
                        for i, email_val in enumerate(emails_addr):
                            if i < len(all_email_cols):
                                pedido_detalhe[f"Email {i + 1}"] = str(email_val)
                    else:
                        logging.info(f"Seção de e-mail não encontrada para o pedido {order}.")
                except Exception as e:
                    logging.warning(f"Erro inesperado ao processar e-mails para o pedido {order}")

                try:
                    tax_id_section = driver.find_element(By.XPATH,
                        '//div[@class="c-jJgXmn"]/p[contains(@class, "c-jzrCjA-iqCzBn-weight-semibold") and text()="Tax ID"]/ancestor::div[@class="c-jJgXmn"]')
                    
                    valor_element = tax_id_section.find_elements(By.XPATH, './/p[not(contains(@class, "c-jzrCjA-iqCzBn-weight-semibold"))]')
                    if valor_element:
                        pedido_detalhe["Documento"] = str(valor_element[0].text.strip()) if len(valor_element) > 0 else None
                        if len(valor_element) > 1:
                            ie_text = valor_element[1].text.strip()
                            if "INSCRICAO_ESTADUAL:" in ie_text:
                                pedido_detalhe["IE"] = str(ie_text.replace("INSCRICAO_ESTADUAL: ", "").strip())
                            else:
                                pedido_detalhe["IE"] = str(ie_text)
                except Exception as e:
                    logging.warning(f"Não foi possível encontrar ou extrair Tax ID para o pedido {order}")
                    pass
                
                try:
                    nome_comercial_section = driver.find_element(By.XPATH,
                        '//div[@class="c-jJgXmn"]/p[contains(@class, "c-jzrCjA-iqCzBn-weight-semibold") and text()="Nome comercial"]/ancestor::div[@class="c-jJgXmn"]')
                    valor_element = nome_comercial_section.find_elements(By.XPATH, './/p[not(contains(@class, "c-jzrCjA-iqCzBn-weight-semibold"))]')
                    pedido_detalhe["Nome Comercial"] = str(valor_element[0].text.strip()) if valor_element else None
                except Exception as e:
                    logging.warning(f"Não foi possível encontrar ou extrair Nome Comercial para o pedido {order}")
                    pass
                
                
                try:
                    endereco_entrega_section = driver.find_element(By.XPATH,
                        '//div[@class="c-jJgXmn"]/p[contains(@class, "c-jzrCjA-iqCzBn-weight-semibold") and text()="Endereço de entrega"]/ancestor::div[@class="c-jJgXmn"]')
                    endereco_parts = [p.text.strip() for p in endereco_entrega_section.find_elements(By.XPATH, './/p[not(contains(@class, "c-jzrCjA-iqCzBn-weight-semibold"))]')]
                    pedido_detalhe["Endereço de Entrega"] = str(endereco_parts[0]) if len(endereco_parts) > 0 else None
                    pedido_detalhe["Cidade/UF"] = str(endereco_parts[1]) if len(endereco_parts) > 1 else None
                    pedido_detalhe["CEP"] = str(endereco_parts[2]) if len(endereco_parts) > 2 else None
                    pedido_detalhe["Coordenadas"] = str(endereco_parts[3]) if len(endereco_parts) > 3 else None
                except Exception as e:
                    logging.warning(f"Não foi possível encontrar ou extrair Endereço de entrega para o pedido {order}")
                    pass

                try:
                    id_negocio_section = driver.find_element(By.XPATH,
                        '//div[@class="c-jJgXmn"]/p[contains(@class, "c-jzrCjA-iqCzBn-weight-semibold") and text()="ID do negócio"]/ancestor::div[@class="c-jJgXmn"]')
                    valor_element = id_negocio_section.find_elements(By.XPATH, './/p[not(contains(@class, "c-jzrCjA-iqCzBn-weight-semibold"))]')
                    pedido_detalhe["ID do negócio"] = str(valor_element[0].text.strip()) if valor_element else None
                except Exception as e:
                    logging.warning(f"Não foi possível encontrar ou extrair ID do negócio para o pedido {order}")
                    pass

                try:
                    id_cliente_section = driver.find_element(By.XPATH,
                        '//div[@class="c-jJgXmn"]/p[contains(@class, "c-jzrCjA-iqCzBn-weight-semibold") and text()="ID da conta do cliente"]/ancestor::div[@class="c-jJgXmn"]')
                    valor_element = id_cliente_section.find_elements(By.XPATH, './/p[not(contains(@class, "c-jzrCjA-iqCzBn-weight-semibold"))]')
                    pedido_detalhe["ID da conta do cliente"] = str(valor_element[0].text.strip()) if valor_element else None
                except Exception as e:
                    logging.warning(f"Não foi possível encontrar ou extrair ID da conta do cliente para o pedido {order}")
                    pass

                for produto in produtos:
                    try:
                        nome_sku = produto.find_element(By.XPATH, './/td[1]//div/div[2]/p[1]').text.strip()
                        sku = produto.find_element(By.XPATH, './/td[1]//div/div[2]/p[2]').text.strip()
                        preco = produto.find_element(By.XPATH, './/td[1]//div/div[2]/div/p').text.strip()
                        quantidade_pedida = produto.find_element(By.XPATH, './/td[2]').text.strip()
                        quantidade_preparar = produto.find_element(By.XPATH, './/td[3]').text.strip()

                        detalhes.append({**pedido_detalhe,
                                            "SKU": sku,
                                            "Preço": preco,
                                            "Quantidade Pedida": quantidade_pedida,
                                            "Nome do Produto": nome_sku,
                                            "Quantidade Preparar": quantidade_preparar})

                    except Exception as e:
                        logging.warning(f"Erro ao obter dados do produto para o pedido {order}")
                        continue

                pedidos_processados.add(order)
                logging.info(f"Detalhes coletados com sucesso para o pedido: {order}")
                break

            except Exception as e:
                logging.error(f"Erro ao coletar detalhes para o pedido {order}. Tentativa {retries + 1} de {max_retries}.")
                retries += 1
                time.sleep(5)
        else:
            logging.error(f"Falha ao coletar detalhes para o pedido {order} após {max_retries} tentativas.")

    df_detalhes = pd.DataFrame(detalhes)
    return df_detalhes

def baixar_pedidos():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    emails = ['leonardo.campos@rigarr.com.br','cadastro@rigarr.com.br']
    senhas = ['Br@sil32aaaaaaa','Rigarrdistribuidora@2024']
    filiais = ['Rigarr','Castas'] 
    max_retries_main = 3
    
    expected_cols = [
        'Numero Pedido', 'Data Pedido', 'Centro de Distribuição', 'Status',
        'Forma de Pagamento', 'Data Entrega', 'Responsavel', 'Total Pedido',
        'Documento', 'IE', 'Nome Comercial', 'Endereço de Entrega',
        'Cidade/UF', 'CEP', 'Coordenadas', 'ID do negócio', 'ID da conta do cliente',
        'SKU', 'Preço', 'Quantidade Pedida', 'Nome do Produto', 'Quantidade Preparar'
    ]
    for i in range(1, 3):  
        expected_cols.append(f'Telefone {i}')
    for i in range(1, 3):  
        expected_cols.append(f'Email {i}')

    for email, senha, filial in zip(emails, senhas, filiais):
        retries = 0
        while retries < max_retries_main:
            driver = None
            try:
                arquivo_csv = f'Pedidos_A_Preparar_{filial}.csv'
                logging.info(f'Iniciando processamento para a filial {filial}...')

                chrome_options = Options()
                #chrome_options.add_argument("--headless")
                chrome_options.add_argument("--window-size=1920,1080")
                driver = webdriver.Chrome(options=chrome_options)
                driver.maximize_window()
                wait = WebDriverWait(driver, 60)

                logging.info(f"Tentando login com {email} para a filial {filial}.")
                login(driver, wait, email, senha)
                logging.info(f"Login bem-sucedido para {email}.")
                logging.info(f"Coletando pedidos ativos do site para a filial {filial}.")
                df_pedidos_ativos_site = navegar_paginas(driver, wait)
                logging.info(f"Total de {len(df_pedidos_ativos_site)} pedidos ativos encontrados no site para a filial {filial}.")

                if df_pedidos_ativos_site.empty:
                    logging.info(f"Nenhum pedido ativo encontrado para a filial {filial} no site.")
                    if os.path.exists(arquivo_csv):
                        os.remove(arquivo_csv)
                        logging.info(f"Arquivo '{arquivo_csv}' excluído, pois nenhum pedido ativo foi encontrado.")
                    else:
                        logging.info(f"Arquivo '{arquivo_csv}' não existe, nenhuma ação necessária.")
                    break # Sai do loop de retries e vai para a próxima filial
                
                df_pedidos_ativos_site_duplicados = df_pedidos_ativos_site[
                    df_pedidos_ativos_site.duplicated(subset=['Numero Pedido'], keep=False)]
                if not df_pedidos_ativos_site_duplicados.empty:
                    logging.warning("Atenção: Foram encontradas linhas duplicadas de pedidos ativos:")
                    logging.warning(df_pedidos_ativos_site_duplicados)

                if not df_pedidos_ativos_site.empty:
                    pedidos_ativos_site = set(df_pedidos_ativos_site['Numero Pedido'].astype(str))
                    df_detalhes_novos = pd.DataFrame()
                    pedidos_existente = set()

                    if os.path.exists(arquivo_csv):
                        try:
                            logging.info(f"Arquivo '{arquivo_csv}' encontrado. Lendo pedidos existentes.")
                        
                            df_pedidos_existente = pd.read_csv(arquivo_csv, encoding='utf-8-sig',
                                                                dtype={'CEP': str, 'Documento': str, 'IE': str,
                                                                        'Telefone 1': str, 'Telefone 2': str,
                                                                        'Email 1': str, 'Email 2': str})
                            pedidos_existente = set(df_pedidos_existente['Numero Pedido'].astype(str))
                            logging.info(f"Total de {len(pedidos_existente)} pedidos existentes no CSV para a filial {filial}.")

                            novos_pedidos = list(pedidos_ativos_site - pedidos_existente)
                            df_novos_pedidos = df_pedidos_ativos_site[
                                df_pedidos_ativos_site['Numero Pedido'].isin(novos_pedidos)].copy()
                            
                            if not df_novos_pedidos.empty:
                                logging.info(f"Encontrados {len(df_novos_pedidos)} novos pedidos para coletar detalhes.")
                                df_detalhes_novos = coletar_detalhes(driver, wait, df_novos_pedidos, pedidos_existente, filial)
                                logging.info(f"Tamanho do df_detalhes_novos após coletar detalhes: {len(df_detalhes_novos)}")

                            if not df_detalhes_novos.empty:
                                
                                for col in expected_cols:
                                    if col not in df_detalhes_novos.columns:
                                        df_detalhes_novos[col] = None

                                df_detalhes_novos = df_detalhes_novos[expected_cols]

                                df_pedidos_existente = pd.concat([df_pedidos_existente, df_detalhes_novos],
                                                                    ignore_index=True).drop_duplicates(
                                        subset=['Numero Pedido', 'SKU'], keep='first')
                                
                                cols_to_clean = ['CEP', 'Documento', 'IE'] + \
                                                    [f'Telefone {i}' for i in range(1, 3)] + \
                                                    [f'Email {i}' for i in range(1, 3)]
                                for col in cols_to_clean:
                                    if col in df_pedidos_existente.columns:
                                        df_pedidos_existente[col] = df_pedidos_existente[col].astype(str).replace(r'\.0$', '', regex=True)

                                df_pedidos_atualizado = df_pedidos_existente[
                                    df_pedidos_existente['Numero Pedido'].astype(str).isin(list(pedidos_ativos_site))].copy()
                                
                                for col in cols_to_clean:
                                    if col in df_pedidos_atualizado.columns:
                                        df_pedidos_atualizado[col] = df_pedidos_atualizado[col].astype(str).replace(r'\.0$', '', regex=True)
                                
                                
                                for col in expected_cols:
                                    if col not in df_pedidos_atualizado.columns:
                                        df_pedidos_atualizado[col] = None
                                df_pedidos_atualizado = df_pedidos_atualizado[expected_cols]

                                df_pedidos_atualizado.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
                                logging.info(f'Arquivo "{arquivo_csv}" atualizado para a filial {filial}.')

                            else: 
                                df_pedidos_atualizado = df_pedidos_existente[
                                    df_pedidos_existente['Numero Pedido'].astype(str).isin(list(pedidos_ativos_site))].copy()

                                cols_to_clean = ['CEP', 'Documento', 'IE'] + \
                                                    [f'Telefone {i}' for i in range(1, 3)] + \
                                                    [f'Email {i}' for i in range(1, 3)]
                                for col in cols_to_clean:
                                    if col in df_pedidos_atualizado.columns:
                                        df_pedidos_atualizado[col] = df_pedidos_atualizado[col].astype(str).replace(r'\.0$', '', regex=True)
                                
                                for col in expected_cols:
                                    if col not in df_pedidos_atualizado.columns:
                                        df_pedidos_atualizado[col] = None
                                df_pedidos_atualizado = df_pedidos_atualizado[expected_cols]
                                
                                df_pedidos_atualizado.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
                                logging.info(f'Arquivo "{arquivo_csv}" atualizado (sem novos detalhes, mas com limpeza de inativos) para a filial {filial}.')


                        except pd.errors.EmptyDataError:
                            logging.info(f"Arquivo '{arquivo_csv}' está vazio. Criando um novo arquivo.")
                            df_detalhes_novos = coletar_detalhes(driver, wait, df_pedidos_ativos_site, set(), filial)
                            logging.info(f"Tamanho do df_detalhes_novos após coletar detalhes (arquivo vazio): {len(df_detalhes_novos)}")
                            if not df_detalhes_novos.empty:
                        
                                for col in expected_cols:
                                    if col not in df_detalhes_novos.columns:
                                        df_detalhes_novos[col] = None
                                df_detalhes_novos = df_detalhes_novos[expected_cols]

                                cols_to_clean = ['CEP', 'Documento', 'IE'] + \
                                                    [f'Telefone {i}' for i in range(1, 3)] + \
                                                    [f'Email {i}' for i in range(1, 3)]
                                for col in cols_to_clean:
                                    if col in df_detalhes_novos.columns:
                                        df_detalhes_novos[col] = df_detalhes_novos[col].astype(str).replace(r'\.0$', '', regex=True)
                                df_detalhes_novos.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
                                logging.info(f'Dados salvos em "{arquivo_csv}" para a filial {filial}.')
                            else:
                                logging.info(f"Não foram encontrados pedidos ativos para salvar no arquivo '{arquivo_csv}' da filial {filial}. ")

                        except Exception as e:
                            logging.error(f"Erro ao ler ou processar o arquivo '{arquivo_csv}': {e}")

                    else:
                        logging.info(f"Arquivo '{arquivo_csv}' não encontrado. Criando um novo arquivo.")
                        df_detalhes_novos = coletar_detalhes(driver, wait, df_pedidos_ativos_site, set(), filial)
                        logging.info(f"Tamanho do df_detalhes_novos após coletar detalhes (arquivo novo): {len(df_detalhes_novos)}")

                        if not df_detalhes_novos.empty:
                        
                            for col in expected_cols:
                                if col not in df_detalhes_novos.columns:
                                    df_detalhes_novos[col] = None
                            
                            df_detalhes_novos = df_detalhes_novos[expected_cols]

                            cols_to_clean = ['CEP', 'Documento', 'IE'] + \
                                                [f'Telefone {i}' for i in range(1, 3)] + \
                                                [f'Email {i}' for i in range(1, 3)]
                            for col in cols_to_clean:
                                if col in df_detalhes_novos.columns:
                                    df_detalhes_novos[col] = df_detalhes_novos[col].astype(str).replace(r'\.0$', '', regex=True)
                            df_detalhes_novos.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
                            logging.info(f'Dados salvos em "{arquivo_csv}" para a filial {filial}.')
                        else:
                            logging.info(f"Não foram encontrados pedidos ativos para salvar no arquivo '{arquivo_csv}' da filial {filial}. ")
                
             
                break 

            except Exception as e:
                logging.error(f"Ocorreu um erro geral para a filial {filial}: {e}")
                retries += 1
                logging.info(f"Tentando novamente... Tentativa {retries} de {max_retries_main}.")
                if driver:
                    driver.quit() 
                time.sleep(10) 
            finally:
                if retries >= max_retries_main:
                    logging.error(f"O script falhou após {max_retries_main} tentativas para a filial {filial}. Prosseguindo para a próxima filial, se houver.")
                if driver and retries < max_retries_main:
                    driver.quit()