# =======================================================
# TÍTULO: SERVIDOR FLASK (APP.PY) - ASSISTENTE LUMI
# (Login, BD, Salvar VARK, Quiz JSON, Calendário JSON, Matriz JSON)
# =======================================================

# =======================================================
# IMPORTAÇÕES
# =======================================================
import json
import os
import traceback
from datetime import datetime
import logging
from dotenv import load_dotenv
import uuid
import psycopg2  # pode ficar aqui para uso futuro (Render/Postgres)

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
from werkzeug.utils import secure_filename

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

# --- Banco de Dados ---
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Se vier postgres:// (Render), converte para postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        os.path.dirname(__file__), "lumi_database.db"
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Uploads ---
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.cli.command("db-create-all")
def db_create_all():
    """Cria as tabelas do banco de dados (usado pelo Render ou local)."""
    with app.app_context():
        db.create_all()
        print("Banco de dados e tabelas criados com sucesso.")


# Configuração Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Você precisa fazer login para acessar esta página."
login_manager.login_message_category = "warning"


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


# =======================================================
# MODELOS
# =======================================================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    # 'username' é o nome completo
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    matricula = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    cpf = db.Column(db.String(14), unique=True, nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    sexo = db.Column(db.String(30), nullable=True)  # Gênero
    etnia = db.Column(db.String(50), nullable=True)

    vark_scores_json = db.Column(db.Text, nullable=True)
    vark_primary_type = db.Column(db.String(10), nullable=True)

    # Imagem de perfil com default
    profile_image = db.Column(
        db.String(100), nullable=False, default="lumi-2.png"
    )

    def get_vark_scores(self):
        if not self.vark_scores_json:
            return None
        try:
            return json.loads(self.vark_scores_json)
        except json.JSONDecodeError:
            return None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __init__(
        self,
        nome_completo,
        email,
        matricula,
        password=None,
        cpf=None,
        telefone=None,
        genero=None,
        etnia=None,
    ):
        self.username = nome_completo
        self.email = email
        self.matricula = matricula
        if password:
            self.set_password(password)

        self.cpf = cpf
        self.telefone = telefone
        self.sexo = genero
        self.etnia = etnia


class UserFlashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    materia = db.Column(db.String(100), nullable=False)  # Nome do "Deck"
    pergunta = db.Column(db.String(300), nullable=False)
    resposta = db.Column(db.String(500), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "pergunta": self.pergunta,
            "resposta": self.resposta,
            "materia": self.materia,
        }


class ChatHistory(db.Model):
    """Histórico de mensagens do chat, salvo no banco (não na sessão)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # "user" ou "model"
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


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
# FUNÇÕES AUXILIARES DE JSON
# =======================================================
def carregar_dados_json(arquivo):
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


def salvar_dados_json(arquivo, dados):
    try:
        caminho_arquivo = os.path.join(os.path.dirname(__file__), arquivo)
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"ERRO: Falha ao salvar JSON em {arquivo}. Detalhe: {e}")
        traceback.print_exc()
        return False


def carregar_calendario():
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
        event_id = item.get("id", str(uuid.uuid4()))
        event_type = item.get("type", "Outro")
        event_description = item.get("description", "")

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
                data_fim_iso = datetime.strptime(
                    data_fim, "%Y-%m-%d"
                ).strftime("%Y-%m-%d")
            except ValueError:
                print(f"AVISO: Data final inválida ignorada: {data_fim}")

        eventos.append(
            {
                "id": event_id,
                "title": descricao,
                "date": data_inicio,
                "type": event_type,
                "description": event_description,
                "data_obj": data_inicio_obj,
                "data_fim": data_fim_iso,
                "mes_curto": meses_map.get(data_inicio_obj.month),
            }
        )
    return sorted(eventos, key=lambda x: x["data_obj"])


def carregar_matriz():
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
    return carregar_dados_json("metodo_estudo.json")
def carregar_contexto_inicial():
    contexto_base = ""
    contexto_calendario = ""
    contexto_matriz = ""
    contexto_vark = ""

    # 1. informacoes.txt
    try:
        with open("informacoes.txt", "r", encoding="utf-8") as f:
            contexto_base = f.read()
    except FileNotFoundError:
        print("Aviso: 'informacoes.txt' não encontrado.")
        contexto_base = "Você é um assistente acadêmico chamado Lumi, focado em ajudar alunos da UniEVANGÉLICA."
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
                data_str = evento.get("data_obj").strftime("%d/%m/%Y")
                desc = evento.get("title")
                data_fim_str = ""
                if evento.get("data_fim") and evento.get("data_fim") != evento.get(
                    "date"
                ):
                    try:
                        data_fim_obj = datetime.strptime(
                            evento["data_fim"], "%Y-%m-%d"
                        )
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

    # 3. Matriz
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

    # 4. VARK
    try:
        vark_data = carregar_quiz_vark()
        if vark_data:
            resultados_vark = vark_data.get("resultados")
        else:
            resultados_vark = None

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


CONTEXTO_INICIAL = carregar_contexto_inicial()

# =======================================================
# GEMINI - INICIALIZAÇÃO ÚNICA
# =======================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Aqui já usamos o contexto completo como system_instruction
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=CONTEXTO_INICIAL,
        )
        print("✅ Modelo Gemini inicializado com system_instruction.")
    except Exception as e:
        print(f"❌ Erro ao inicializar o modelo Gemini: {e}")
        model = None
else:
    print("⚠️ API Key do Gemini não encontrada. O Chatbot não funcionará.")


# =======================================================
# FUNÇÕES DE HISTÓRICO
# =======================================================
def get_initial_chat_history():
    """Mensagem inicial padrão do chat (modelo)."""
    return [
        {
            "role": "model",
            "parts": [
                "Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje? 💡"
            ],
        }
    ]


def carregar_historico_usuario(user_id):
    """Retorna uma lista de mensagens no formato esperado pelo Gemini."""
    historico = ChatHistory.query.filter_by(user_id=user_id).order_by(ChatHistory.timestamp).all()
    return [
        {"role": h.role, "parts": [h.content]}
        for h in historico
    ]


def salvar_mensagem_no_banco(user_id, role, content):
    """Salva uma mensagem no histórico do usuário."""
    nova_msg = ChatHistory(user_id=user_id, role=role, content=content)
    db.session.add(nova_msg)
    db.session.commit()


# =======================================================
# ROTAS DE AUTENTICAÇÃO
# =======================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email")
        nome_completo = request.form.get("username")
        matricula = request.form.get("matricula")
        password = request.form.get("password")
        cpf = request.form.get("cpf")
        telefone = request.form.get("telefone")
        genero = request.form.get("sexo")
        etnia = request.form.get("etnia")

        user_by_email = User.query.filter_by(email=email).first()
        user_by_matricula = User.query.filter_by(matricula=matricula).first()
        user_by_cpf = User.query.filter_by(cpf=cpf).first()

        if user_by_email:
            flash("Este e-mail já está cadastrado. Tente fazer login.", "warning")
            return redirect(url_for("login"))
        if user_by_matricula:
            flash("Esta matrícula já está cadastrada. Tente fazer login.", "warning")
            return redirect(url_for("login"))
        if user_by_cpf:
            flash("Este CPF já está cadastrado. Tente fazer login.", "warning")
            return redirect(url_for("login"))

        try:
            new_user = User(
                email=email,
                nome_completo=nome_completo,
                matricula=matricula,
                cpf=cpf,
                telefone=telefone,
                genero=genero,
                etnia=etnia,
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
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        identifier = request.form.get("login_identifier")
        password = request.form.get("password")
        user = User.query.filter(
            (User.email == identifier)
            | (User.matricula == identifier)
            | (User.cpf == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("index"))
        else:
            flash(
                "Email/Matrícula/CPF ou senha inválidos. Tente novamente.", "danger"
            )

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você foi desconectado.", "info")
    return redirect(url_for("login"))


# =======================================================
# ROTAS DE PÁGINA
# =======================================================
@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/chat")
@login_required
def chat():
    # Garante que o histórico inicial existe no banco para este usuário
    historico_existente = ChatHistory.query.filter_by(user_id=current_user.id).first()
    if not historico_existente:
        # salva a mensagem inicial padrão no banco
        salvar_mensagem_no_banco(
            current_user.id,
            "model",
            "Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje? 💡"
        )
    return render_template("chat.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user

    if request.method == "POST":
        try:
            # Upload da imagem
            if "profile_pic" in request.files:
                file = request.files["profile_pic"]
                if file and file.filename != "" and allowed_file(file.filename):
                    extension = file.filename.rsplit(".", 1)[1].lower()
                    unique_filename = f"{uuid.uuid4()}.{extension}"
                    save_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], unique_filename
                    )
                    file.save(save_path)

                    if user.profile_image != "lumi-2.png":
                        old_path = os.path.join(
                            app.config["UPLOAD_FOLDER"], user.profile_image
                        )
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception as e:
                                print(
                                    f"Aviso: Não foi possível remover o arquivo antigo: {e}"
                                )

                    user.profile_image = unique_filename

            novo_username = request.form.get("nome")
            novo_email = request.form.get("email")
            novo_telefone = request.form.get("telefone")
            novo_sexo = request.form.get("genero")
            novo_etnia = request.form.get("etnia")

            if novo_email != user.email:
                email_existente = User.query.filter_by(email=novo_email).first()
                if email_existente:
                    flash(
                        "Este e-mail já está em uso por outra conta. Tente outro.",
                        "danger",
                    )
                    return redirect(url_for("profile"))

            user.username = novo_username
            user.email = novo_email
            user.telefone = novo_telefone
            user.sexo = novo_sexo
            user.etnia = novo_etnia

            db.session.commit()

            flash("Perfil atualizado com sucesso!", "success")
            return redirect(url_for("profile"))

        except Exception as e:
            db.session.rollback()
            print(f"ERRO ao atualizar perfil: {e}")
            traceback.print_exc()
            flash(f"Ocorreu um erro ao atualizar: {e}", "danger")

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
        flash("Nenhum evento encontrado no calendário.", "info")
    return render_template("calendario.html", eventos_data=eventos_data)


@app.route("/flashcards")
@login_required
def flashcards():
    dados_json = carregar_dados_json("flashcards.json")
    system_decks = {}
    if dados_json:
        system_decks = dados_json.get("flash_cards", dados_json)

    user_cards = UserFlashcard.query.filter_by(user_id=current_user.id).all()
    user_decks = {}
    for card in user_cards:
        if card.materia not in user_decks:
            user_decks[card.materia] = []
        user_decks[card.materia].append(card.to_dict())

    return render_template(
        "flashcards.html",
        system_decks=system_decks,
        user_decks=user_decks,
    )


@app.route("/foco")
@login_required
def modo_foco():
    return render_template("foco.html")


@app.route("/limpar")
@login_required
def limpar_chat():
    # Apaga todo o histórico do usuário
    ChatHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    # Recria a mensagem inicial de boas-vindas
    salvar_mensagem_no_banco(
        current_user.id,
        "model",
        "Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje? 💡"
    )
    return redirect(url_for("chat"))


@app.route("/metodo_de_estudo")
@login_required
def metodo_de_estudo():
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


# ✅ NOVA ROTA: SIMULADOR DE PROVAS
@app.route("/simulador")
@login_required
def simulador():
    simulador_data = carregar_dados_json("simulador.json")
    if simulador_data is None:
        flash("Erro ao carregar o simulado. Verifique o arquivo simulador.json.", "danger")
    return render_template("simulador.html", simulador_data=simulador_data)

@app.route("/simulador/iniciar", methods=["POST"])
@login_required
def simulador_iniciar():
    data_request = request.get_json() or {}
    quantidade_solicitada = data_request.get("quantidade", 10)
    disciplina_escolhida = data_request.get("disciplina", "todas")
    
    data = carregar_dados_json("simulador.json")

    if not data or "pools" not in data:
        return jsonify({"erro": "Arquivo simulador.json inválido."}), 400

    # Filtrar pools por disciplina, se especificada
    if disciplina_escolhida == "todas":
        pools_filtrados = data["pools"]
    else:
        pools_filtrados = []
        for pool in data["pools"]:
            # Verifica se alguma questão no pool tem o prefixo da disciplina
            questoes_pool = pool.get("questions", [])
            if questoes_pool and questoes_pool[0].get("id", "").startswith(disciplina_escolhida):
                pools_filtrados.append(pool)
    
    if not pools_filtrados:
        return jsonify({"erro": "Nenhuma questão encontrada para a disciplina selecionada."}), 400

    # Coletar todas as questões dos pools filtrados
    todas_questoes = []
    for pool in pools_filtrados:
        todas_questoes.extend(pool.get("questions", []))

    if not todas_questoes:
        return jsonify({"erro": "Nenhuma questão encontrada em 'questions'."}), 400

    import random
    # Seleciona a quantidade escolhida pelo usuário
    num_questoes = min(quantidade_solicitada, len(todas_questoes))
    selecionadas = random.sample(todas_questoes, num_questoes)

    # Salva as questões completas na sessão (com gabarito)
    session["simulador_questoes"] = selecionadas

    # Envia ao frontend SEM o gabarito
    questoes_sem_gabarito = []
    for q in selecionadas:
        questoes_sem_gabarito.append({
            "texto": q["stem"],
            "alternativas": q["options"]
        })

    return jsonify({"questoes": questoes_sem_gabarito})

@app.route("/simulador/resultado", methods=["POST"])
@login_required
def simulador_resultado():
    data = request.get_json()
    respostas = data.get("respostas", {})

    questoes = session.get("simulador_questoes", [])

    if not questoes:
        return jsonify({"erro": "Nenhuma questão encontrada na sessão."}), 400

    acertos = 0
    gabarito = []

    for i, q in enumerate(questoes):
        correta = q["correct"]
        # Aceita tanto string "0", "1" quanto int 0, 1
        marcada = respostas.get(str(i)) or respostas.get(i)

        if marcada == correta:
            acertos += 1

        gabarito.append({
            "numero": i + 1,
            "correta": correta
        })

    return jsonify({
        "acertos": acertos,
        "total": len(questoes),
        "gabarito": gabarito
    })
# =======================================================
# API: FLASHCARDS
# =======================================================
@app.route("/add_flashcard", methods=["POST"])
@login_required
def add_flashcard():
    data = request.json
    materia = data.get("materia")
    cards_list = data.get("cards")

    if not materia or not cards_list or len(cards_list) == 0:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Preencha a matéria e adicione pelo menos um card.",
                }
            ),
            400,
        )

    try:
        for card_item in cards_list:
            pergunta = card_item.get("pergunta")
            resposta = card_item.get("resposta")
            if pergunta and resposta:
                novo_card = UserFlashcard(
                    user_id=current_user.id,
                    materia=materia,
                    pergunta=pergunta,
                    resposta=resposta,
                )
                db.session.add(novo_card)

        db.session.commit()
        return jsonify(
            {
                "success": True,
                "message": f"{len(cards_list)} cards criados com sucesso!",
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# =======================================================
# API: CHAT /ask
# =======================================================
@app.route("/ask", methods=["POST"])
@login_required
def ask():
    if model is None:
        return jsonify({"resposta": "Erro: API Key não configurada."}), 500

    dados = request.get_json()
    pergunta_usuario = (dados.get("pergunta") or "").strip()

    if not pergunta_usuario:
        return jsonify({"resposta": "Por favor, digite uma pergunta."}), 400

    # Carrega flashcards do sistema para dar contexto extra
    dados_flashcards = carregar_dados_json("flashcards.json") or {}
    texto_flashcards = json.dumps(dados_flashcards, ensure_ascii=False, indent=2)

    # Carrega histórico do usuário a partir do banco
    historico = carregar_historico_usuario(current_user.id)
    if not historico:
        # Se por algum motivo não houver histórico, cria a mensagem inicial
        salvar_mensagem_no_banco(
            current_user.id,
            "model",
            "Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje? 💡"
        )
        historico = carregar_historico_usuario(current_user.id)

    # Adiciona a mensagem de contexto de flashcards apenas uma vez
    if not any(
        msg.get("role") == "user" and "INÍCIO DOS FLASHCARDS" in "".join(msg["parts"])
        for msg in historico
    ):
        instrucao_flashcards = f"""
Você é a Lumi, uma assistente acadêmica universitária da UniEVANGÉLICA.
Seja prestativa, use emojis de forma equilibrada e fale de forma motivadora.
Responda sempre em Português do Brasil.
Use formatação Markdown (negrito, listas) para organizar a resposta.

IMPORTANTE: Você tem acesso ao banco de dados de Flashcards do aluno abaixo.
Use essas perguntas e respostas como base de conhecimento se o aluno perguntar sobre esses temas:

--- INÍCIO DOS FLASHCARDS ---
{texto_flashcards}
--- FIM DOS FLASHCARDS ---

Se a pergunta não estiver nos flashcards, use seu conhecimento geral para responder.
"""
        historico.append({"role": "user", "parts": [instrucao_flashcards]})
        salvar_mensagem_no_banco(current_user.id, "user", instrucao_flashcards)

    # Adiciona a pergunta atual do usuário
    historico.append({"role": "user", "parts": [pergunta_usuario]})
    salvar_mensagem_no_banco(current_user.id, "user", pergunta_usuario)

    try:
        chat = model.start_chat(history=historico)
        response = chat.send_message(pergunta_usuario)
        texto_resposta = response.text

        salvar_mensagem_no_banco(current_user.id, "model", texto_resposta)

        return jsonify({"resposta": texto_resposta})

    except Exception as e:
        print(f"Erro Gemini: {e}")
        traceback.print_exc()
        return (
            jsonify(
                {
                    "resposta": "Desculpe, tive um problema ao falar com a IA. Tente novamente em alguns instantes."
                }
            ),
            500,
        )


# =======================================================
# API: VARK
# =======================================================
@app.route("/save_vark_result", methods=["POST"])
@login_required
def save_vark_result():
    data = request.json
    if not data or "scores" not in data or "primaryType" not in data:
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    scores = data["scores"]
    primary_type = data["primaryType"]

    if not isinstance(scores, dict) or not isinstance(primary_type, str):
        return (
            jsonify(
                {"success": False, "message": "Tipos de dados inválidos."}
            ),
            400,
        )
    if not all(
        k in scores and isinstance(scores[k], int) for k in ["V", "A", "R", "K"]
    ):
        return (
            jsonify(
                {"success": False, "message": "Formato de scores inválido."}
            ),
            400,
        )
    if not primary_type or len(primary_type) > 10:
        return (
            jsonify(
                {"success": False, "message": "Tipo primário inválido."}
            ),
            400,
        )

    try:
        user = current_user
        user.vark_scores_json = json.dumps(scores)
        user.vark_primary_type = primary_type
        db.session.commit()
        return jsonify(
            {"success": True, "message": "Resultado salvo com sucesso."}
        )
    except Exception as e:
        db.session.rollback()
        print(f"ERRO ao salvar resultado VARK para user {current_user.id}: {e}")
        traceback.print_exc()
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Erro interno do servidor: {e}",
                }
            ),
            500,
        )


# =======================================================
# API: CALENDÁRIO
# =======================================================
@app.route("/save_calendar_event", methods=["POST"])
@login_required
def save_calendar_event():
    data = request.json
    if not data or not data.get("title") or not data.get("date"):
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    eventos = carregar_dados_json("calendario.json") or []
    event_id = data.get("id")

    evento_salvo = {
        "id": event_id if event_id else str(uuid.uuid4()),
        "data_inicio": data.get("date"),
        "descricao": data.get("title"),
        "type": data.get("type", "Outro"),
        "description": data.get("description", ""),
    }

    if event_id:
        evento_encontrado = False
        for i, evento in enumerate(eventos):
            if evento.get("id") == event_id:
                eventos[i] = evento_salvo
                evento_encontrado = True
                break
        if not evento_encontrado:
            eventos.append(evento_salvo)
    else:
        eventos.append(evento_salvo)

    if salvar_dados_json("calendario.json", eventos):
        return jsonify({"success": True, "message": "Evento salvo com sucesso."})
    else:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Erro ao salvar o arquivo JSON.",
                }
            ),
            500,
        )


@app.route("/delete_calendar_event", methods=["POST"])
@login_required
def delete_calendar_event():
    data = request.json
    event_id = data.get("id")
    if not event_id:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "ID do evento não fornecido.",
                }
            ),
            400,
        )

    eventos = carregar_dados_json("calendario.json") or []
    novos_eventos = [evento for evento in eventos if evento.get("id") != event_id]

    if len(novos_eventos) == len(eventos):
        return jsonify({"success": False, "message": "Evento não encontrado."}), 404

    if salvar_dados_json("calendario.json", novos_eventos):
        return jsonify({"success": True, "message": "Evento excluído com sucesso."})
    else:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Erro ao salvar o arquivo JSON.",
                }
            ),
            500,
        )


# =======================================================
# API: SIMULADOR DE PROVAS
# =======================================================
@app.route("/api/simulador_config")
@login_required
def api_simulador_config():
    simulador_data = carregar_dados_json("simulador.json")
    if simulador_data is None:
        return jsonify({"success": False, "message": "Arquivo simulador.json não encontrado."}), 500
    return jsonify({"success": True, "data": simulador_data})


# =======================================================
# FILTRO JINJA
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
# MAIN
# =======================================================
if __name__ == "__main__":
    if model is None:
        print("Servidor Flask NÃO foi iniciado. Verifique a GEMINI_API_KEY no .env.")
    else:
        with app.app_context():
            print("Criando tabelas do banco de dados (se não existirem)...")
            db.create_all()
            print("Tabelas prontas.")

        print("Iniciando servidor Flask em http://127.0.0.1:5000")
        app.run(debug=True, host="0.0.0.0", port=5000)
