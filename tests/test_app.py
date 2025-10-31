# =======================================================
# TESTES AUTOMATIZADOS – LUMI ASSISTENTE ACADÊMICA
# =======================================================
# Objetivo: garantir o funcionamento básico do backend Flask e rotas principais
# =======================================================

import sys
from pathlib import Path

import pytest
# --- Pool estático garante a mesma conexão SQLite na memória ---
from sqlalchemy.pool import StaticPool

# =======================================================
# AJUSTE DO CAMINHO PARA IMPORTAÇÃO DO APP
# =======================================================
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import app, db, User


@pytest.fixture
def client():
    """Cria um cliente de teste do Flask."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # BD temporário
    # --- Mantém a conexão em memória estável durante os testes ---
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        # --- Limpeza do banco ao final de cada teste ---
        with app.app_context():
            db.session.remove()
            db.drop_all()


# =======================================================
# 1️⃣ TESTE: Página inicial requer login
# =======================================================
def test_home_requires_login(client):
    """A página inicial deve redirecionar se o usuário não estiver logado."""
    response = client.get('/')
    assert response.status_code == 302  # Redireciona para login
    assert '/login' in response.headers['Location']


# =======================================================
# 2️⃣ TESTE: Página de login carrega corretamente
# =======================================================
def test_login_page_loads(client):
    """Verifica se a página de login carrega."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login' in response.data or b'E-mail' in response.data


# =======================================================
# 3️⃣ TESTE: Registro de novo usuário
# =======================================================
def test_register_new_user(client):
    """Verifica se o registro cria um novo usuário com sucesso."""
    response = client.post('/register', data={
        'email': 'teste@teste.com',
        'username': 'TesteUser',
        'matricula': '12345',
        'password': 'senha123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert (
        b'Lumi' in response.data
        or b'Assistente' in response.data
        or b'Conta criada com sucesso' in response.data
    )
    with app.app_context():
        user = User.query.filter_by(email='teste@teste.com').first()
        assert user is not None


# =======================================================
# 4️⃣ TESTE: Login e acesso autorizado
# =======================================================
def test_login_and_access_home(client):
    """Testa se o login funciona e dá acesso à página inicial."""
    with app.app_context():
        user = User(username='UsuárioTeste', email='user@teste.com', matricula='99999')
        user.set_password('123456')
        db.session.add(user)
        db.session.commit()

    response = client.post('/login', data={
        'login_identifier': 'user@teste.com',
        'password': '123456'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert (
        b'Ol\xc3\xa1, Usu\xc3\xa1rioTeste' in response.data
        or b'Logout' in response.data
        or b'Assistente' in response.data
    )
