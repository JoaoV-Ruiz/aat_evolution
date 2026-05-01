import logging
import pandas as pd
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import Config

# Tabela de de/para dos colaboradores da Osirnet
TABELA_NOMES = {
    "396": "DIOGO TABORDA", "728": "VINICIUS COPPA", "734": "NATHALI VALLIER", "1163": "JULIA DUARTE",
    "1177": "KAUÃ GOCKS", "1318": "FILIPE VAZ", "1267": "ALISSON GUERREIRO",
    "931": "JOÃO VITOR RUIZ", "960": "RICHER ARAUJO", "667": "CRISTIANO MARQUES", 
    "441": "CAIO ALVES DOS REIS", "968": "SINDEW CRIZEL", "322" : "IGOR SALDANHA"
}

def executar_scraping():
    """
    Realiza o webscraping dos chamados amarelos e retorna:
    1. Lista de dicionários com dados individuais dos técnicos.
    2. Dicionário com os dados gerais do sistema.
    """
    logging.info("Iniciando coleta via Selenium: Chamados Amarelos")
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get(Config.URL_COLETA)
        wait = WebDriverWait(driver, 30)
        
        # Login no sistema
        wait.until(EC.presence_of_element_located((By.ID, "login"))).send_keys(Config.EMAIL_CORP)
        time.sleep(0.5) 
        driver.find_element(By.ID, "password").send_keys(Config.SENHA_SISTEMA)
        driver.find_element(By.NAME, "entrar").click()
        
        # Aguarda a página carregar a lista principal
        time.sleep(5)
        WebDriverWait(driver, 30).until(lambda d: d.find_element(By.CLASS_NAME, "lista-sucesso"))
        
        # Busca todas as linhas que possuem o atributo data-checado (seja '0' ou ID)
        elementos_checar = driver.find_elements(By.XPATH, "//*[@data-checado]")
        total_sucesso = len(elementos_checar)
        
        contagem = {nome: 0 for nome in TABELA_NOMES.values()}
        total_checados = 0
        total_nao_checados = 0
        
        # Nova lógica de contagem baseada no valor "0"
        for el in elementos_checar:
            val = el.get_attribute("data-checado")
            
            if val == "0":
                total_nao_checados += 1
            elif val in TABELA_NOMES:
                contagem[TABELA_NOMES[val]] += 1
                total_checados += 1
        
        # A MUDANÇA ESTÁ AQUI: Removemos o filtro que ignorava os zeros
        df = pd.DataFrame(list(contagem.items()), columns=["Colaborador", "Qtd"])
        df_final = df.sort_values(by="Qtd", ascending=False)
        
        driver.quit() 

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Formata os dados INDIVIDUAIS
        dados_individuais = []
        if not df_final.empty:
            for _, row in df_final.iterrows():
                dados_individuais.append({
                    "colaborador": row["Colaborador"],
                    "checados_colaborador": int(row["Qtd"]),
                    "ultima_atualizacao": agora
                })

        # 2. Formata os dados GERAIS (Sempre com id = 1)
        dados_gerais = {
            "id": 1, 
            "total_sucesso": int(total_sucesso),
            "total_checados": int(total_checados),
            "total_nao_checados": int(total_nao_checados),
            "ultima_atualizacao": agora
        }

        logging.info(f"Coleta Amarelos concluída. Atualizando {len(dados_individuais)} técnicos no banco.")
        
        return dados_individuais, dados_gerais

    except Exception as e:
        logging.error(f"Erro na coleta Selenium (Amarelos): {str(e)}")
        try:
            driver.save_screenshot("erro_amarelos.png") 
        except:
            pass
        if driver:
            driver.quit()
        return None, None