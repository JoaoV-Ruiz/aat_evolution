import os
import glob
import shutil
import logging
import time
import calendar
import unicodedata
import re
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from config import Config

# --- MAPEAMENTO PLANILHA (TME) ---
MAPEAMENTO_TECNICOS = {
    "Alisson Do Couto Guerreiro": "ALISSON DO COUTO GUERREIRO", "Caio Alves dos Reis": "CAIO REIS",
    "Cristiano Weber Marques": "CRISTIANO MARQUES", "Diogo Taborda de Bitencourt": "DIOGO TABORDA DE BITENCOURT",
    "Filipe Vieira Vaz": "FILIPE VIEIRA VAZ", "Igor Saldanha Noguez": "IGOR SALDANHA",
    "João Vitor Ruiz Barboza": "JOÃO VITOR RUIZ BARBOZA", "Julia da Silva Duarte": "JULIA DA SILVA DUARTE",
    "Kauã Larri Gocks da Silveira": "KAUÃ LARRI GOCKS DA SILVEIRA", "Nathali Elisa Xavier Vallier": "NATHALI VALLIER",
    "Richer Falcão Araujo": "RICHER FALCÃO ARAUJO", "Sindew Crizel Nunes": "SINDEW CRIZEL NUNES",
    "Vinicius Maciel Coppa": "VINICIUS COPPA"
}

# --- MAPEAMENTO ERP (ENCERRAMENTOS) ---
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

# ==========================================
# 1. FUNÇÕES DE APOIO GERAIS
# ==========================================
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

def converter_para_segundos(tempo_str):
    if not tempo_str or str(tempo_str).strip() in ["", "FORA", "---"]: return None
    try:
        partes = str(tempo_str).split(':')
        if len(partes) == 3: return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
        elif len(partes) == 2: return int(partes[0]) * 60 + int(partes[1])
        return None
    except: return None

def mover_arquivo_recente():
    """Busca o arquivo mais recente baixado e move para a pasta temporária"""
    time.sleep(5)
    arquivos = glob.glob(os.path.join(Config.DOWNLOAD_DIR, "*.csv"))
    if not arquivos: return None
    
    arquivo_recente = max(arquivos, key=os.path.getmtime)
    nome_arq = f"relatorio_diario_{int(time.time())}.csv"
    caminho_final = os.path.join(Config.DATA_TEMP, nome_arq)
    
    shutil.move(arquivo_recente, caminho_final)
    return caminho_final

# ==========================================
# 2. COLETA DE PLANILHA (TME)
# ==========================================
def carregar_tme_por_mes(mes_numero):
    logging.info(f"Acessando Google Sheets: coletando dados do mês {mes_numero}...")
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(Config.GOOGLE_JSON_CREDENTIALS, scopes=scopes)
        cliente = gspread.authorize(creds)
        planilha = cliente.open_by_url(Config.SPREADSHEET_URL)
        aba = planilha.worksheet("AtendimentoTécnico")
        aba.update_acell('B2', mes_numero)
        time.sleep(4) 
        return aba.get("A8:AJ20")
    except Exception as e:
        logging.error(f"Erro ao acessar Planilha (Mês {mes_numero}): {repr(e)}")
        return None

def processar_dados_planilha(dados_tme_raw, mes, ano):
    registros = []
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _, num_dias = calendar.monthrange(ano, mes)
    hoje = datetime.now()

    mapa_tme = {str(linha[0]).strip(): linha[3:] for linha in dados_tme_raw if len(linha) > 0}

    for tec_planilha, nome_oficial in MAPEAMENTO_TECNICOS.items():
        tec_limpo = tec_planilha.strip()
        tempos_raw = mapa_tme.get(tec_limpo, [])
        while len(tempos_raw) < 31: tempos_raw.append("")

        for dia in range(1, num_dias + 1):
            if ano == hoje.year and mes == hoje.month and dia > hoje.day:
                continue 
                
            tme_dia_str = str(tempos_raw[dia - 1]).strip() if (dia - 1) < len(tempos_raw) else ""
            tme_seg = converter_para_segundos(tme_dia_str)
            data_ref = f"{ano}-{mes:02d}-{dia:02d}"
            
            registros.append({
                "id_unico": f"{nome_oficial}_{data_ref}",
                "colaborador": nome_oficial,
                "data_referencia": data_ref,
                "tme_bruto": tme_dia_str,
                "tme_segundos": int(tme_seg) if tme_seg is not None else 0,
                "ultima_atualizacao": agora_str
            })

    return registros

