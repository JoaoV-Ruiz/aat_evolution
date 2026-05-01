import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from config import Config

def executar_scraping():
    logging.info("Iniciando leitura da Planilha de Batida de Caixa...")
    
    try:
        # Configuração de credenciais do Google
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(Config.GOOGLE_JSON_CREDENTIALS, scopes=scopes)
        cliente = gspread.authorize(creds)
        
        # ⚠️ AJUSTE AQUI: Substitua pelos dados reais da sua planilha
        planilha = cliente.open_by_url("https://docs.google.com/spreadsheets/d/1oYlw1uoSNYkUjZGO6m0zxti4800mThg_3uiWeo_IWyY/edit?gid=1239844842#gid=1239844842")
        aba = planilha.worksheet("Respostas ao formulário 1")
        
        # Puxa tudo como uma lista bruta de valores (ignora erros de cabeçalho)
        dados_brutos = aba.get_all_values()
        
        if not dados_brutos or len(dados_brutos) < 2:
            logging.warning("Planilha de Batida de Caixa vazia ou sem dados suficientes.")
            return []
            
        # Log para conferência de cabeçalhos (ajuda no debug)
        cabecalhos = dados_brutos[0]
        logging.info(f"🔍 CABEÇALHOS ENCONTRADOS: {cabecalhos}") 
        
        linhas_dados = dados_brutos[1:]
        
        # Dicionário para eliminar duplicatas de protocolo antes de enviar ao Supabase
        registros_dict = {}
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        def pega_valor(linha_atual, indice):
            """
            Função auxiliar para evitar erro se o Google Sheets 
            encurtar a linha quando as últimas colunas estão vazias.
            """
            if indice < len(linha_atual):
                return str(linha_atual[indice]).strip()
            return ""

        for linha in linhas_dados:
            # Pegamos o protocolo na coluna de índice 1 (segunda coluna)
            protocolo = pega_valor(linha, 1)
            
            # Só processamos se o protocolo existir
            if not protocolo:
                continue
                
            # Salvamos no dicionário usando o protocolo como chave.
            # Se houver um protocolo repetido, o último da planilha prevalece.
            registros_dict[protocolo] = {
                "id_unico": protocolo,
                "datetime": pega_valor(linha, 0), 
                "protocolo": protocolo,
                "caixa": pega_valor(linha, 2),
                "portas_livres": pega_valor(linha, 3),
                "colaborador": pega_valor(linha, 4),
                "ultima_atualizacao": agora
            }
            
        # Convertemos o dicionário de volta para uma lista para o retorno
        registros = list(registros_dict.values())
            
        logging.info(f"Batida de Caixa lida: {len(registros)} registros únicos processados.")
        return registros

    except Exception as e:
        logging.error(f"Erro ao ler a planilha de Batida de Caixa: {str(e)}")
        return None