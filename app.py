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
import locale
from dotenv import load_dotenv
import uuid 
import psycopg2

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
DATABASE_URL = os.getenv('DATABASE_URL')
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

# === MUDANÇA (CORREÇÃO) ===
# Esta linha foi acidentalmente removida. Ela DEFINE o 'db'.
db = SQLAlchemy(app)
# === FIM DA MUDANÇA (CORREÇÃO) ===


# === MUDANÇA === Configurações de Upload
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
# === FIM DA MUDANÇA ===


@app.cli.command("db-create-all")
def db_create_all():
    """Cria as tabelas do banco de dados (usado pelo Render)."""
    with app.app_context():
        db.create_all()
        print("v2 - Banco de dados e tabelas criados com sucesso.")


# Configuração Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Você precisa fazer login para acessar esta página."
login_manager.login_message_category = "warning"


# === MUDANÇA === Função auxiliar para verificar extensão do arquivo
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
# === FIM DA MUDANÇA ===


# =======================================================
# MODELO DE DADOS (User - Atualizado com NOVOS CAMPOS)
# =======================================================
class User(db.Model, UserMixin):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False) # 'username' é o NOME
    email = db.Column(db.String(120), unique=True, nullable=False)
    matricula = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    cpf = db.Column(db.String(14), unique=True, nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    sexo = db.Column(db.String(30), nullable=True) # Gênero
    etnia = db.Column(db.String(50), nullable=True)

    vark_scores_json = db.Column(db.Text, nullable=True)
    vark_primary_type = db.Column(db.String(10), nullable=True)

    # === MUDANÇA === Coluna para salvar o NOME DO ARQUIVO da imagem
    profile_image = db.Column(db.String(100), nullable=False, default='lumi-2.png')
    # === FIM DA MUDANÇA ===


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

    # === MUDANÇA === Renomeei 'username' para 'nome_completo'
    # e 'sexo' para 'genero' para bater com o seu HTML/Formulário
    def __init__(self, nome_completo, email, matricula, password=None, cpf=None, telefone=None, genero=None, etnia=None):
        self.username = nome_completo # O formulário usa 'username', mas seu HTML exibe 'nome'
        self.email = email
        self.matricula = matricula
        if password:
            self.set_password(password)

        self.cpf = cpf
        self.telefone = telefone
        self.sexo = genero # 'sexo' no BD, 'genero' no formulário
        self.etnia = etnia


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
# (Seu código original mantido aqui)
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
        model = genai.GenerativeModel(
            "gemini-2.5-flash")

        print("✅ Modelo Gemini inicializado com sucesso (gemini-2.5-flash).")
    except Exception as e:
        print(f"❌ Erro ao inicializar o modelo Gemini: {e}")
        GEMINI_API_KEY = None
else:
    print("⚠️ API Key do Gemini não encontrada. O Chatbot não funcionará.")


# =======================================================
# 2. FUNÇÕES AUXILIARES (CARREGAMENTO DE DADOS)
# =======================================================
# (Seu código original mantido aqui)
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

# (Seu código original 'carregar_calendario', 'carregar_matriz', etc. mantido)
def carregar_calendario():
    meses_map = {
        1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
        7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ",
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
                    data_fim, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                print(f"AVISO: Data final inválida ignorada: {data_fim}")

        eventos.append({
            "id": event_id,
            "title": descricao,
            "date": data_inicio,
            "type": event_type,
            "description": event_description,
            "data_obj": data_inicio_obj,
            "data_fim": data_fim_iso,
            "mes_curto": meses_map.get(data_inicio_obj.month),
        })
    return sorted(eventos, key=lambda x: x["data_obj"])


def carregar_matriz():
    dados = carregar_dados_json("matriz.json")
    if dados and isinstance(dados, list):
        return dados
    elif dados and isinstance(dados, dict):
        print(
            "AVISO: matriz.json em formato antigo (objeto único). Convertendo para lista.")
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

    # 1. Carrega o contexto principal (informacoes.txt)
    try:
        with open("informacoes.txt", "r", encoding="utf-8") as f:
            contexto_base = f.read()
    except FileNotFoundError:
        print("Aviso: 'informacoes.txt' não encontrado. O chatbot pode não ter contexto.")
        contexto_base = "Você é um assistente acadêmico chamado Lumi, focado em ajudar alunos da UniEVANGÉLICA."
    except Exception as e:
        print(f"Erro ao ler 'informacoes.txt': {e}")
        contexto_base = "Você é um assistente acadêmico chamado Lumi."

    # 2. Carrega e formata o Calendário
    print("Carregando Calendário para o contexto...")
    try:
        eventos = carregar_calendario()
        if eventos:
            contexto_calendario = "\n\n=== CALENDÁRIO ACADÊMICO (Use para responder perguntas sobre datas) ===\n"
            for evento in eventos:
                data_str = evento.get("data_obj").strftime('%d/%m/%Y')
                desc = evento.get("title")
                data_fim_str = ""
                if evento.get("data_fim") and evento.get("data_fim") != evento.get("date"):
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
        matriz_data = carregar_matriz()
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
                    contexto_matriz += f"  Professor: {prof}\n"
                    contexto_matriz += f"  Horário: {dia}, {horario}\n"
                    contexto_matriz += f"  Sala: {sala}\n\n"
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
        vark_data = carregar_quiz_vark()
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
                    contexto_vark += f"  - {m}\n"
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


CONTEXTO_INICIAL = carregar_contexto_inicial()


# =======================================================
# 1.5. INICIALIZAÇÃO DO MODELO GEMINI (COM CONTEXTO)
# =======================================================
if GEMINI_API_KEY:
    try:
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=CONTEXTO_INICIAL
        )
        print("✅ Modelo Gemini inicializado com system_instruction (contexto completo).")
    except Exception as e:
        print(f"❌ Erro ao inicializar o modelo Gemini: {e}")
        GEMINI_API_KEY = None
else:
    print("⚠️ API Key não encontrada. O Chatbot não funcionará.")


# =======================================================
# 3. ROTAS PRINCIPAIS (LOGIN, PÁGINAS, ETC.)
# =======================================================
def get_initial_chat_history():
    """Retorna a estrutura de histórico inicial para a sessão."""
    return [
        {
            "role": "model",
            "parts": [
                "Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje? 💡"
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
        nome_completo = request.form.get("username") # O formulário envia 'username'
        matricula = request.form.get("matricula")
        password = request.form.get("password")
        cpf = request.form.get("cpf")
        telefone = request.form.get("telefone")
        genero = request.form.get("sexo") # O formulário envia 'sexo'
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
                etnia=etnia
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
            (getattr(User, "email") == identifier) |
            (getattr(User, "matricula") == identifier) |
            (getattr(User, "cpf") == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("index"))
        else:
            flash("Email/Matrícula/CPF ou senha inválidos. Tente novamente.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Lida com o logout do usuário."""
    logout_user()
    flash("Você foi desconectado.", "info")
    return redirect(url_for("login"))


# =======================================================
# === MUDANÇA NA ESTRUTURA DAS ROTAS ===
# =======================================================

@app.route("/")
@login_required
def index():
    """Renderiza a página inicial do MENU."""
    return render_template("index.html")


@app.route("/chat")
@login_required
def chat():
    """Renderiza a página do CHAT."""
    if "historico" not in session:
        session["historico"] = get_initial_chat_history()
    return render_template("chat.html")

# =======================================================

# =======================================================
# === ROTA DE PERFIL (COM UPLOAD DE ARQUIVO) ===
# =======================================================
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Renderiza a página de perfil (GET) e salva as atualizações (POST)."""
    
    user = current_user 

    if request.method == "POST":
        # --- Lógica para SALVAR os dados ---
        
        try:
            # --- 1. Lógica de Upload da Imagem ---
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                
                if file and file.filename != '' and allowed_file(file.filename):
                    
                    filename_secure = secure_filename(file.filename)
                    extension = filename_secure.rsplit('.', 1)[1].lower()
                    unique_filename = f"{uuid.uuid4()}.{extension}"
                    
                    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
                    
                    file.save(save_path)
                    
                    if user.profile_image != 'lumi-2.png':
                        old_path = os.path.join(app.config["UPLOAD_FOLDER"], user.profile_image)
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception as e:
                                print(f"Aviso: Não foi possível remover o arquivo antigo: {e}")
                                
                    user.profile_image = unique_filename
            
            # --- 2. Lógica para salvar os dados do formulário ---
            
            # (No seu HTML o 'Nome Completo' tem o name="nome")
            novo_username = request.form.get('nome') 
            novo_email = request.form.get('email')
            novo_telefone = request.form.get('telefone')
             # (No seu HTML o 'Gênero' tem o name="genero")
            novo_sexo = request.form.get('genero')
            novo_etnia = request.form.get('etnia')

            if novo_email != user.email:
                email_existente = User.query.filter_by(email=novo_email).first()
                if email_existente:
                    flash('Este e-mail já está em uso por outra conta. Tente outro.', 'danger')
                    return redirect(url_for('profile'))
            
            user.username = novo_username # 'username' no BD, 'nome' no formulário
            user.email = novo_email
            user.telefone = novo_telefone
            user.sexo = novo_sexo # 'sexo' no BD, 'genero' no formulário
            user.etnia = novo_etnia
            
            db.session.commit()
            
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('profile'))

        except Exception as e:
            db.session.rollback()
            print(f"ERRO ao atualizar perfil: {e}")
            traceback.print_exc() 
            flash(f'Ocorreu um erro ao atualizar: {e}', 'danger')

    # --- Lógica para MOSTRAR a página (GET) ---
    return render_template("profile.html")
# =======================================================
# === FIM DA ROTA DE PERFIL ===
# =======================================================


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
    """Limpa o histórico do chat da sessão e redireciona para o CHAT."""
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
# 4. ROTAS DA API (CHAT, VARK E CALENDÁRIO)
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
    
    pergunta = data["pergunta"] # Pergunta original do usuário

    try:
        # (Sua lógica de data e hora mantida)
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
            except locale.Error:
                locale.setlocale(locale.LC_TIME, '')
        
        data_hora_atual = datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        
        pergunta_com_contexto = (
            f"Contexto de data/hora atual (use APENAS se o usuário perguntar sobre 'hoje', 'agora', etc.): {data_hora_atual}.\n"
            f"Pergunta do usuário: {pergunta}"
        )

        historico_chat = session.get("historico", get_initial_chat_history())

        chat = model.start_chat(history=historico_chat)
        
        response = chat.send_message(pergunta_com_contexto)

        historico_chat.append({"role": "user", "parts": [pergunta]})
        historico_chat.append({"role": "model", "parts": [response.text]})
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

# (Suas rotas de calendário 'save_calendar_event' e 'delete_calendar_event' mantidas)
@app.route("/save_calendar_event", methods=["POST"])
@login_required
def save_calendar_event():
    data = request.json
    if not data or not data.get('title') or not data.get('date'):
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    eventos = carregar_dados_json("calendario.json") or []
    event_id = data.get("id")

    evento_salvo = {
        "id": event_id if event_id else str(uuid.uuid4()),
        "data_inicio": data.get("date"),
        "descricao": data.get("title"),
        "type": data.get("type", "Outro"),
        "description": data.get("description", "")
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
        return jsonify({"success": False, "message": "Erro ao salvar o arquivo JSON."}), 500


@app.route("/delete_calendar_event", methods=["POST"])
@login_required
def delete_calendar_event():
    data = request.json
    event_id = data.get("id")
    if not event_id:
        return jsonify({"success": False, "message": "ID do evento não fornecido."}), 400

    eventos = carregar_dados_json("calendario.json") or []

    novos_eventos = [
        evento for evento in eventos if evento.get("id") != event_id]

    if len(novos_eventos) == len(eventos):
        return jsonify({"success": False, "message": "Evento não encontrado."}), 404

    if salvar_dados_json("calendario.json", novos_eventos):
        return jsonify({"success": True, "message": "Evento excluído com sucesso."})
    else:
        return jsonify({"success": False, "message": "Erro ao salvar o arquivo JSON."}), 500


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