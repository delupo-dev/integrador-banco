import os
import logging
import pyodbc
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv
from datetime import datetime
import re

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("etl_integradora.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

def sanitize_column_name(name):
    """Remove caracteres especiais e espaços para evitar erros no PostgreSQL"""
    # Remove acentos e caracteres especiais
    name = name.replace('º', 'n').replace('ª', 'a').replace('(', '').replace(')', '').replace('/', '_').replace('-', '_').replace(' ', '_')
    # Remove acentos comuns (simplificado)
    name = re.sub(r'[ÁÀÂÃ]', 'A', name)
    name = re.sub(r'[ÉÈÊ]', 'E', name)
    name = re.sub(r'[ÍÌÎ]', 'I', name)
    name = re.sub(r'[ÓÒÔÕ]', 'O', name)
    name = re.sub(r'[ÚÙÛ]', 'U', name)
    name = re.sub(r'[Ç]', 'C', name)
    # Remove qualquer outro caractere não alfanumérico (exceto underscore)
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    return name.lower()

def get_source_connection():
    """Conecta ao SQL Server (Origem)"""
    try:
        conn_str = (
            f"DRIVER={os.getenv('DB_SOURCE_DRIVER')};"
            f"SERVER={os.getenv('DB_SOURCE_HOST')};"
            f"DATABASE={os.getenv('DB_SOURCE_NAME')};"
            f"UID={os.getenv('DB_SOURCE_USER')};"
            f"PWD={os.getenv('DB_SOURCE_PASS')}"
        )
        return pyodbc.connect(conn_str)
    except Exception as e:
        logger.error(f"Erro ao conectar no SQL Server: {e}")
        raise

def get_target_connection():
    """Conecta ao PostgreSQL (Destino)"""
    try:
        return psycopg2.connect(
            host=os.getenv('DB_TARGET_HOST'),
            database=os.getenv('DB_TARGET_NAME'),
            user=os.getenv('DB_TARGET_USER'),
            password=os.getenv('DB_TARGET_PASS'),
            port=os.getenv('DB_TARGET_PORT')
        )
    except Exception as e:
        logger.error(f"Erro ao conectar no PostgreSQL: {e}")
        raise

def ensure_table_exists(cursor, columns_with_types):
    """Cria a tabela boletos ou adiciona colunas faltantes"""
    # 1. Cria a tabela base se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS boletos (
            id SERIAL PRIMARY KEY
        );
    """)
    
    # 2. Verifica as colunas que já existem
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'boletos';")
    existing_columns = {row[0] for row in cursor.fetchall()}
    
    # 3. Adiciona colunas que estão faltando
    for name, type_obj in columns_with_types:
        safe_name = sanitize_column_name(name)
        if safe_name not in existing_columns:
            # Mapeamento básico de tipos
            if 'Decimal' in str(type_obj):
                pg_type = "NUMERIC"
            elif 'int' in str(type_obj).lower():
                pg_type = "INTEGER"
            else:
                pg_type = "TEXT"
            
            logger.info(f"Adicionando nova coluna: {safe_name}")
            cursor.execute(f'ALTER TABLE boletos ADD COLUMN "{safe_name}" {pg_type};')

def run_etl():
    start_time = datetime.now()
    logger.info("Iniciando processo de ETL...")
    
    source_conn = None
    target_conn = None
    
    try:
        # 1. Extração (SQL Server)
        source_conn = get_source_connection()
        source_cursor = source_conn.cursor()
        
        logger.info("Extraindo dados da view vis_boleto_app...")
        source_cursor.execute("SELECT * FROM vis_boleto_app")
        
        # Obter nomes das colunas e tipos
        raw_columns = [column[0] for column in source_cursor.description]
        rows = source_cursor.fetchall()
        
        if not rows:
            logger.warning("Nenhum dado encontrado na origem. Abortando carga.")
            return

        # Amostra de tipos para criação da tabela
        col_types = []
        for i, col_name in enumerate(raw_columns):
            sample_val = rows[0][i]
            col_types.append((col_name, type(sample_val)))

        logger.info(f"{len(rows)} registros extraídos com sucesso.")

        # 2. Carga (PostgreSQL)
        target_conn = get_target_connection()
        target_cursor = target_conn.cursor()
        
        # Início da Transação
        try:
            logger.info("Verificando/Criando tabela de destino...")
            ensure_table_exists(target_cursor, col_types)
            
            logger.info("Limpando tabela de destino (Truncate)...")
            target_cursor.execute("TRUNCATE TABLE boletos RESTART IDENTITY;")
            
            logger.info("Iniciando Bulk Insert no PostgreSQL...")
            
            # Sanitiza os nomes das colunas para o INSERT
            safe_columns = [sanitize_column_name(col) for col in raw_columns]
            quoted_columns = [f'"{col}"' for col in safe_columns]
            col_names = ",".join(quoted_columns)
            query = f'INSERT INTO boletos ({col_names}) VALUES %s'
            
            # Converte as linhas do pyodbc para tuplas
            data_to_insert = [tuple(row) for row in rows]
            
            # Executa a inserção em lotes
            extras.execute_values(
                target_cursor, 
                query, 
                data_to_insert,
                page_size=1000
            )
            
            target_conn.commit()
            logger.info("Transação confirmada (COMMIT) com sucesso.")
            
        except Exception as e:
            target_conn.rollback()
            logger.error(f"Erro durante a carga no PostgreSQL. Realizando ROLLBACK. Detalhe: {e}")
            raise

    except Exception as e:
        logger.critical(f"Falha crítica no processo de ETL: {e}")
    
    finally:
        if source_conn:
            source_conn.close()
            logger.info("Conexão SQL Server fechada.")
        if target_conn:
            target_conn.close()
            logger.info("Conexão PostgreSQL fechada.")
            
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"Processo finalizado em {duration}.")

if __name__ == "__main__":
    run_etl()
