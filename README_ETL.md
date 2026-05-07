# Guia de Implantação: Integrador ETL Banco

Este documento descreve como configurar e agendar o script de integração (ETL) entre o SQL Server (Origem) e o PostgreSQL (Destino) em ambientes de servidor.

---

## 1. Pré-requisitos do Sistema

### 🖥️ Microsoft Windows
1. **Python 3.8+**: [Download aqui](https://www.python.org/).
2. **Driver ODBC**: Necessário para conectar no SQL Server. Instale o [Microsoft ODBC Driver 17 ou 18](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).

### 🐧 Linux (Ubuntu/Debian)
1. **Python 3.8+**: `sudo apt update && sudo apt install python3 python3-pip python3-venv`.
2. **Dependências ODBC**:
   ```bash
   sudo apt install unixodbc-dev
   ```
3. **Microsoft ODBC Driver for Linux**: Siga as instruções oficiais da Microsoft para instalar o driver `msodbcsql17` ou `msodbcsql18` baseado na sua distro.

---

## 2. Instalação e Configuração

1. **Clonar/Copiar os arquivos**: Mova a pasta do projeto para o servidor (ex: `C:\Scripts\integrador` ou `/opt/integrador`).
2. **Criar Ambiente Virtual (VENV)**:
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate

   # Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Instalar Dependências**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configurar Variáveis (.env)**:
   Crie o arquivo `.env` na raiz do projeto preenchendo as credenciais de Origem (SQL Server) e Destino (PostgreSQL).

---

## 3. Agendamento Automático

### ⏰ No Windows (Task Scheduler)
1. Abra o **Agendador de Tarefas** e clique em **Criar Tarefa Básica**.
2. **Nome**: `ETL_Sincronizacao_Boleto`.
3. **Disparador**: Diariamente (ex: às 02:00 da manhã).
4. **Ação**: Iniciar um programa.
5. **Programa/script**: Caminho para o Python dentro da venv.
   - Ex: `C:\caminho\do\projeto\.venv\Scripts\python.exe`
6. **Argumentos**: `"C:\caminho\do\projeto\etl_boletos.py"`
7. **Iniciar em**: `C:\caminho\do\projeto\`

### ⏰ No Linux (Crontab)
1. Abra o editor do crontab: `crontab -e`.
2. Adicione a linha para rodar todos os dias às 02:00:
   ```bash
   00 02 * * * /opt/integrador/.venv/bin/python /opt/integrador/etl_boletos.py >> /opt/integrador/etl.log 2>&1
   ```

---

## 4. Monitoramento e Logs
- O script gera automaticamente um arquivo chamado `etl_integradora.log` na pasta raiz.
- **Auto-ajuste de Schema**: O script detecta automaticamente novas colunas adicionadas na View do SQL Server e as cria no PostgreSQL sem necessidade de intervenção manual.
- **Transacional**: Em caso de falha no meio da carga, o script realiza um `ROLLBACK`, garantindo que os dados no PostgreSQL não fiquem corrompidos ou parciais.
