import os
import re
import time
import glob
import shutil
import calendar
import logging
import unicodedata
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from config import Config

# Dicionário de limpeza de nomes dos técnicos
TERMOS_BUSCA = {
    "ALISSONDOCOUTOGUERREIRO": "ALISSON DO COUTO GUERREIRO", "IGORSALDANHA": "IGOR SALDANHA",
    "JOAOVITORRUIZBARBOZA": "JOÃO VITOR RUIZ BARBOZA", "VINICIUSCOPPA": "VINICIUS COPPA",
    "JULIADASILVADUARTE": "JULIA DA SILVA DUARTE", "KAULARRIGOCKSDASILVEIRA": "KAUÃ LARRI GOCKS DA SILVEIRA",
    "KAUALARRIGOCKSDASILVEIRA": "KAUÃ LARRI GOCKS DA SILVEIRA", "CAIOREIS": "CAIO REIS",
    "DIOGOTABORDADEBITENCOURT": "DIOGO BITENCOURT",
    "NATHALIVALLIER": "NATHALI VALLIER", "RICHERFALCAOARAUJO": "RICHER FALCÃO ARAUJO",
    "SINDEWCRIZELNUNES": "SINDEW CRIZEL NUNES", "CRISTIANOMARQUES": "CRISTIANO MARQUES",
    "FILIPEVIEIRAVAZ": "FILIPE VIEIRA VAZ"
}

def super_limpeza(texto):
    if not isinstance(texto, str): return ""
    texto = texto.split(" / ")[0].upper()
    texto = unicodedata.normalize('NFKD', texto)
    texto = "".join([c for c in texto if not unicodedata.combining(c)])
    return re.sub(r'[^A-Z]', '', texto)

def identificar_pela_chave(nome_bruto_csv):
    if pd.isna(nome_bruto_csv) or "Sem Atendente" in str(nome_bruto_csv): return None
    nome_limpo_csv = super_limpeza(str(nome_bruto_csv))
    for chave_limpa, nome_bonito in TERMOS_BUSCA.items():
        if chave_limpa in nome_limpo_csv: return nome_bonito
    return None