# ==========================================
# 3. COLETA ERP (SELENIUM) E PROCESSAMENTO DIÁRIO
# ==========================================
def coletar_e_processar_erp_diario(data_inicio, data_fim):
    logging.info(f"Iniciando Selenium ERP: Coletando de {data_inicio} até {data_fim}")
    
    # Limpa pasta de downloads
    for f in glob.glob(os.path.join(Config.DOWNLOAD_DIR, "*.csv")):
        try: os.remove(f)
        except: pass

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": Config.DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    })

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

        # Login
        driver.get(Config.URL_ERP)
        time.sleep(5)
        try:
            forcar_input_react(wait.until(EC.element_to_be_clickable((By.ID, ":r0:"))), Config.ERP_USER)
            forcar_input_react(driver.find_element(By.ID, ":r1:"), Config.ERP_PASS) 
            driver.find_element(By.XPATH, "//button[@data-testid='button' and contains(., 'Entrar')]").click()
            time.sleep(8)
        except: pass

        # Transição Tela Antiga
        try:
            btn_ant = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Tela antiga']")))
            driver.execute_script("arguments[0].click();", btn_ant)
            time.sleep(6)
        except: pass
        
        # Filtros
        driver.get(Config.URL_ERP)
        time.sleep(5)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@tooltip='Filtro avançado']"))).click()
        time.sleep(3)

        driver.find_element(By.ID, "teamId").click()
        time.sleep(1)
        f_all = wait.until(EC.element_to_be_clickable((By.ID, "filterAll")))
        f_all.send_keys("COP Encerramentos")
        f_all.send_keys(Keys.ENTER)
        time.sleep(2)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='datagrid_row' and contains(text(), 'COP Encerramentos')]"))).click()
        time.sleep(1)
        driver.find_element(By.XPATH, "//button[contains(., 'Confirmar')]").click()

        # Limpeza e input de datas
        driver.execute_script("""
            ['beginInitialDate', 'endInitialDate'].forEach(id => {
                var el = document.getElementById(id);
                if(el) { el.focus(); el.value = ''; el.dispatchEvent(new Event('input', {bubbles:true})); el.blur(); }
            });
        """)
        forcar_input_react(driver.find_element(By.ID, "initialReportClosingDate"), data_inicio)
        forcar_input_react(driver.find_element(By.ID, "finalReportClosingDate"), data_fim)
        time.sleep(2)
        driver.find_element(By.XPATH, "//button[contains(., 'aplicar')]").click()
        time.sleep(15)

        # Exportação CSV
        btn_exp = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@tooltip='Imprimir/Exportar']")))
        driver.execute_script("arguments[0].click();", btn_exp)
        time.sleep(2)
        btn_csv = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., '.CSV')]")))
        driver.execute_script("arguments[0].click();", btn_csv)
        
        logging.info("Aguardando o download do CSV do ERP...")
        time.sleep(30) 
        
        # Processar o CSV no Pandas
        caminho_csv = mover_arquivo_recente()
        if not caminho_csv: return []

        logging.info("Processando CSV Diário no Pandas...")
        df = pd.read_csv(caminho_csv, sep=None, engine='python', encoding='latin-1', on_bad_lines='skip')
        
        # MUDANÇA CRÍTICA: Forçar a busca EXCLUSIVA pela coluna de Encerramento (Ignorando a Abertura)
        col_encontrada = [c for c in df.columns if "encerrament" in str(c).lower() and "data" in str(c).lower()]
        if not col_encontrada:
            col_encontrada = [c for c in df.columns if "encerrament" in str(c).lower()]
            
        possiveis_cols = ["Atendente", "Usuário Encerramento", "Responsável", "Nome"]
        coluna_tecnico = next((c for c in possiveis_cols if c in df.columns), df.columns[3])

        # Converte a coluna encontrada para datetime
        df['DATA_REF'] = pd.to_datetime(df[col_encontrada[0]], dayfirst=True, errors='coerce')
        
        # Converte as datas de inicio e fim (ex: 01/03/2026 e 30/04/2026) para objetos datetime
        dt_ini_obj = pd.to_datetime(data_inicio, format='%d/%m/%Y')
        # Adiciona o final do dia (23:59:59) para garantir que pega todo o último dia
        dt_fim_obj = pd.to_datetime(data_fim, format='%d/%m/%Y') + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        # MUDANÇA CRÍTICA: Corta fora do DataFrame qualquer linha que a data não esteja dentro do período exato
        df_limpo = df[(df['DATA_REF'] >= dt_ini_obj) & (df['DATA_REF'] <= dt_fim_obj)].copy()

        # Formata a data para ISO (YYYY-MM-DD)
        df_limpo['dia_mes_ano'] = df_limpo['DATA_REF'].dt.strftime('%Y-%m-%d')
        
        df_limpo['Atendente'] = df_limpo[coluna_tecnico].apply(identificar_pela_chave)
        df_limpo = df_limpo.dropna(subset=['Atendente', 'dia_mes_ano'])
        
        # Agrupa Diariamente
        df_agrupado = df_limpo.groupby(['Atendente', 'dia_mes_ano']).size().reset_index(name='total_encerrados')
        
        dados_diarios = []
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for _, row in df_agrupado.iterrows():
            dados_diarios.append({
                "id_unico": f"{row['Atendente']}_{row['dia_mes_ano']}",
                "colaborador": row["Atendente"],
                "dia_mes_ano": row["dia_mes_ano"],
                "total_encerrados": int(row["total_encerrados"]),
                "ultima_atualizacao": agora
            })
            
        os.remove(caminho_csv)
        return dados_diarios

    except Exception as e:
        logging.error(f"Erro no scraping do ERP (Performance): {str(e)}")
        return []
    finally:
        if driver: driver.quit()

