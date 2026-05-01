import os
from dotenv import load_dotenv
import json

load_dotenv()

class Config:
    # --- SUPABASE ---
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    # --- SISTEMAS (AMARELOS E ERP) ---
    URL_COLETA = os.getenv("URL_COLETA")
    EMAIL_CORP = os.getenv("EMAIL_CORP")
    SENHA_SISTEMA = os.getenv("SENHA_SISTEMA")
    URL_ERP = os.getenv("URL_ERP")
    ERP_USER = os.getenv("ERP_USER")
    ERP_PASS = os.getenv("ERP_PASS")

    # --- PLANILHA GOOGLE ---
    SPREADSHEET_URL = os.getenv("SPREADSHEET_URL")

    # --- PASTAS E ARQUIVOS ---
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
    DATA_TEMP = os.path.join(BASE_DIR, "data_temp")
    
    # Aponta para o arquivo JSON na raiz do projeto
    GOOGLE_JSON_CREDENTIALS = json.loads(os.getenv("GOOGLE_JSON_CREDENTIALS_2"))
    GOOGLE_JSON_CREDENTIALS_2 = json.loads(os.getenv("GOOGLE_JSON_CREDENTIALS"))

os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
os.makedirs(Config.DATA_TEMP, exist_ok=True)