import logging
from config import Config
from supabase import create_client, Client

# Inicializa o cliente do Supabase usando as variáveis do Config
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

def enviar_para_banco(tabela, dados, chave_conflito="colaborador"):
    """
    Recebe o nome da tabela, uma lista de dicionários (JSON) e a chave de conflito.
    Realiza um UPSERT baseado na chave informada.
    """
    try:
        # O upsert atualiza o registro se a chave de conflito já existir, ou insere se for novo
        response = supabase.table(tabela).upsert(
            dados, 
            on_conflict=chave_conflito
        ).execute()
        return response
    except Exception as e:
        logging.error(f"Erro ao inserir/atualizar na tabela {tabela}: {e}")
        return None