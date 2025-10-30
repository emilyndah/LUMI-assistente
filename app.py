<<<<<<< Updated upstream
# =======================================================
# TÍTULO: SERVIDOR FLASK (APP.PY) - ASSISTENTE LUMI
# (Login, BD, Salvar VARK, Quiz JSON, Calendário JSON, Matriz JSON)
# =======================================================

# =======================================================
# IMPORTAÇÕES
# =======================================================
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify, flash, abort)
import json
import os
from datetime import datetime, date
import google.generativeai as genai
from dotenv import load_dotenv
import traceback
import re

from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

# =======================================================
# CONFIGURAÇÃO DA APLICAÇÃO FLASK
# =======================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "chave_secreta_final_lumi_app_v6_save_vark") # Nova chave
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'lumi_database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuração Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
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
    vark_scores_json = db.Column(db.String(100), nullable=True) # Guarda scores como {"V":2, "A":5,...}
    vark_primary_type = db.Column(db.String(10), nullable=True) # Guarda o tipo principal (ex: 'A', 'V/K')

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
                print(f"ERRO: Falha ao decodificar vark_scores_json para user {self.id}")
                return None
        return None

    def __repr__(self):
        # Atualiza a representação para incluir o tipo VARK, se existir
        vark_info = self.vark_primary_type or "N/A"
        return f'<User {self.username} (Matr: {self.matricula} / VARK: {vark_info})>'

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
# FUNÇÃO DE VALIDAÇÃO DE EMAIL
# =======================================================
def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