# ==========================================
# 4. FUNÇÃO PRINCIPAL (ORQUESTRADOR)
# ==========================================
def executar_scraping():
    logging.info("=== Iniciando Módulo Completo de Performance ===")
    agora = datetime.now()
    
    # Define o primeiro dia do MÊS PASSADO
    primeiro_dia_mes_passado = (agora.replace(day=1) - timedelta(days=1)).replace(day=1)
    # Define o último dia do MÊS ATUAL
    ultimo_dia_mes_atual = agora.replace(day=calendar.monthrange(agora.year, agora.month)[1])

    ini_str = primeiro_dia_mes_passado.strftime("%d/%m/%Y")
    fim_str = ultimo_dia_mes_atual.strftime("%d/%m/%Y")

    # 1. Busca TME na Planilha
    tme_atual = carregar_tme_por_mes(agora.month)
    tme_passado = carregar_tme_por_mes(primeiro_dia_mes_passado.month)

    dados_tme_finais = []
    if tme_passado:
        dados_tme_finais.extend(processar_dados_planilha(tme_passado, primeiro_dia_mes_passado.month, primeiro_dia_mes_passado.year))
    if tme_atual:
        dados_tme_finais.extend(processar_dados_planilha(tme_atual, agora.month, agora.year))

    # 2. Busca Encerramentos Diários no ERP via Selenium
    dados_erp_diarios = coletar_e_processar_erp_diario(ini_str, fim_str)

    logging.info(f"Módulo Performance concluído: {len(dados_tme_finais)} registros TME e {len(dados_erp_diarios)} registros ERP.")
    
    # Retorna os dois pacotes para a main.py salvar em tabelas separadas
    return dados_tme_finais, dados_erp_diarios