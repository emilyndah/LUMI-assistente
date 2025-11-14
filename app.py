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
import logging
from dotenv import load_dotenv

# ===== ADIÇÕES PARA O SIMULADOR =====
import uuid
import random
from math import floor
from datetime import datetime, timedelta, timezone
# ===== FIM ADIÇÕES =====

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
DATABASE_URL = os.getenv("DATABASE_URL")
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
        print("v2 - Banco de dados e tabelas criados com sucesso.")


# Configuração Flask-Login
login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    if user_id is not None:
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            print(f"DEBUG: Invalid user_id format in session: {user_id}")
            return None
    return None


login_manager.init_app(app)
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


# ===== MODELOS DO SIMULADOR (adição cirúrgica) =====
class Attempt(db.Model):
    __tablename__ = "attempts"
    id = db.Column(db.String(36), primary_key=True)  # uuid4
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # armazenamos naive (UTC) por compatibilidade
    started_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    # novo: horário real de finalização
    finished_at = db.Column(db.DateTime, nullable=True)
    duration_min = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="active")  # active|finished
    seed = db.Column(db.Integer, nullable=False)
    disciplines_json = db.Column(db.Text, nullable=False)  # ["disc1","disc2",...]
    questions_snapshot = db.Column(
        db.Text, nullable=False
    )  # [{id,stem,options,correct,index,...}]


class AttemptAnswer(db.Model):
    __tablename__ = "attempt_answers"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attempt_id = db.Column(
        db.String(36), db.ForeignKey("attempts.id"), nullable=False, index=True
    )
    question_id = db.Column(db.String(64), nullable=False)
    option = db.Column(db.String(2), nullable=False)  # "A"-"E"
    is_correct = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


# ===== FIM MODELOS SIMULADOR =====

# =======================================================
# 1. CONSTANTES E CONFIGURAÇÃO DO GEMINI
# =======================================================
GEMINI_API_KEY = None
model = None
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    print("=" * 80)
    print("ERRO: Variável de ambiente GEMINI_API_KEY não encontrada.")
    print("Por favor, crie um arquivo .env e adicione a linha:")
    print("GEMINI_API_KEY=SUA_CHAVE_AQUI")
    print("=" * 80)

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
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
    from datetime import datetime as _dt  # evitar conflito com helpers

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
        print("AVISO: calendario.json possui formato inválido. Esperada lista de eventos.")
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
            data_inicio_obj = _dt.strptime(data_inicio, "%Y-%m-%d")
        except ValueError:
            print(f"AVISO: Data de início inválida ignorada: {data_inicio}")
            continue

        data_fim_iso = None
        if data_fim:
            try:
                data_fim_iso = _dt.strptime(data_fim, "%Y-%m-%d").strftime("%Y-%m-%d")
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
        print("AVISO: matriz.json em formato antigo (objeto único). Convertendo para lista.")
        return [dados]
    else:
        print("AVISO: Falha ao carregar ou formato inválido para matriz.json.")
        return None


def carregar_quiz_vark():
    """Carrega dados do quiz VARK."""
    return carregar_dados_json("metodo_estudo.json")


