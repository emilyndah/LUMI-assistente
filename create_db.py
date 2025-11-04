# ==================================
# SCRIPT DE CRIAÇÃO DO BANCO DE DADOS
# (create_db.py) - COM DEBUG
# ==================================
import os
from app import app, db  # Esta linha IMPORTA e EXECUTA a lógica do app.py

print("--- [create_db.py] Script iniciado ---")

# --- VAMOS ADICIONAR O DEBUG AQUI ---
# Vamos printar a URL que o app.py configurou ANTES de tentar qualquer coisa
try:
    configured_url = app.config.get("SQLALCHEMY_DATABASE_URI")
    print(
        f"--- [create_db.py] DEBUG: URL configurada no app: {configured_url} ---")
except Exception as e:
    print(f"--- [create_db.py] DEBUG: Erro ao ler config: {e} ---")
# --- FIM DO DEBUG ---

# Seta a variável de ambiente (não afeta o config já carregado, mas é uma boa prática)
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///")

# Força o app a carregar a configuração do banco de dados
with app.app_context():
    print("--- [create_db.py] Dentro do app_context ---")

    try:
        print("Tentando criar todas as tabelas...")
        db.create_all()
        print("--- [create_db.py] SUCESSO: Tabelas criadas. ---")
    except Exception as e:
        print(f"--- [create_db.py] ERRO: Falha ao criar tabelas: {e} ---")

print("--- [create_db.py] Script finalizado ---")
