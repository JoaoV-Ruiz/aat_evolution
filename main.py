import time
import logging
from modules import chamados_amarelos, encerramentos, perfomance, batida_caixa_historico
from database import enviar_para_banco

# --- CONFIGURAÇÃO DE LOGS ---
# Grava tudo em um arquivo .log para auditoria e também mostra no terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler("execucao_projeto.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def rodar_ciclo_de_automacao():
    """Executa a sequência de módulos configurados na lista de tarefas."""
    logging.info("🚀 Iniciando novo ciclo de coleta...")

    # Lista de módulos ativos
    tarefas = [
        {
            "nome": "Chamados Amarelos",
            "modulo": chamados_amarelos
        },
        {
            "nome": "Encerramentos",
            "modulo": encerramentos,
            "tabela": "dados_encerramentos",
            "chave_conflito": "id_unico"
        },
        {
            "nome": "Performance Operacional",
            "modulo": perfomance
        },
        {
            "nome": "Histórico Batida Caixa",
            "modulo": batida_caixa_historico,
            "tabela": "dados_batida_caixa",
            "chave_conflito": "id_unico"
        }
        
    ]

    for tarefa in tarefas:
        try:
            logging.info(f"🛰️ Processando módulo: {tarefa['nome']}...")
            
            # --- SE FOR O MÓDULO DOS AMARELOS ---
            if tarefa['nome'] == "Chamados Amarelos":
                dados_ind, dados_gerais = tarefa['modulo'].executar_scraping()
                
                if dados_ind and dados_gerais:
                    enviar_para_banco("monitoramento_osirnet", dados_ind, "colaborador")
                    enviar_para_banco("monitoramento_geral", dados_gerais, "id")
                    logging.info("✅ Chamados Amarelos e Visão Geral atualizados no banco.")
                else:
                    logging.warning("⚠️ Chamados Amarelos não retornou dados.")

            # --- SE FOR PERFORMANCE OPERACIONAL ---
            elif tarefa['nome'] == "Performance Operacional":
                dados_tme, dados_diarios_erp = tarefa['modulo'].executar_scraping()
                
                # Salva o TME na tabela 'dados_performance'
                if dados_tme:
                    enviar_para_banco("dados_performance", dados_tme, "id_unico")
                
                # Salva a Volumetria Diária na tabela 'dados_encerramentos_mensal'
                if dados_diarios_erp:
                    enviar_para_banco("dados_encerramentos_mensal", dados_diarios_erp, "id_unico")
                    
                if dados_tme or dados_diarios_erp:
                    logging.info("✅ Dados de Performance e Volumetria Diária atualizados no banco.")
                else:
                    logging.warning("⚠️ Módulo de Performance não retornou dados.")

            # --- SE FOR OUTRO MÓDULO (ENCERRAMENTOS MENSAIS) ---
            else:
                dados = tarefa['modulo'].executar_scraping()
                if dados and len(dados) > 0:
                    enviar_para_banco(tarefa['tabela'], dados, tarefa['chave_conflito'])
                    logging.info(f"✅ {tarefa['nome']} finalizado e banco atualizado.")
                else:
                    logging.warning(f"⚠️ {tarefa['nome']} não retornou novos dados.")

        except Exception as e:
            logging.error(f"❌ Falha crítica na rotina de {tarefa['nome']}: {str(e)}")

    logging.info("🏁 Ciclo completo finalizado.\n")

def main():
    logging.info("⚙️ Sistema de Automação Osirnet Iniciado.")
    
    # Define o intervalo base entre os inícios de cada ciclo
    intervalo_segundos = 5 * 60  # 5 minutos

    while True:
        tempo_inicio_ciclo = time.time()
        proxima_execucao = tempo_inicio_ciclo + intervalo_segundos
        
        rodar_ciclo_de_automacao()
        
        # Calcula quanto tempo sobrou até dar os 5 minutos
        tempo_espera = max(0, proxima_execucao - time.time())
        
        if tempo_espera > 0:
            logging.info(f"⏳ Aguardando {int(tempo_espera / 60)} minutos e {int(tempo_espera % 60)} segundos para o próximo ciclo...")
            time.sleep(tempo_espera)
        else:
            logging.warning("⚠️ O ciclo levou mais de 5 minutos para rodar. Iniciando o próximo imediatamente.")

if __name__ == "__main__":
    main()