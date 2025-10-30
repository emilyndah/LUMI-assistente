
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
app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "chave_secreta_final_lumi_app_v6_save_vark"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    os.path.dirname(__file__), "lumi_database.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Configuração Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Você precisa fazer login para acessar esta página."
login_manager.login_message_category = "warning"


# =======================================================
# MODELO DE DADOS (User - Atualizado com VARK)
# =======================================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    # **** NOVAS COLUNAS PARA RESULTADO VARK ****
    vark_scores_json = db.Column(
        db.String(100), nullable=True
    )  # Guarda scores como {"V":2, "A":5,...}
    vark_primary_type = db.Column(
        db.String(10), nullable=True
    )  # Guarda o tipo principal (ex: 'A', 'V/K')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Função helper para obter scores como dicionário Python
    def get_vark_scores(self):
        """Retorna os scores VARK salvos como um dicionário, ou None."""
        if self.vark_scores_json:
            try:
                return json.loads(self.vark_scores_json)
            except json.JSONDecodeError:
                print(
                    f"ERRO: Falha ao decodificar vark_scores_json para user {self.id}"
                )
                return None
        return None

    def __repr__(self):
        # Atualiza a representação para incluir o tipo VARK, se existir
        vark_info = self.vark_primary_type or "N/A"
        return f"<User {self.username} (Matr: {self.matricula} / VARK: {vark_info})>"


@login_manager.user_loader
def load_user(user_id):
    if user_id is not None:
        try:
            # db.session.get é o método recomendado para buscar por PK
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            print(f"DEBUG: Invalid user_id format in session: {user_id}")
            return None
    return None


# =======================================================
# 1. CONSTANTES E CONFIGURAÇÃO DO GEMINI
# =======================================================
GEMINI_API_KEY = None
model = None
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
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

        generation_config = {
            "temperature": 0.8,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 1500,
        }

        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
        ]

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",  # Usei o 1.5-flash, mas pode ser o "gemini-pro"
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        print("Modelo Gemini inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar o modelo Gemini: {e}")
        GEMINI_API_KEY = None  # Falha na inicialização
else:
    print("API Key do Gemini não encontrada. O Chatbot não funcionará.")


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


