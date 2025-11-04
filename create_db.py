# ==================================
# SCRIPT DE CRIAÇÃO DO BANCO DE DADOS
# (create_db.py) - COM DEBUG
# ==================================
import os
from app import app, db

print("--- [create_db.py] Script iniciado ---")

# Debug: mostra a URL configurada
try:
    configured_url = app.config.get("SQLALCHEMY_DATABASE_URI")
    print(
        f"--- [create_db.py] DEBUG: URL configurada no app: {configured_url} ---")
except Exception as e:
    print(f"--- [create_db.py] DEBUG: Erro ao ler config: {e} ---")

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
