
# =======================================================
# TÍTULO: SERVIDOR FLASK (APP.PY) - ASSISTENTE LUMI
# (Login, BD, Salvar VARK, Quiz JSON, Calendário JSON, Matriz JSON)
# =======================================================

# =======================================================
# IMPORTAÇÕES (Limpas e Agrupadas)
# =======================================================
import json
import os
import re
import traceback
from datetime import datetime
import logging
from dotenv import load_dotenv

import google.generativeai as genai
from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
    flash,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from werkzeug.security import generate_password_hash, check_password_hash


load_dotenv()

# =======================================================
# CONFIGURAÇÃO DA APLICAÇÃO FLASK
# =======================================================
logging.basicConfig(
    filename="lumi.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.info("Servidor iniciado - monitorando eventos Lumi")

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "chave_secreta_final_lumi_app_v6_save_vark"
)
# --- Lógica do Banco de Dados para Produção (Render) ---
db_url = os.environ.get("DATABASE_URL")
if db_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        os.path.dirname(__file__), "lumi_database.db"
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


@app.cli.command("db-create-all")
def db_create_all():
    """Cria as tabelas do banco de dados (usado pelo Render)."""
    with app.app_context():
        db.create_all()
        print("Banco de dados e tabelas criados com sucesso.")


# Configuração Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
# redireciona para /login se não estiver autenticado
login_manager.login_view = "login"
login_manager.login_message = "Você precisa fazer login para acessar esta página."
login_manager.login_message_category = "warning"