def processar_csv(caminho_csv):
    """Lê o CSV gigante, limpa e retorna dados agrupados para o Supabase"""
    if not caminho_csv or not os.path.exists(caminho_csv):
        logging.warning("Nenhum CSV encontrado para processar.")
        return None
        
    try:
        logging.info(f"Processando CSV de encerramentos ({caminho_csv}) via Pandas...")
        df = pd.read_csv(caminho_csv, sep=None, engine='python', encoding='latin-1', on_bad_lines='skip')
        col_encontrada = [c for c in df.columns if "Encerramento" in c]
        if not col_encontrada: 
            return None
        
        df['DATA_REF'] = pd.to_datetime(df[col_encontrada[0]], dayfirst=True, errors='coerce')
        df['MES_ANO'] = df['DATA_REF'].dt.strftime('%m/%Y')
        
        possiveis_cols = ["Atendente", "Usuário Encerramento", "Responsável", "Nome"]
        coluna_tecnico = next((c for c in possiveis_cols if c in df.columns), df.columns[3])
        
        df['Atendente'] = df[coluna_tecnico].apply(identificar_pela_chave)
        df_limpo = df.dropna(subset=['Atendente', 'DATA_REF']).copy()
        
        # Agrupa os dados: Conta quantos protocolos cada Atendente fez por Mês/Ano
        df_agrupado = df_limpo.groupby(['Atendente', 'MES_ANO']).size().reset_index(name='total_encerrados')
        
        # Converte para lista de dicionários pro Supabase
        dados_formatados = []
        for _, row in df_agrupado.iterrows():
            dados_formatados.append({
                "id_unico": f"{row['Atendente']}_{row['MES_ANO']}", # Chave que impede duplicidade no banco
                "colaborador": row["Atendente"],
                "mes_ano": row["MES_ANO"],
                "total_encerrados": int(row["total_encerrados"]),
                "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
        # Apaga o CSV original para não lotar o HD do servidor com o tempo
        os.remove(caminho_csv)
        logging.info("CSV processado e deletado com sucesso.")
        
        return dados_formatados
    except Exception as e:
        logging.error(f"Erro ao analisar o CSV de Encerramentos: {e}")
        return None

def mover_arquivo_recente():
    """Busca o arquivo mais recente baixado e move para a pasta temporária do projeto"""
    time.sleep(5) # Garante que o download finalizou
    arquivos = glob.glob(os.path.join(Config.DOWNLOAD_DIR, "*.csv"))
    if not arquivos: 
        return None
    
    arquivo_recente = max(arquivos, key=os.path.getmtime)
    nome_arq = f"relatorio_encerras_{int(time.time())}.csv"
    caminho_final = os.path.join(Config.DATA_TEMP, nome_arq)
    
    shutil.move(arquivo_recente, caminho_final)
    return caminho_final

def executar_scraping():
    """Função principal chamada pela main.py"""
    logging.info("Iniciando coleta via Selenium: Encerramentos (Download CSV)")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    prefs = {
        "download.default_directory": Config.DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": Config.DOWNLOAD_DIR})
        wait = WebDriverWait(driver, 40)
        
        def forcar_input_react(elemento, valor):
            script = """
            var element = arguments[0]; var value = arguments[1]; var lastValue = element.value;
            element.value = value; var event = new Event('input', { bubbles: true });
            var tracker = element._valueTracker; if (tracker) { tracker.setValue(lastValue); }
            element.dispatchEvent(event); element.dispatchEvent(new Event('change', { bubbles: true }));
            """
            driver.execute_script(script, elemento, valor)

        # 1. Login no ERP
        driver.get(Config.URL_ERP)
        time.sleep(5)
        try:
            c_user = wait.until(EC.element_to_be_clickable((By.ID, ":r0:")))
            c_pass = driver.find_element(By.ID, ":r1:")
            forcar_input_react(c_user, Config.ERP_USER)
            forcar_input_react(c_pass, Config.ERP_PASS) 
            driver.find_element(By.XPATH, "//button[@data-testid='button' and contains(., 'Entrar')]").click()
            time.sleep(10)
        except: 
            pass

        # 2. Transição para Tela Antiga
        try:
            btn_ant = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Tela antiga']")))
            driver.execute_script("arguments[0].click();", btn_ant)
            time.sleep(6)
        except: 
            pass
        
        # 3. Aplicação de Filtros
        try:
            driver.get(Config.URL_ERP)
            time.sleep(5)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@tooltip='Filtro avançado']"))).click()
            time.sleep(3)

            driver.find_element(By.ID, "teamId").click()
            time.sleep(1)
            f_all = wait.until(EC.element_to_be_clickable((By.ID, "filterAll")))
            f_all.send_keys("COP Encerramentos")
            f_all.send_keys(Keys.ENTER)
            time.sleep(3)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='datagrid_row' and contains(text(), 'COP Encerramentos')]"))).click()
            time.sleep(1)
            driver.find_element(By.XPATH, "//button[contains(., 'Confirmar')]").click()

            # Limpeza de datas antigas nos inputs
            driver.execute_script("""
                ['beginInitialDate', 'endInitialDate'].forEach(id => {
                    var el = document.getElementById(id);
                    if(el) { el.focus(); el.value = ''; el.dispatchEvent(new Event('input', {bubbles:true})); el.blur(); }
                });
            """)

            # Seta a data final para o último dia do mês atual
            hj = datetime.now()
            fim = hj.replace(day=calendar.monthrange(hj.year, hj.month)[1]).strftime("%d/%m/%Y")
            forcar_input_react(driver.find_element(By.ID, "finalReportClosingDate"), fim)
            time.sleep(2)
            driver.find_element(By.XPATH, "//button[contains(., 'aplicar')]").click()
            time.sleep(12)
        except: 
            pass

        # 4. Exportação do CSV
        btn_exp = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@tooltip='Imprimir/Exportar']")))
        driver.execute_script("arguments[0].click();", btn_exp)
        time.sleep(2)
        
        btn_csv = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., '.CSV')]")))
        driver.execute_script("arguments[0].click();", btn_csv)
        
        logging.info("Aguardando o download do CSV...")
        time.sleep(25) 
        
        # 5. Processamento dos Dados
        caminho_csv = mover_arquivo_recente()
        dados = processar_csv(caminho_csv)
        
        return dados

    except Exception as e:
        logging.error(f"Ocorreu um erro crítico no módulo de Encerramentos: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()