def carregar_contexto_inicial():
    """Carrega o contexto base e adiciona dados do calendário, matriz e métodos de estudo."""
    from datetime import datetime as _dt

    contexto_base = ""
    contexto_calendario = ""
    contexto_matriz = ""
    contexto_vark = ""

    # 1. Contexto principal
    try:
        with open("informacoes.txt", "r", encoding="utf-8") as f:
            contexto_base = f.read()
    except FileNotFoundError:
        print("Aviso: 'informacoes.txt' não encontrado. O chatbot pode não ter contexto.")
        contexto_base = (
            "Você é um assistente acadêmico chamado Lumi, focado em ajudar alunos da UniEVANGÉLICA."
        )
    except Exception as e:
        print(f"Erro ao ler 'informacoes.txt': {e}")
        contexto_base = "Você é um assistente acadêmico chamado Lumi."

    # 2. Calendário
    try:
        eventos = carregar_calendario()
        if eventos:
            contexto_calendario = (
                "\n\n=== CALENDÁRIO ACADÊMICO (Use para responder perguntas sobre datas) ===\n"
            )
            for evento in eventos:
                data_str = evento.get("data")
                desc = evento.get("evento")
                data_fim_str = ""
                if evento.get("data_fim") and evento.get("data_fim") != evento.get(
                    "data_iso"
                ):
                    try:
                        data_fim_obj = _dt.strptime(evento["data_fim"], "%Y-%m-%d")
                        data_fim_str = f" até {data_fim_obj.strftime('%d/%m/%Y')}"
                    except ValueError:
                        pass
                contexto_calendario += f"- Em {data_str}{data_fim_str}: {desc}\n"
            contexto_calendario += (
                "======================================================================\n"
            )
    except Exception as e:
        print(f"ERRO ao processar calendário para o contexto: {e}")
        traceback.print_exc()

    # 3. Matriz Curricular
    try:
        matriz_data = carregar_matriz()
        if matriz_data:
            contexto_matriz = "\n\n=== MATRIZ CURRICULAR (Use para responder sobre aulas, professores, horários e salas) ===\n"
            for periodo_info in matriz_data:
                periodo_nome = periodo_info.get("periodo", "Período Não Identificado")
                contexto_matriz += f"\n--- Período {periodo_nome} ---\n"
                disciplinas = periodo_info.get("disciplinas", [])
                if not disciplinas:
                    contexto_matriz += (
                        "(Nenhuma disciplina listada para este período)\n"
                    )

                for disc in disciplinas:
                    nome = disc.get("nome", "Sem nome")
                    prof = disc.get("professor", "A definir")
                    dia = disc.get("dia", "A definir")
                    horario = disc.get("horario", "A definir")
                    sala = disc.get("sala", "A definir")

                    contexto_matriz += f"- Disciplina: {nome}\n"
                    contexto_matriz += f"  Professor: {prof}\n"
                    contexto_matriz += f"  Horário: {dia}, {horario}\n"
                    contexto_matriz += f"  Sala: {sala}\n\n"

            contexto_matriz += (
                "======================================================================\n"
            )
    except Exception as e:
        print(f"ERRO ao processar matriz para o contexto: {e}")
        traceback.print_exc()

    # 4. Métodos de Estudo (VARK)
    try:
        vark_data = carregar_quiz_vark()
        resultados_vark = (vark_data or {}).get("resultados")
        if resultados_vark:
            contexto_vark = (
                "\n\n=== MÉTODOS DE ESTUDO (Use para explicar os estilos VARK) ===\n"
            )
            for tipo, info in resultados_vark.items():
                titulo = info.get("titulo", tipo)
                desc = info.get("descricao", "Sem descrição.")
                metodos = info.get("metodos", [])

                contexto_vark += f"\n--- {titulo} ({tipo}) ---\n"
                contexto_vark += f"{desc}\n"
                contexto_vark += "Métodos sugeridos:\n"
                for m in metodos:
                    contexto_vark += f"  - {m}\n"

            contexto_vark += (
                "======================================================================\n"
            )
    except Exception as e:
        print(f"ERRO ao processar VARK para o contexto: {e}")
        traceback.print_exc()

    return contexto_base + contexto_calendario + contexto_matriz + contexto_vark


# A variável CONTEXTO_INICIAL é recarregada aqui
CONTEXTO_INICIAL = carregar_contexto_inicial()

# =======================================================
# 1.5. INICIALIZAÇÃO DO MODELO GEMINI (COM CONTEXTO)
# =======================================================
if GEMINI_API_KEY:
    try:
        model = genai.GenerativeModel(
            "gemini-2.5-flash", system_instruction=CONTEXTO_INICIAL
        )
        print("✅ Modelo Gemini inicializado com system_instruction (contexto completo).")
    except Exception as e:
        print(f"❌ Erro ao inicializar o modelo Gemini: {e}")
        GEMINI_API_KEY = None
else:
    print("⚠️ API Key não encontrada. O Chatbot não funcionará.")