# =======================================================
# MODELO DE DADOS (User - Atualizado com VARK)
# =======================================================
class User(db.Model, UserMixin):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    matricula = db.Column(db.String(80), unique=True, nullable=False)

    password_hash = db.Column(db.String(256), nullable=False)
    vark_scores_json = db.Column(db.Text, nullable=True)
    vark_primary_type = db.Column(db.String(10), nullable=True)

    def get_vark_scores(self):
        """Retorna os scores VARK como dicionário."""
        if not self.vark_scores_json:
            return None
        try:
            return json.loads(self.vark_scores_json)
        except json.JSONDecodeError:
            return None

    def set_password(self, password):
        """Cria um hash da senha e o armazena."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica se a senha em texto puro bate com o hash armazenado."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __init__(self, username, email, matricula, password=None):
        self.username = username
        self.email = email
        self.matricula = matricula
        if password:
            self.set_password(password)
        self.vark_scores_json = None
        self.vark_primary_type = None


@login_manager.user_loader
def load_user(user_id):
    if user_id is not None:
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            print(f"DEBUG: Invalid user_id format in session: {user_id}")
            return None
    return None


# =======================================================
# 1. CONSTANTES E CONFIGURAÇÃO DO GEMINI
# =======================================================
# --- MUDANÇA 1 ---
# Agora apenas configuramos a API Key aqui.
# A inicialização do 'model' foi movida para DEPOIS do contexto ser carregado.
GEMINI_API_KEY = None
model = None  # Será inicializado APÓS o contexto ser carregado
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)  # Configura a API aqui
except KeyError:
    print("=" * 80)
    print("ERRO: Variável de ambiente GEMINI_API_KEY não encontrada.")
    print("Por favor, crie um arquivo .env e adicione a linha:")
    print("GEMINI_API_KEY=SUA_CHAVE_AQUI")
    print("=" * 80)

# --- Configuração do Modelo ---
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)

        # Atualizado para versão 2.5 da API
        model = genai.GenerativeModel(
            "gemini-2.5-flash")  # ou "gemini-2.5-pro"

        print("✅ Modelo Gemini inicializado com sucesso (gemini-2.5-flash).")
    except Exception as e:
        print(f"❌ Erro ao inicializar o modelo Gemini: {e}")
        GEMINI_API_KEY = None

else:
    print("⚠️ API Key do Gemini não encontrada. O Chatbot não funcionará.")


# --- Contexto Inicial (Sistema) ---
def carregar_contexto_inicial():
    """Carrega o contexto base do arquivo informacoes.txt."""
    try:
        with open("informacoes.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(
            "Aviso: 'informacoes.txt' não encontrado. O chatbot pode não ter contexto."
        )
        return "Você é um assistente acadêmico chamado Lumi, focado em ajudar alunos da UniEVANGÉLICA."
    except Exception as e:
        print(f"Erro ao ler 'informacoes.txt': {e}")
        return "Você é um assistente acadêmico chamado Lumi."


CONTEXTO_INICIAL = carregar_contexto_inicial()

# =======================================================
# 2. FUNÇÕES AUXILIARES (CARREGAMENTO DE DADOS)
# =======================================================


def carregar_dados_json(arquivo):
    """Função genérica para carregar dados de um arquivo JSON."""
    try:
        caminho_arquivo = os.path.join(os.path.dirname(__file__), arquivo)
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"AVISO: Arquivo {arquivo} não encontrado.")
        return None
    except json.JSONDecodeError as e:
        print(f"ERRO: Falha ao decodificar JSON em {arquivo}. Detalhe: {e}")
        return None
    except Exception as e:
        print(f"ERRO inesperado ao ler {arquivo}: {e}")
        traceback.print_exc()
        return None


def carregar_calendario():
    """Carrega, formata e ordena os eventos do calendário."""
    meses_map = {
        1: "JAN",
        2: "FEV",
        3: "MAR",
        4: "ABR",
        5: "MAI",
        6: "JUN",
        7: "JUL",
        8: "AGO",
        9: "SET",
        10: "OUT",
        11: "NOV",
        12: "DEZ",
    }
    eventos = []
    dados = carregar_dados_json("calendario.json")
    if dados is None:
        print("AVISO: calendario.json não foi carregado. Retornando lista vazia.")
        return []

    if not isinstance(dados, list):
        print(
            "AVISO: calendario.json possui formato inválido. Esperada lista de eventos."
        )
        return []

    for item in dados:
        if not isinstance(item, dict):
            print(f"AVISO: Evento ignorado por formato inválido: {item}")
            continue

        data_inicio = item.get("data_inicio")
        descricao = item.get("descricao", "Evento sem descrição")
        data_fim = item.get("data_fim")

        if not data_inicio:
            print(f"AVISO: Evento sem data de início ignorado: {item}")
            continue

        try:
            data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d")
        except ValueError:
            print(f"AVISO: Data de início inválida ignorada: {data_inicio}")
            continue

        data_fim_iso = None
        if data_fim:
            try:
                data_fim_iso = datetime.strptime(data_fim, "%Y-%m-%d").strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                print(f"AVISO: Data final inválida ignorada: {data_fim}")

        eventos.append(
            {
                "data": data_inicio_obj.strftime("%d/%m/%Y"),
                "evento": descricao,
                "data_obj": data_inicio_obj,
                "data_iso": data_inicio,
                "data_fim": data_fim_iso,
                "mes_curto": meses_map.get(data_inicio_obj.month),
            }
        )
    return sorted(eventos, key=lambda x: x["data_obj"])


def carregar_matriz():
    """Carrega dados da matriz curricular."""
    dados = carregar_dados_json("matriz.json")
    if dados and isinstance(dados, list):
        return dados
    elif dados and isinstance(dados, dict):
        # Suporte ao formato antigo que era um objeto único
        print(
            "AVISO: matriz.json em formato antigo (objeto único). Convertendo para lista.")
        return [dados]
    else:
        print("AVISO: Falha ao carregar ou formato inválido para matriz.json.")
        return None


def carregar_quiz_vark():
    """Carrega dados do quiz VARK."""
    return carregar_dados_json("metodo_estudo.json")


def carregar_contexto_inicial():
    """Carrega o contexto base e adiciona dados do calendário, matriz e métodos de estudo."""
    contexto_base = ""
    contexto_calendario = ""
    contexto_matriz = ""
    contexto_vark = ""

    # 1. Carrega o contexto principal (informacoes.txt)
    try:
        with open("informacoes.txt", "r", encoding="utf-8") as f:
            contexto_base = f.read()
    except FileNotFoundError:
        print(
            "Aviso: 'informacoes.txt' não encontrado. O chatbot pode não ter contexto."
        )
        contexto_base = "Você é um assistente acadêmico chamado Lumi, focado em ajudar alunos da UniEVANGÉLICA."
    except Exception as e:
        print(f"Erro ao ler 'informacoes.txt': {e}")
        contexto_base = "Você é um assistente acadêmico chamado Lumi."

    # 2. Carrega e formata o Calendário
    print("Carregando Calendário para o contexto...")
    try:
        eventos = carregar_calendario()  # Função já existente
        if eventos:
            contexto_calendario = "\n\n=== CALENDÁRIO ACADÊMICO (Use para responder perguntas sobre datas) ===\n"
            for evento in eventos:
                data_str = evento.get("data")  # "dd/mm/YYYY"
                desc = evento.get("evento")
                data_fim_str = ""
                if evento.get("data_fim") and evento.get("data_fim") != evento.get("data_iso"):
                    try:
                        data_fim_obj = datetime.strptime(
                            evento["data_fim"], "%Y-%m-%d")
                        data_fim_str = f" até {data_fim_obj.strftime('%d/%m/%Y')}"
                    except ValueError:
                        pass
                contexto_calendario += f"- Em {data_str}{data_fim_str}: {desc}\n"
            contexto_calendario += "======================================================================\n"
            print(f"Calendário carregado. {len(eventos)} eventos.")
        else:
            print(
                "AVISO: Não foi possível carregar os eventos do calendário no contexto.")
    except Exception as e:
        print(f"ERRO ao processar calendário para o contexto: {e}")
        traceback.print_exc()

    # 3. Carrega e formata a Matriz Curricular
    print("Carregando Matriz Curricular para o contexto...")
    try:
        matriz_data = carregar_matriz()  # Função já existente
        if matriz_data:
            contexto_matriz = "\n\n=== MATRIZ CURRICULAR (Use para responder sobre aulas, professores, horários e salas) ===\n"
            for periodo_info in matriz_data:
                periodo_nome = periodo_info.get(
                    'periodo', 'Período Não Identificado')
                contexto_matriz += f"\n--- Período {periodo_nome} ---\n"
                disciplinas = periodo_info.get('disciplinas', [])
                if not disciplinas:
                    contexto_matriz += "(Nenhuma disciplina listada para este período)\n"

                for disc in disciplinas:
                    nome = disc.get('nome', 'Sem nome')
                    prof = disc.get('professor', 'A definir')
                    dia = disc.get('dia', 'A definir')
                    horario = disc.get('horario', 'A definir')
                    sala = disc.get('sala', 'A definir')

                    contexto_matriz += f"- Disciplina: {nome}\n"
                    contexto_matriz += f"  Professor: {prof}\n"
                    contexto_matriz += f"  Horário: {dia}, {horario}\n"
                    contexto_matriz += f"  Sala: {sala}\n\n"

            contexto_matriz += "======================================================================\n"
            print("Matriz Curricular carregada para o contexto.")
        else:
            print("AVISO: Não foi possível carregar a matriz curricular no contexto.")
    except Exception as e:
        print(f"ERRO ao processar matriz para o contexto: {e}")
        traceback.print_exc()

    # 4. Carrega e formata os Métodos de Estudo (VARK)
    print("Carregando Métodos de Estudo (VARK) para o contexto...")
    try:
        vark_data = carregar_quiz_vark()  # Função já existente
        resultados_vark = vark_data.get('resultados')
        if resultados_vark:
            contexto_vark = "\n\n=== MÉTODOS DE ESTUDO (Use para explicar os estilos VARK) ===\n"
            for tipo, info in resultados_vark.items():
                titulo = info.get('titulo', tipo)
                desc = info.get('descricao', 'Sem descrição.')
                metodos = info.get('metodos', [])

                contexto_vark += f"\n--- {titulo} ({tipo}) ---\n"
                contexto_vark += f"{desc}\n"
                contexto_vark += "Métodos sugeridos:\n"
                for m in metodos:
                    contexto_vark += f"  - {m}\n"

            contexto_vark += "======================================================================\n"
            print("Métodos VARK carregados para o contexto.")
        else:
            print("AVISO: Não foi possível carregar os resultados VARK no contexto.")
    except Exception as e:
        print(f"ERRO ao processar VARK para o contexto: {e}")
        traceback.print_exc()

    # 5. Combina tudo
    print("Contexto inicial montado com sucesso.")
    return contexto_base + contexto_calendario + contexto_matriz + contexto_vark


# A variável CONTEXTO_INICIAL é carregada aqui
CONTEXTO_INICIAL = carregar_contexto_inicial()


# =======================================================
# 1.5. INICIALIZAÇÃO DO MODELO GEMINI (COM CONTEXTO)
# =======================================================
# --- MUDANÇA 2 ---
# Movemos a inicialização do modelo para DEPOIS de carregar o contexto,
# para que possamos injetá-lo como "system_instruction".
# Isso resolve o problema do "cookie too large".
if GEMINI_API_KEY:
    try:
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=CONTEXTO_INICIAL  # <-- AQUI ESTÁ A MÁGICA!
        )
        print("✅ Modelo Gemini inicializado com system_instruction (contexto completo).")
    except Exception as e:
        print(f"❌ Erro ao inicializar o modelo Gemini: {e}")
        GEMINI_API_KEY = None  # Garante que o app não tente usar um modelo falho
else:
    print("⚠️ API Key não encontrada. O Chatbot não funcionará.")


# =======================================================
# 3. ROTAS PRINCIPAIS (LOGIN, PÁGINAS, ETC.)
# =======================================================

# --- MUDANÇA 3 ---
# O CONTEXTO_INICIAL FOI REMOVIDO DAQUI.
# Ele agora vive dentro do 'model' (system_instruction).
# A sessão guardará APENAS as perguntas e respostas (que é pequeno).
def get_initial_chat_history():
    """Retorna a estrutura de histórico inicial para a sessão."""
    return [
        {
            "role": "model",
            "parts": [
                "Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje?"
            ],
        },
    ]

# =======================================================
# 5. ROTAS DE AUTENTICAÇÃO (Login, Registro, Logout)
# =======================================================


@app.route("/register", methods=["GET", "POST"])
def register():
    """Lida com o registro de novos usuários."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        matricula = request.form.get("matricula")
        password = request.form.get("password")

        user_by_email = User.query.filter_by(email=email).first()
        user_by_matricula = User.query.filter_by(matricula=matricula).first()

        if user_by_email:
            flash("Este e-mail já está cadastrado. Tente fazer login.", "warning")
            return redirect(url_for("login"))

        if user_by_matricula:
            flash("Esta matrícula já está cadastrada. Tente fazer login.", "warning")
            return redirect(url_for("login"))

        try:
            new_user = User(
                email=email,
                username=username,
                matricula=matricula
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)
            flash("Conta criada com sucesso! Você foi logado.", "success")
            return redirect(url_for("index"))

        except Exception as e:
            db.session.rollback()
            print(f"Erro ao registrar usuário: {e}")
            flash("Ocorreu um erro ao criar sua conta. Tente novamente.", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Lida com o login do usuário."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        identifier = request.form.get("login_identifier")
        password = request.form.get("password")
        user = User.query.filter(
            (getattr(User, "email") == identifier) | (
                getattr(User, "matricula") == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("index"))
        else:
            flash("E-mail/Matrícula ou senha inválidos. Tente novamente.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Lida com o logout do usuário."""
    logout_user()
    flash("Você foi desconectado.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    """Renderiza a página inicial do chat."""
    if "historico" not in session:
        session["historico"] = get_initial_chat_history()
    return render_template("index.html")


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


@app.route("/faq")
@login_required
def faq():
    dados = carregar_dados_json("faq.json") or []
    return render_template("faq.html", faq_data=dados)


@app.route("/calendario")
@login_required
def calendario():
    eventos_data = carregar_calendario()
    if not eventos_data:
        flash("Não foi possível carregar os eventos do calendário.", "danger")
    return render_template("calendario.html", eventos_data=eventos_data)


@app.route("/flashcards")
@login_required
def flashcards():
    dados = carregar_dados_json("flashcards.json")
    flashcard_data = {}
    if dados:
        flashcard_data = dados.get("flash_cards", dados)
    if not flashcard_data:
        flash("Não foi possível carregar os flashcards.", "warning")
    return render_template("flashcards.html", flashcard_data=flashcard_data)


@app.route("/foco")
@login_required
def modo_foco():
    """Renderiza a página do Modo Foco (timer)."""
    return render_template("foco.html")


@app.route("/limpar")
@login_required
def limpar_chat():
    """Limpa o histórico do chat da sessão e redireciona para o início."""
    session["historico"] = get_initial_chat_history()
    return redirect(url_for("index"))


@app.route("/metodo_de_estudo")
@login_required
def metodo_de_estudo():
    """Renderiza quiz ou resultado VARK salvo."""
    quiz_data = carregar_quiz_vark()
    saved_vark_result = None

    if current_user.is_authenticated and current_user.vark_primary_type:
        scores = current_user.get_vark_scores()
        if scores:
            saved_vark_result = {
                "primaryType": current_user.vark_primary_type,
                "scores": scores,
            }

    if quiz_data is None:
        flash("Erro ao carregar as perguntas do quiz. Tente novamente.", "danger")
        return render_template(
            "metodo_de_estudo.html",
            quiz_data=None,
            error=True,
            saved_vark_result=saved_vark_result,
        )

    return render_template(
        "metodo_de_estudo.html",
        quiz_data=quiz_data,
        saved_vark_result=saved_vark_result,
    )


# =======================================================
# 4. ROTAS DA API (CHAT E SALVAR VARK)
# =======================================================


@app.route("/ask", methods=["POST"])
@login_required
def ask():
    """Recebe perguntas do usuário e retorna respostas do Gemini."""
    if not model:
        return (
            jsonify(
                {"resposta": "Desculpe, o serviço de chat não está configurado."}),
            500,
        )

    data = request.json
    if not data or "pergunta" not in data:
        return jsonify({"resposta": "Nenhuma pergunta recebida."}), 400
    pergunta = data["pergunta"]

    try:
        # Pega o histórico PEQUENO da sessão
        historico_chat = session.get("historico", get_initial_chat_history())

        # Inicia o chat. O 'model' já sabe o CONTEXTO (system_instruction).
        # Nós passamos apenas o histórico da conversa.
        chat = model.start_chat(history=historico_chat)
        response = chat.send_message(pergunta)

        # Adiciona a pergunta e resposta ao histórico PEQUENO
        historico_chat.append({"role": "user", "parts": [pergunta]})
        historico_chat.append({"role": "model", "parts": [response.text]})

        # Salva o histórico PEQUENO de volta na sessão
        session["historico"] = historico_chat

        return jsonify({"resposta": response.text})

    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        traceback.print_exc()
        return (
            jsonify({"resposta": f"Desculpe, ocorreu um erro: {e}"}),
            500,
        )


@app.route("/save_vark_result", methods=["POST"])
@login_required
def save_vark_result():
    """Recebe os resultados do quiz VARK e salva no perfil do usuário."""
    data = request.json
    if not data or "scores" not in data or "primaryType" not in data:
        print(
            f"DEBUG: Dados incompletos recebidos em /save_vark_result: {data}")
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    scores = data["scores"]
    primary_type = data["primaryType"]

    if not isinstance(scores, dict) or not isinstance(primary_type, str):
        print(
            f"DEBUG: Tipos de dados inválidos: {type(scores)}, {type(primary_type)}")
        return jsonify({"success": False, "message": "Tipos de dados inválidos."}), 400
    if not all(k in scores and isinstance(scores[k], int) for k in ["V", "A", "R", "K"]):
        return jsonify({"success": False, "message": "Formato de scores inválido."}), 400
    if not primary_type or len(primary_type) > 10:
        return jsonify({"success": False, "message": "Tipo primário inválido."}), 400

    try:
        user = current_user
        user.vark_scores_json = json.dumps(scores)
        user.vark_primary_type = primary_type
        db.session.commit()
        return (
            jsonify({"success": True, "message": "Resultado salvo com sucesso."}),
            200,
        )
    except Exception as e:
        db.session.rollback()
        print(
            f"ERRO ao salvar resultado VARK para user {current_user.id}: {e}")
        traceback.print_exc()
        return (
            jsonify({"success": False, "message": f"Erro interno do servidor: {e}"}),
            500,
        )


# =======================================================
# 5. FILTRO JINJA (para formatar data no template)
# =======================================================
@app.template_filter("format_date_br")
def format_date_br_filter(value):
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value


# =======================================================
# 6. EXECUÇÃO DO SERVIDOR E CRIAÇÃO DO BD
# =======================================================
if __name__ == "__main__":
    if GEMINI_API_KEY is None:
        print("Servidor Flask NÃO foi iniciado. Verifique o erro da API Key acima.")
    else:
        with app.app_context():
            print("Criando tabelas do banco de dados (se não existirem)...")
            db.create_all()
            print("Tabelas prontas.")

        print("Iniciando servidor Flask em http://127.0.0.1:5000")
        app.run(debug=True, host="0.0.0.0", port=5000)
