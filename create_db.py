# ==================================
# SCRIPT DE CRIAÇÃO DO BANCO DE DADOS
# (create_db.py)
# ==================================
import os
from app import app, db

print("--- [create_db.py] Script iniciado ---")

# Precisamos 'enganar' o app.py para que ele use o
# banco de dados de produção (PostgreSQL) e não o SQLite.
# Fazemos isso setando a variável de ambiente ANTES de criar as tabelas.
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