# =======================================================
# 1. CONSTANTES E CONFIGURAÇÃO DO GEMINI (Sem alterações)
# =======================================================
GEMINI_API_KEY = None; model = None;
try:
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]; genai.configure(api_key=GEMINI_API_KEY);
    generation_config = { "temperature": 0.8, "top_p": 0.9, "top_k": 40, "max_output_tokens": 1500, };
    safety_settings = [ {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, ];
    model = genai.GenerativeModel( model_name="gemini-1.5-flash-latest", generation_config=generation_config, safety_settings=safety_settings );
    print("Modelo Gemini inicializado com sucesso.")
except KeyError: print("ERRO: Variável de ambiente GEMINI_API_KEY não encontrada.")
except Exception as e: print(f"Erro ao inicializar o modelo Gemini: {e}"); GEMINI_API_KEY = None

# =======================================================
# 2. FUNÇÕES AUXILIARES (CARREGAMENTO DE DADOS JSON)
# =======================================================
def carregar_dados_json(arquivo):
    try:
        caminho_arquivo = os.path.join(os.path.dirname(__file__), arquivo)
        with open(caminho_arquivo, "r", encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: print(f"AVISO: Arquivo {arquivo} não encontrado."); return None
    except json.JSONDecodeError as e: print(f"ERRO: Falha ao decodificar JSON em {arquivo}. Detalhe: {e}"); return None
    except Exception as e: print(f"ERRO inesperado ao ler {arquivo}: {e}"); traceback.print_exc(); return None

def carregar_calendario(formatar_para_template=False):
    eventos_json = carregar_dados_json("calendario.json")
    if eventos_json is None or not isinstance(eventos_json, list):
        print("ERRO: Falha ao carregar ou formato inválido para calendario.json.")
        return []
    if not formatar_para_template:
        try: return sorted(eventos_json, key=lambda x: x.get("data_inicio", "9999-99-99"))
        except Exception as e: print(f"ERRO: Falha ao ordenar calendário para contexto: {e}"); return eventos_json
    eventos_formatados = []; meses_map = { 1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN", 7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ" }
    for evento in eventos_json:
        try:
            data_inicio_str = evento.get("data_inicio"); descricao = evento.get("descricao", "Evento");
            if not data_inicio_str: continue
            data_obj = datetime.strptime(data_inicio_str, "%Y-%m-%d");
            eventos_formatados.append({
                "data": data_obj.strftime("%d/%m/%Y"), "evento": descricao, "data_obj": data_obj,
                "data_iso": data_inicio_str, "mes_curto": meses_map.get(data_obj.month),
                "data_fim": evento.get("data_fim")
            })
        except (ValueError, KeyError, TypeError) as e: print(f"AVISO: Ignorando evento do calendário inválido para template: {evento} - {e}");
    return sorted(eventos_formatados, key=lambda x: x["data_obj"])

def carregar_matriz():
    dados = carregar_dados_json("matriz.json")
    if dados and isinstance(dados, list): return dados
    elif dados and isinstance(dados, dict): print("AVISO: matriz.json em formato antigo (objeto único). Convertendo para lista."); return [dados]
    else: print("AVISO: Falha ao carregar ou formato inválido para matriz.json."); return None

def carregar_quiz_vark(): return carregar_dados_json("metodo_estudo.json")

# =======================================================
# CONTEXTO INICIAL (COMBINA DADOS)
# =======================================================
def calcular_contexto_inicial():
    contexto_base = "Você é Lumi, assistente acadêmico da UniEVANGÉLICA, Anápolis, GO."; info_gerais = ""
    try:
        caminho_info = os.path.join(os.path.dirname(__file__), "informacoes.txt")
        if os.path.exists(caminho_info):
            with open(caminho_info, "r", encoding="utf-8") as f: info_gerais = f.read().strip(); print("Info gerais carregadas.");
        else: print("AVISO: 'informacoes.txt' não encontrado.");
    except Exception as e: print(f"Erro ao ler 'informacoes.txt': {e}");

    contexto_calendario = "\n\n[Calendário Acadêmico Resumido]\n"; eventos_calendario = carregar_calendario(False);
    if eventos_calendario:
        eventos_ctx = []; hoje = date.today(); count = 0; max_ctx = 15;
        for ev in eventos_calendario:
            if count >= max_ctx: break
            try:
                di_str = ev.get("data_inicio"); df_str = ev.get("data_fim", di_str); desc = ev.get("descricao", "?");
                if not di_str: continue
                di = datetime.strptime(di_str, "%Y-%m-%d").date(); df = datetime.strptime(df_str, "%Y-%m-%d").date();
                if df >= hoje:
                    fmt = "%d/%m/%Y"; ev_str = f"- {di.strftime(fmt)}";
                    if df != di: ev_str += f" a {df.strftime(fmt)}";
                    ev_str += f": {desc}"; eventos_ctx.append(ev_str); count += 1;
            except: continue
        if eventos_ctx: contexto_calendario += "\n".join(eventos_ctx);
        else: contexto_calendario += "Nenhum evento futuro encontrado.\n";
    else: contexto_calendario += "Dados indisponíveis.\n";

    contexto_matriz = "\n\n[Matriz Curricular Resumida - Eng. IA]\n"; dados_matriz = carregar_matriz();
    if dados_matriz:
        max_p_ctx = 3; max_d_ctx = 5;
        for i, p_info in enumerate(dados_matriz):
            if i >= max_p_ctx: break
            if not isinstance(p_info, dict): continue
            num_p = p_info.get('periodo', f'{i+1}º'); discs = p_info.get('disciplinas', []);
            if isinstance(discs, list) and discs:
                contexto_matriz += f"\n {num_p} Período:\n";
                nomes = [d.get('nome', '?') for d in discs[:max_d_ctx] if isinstance(d, dict)];
                contexto_matriz += "  - " + "\n  - ".join(nomes);
                if len(discs) > max_d_ctx: contexto_matriz += "\n  - (...)";
                contexto_matriz += "\n";
        if len(dados_matriz) > max_p_ctx: contexto_matriz += "(...)\n";
    else: contexto_matriz += "Dados indisponíveis.\n";

    contexto_vark = "\n\n[Quiz Estilo Aprendizagem VARK]\n"; quiz_data = carregar_quiz_vark();
    if quiz_data and "resultados" in quiz_data:
        contexto_vark += f"Ofereço um quiz ({len(quiz_data.get('perguntas',[]))} perguntas) para identificar estilo VARK. {quiz_data.get('descricao', '')}\nResumo:\n";
        for tipo, det in quiz_data["resultados"].items():
            desc = det.get('descricao', ''); pt = desc.find('.'); desc = desc[:pt+1] if pt!=-1 else desc;
            contexto_vark += f"- {det.get('titulo', tipo)} ({tipo}): {desc}\n";
    else: contexto_vark += "Ofereço quiz VARK.\n";

    contexto_final = f"{contexto_base}\n{info_gerais}\n{contexto_calendario}\n{contexto_matriz}\n{contexto_vark}".strip()
    print("-" * 15 + " CONTEXTO INICIAL CALCULADO (resumo) " + "-" * 15);
    # print(contexto_final) # Descomentar para ver contexto completo
    print("-" * (30 + len(" CONTEXTO INICIAL CALCULADO (resumo) ")));
    return contexto_final

CONTEXTO_INICIAL = calcular_contexto_inicial()

# =======================================================
# 3. ROTAS DE AUTENTICAÇÃO
# =======================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        login_identifier = request.form.get('login_identifier'); password = request.form.get('password'); remember = bool(request.form.get('remember'));
        if not login_identifier or not password: flash('Email/Matrícula e senha são obrigatórios.', 'warning'); return redirect(url_for('login'));
        user = User.query.filter( (User.email == login_identifier) | (User.matricula == login_identifier) ).first();
        if user and user.check_password(password):
            login_user(user, remember=remember); flash('Login realizado com sucesso!', 'success'); next_page = request.args.get('next');
            # session.pop('historico', None) # Opcional: Limpar histórico ao logar
            return redirect(next_page or url_for('index'));
        else: flash('Email/Matrícula ou senha inválidos.', 'danger'); return redirect(url_for('login'));
    return render_template('login.html');

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'));
    if request.method == 'POST':
        username = request.form.get('username'); email = request.form.get('email'); matricula = request.form.get('matricula'); password = request.form.get('password'); password_confirm = request.form.get('password_confirm');
        error_occurred = False;
        if not all([username, email, matricula, password, password_confirm]): flash('Todos os campos são obrigatórios.', 'warning'); error_occurred = True;
        elif not is_valid_email(email): flash('Formato de email inválido.', 'warning'); error_occurred = True;
        elif password != password_confirm: flash('As senhas não coincidem.', 'warning'); error_occurred = True;
        else:
            existing_user = User.query.filter((User.username == username) | (User.email == email) | (User.matricula == matricula)).first();
            if existing_user:
                if existing_user.username == username: flash('Este nome de utilizador já está em uso.', 'warning')
                elif existing_user.email == email: flash('Este email já está registado.', 'warning')
                else: flash('Esta matrícula já está registada.', 'warning')
                error_occurred = True;
        if error_occurred: return redirect(url_for('register'));
        try:
            new_user = User(username=username, email=email, matricula=matricula); new_user.set_password(password); db.session.add(new_user); db.session.commit();
            flash('Conta criada com sucesso! Por favor, faça login.', 'success'); return redirect(url_for('login')); # Redireciona para LOGIN
        except Exception as e:
            db.session.rollback(); flash('Ocorreu um erro ao criar a conta. Tente novamente.', 'danger'); print(f"Erro ao registrar utilizador '{username}': {e}"); traceback.print_exc(); return redirect(url_for('register'));
    return render_template('register.html');

@app.route('/logout')
@login_required
def logout(): logout_user(); session.clear(); flash('Você foi desconectado.', 'info'); return redirect(url_for('login'));

# =======================================================
# 4. ROTAS PRINCIPAIS (Protegidas)
# =======================================================
@app.route("/")
@login_required
def index():
    if 'historico' not in session or not session.get('historico') or CONTEXTO_INICIAL not in session['historico'][0]['parts'][0]:
        session['historico'] = [{"role": "user", "parts": [CONTEXTO_INICIAL]}, {"role": "model", "parts": [f"Olá {current_user.username}! Eu sou a Lumi. Como posso te ajudar hoje?"]}]
    return render_template("index.html", current_user=current_user)

@app.route("/profile")
@login_required
def profile(): return render_template("profile.html") # current_user já está disponível

@app.route("/faq")
@login_required
def faq(): dados = carregar_dados_json("faq.json") or []; return render_template("faq.html", faq_data=dados)

@app.route("/calendario")
@login_required
def calendario():
    eventos_data = carregar_calendario(formatar_para_template=True)
    if not eventos_data and carregar_dados_json("calendario.json") is not None: flash("Eventos carregados, mas erro na formatação.", "warning")
    elif not eventos_data: flash("Não foi possível carregar os eventos do calendário.", "danger")
    return render_template("calendario.html", eventos_data=eventos_data)

@app.route("/flashcards")
@login_required
def flashcards():
    dados = carregar_dados_json("flashcards.json"); flashcard_data = {};
    if dados: flashcard_data = dados.get("flash_cards", dados)
    if not flashcard_data: flash("Não foi possível carregar os flashcards.", "warning")
    return render_template("flashcards.html", flashcard_data=flashcard_data)

@app.route("/limpar")
@login_required
def limpar_chat():
    session.pop('historico', None)
    flash("Histórico do chat limpo!", "info")
    return redirect(url_for('index'))

# **** ROTA MÉTODO DE ESTUDO ATUALIZADA ****
@app.route("/metodo_de_estudo")
@login_required
def metodo_de_estudo():
    """Renderiza quiz ou resultado VARK salvo."""
    quiz_data = carregar_quiz_vark() # Carrega as perguntas/opções do JSON
    saved_vark_result = None # Inicializa como None

    # Verifica se o utilizador logado já tem resultado salvo no BD
    if current_user.is_authenticated and current_user.vark_primary_type:
        scores = current_user.get_vark_scores() # Usa a função helper no modelo User
        if scores:
            saved_vark_result = {
                "primaryType": current_user.vark_primary_type,
                "scores": scores
            }
            # print(f"DEBUG: Encontrado resultado VARK salvo para {current_user.username}: {saved_vark_result}") # Debug

    # Verifica se houve erro ao carregar os dados do quiz (perguntas)
    if quiz_data is None:
        flash("Erro ao carregar as perguntas do quiz. Tente novamente mais tarde.", "danger")
        # Mesmo com erro nas perguntas, passa o resultado salvo se existir
        # O template precisa tratar 'quiz_data=None'
        return render_template("metodo_de_estudo.html", quiz_data=None, error=True, saved_vark_result=saved_vark_result)

    # Passa tanto os dados do quiz quanto o resultado salvo (que pode ser None)
    return render_template("metodo_de_estudo.html", quiz_data=quiz_data, saved_vark_result=saved_vark_result)

# =======================================================
# 5. ROTAS DA API (CHAT E SALVAR VARK)
# =======================================================
@app.route("/ask", methods=["POST"])
@login_required
def ask():
    if not model: return jsonify({"resposta": "Desculpe, o serviço de chat não está configurado."}), 500
    data = request.json; pergunta = data.get("pergunta") if data else None;
    if not pergunta: return jsonify({"resposta": "Nenhuma pergunta recebida."}), 400
    try:
        historico_chat = session.get('historico', None);
        if historico_chat is None or not historico_chat or CONTEXTO_INICIAL not in historico_chat[0]['parts'][0]:
            print("DEBUG: Recriando histórico na sessão para /ask");
            historico_chat = [{"role": "user", "parts": [CONTEXTO_INICIAL]}, {"role": "model", "parts": [f"Olá {current_user.username}! Como posso ajudar?"]}]
        chat = model.start_chat(history=historico_chat); response = chat.send_message(pergunta); response_text = getattr(response, 'text', 'Desculpe, não consegui gerar uma resposta.');
        historico_chat.append({"role": "user", "parts": [pergunta]}); historico_chat.append({"role": "model", "parts": [response_text]});
        session['historico'] = historico_chat;
        return jsonify({"resposta": response_text});
    except Exception as e:
        print(f"Erro na API do Gemini ou processamento na rota /ask: {e}");
        traceback.print_exc();
        return jsonify({"resposta": f"Desculpe, ocorreu um erro inesperado."}), 500;

# **** NOVA ROTA PARA SALVAR VARK ****
@app.route("/save_vark_result", methods=["POST"])
@login_required # Só utilizadores logados podem salvar
def save_vark_result():
    """Recebe os resultados do quiz VARK via JSON e salva no perfil do usuário."""
    data = request.json
    scores = data.get('scores') # Espera algo como {"V": 5, "A": 3, "R": 6, "K": 2}
    primary_type = data.get('primaryType') # Espera algo como "R" ou "V/R"

    if scores is None or primary_type is None:
        print(f"DEBUG: Dados incompletos recebidos em /save_vark_result: {data}")
        return jsonify({"success": False, "message": "Dados incompletos recebidos."}), 400

    # Validação básica dos dados recebidos
    if not isinstance(scores, dict) or not isinstance(primary_type, str):
         print(f"DEBUG: Tipos de dados inválidos recebidos em /save_vark_result: scores={type(scores)}, primary_type={type(primary_type)}")
         return jsonify({"success": False, "message": "Tipos de dados inválidos."}), 400
    # Verifica se as chaves V,A,R,K existem e os valores são números
    if not all(k in scores and isinstance(scores[k], int) for k in ['V', 'A', 'R', 'K']):
         print(f"DEBUG: Scores inválidos recebidos em /save_vark_result: {scores}")
         return jsonify({"success": False, "message": "Formato de scores inválido."}), 400
    # Verifica o tipo primário (simplificado)
    if not primary_type or len(primary_type) > 10: # Limita tamanho
         print(f"DEBUG: primaryType inválido recebido em /save_vark_result: {primary_type}")
         return jsonify({"success": False, "message": "Tipo primário inválido."}), 400


    try:
        # Pega o utilizador atual logado (Flask-Login garante que ele existe)
        user = current_user
        # Converte o dicionário de scores para uma string JSON para guardar no BD
        user.vark_scores_json = json.dumps(scores)
        user.vark_primary_type = primary_type

        # Adiciona o utilizador à sessão do DB antes de commitar alterações
        # (Boa prática, especialmente se o objeto veio da sessão e não de uma query recente)
        db.session.add(user)
        db.session.commit() # Salva as alterações no banco de dados
        print(f"DEBUG: Resultado VARK salvo para user {user.username}: Scores={user.vark_scores_json}, Tipo={user.vark_primary_type}")
        return jsonify({"success": True, "message": "Resultado salvo com sucesso."})

    except Exception as e:
        db.session.rollback() # Desfaz em caso de erro
        print(f"ERRO ao salvar resultado VARK para user {current_user.username}: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": "Erro interno ao salvar resultado."}), 500

# =======================================================
# 6. FILTRO JINJA (para formatar data no template)
# =======================================================
@app.template_filter('format_date_br')
def format_date_br_filter(value):
    if not value: return ""
    try: return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError: return value

# =======================================================
# 7. EXECUÇÃO DO SERVIDOR E CRIAÇÃO DO BD
# =======================================================
if __name__ == "__main__":
    with app.app_context():
        try: db.create_all(); print("Tabelas do banco de dados verificadas/criadas.")
        except Exception as e: print(f"ERRO CRÍTICO ao criar/verificar tabelas: {e}"); traceback.print_exc(); exit(1);
    if GEMINI_API_KEY is None: print("AVISO: API Key do Gemini não encontrada. O Chatbot não funcionará.")
    print("Iniciando servidor Flask...")
    print(f"Acesse em: http://127.0.0.1:5000 (ou use o IP da sua máquina: http://<seu-ip>:5000)")
    app.run(debug=True, host="0.0.0.0", port=5000)