# =======================================================
# Helpers de tempo (UTC aware + horário padrão)
# =======================================================
def _utcnow():
    return datetime.now(timezone.utc)


def _to_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        # trata registros antigos/naive como UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# fuso horário padrão (Horário de Brasília: UTC-3)
DEFAULT_TZ = timezone(timedelta(hours=-3))


def _to_local(dt):
    """Converte datetime armazenado (naive UTC ou aware) para fuso padrão."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(DEFAULT_TZ)


def _fmt_local(dt):
    """Formata datetime no fuso padrão como ISO sem offset (YYYY-MM-DDTHH:MM:SS)."""
    local = _to_local(dt)
    if local is None:
        return None
    return local.replace(tzinfo=None).isoformat(timespec="seconds")


# =======================================================
# 3. ROTAS PRINCIPAIS (LOGIN, PÁGINAS, ETC.)
# =======================================================
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
            new_user = User(email=email, username=username, matricula=matricula)
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
            (getattr(User, "email") == identifier)
            | (getattr(User, "matricula") == identifier)
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
            jsonify({"resposta": "Desculpe, o serviço de chat não está configurado."}),
            500,
        )

    data = request.json
    if not data or "pergunta" not in data:
        return jsonify({"resposta": "Nenhuma pergunta recebida."}), 400
    pergunta = data["pergunta"]

    try:
        historico_chat = session.get("historico", get_initial_chat_history())
        chat = model.start_chat(history=historico_chat)
        response = chat.send_message(pergunta)

        historico_chat.append({"role": "user", "parts": [pergunta]})
        historico_chat.append({"role": "model", "parts": [response.text]})
        session["historico"] = historico_chat

        return jsonify({"resposta": response.text})

    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        traceback.print_exc()
        return (jsonify({"resposta": f"Desculpe, ocorreu um erro: {e}"}), 500)


@app.route("/save_vark_result", methods=["POST"])
@login_required
def save_vark_result():
    """Recebe os resultados do quiz VARK e salva no perfil do usuário."""
    data = request.json
    if not data or "scores" not in data or "primaryType" not in data:
        print(f"DEBUG: Dados incompletos recebidos em /save_vark_result: {data}")
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    scores = data["scores"]
    primary_type = data["primaryType"]

    if not isinstance(scores, dict) or not isinstance(primary_type, str):
        print(
            f"DEBUG: Tipos de dados inválidos: {type(scores)}, {type(primary_type)}"
        )
        return jsonify({"success": False, "message": "Tipos de dados inválidos."}), 400
    if not all(k in scores and isinstance(scores[k], int) for k in ["V", "A", "R", "K"]):
        return (
            jsonify({"success": False, "message": "Formato de scores inválido."}),
            400,
        )
    if not primary_type or len(primary_type) > 10:
        return (
            jsonify({"success": False, "message": "Tipo primário inválido."}),
            400,
        )

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
        print(f"ERRO ao salvar resultado VARK para user {current_user.id}: {e}")
        traceback.print_exc()
        return (
            jsonify(
                {"success": False, "message": f"Erro interno do servidor: {e}"}
            ),
            500,
        )


# =======================================================
# 4.1. SIMULADOR DE PROVAS (ATUALIZADO PARA policy+pools + modos)
# =======================================================
SIM_POLICY = {
    "mode": "global",
    "min_questions_total": 12,
    "max_questions_total": 40,  # teto global (Simulado pode ir até 40)
    "default_questions_total": 16,
    "selection_method": "random_without_replacement",
    "shuffle_options": True,
    "seed_per_attempt": "attempt_id",
    "time": {
        "validate_server_started_at": True,
        "auto_finish_on_timeout": True,
        "allowed_duration_minutes": [15, 30, 45, 60, 90, 120, 150, 180],
    },
    "integrity": {
        "hide_answer_key_until_finish": True,
        "lock_after_finish": True,
        "prevent_double_submit": True,
    },
}


def carregar_pool_simulador():
    raw = carregar_dados_json("simulador_de_provas.json") or {}
    policy = raw.get("policy") or {}
    pools = raw.get("pools") or []

    disciplinas = []
    for p in pools:
        nome = p.get("discipline") or p.get("nome") or "Sem nome"
        qs = p.get("questions") or []
        qs_norm = []
        for q in qs:
            if not isinstance(q, dict):
                continue
            if (
                not q.get("id")
                or not q.get("stem")
                or not q.get("options")
                or not q.get("correct")
            ):
                continue
            qs_norm.append(
                {
                    "id": str(q["id"]),
                    "stem": str(q["stem"]),
                    "options": dict(q["options"]),
                    "correct": str(q["correct"]).strip().upper(),
                }
            )
        disciplinas.append({"nome": nome, "questions": qs_norm})

    # merge policy
    global SIM_POLICY

    def deep_merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                deep_merge(dst[k], v)
            else:
                dst[k] = v
        return dst

    SIM_POLICY = deep_merge(SIM_POLICY, policy)

    return {"disciplinas": disciplinas, "policy": SIM_POLICY}


POOL_SIMULADOR = carregar_pool_simulador()


def obter_todas_disciplinas():
    return POOL_SIMULADOR.get("disciplinas", [])


def coletar_disciplinas_validas(nomes):
    nomes_set = set(nomes or [])
    return [
        d for d in POOL_SIMULADOR.get("disciplinas", []) if d.get("nome") in nomes_set
    ]


def embaralhar_alternativas(q, rng, do_shuffle=True):
    options = q.get("options") or {}
    if not do_shuffle:
        return {
            "id": q.get("id"),
            "stem": q.get("stem"),
            "options": options,
            "correct": q.get("correct"),
        }

    pairs = list(options.items())
    rng.shuffle(pairs)
    letters = ["A", "B", "C", "D", "E"]
    options_out, new_correct = {}, None
    for i, (orig_letter, text) in enumerate(pairs):
        L = letters[i]
        options_out[L] = text
        if str(orig_letter).upper() == str(q.get("correct")).upper():
            new_correct = L
    return {
        "id": q.get("id"),
        "stem": q.get("stem"),
        "options": options_out,
        "correct": new_correct,
    }


def _alloc_even(disciplinas, total):
    k = len(disciplinas)
    base = total // k
    resto = total - base * k
    alloc = [base + (1 if i < resto else 0) for i in range(k)]
    return alloc


def _alloc_auto(disciplinas, total):
    sizes = [len(d.get("questions", [])) for d in disciplinas]
    S = sum(sizes) or 1
    raw = [total * s / S for s in sizes]
    alloc = [floor(x) for x in raw]
    rest = total - sum(alloc)
    fracs = sorted(
        [(raw[i] - alloc[i], i) for i in range(len(disciplinas))], reverse=True
    )
    for _, i in fracs[:rest]:
        alloc[i] += 1
    spill = 0
    for i, a in enumerate(alloc):
        cap = sizes[i]
        if a > cap:
            spill += a - cap
            alloc[i] = cap
    if spill:
        for i in sorted(
            range(len(disciplinas)), key=lambda j: (sizes[j] - alloc[j]), reverse=True
        ):
            if spill == 0:
                break
            room = sizes[i] - alloc[i]
            if room <= 0:
                continue
            take = min(room, spill)
            alloc[i] += take
            spill -= take
    return alloc


def montar_lista_questoes(
    disciplinas_escolhidas, total, rng, distribution, selection_method, shuffle_opts
):
    if not disciplinas_escolhidas:
        return []

    if distribution == "even":
        alloc = _alloc_even(disciplinas_escolhidas, total)
    else:
        alloc = _alloc_auto(disciplinas_escolhidas, total)

    selecionadas = []
    for disc, qtd in zip(disciplinas_escolhidas, alloc):
        pool = list(disc.get("questions", []))
        rng.shuffle(pool)
        if selection_method == "random_without_replacement":
            slice_qs = pool[:qtd]
        else:
            slice_qs = pool[:qtd]
        selecionadas.extend(slice_qs)

    if len(selecionadas) < total:
        faltam = total - len(selecionadas)
        resto_pool = []
        for disc, qtd in zip(disciplinas_escolhidas, alloc):
            pool = list(disc.get("questions", []))
            sobra = pool[qtd:]
            resto_pool.extend(sobra)
        rng.shuffle(resto_pool)
        selecionadas.extend(resto_pool[:faltam])

    selecionadas = selecionadas[:total]
    rng.shuffle(selecionadas)

    final = []
    for idx, q in enumerate(selecionadas):
        q2 = embaralhar_alternativas(q, rng, do_shuffle=bool(shuffle_opts))
        q2["index"] = idx
        final.append(q2)
    return final


def sanitize_int(v, default):
    try:
        return int(v)
    except Exception:
        return default


def _validate_total(total):
    mn = int(SIM_POLICY.get("min_questions_total", 12))
    mx = int(SIM_POLICY.get("max_questions_total", 40))
    if total < mn or total > mx:
        return False, f"Total de questões deve estar entre {mn} e {mx}."
    return True, None


def _validate_duration(dur):
    allowed = SIM_POLICY.get("time", {}).get("allowed_duration_minutes") or [
        15,
        30,
        45,
        60,
        90,
        120,
        150,
        180,
    ]
    if dur not in allowed:
        return False, f"Duração inválida. Permitidos: {allowed}."
    return True, None


# ---- Rotas do simulador ----
@app.route("/simulador_de_provas")
@login_required
def simulador_de_provas():
    return render_template(
        "simulador_de_provas.html", current_year=_utcnow().year
    )


@app.route("/simulados", methods=["GET"])
@login_required
def list_attempts():
    atts = (
        Attempt.query.filter_by(user_id=current_user.id)
        .order_by(Attempt.started_at.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": a.id,
                "status": a.status,
                "total": a.total,
                "duration_min": a.duration_min,
                "started_at": _fmt_local(a.started_at),
                # fim mostrado: horário real se existir, senão o limite
                "ends_at": _fmt_local(a.finished_at or a.ends_at),
            }
            for a in atts
        ]
    )


@app.route("/simulados", methods=["POST"])
@login_required
def create_attempt():
    data = request.json or {}

    # modo de geração
    mode = (data.get("mode") or "simulado").strip().lower()
    if mode not in {"simulado", "prova"}:
        mode = "simulado"

    nomes = data.get("disciplinas", []) or data.get("subjects", [])
    default_total = int(SIM_POLICY.get("default_questions_total", 16))
    total_req = sanitize_int(data.get("total") or data.get("total_qtd"), default_total)

    # limite específico do modo: prova cap 36, simulado respeita policy global (até 40)
    if mode == "prova" and total_req > 36:
        total_req = 36

    ok, msg = _validate_total(total_req)
    if not ok:
        return jsonify({"resposta": msg}), 400

    duration_req = sanitize_int(
        data.get("duration") or data.get("duracao_min"), 60
    )
    ok, msg = _validate_duration(duration_req)
    if not ok:
        return jsonify({"resposta": msg}), 400

    distribution = (data.get("distribution") or "auto").lower()
    if distribution not in {"auto", "even"}:
        distribution = "auto"

    if mode == "simulado":
        ds = obter_todas_disciplinas()
        if len(ds) == 0:
            return jsonify({"resposta": "Não há disciplinas disponíveis no pool."}), 400
        selected_names = [d.get("nome") for d in ds]
    else:  # "prova"
        if not isinstance(nomes, list) or len(nomes) != 1:
            return (
                jsonify(
                    {"resposta": "Para 'prova', selecione exatamente uma disciplina."}
                ),
                400,
            )
        ds = coletar_disciplinas_validas(nomes)
        if len(ds) != 1:
            return jsonify({"resposta": "Disciplina inválida."}), 400
        selected_names = [ds[0].get("nome")]

    # cria id antes para seed
    aid = str(uuid.uuid4())

    seed_policy = (SIM_POLICY.get("seed_per_attempt") or "attempt_id").lower()
    if seed_policy == "attempt_id":
        seed = int(uuid.UUID(aid)) & 0x7FFFFFFF
    else:
        seed = random.randint(1, 2**31 - 1)

    rng = random.Random(seed)
    selection_method = SIM_POLICY.get(
        "selection_method", "random_without_replacement"
    )
    shuffle_opts = bool(SIM_POLICY.get("shuffle_options", True))

    quest_list = montar_lista_questoes(
        disciplinas_escolhidas=ds,
        total=total_req,
        rng=rng,
        distribution=distribution,
        selection_method=selection_method,
        shuffle_opts=shuffle_opts,
    )

    if len(quest_list) < total_req:
        return (
            jsonify({"resposta": "Pool insuficiente para o total solicitado."}),
            400,
        )

    snapshot = json.dumps(quest_list, ensure_ascii=False)
    now = _utcnow()
    ends = now + timedelta(minutes=duration_req)

    att = Attempt(
        id=aid,
        user_id=current_user.id,
        started_at=now.replace(tzinfo=None),  # armazenamos naive UTC
        ends_at=ends.replace(tzinfo=None),
        finished_at=None,
        duration_min=duration_req,
        total=total_req,
        status="active",
        seed=seed,
        disciplines_json=json.dumps(selected_names, ensure_ascii=False),
        questions_snapshot=snapshot,
    )
    db.session.add(att)
    db.session.commit()

    pub_questions = [
        {"id": q["id"], "index": i, "stem": q["stem"], "options": q["options"]}
        for i, q in enumerate(quest_list)
    ]
    order = list(range(len(pub_questions)))

    return jsonify(
        {
            "id": aid,
            "mode": mode,
            "subjects": selected_names,
            "started_at": _fmt_local(att.started_at),
            "ends_at": _fmt_local(att.ends_at),
            "duration_min": duration_req,
            "status": "active",
            "order": order,
            "questions": pub_questions,
            "policy": {
                "hide_answer_key_until_finish": bool(
                    SIM_POLICY.get("integrity", {}).get(
                        "hide_answer_key_until_finish", True
                    )
                ),
                "lock_after_finish": bool(
                    SIM_POLICY.get("integrity", {}).get("lock_after_finish", True)
                ),
            },
        }
    )


@app.route("/simulados/<attempt_id>", methods=["GET"])
@login_required
def get_attempt(attempt_id):
    att = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first()
    if not att:
        return jsonify({"resposta": "Tentativa não encontrada."}), 404

    try:
        qs = json.loads(att.questions_snapshot)
    except Exception:
        qs = []

    answers = AttemptAnswer.query.filter_by(attempt_id=att.id).all()
    ans_map = {a.question_id: a.option for a in answers}

    pub_questions = []
    for i, q in enumerate(qs):
        pub_questions.append(
            {
                "id": q["id"],
                "index": q.get("index", i),
                "stem": q["stem"],
                "options": q["options"],
            }
        )

    return jsonify(
        {
            "id": att.id,
            "started_at": _fmt_local(att.started_at),
            "ends_at": _fmt_local(att.finished_at or att.ends_at),
            "duration_min": att.duration_min,
            "status": att.status,
            "order": list(range(len(pub_questions))),
            "questions": pub_questions,
            "answers": ans_map,
        }
    )


@app.route("/simulados/<attempt_id>/answer", methods=["POST"])
@login_required
def answer_attempt(attempt_id):
    data = request.json or {}
    qid = str(data.get("question_id"))
    opt = (
        str(data.get("option")).upper().strip()
        if data.get("option") is not None
        else None
    )

    if not qid or opt not in {"A", "B", "C", "D", "E"}:
        return jsonify({"resposta": "Parâmetros inválidos."}), 400

    att = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first()
    if not att:
        return jsonify({"resposta": "Tentativa não encontrada."}), 404
    if att.status != "active":
        return jsonify({"resposta": "Tentativa já finalizada."}), 400

    # valida timeout com datetimes aware
    if bool(SIM_POLICY.get("time", {}).get("validate_server_started_at", True)):
        now = _utcnow()
        if now > _to_utc(att.ends_at):
            if bool(SIM_POLICY.get("time", {}).get("auto_finish_on_timeout", True)):
                att.status = "finished"
                att.finished_at = now.replace(tzinfo=None)
                db.session.commit()
            return jsonify({"resposta": "Tempo esgotado. Tentativa encerrada."}), 400

    try:
        qs = json.loads(att.questions_snapshot)
    except Exception:
        return jsonify({"resposta": "Falha no snapshot da tentativa."}), 500

    qmap = {q["id"]: q for q in qs}
    if qid not in qmap:
        return jsonify({"resposta": "Questão inválida para esta tentativa."}), 400

    correct = qmap[qid]["correct"]
    is_correct = opt == correct

    existing = AttemptAnswer.query.filter_by(
        attempt_id=att.id, question_id=qid
    ).first()
    if existing:
        existing.option = opt
        existing.is_correct = is_correct
    else:
        db.session.add(
            AttemptAnswer(
                attempt_id=att.id, question_id=qid, option=opt, is_correct=is_correct
            )
        )
    db.session.commit()
    return jsonify({"ok": True})


# -------- Helper para relatório (usado em finish e report) --------
def _build_attempt_report(att, now_utc=None):
    try:
        qs = json.loads(att.questions_snapshot)
    except Exception:
        qs = []

    answers = AttemptAnswer.query.filter_by(attempt_id=att.id).all()
    ans_map = {a.question_id: a.option for a in answers}
    correct_map = {q["id"]: q["correct"] for q in qs}

    correct_count = 0
    report = []
    for q in qs:
        your = ans_map.get(q["id"])
        corr = correct_map.get(q["id"])
        if your and corr and your == corr:
            correct_count += 1
        report.append(
            {
                "id": q["id"],
                "stem": q["stem"],
                "your": your if your else "—",
                "correct": corr,
                "review_url": None,
            }
        )

    total = att.total
    score = (correct_count / total) * 100 if total else 0.0

    started_utc = _to_utc(att.started_at)
    ends_utc = _to_utc(att.ends_at)
    finished_utc = _to_utc(att.finished_at) if att.finished_at else None

    # se não vier "agora", usa horário real de fim (se existir)
    if now_utc is None:
        now_utc = finished_utc or _utcnow()

    effective_end = finished_utc or now_utc
    spent_seconds = int((min(effective_end, ends_utc) - started_utc).total_seconds())

    return {
        "score": round(score, 2),
        "correct_count": correct_count,
        "total": total,
        "spent_seconds": spent_seconds,
        "report": report,
    }


@app.route("/simulados/<attempt_id>/finish", methods=["POST"])
@login_required
def finish_attempt(attempt_id):
    att = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first()
    if not att:
        return jsonify({"resposta": "Tentativa não encontrada."}), 404
    if att.status == "finished":
        return jsonify({"resposta": "Tentativa já finalizada."}), 400

    now = _utcnow()
    att.status = "finished"
    att.finished_at = now.replace(tzinfo=None)
    db.session.commit()

    payload = _build_attempt_report(att, now_utc=now)
    return jsonify(payload)


@app.route("/simulados/<attempt_id>/report", methods=["GET"])
@login_required
def report_attempt(attempt_id):
    """Retorna o relatório de uma tentativa já finalizada (para o histórico)."""
    att = Attempt.query.filter_by(id=attempt_id, user_id=current_user.id).first()
    if not att:
        return jsonify({"resposta": "Tentativa não encontrada."}), 404
    if att.status != "finished":
        return jsonify({"resposta": "Tentativa ainda não foi finalizada."}), 400

    payload = _build_attempt_report(att)
    return jsonify(payload)


# =======================================================
# 5. FILTRO JINJA (para formatar data no template)
# =======================================================
@app.template_filter("format_date_br")
def format_date_br_filter(value):
    if not value:
        return ""
    try:
        from datetime import datetime as _dt

        return _dt.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
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