# --- CORREÇÃO FUNÇÃO DO CALENDÁRIO ---
# A função anterior estava misturando duas lógicas (ler TXT e ler JSON)
# e usava uma variável 'eventos_json' que não existia.
# Esta versão faz apenas uma coisa: lê o 'calendario.txt' e retorna os dados.
def carregar_calendario():
    """Carrega, formata e ordena os eventos do calendário a partir de calendario.txt."""
    eventos = []
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

    try:
        with open("calendario.txt", "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue

                partes = linha.split(":", 1)
                if len(partes) < 2:
                    continue  # Ignora linhas mal formatadas

                data_str = partes[0].strip()
                evento_str = partes[1].strip()

                try:
                    data_obj = datetime.strptime(data_str, "%d/%m/%Y")
                    eventos.append(
                        {
                            "data": data_str,  # Formato original: DD/MM/YYYY
                            "evento": evento_str,
                            "data_obj": data_obj,  # Para ordenar
                            "data_iso": data_obj.strftime(
                                "%Y-%m-%d"
                            ),  # Para FullCalendar
                            "mes_curto": meses_map.get(data_obj.month),
                        }
                    )
                except ValueError:
                    print(f"Formato de data inválido ignorado: {data_str}")

    except FileNotFoundError:
        print("Arquivo calendario.txt não encontrado.")
        return []
    except Exception as e:
        print(f"Erro ao ler o calendário: {e}")
        return []

    # Ordena a lista final de eventos pela data
    return sorted(eventos, key=lambda x: x["data_obj"])


def carregar_matriz():
    dados = carregar_dados_json("matriz.json")
    if dados and isinstance(dados, list):
        return dados
    elif dados and isinstance(dados, dict):
        print(
            "AVISO: matriz.json em formato antigo (objeto único). Convertendo para lista."
        )
        return [dados]
    else:
        print("AVISO: Falha ao carregar ou formato inválido para matriz.json.")
        return None


def carregar_quiz_vark():
    return carregar_dados_json("metodo_estudo.json")


# =======================================================
# 3. ROTAS PRINCIPAIS (LOGIN, PÁGINAS, ETC.)
# =======================================================


# --- REMOÇÃO DE DUPLICIDADE ---
# Criei esta função para definir o histórico inicial.
# Antes, esse mesmo bloco de código estava duplicado em 2 rotas.
def get_initial_chat_history():
    """Retorna a estrutura de histórico inicial para a sessão."""
    return [
        {"role": "user", "parts": [CONTEXTO_INICIAL]},
        {
            "role": "model",
            "parts": [
                "Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje?"
            ],
        },
    ]


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
    return render_template("profile.html")  # current_user já está disponível


@app.route("/faq")
@login_required
def faq():
    dados = carregar_dados_json("faq.json") or []
    return render_template("faq.html", faq_data=dados)


@app.route("/calendario")
@login_required
def calendario():
    # Chamada corrigida, sem o parâmetro 'formatar_para_template'
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
def modo_foco():
    """Renderiza a página do Modo Foco (timer)."""
    return render_template("foco.html")


@app.route("/limpar")
@login_required
def limpar_chat():
    """Limpa o histórico do chat da sessão e redireciona para o início."""
    # Usa a função helper para evitar duplicidade
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
    pergunta = data.get("pergunta")
    if not pergunta:
        return jsonify({"resposta": "Nenhuma pergunta recebida."}), 400

    try:
        # Garante que o histórico exista na sessão
        historico_chat = session.get("historico", get_initial_chat_history())

        chat = model.start_chat(history=historico_chat)
        response = chat.send_message(pergunta)

        # Atualiza o histórico na sessão
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


# --- CORREÇÃO ROTA SALVAR VARK ---
# 1. A lógica do CHAT (Gemini) estava copiada aqui por engano. Eu a removi.
# 2. Faltava a linha 'db.session.commit()' para salvar no banco de dados.
# 3. Adicionei 'db.session.rollback()' em caso de erro.
# 4. Adicionei uma resposta JSON de sucesso (message: "Resultado salvo...").
@app.route("/save_vark_result", methods=["POST"])
@login_required
def save_vark_result():
    """Recebe os resultados do quiz VARK e salva no perfil do usuário."""
    data = request.json
    scores = data.get("scores")
    primary_type = data.get("primaryType")

    # Bloco de validação (estava ótimo, mantive)
    if scores is None or primary_type is None:
        print(f"DEBUG: Dados incompletos recebidos em /save_vark_result: {data}")
        return jsonify({"success": False, "message": "Dados incompletos."}), 400
    if not isinstance(scores, dict) or not isinstance(primary_type, str):
        print(f"DEBUG: Tipos de dados inválidos: {type(scores)}, {type(primary_type)}")
        return jsonify({"success": False, "message": "Tipos de dados inválidos."}), 400
    if not all(
        k in scores and isinstance(scores[k], int) for k in ["V", "A", "R", "K"]
    ):
        print(f"DEBUG: Scores inválidos: {scores}")
        return (
            jsonify({"success": False, "message": "Formato de scores inválido."}),
            400,
        )
    if not primary_type or len(primary_type) > 10:
        print(f"DEBUG: primaryType inválido: {primary_type}")
        return jsonify({"success": False, "message": "Tipo primário inválido."}), 400

    # Lógica de salvar (Corrigida)
    try:
        user = current_user
        user.vark_scores_json = json.dumps(scores)
        user.vark_primary_type = primary_type

        # --- !! CORREÇÃO CRÍTICA !! ---
        # Faltava isso para salvar as mudanças no banco de dados
        db.session.commit()

        print(f"DEBUG: Resultado VARK salvo com sucesso para {user.username}")
        return (
            jsonify({"success": True, "message": "Resultado salvo com sucesso."}),
            200,
        )

    except Exception as e:
        # --- BOA PRÁTICA ---
        # Se der erro, reverter quaisquer mudanças na sessão
        db.session.rollback()
        print(f"ERRO ao salvar resultado VARK para user {current_user.id}: {e}")
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
        # --- ADIÇÃO IMPORTANTE ---
        # Isso cria o arquivo .db e as tabelas (ex: User)
        # automaticamente na primeira vez que você roda o app.
        with app.app_context():
            print("Criando tabelas do banco de dados (se não existirem)...")
            db.create_all()
            print("Tabelas prontas.")

        print("Iniciando servidor Flask em http://127.0.0.1:5000")
        app.run(debug=True, host="0.0.0.0", port=5000)
