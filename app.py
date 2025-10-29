# =======================================================
# TÍTULO: SERVIDOR FLASK (APP.PY) - ASSISTENTE LUMI
# (Login, BD, Quiz VARK JSON, Calendário JSON, Matriz JSON)
# =======================================================

# =======================================================
# IMPORTAÇÕES
# =======================================================
from flask import (Flask, render_template, request, session, redirect, url_for, jsonify, flash, abort)
import json
import os
from datetime import datetime, date # Adicionado date para comparação
import google.generativeai as genai
from dotenv import load_dotenv
import traceback
import re # Para validação de email
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

# =======================================================
# CONFIGURAÇÃO DA APLICAÇÃO FLASK
# =======================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "chave_secreta_final_lumi_app_v5_json") # Chave atualizada
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
# MODELO DE DADOS (User)
# =======================================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.email} / {self.matricula})>'

@login_manager.user_loader
def load_user(user_id):
    if user_id is not None:
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
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
    model = genai.GenerativeModel( model_name="gemini-pro", generation_config=generation_config, safety_settings=safety_settings );
    print("Modelo Gemini inicializado com sucesso.")
except KeyError: print("ERRO: Variável de ambiente GEMINI_API_KEY não encontrada.")
except Exception as e: print(f"Erro ao inicializar o modelo Gemini: {e}"); GEMINI_API_KEY = None

# =======================================================
# 2. FUNÇÕES AUXILIARES (CARREGAMENTO DE DADOS - ATUALIZADAS)
# =======================================================
def carregar_dados_json(arquivo):
    """Função genérica para carregar dados de um arquivo JSON. Retorna None em caso de erro."""
    try:
        caminho_arquivo = os.path.join(os.path.dirname(__file__), arquivo)
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"AVISO: Arquivo {arquivo} não encontrado em {caminho_arquivo}.")
        return None
    except json.JSONDecodeError as e:
        print(f"ERRO: Falha ao decodificar o JSON em {arquivo}. Verifique a formatação. Detalhe: {e}")
        return None
    except Exception as e:
        print(f"ERRO: Erro inesperado ao ler {arquivo}: {e}")
        traceback.print_exc()
        return None

# **** FUNÇÃO MODIFICADA PARA LER calendario.json ****
def carregar_calendario(formatar_para_template=False):
    """Carrega eventos do calendario.json.

    Args:
        formatar_para_template (bool): Se True, formata a saída para
            ser compatível com o template calendario.html (data_iso, evento, mes_curto).
            Se False, retorna a lista de dicionários do JSON original.

    Returns:
        list: Lista de dicionários de eventos, formatada ou não. Retorna lista vazia em caso de erro.
    """
    eventos_json = carregar_dados_json("calendario.json")

    if eventos_json is None:
        return [] # Retorna lista vazia se o ficheiro não foi encontrado ou teve erro

    if not isinstance(eventos_json, list):
        print("ERRO: O ficheiro calendario.json não contém uma lista JSON válida no nível superior.")
        return []

    if not formatar_para_template:
        # Apenas ordena por data_inicio para o contexto
        try:
            # Garante que eventos sem data_inicio não quebrem a ordenação
            return sorted(eventos_json, key=lambda x: x.get("data_inicio", "9999-99-99"))
        except Exception as e:
             print(f"ERRO: Falha ao ordenar calendário para o contexto: {e}")
             return eventos_json # Retorna desordenado

    # --- Formatação para compatibilidade com calendario.html ---
    eventos_formatados = []
    meses_map = { 1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN", 7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ" }

    for evento in eventos_json:
        try:
            data_inicio_str = evento.get("data_inicio")
            descricao = evento.get("descricao", "Evento sem descrição")

            if not data_inicio_str:
                print(f"AVISO: Evento sem 'data_inicio' ignorado no calendario.json: {descricao}")
                continue

            # Converte a data YYYY-MM-DD para objeto datetime
            data_obj = datetime.strptime(data_inicio_str, "%Y-%m-%d")

            eventos_formatados.append({
                "data": data_obj.strftime("%d/%m/%Y"), # Formato DD/MM/YYYY para exibição
                "evento": descricao,                    # Usa a descrição como nome do evento
                "data_obj": data_obj,                   # Objeto datetime para ordenar
                "data_iso": data_inicio_str,            # Formato YYYY-MM-DD (já vem do JSON)
                "mes_curto": meses_map.get(data_obj.month), # Mês abreviado
                "data_fim": evento.get("data_fim")      # Guarda data_fim se existir
            })
        except ValueError:
            print(f"AVISO: Formato de data inválido ('YYYY-MM-DD' esperado) em 'data_inicio' no calendario.json: {data_inicio_str}")
        except Exception as e:
            print(f"ERRO inesperado ao processar evento do calendário para template: {evento} - {e}")

    # Ordena os eventos formatados pela data de início
    return sorted(eventos_formatados, key=lambda x: x["data_obj"])

# **** NOVA FUNÇÃO ****
def carregar_matriz():
    """Carrega os dados da matriz curricular do matriz.json."""
    dados = carregar_dados_json("matriz.json")
    # Verifica se carregou e se é uma lista (novo formato esperado)
    if dados and isinstance(dados, list):
         return dados
    # Verifica se carregou e se é um dicionário (formato antigo de 1 período)
    elif dados and isinstance(dados, dict) and "periodo" in dados and "disciplinas" in dados:
         print("AVISO: matriz.json parece conter apenas um período. Convertendo para lista.")
         return [dados] # Converte para lista para consistência
    else:
         print("AVISO: Formato inesperado ou erro ao carregar matriz.json. Esperava uma lista de períodos ou um objeto de período único.")
         return None # Retorna None se o formato for inválido ou erro


def carregar_quiz_vark():
    """Carrega os dados do quiz VARK do metodo_estudo.json."""
    return carregar_dados_json("metodo_estudo.json")

# =======================================================
# CONTEXTO INICIAL (ATUALIZADO PARA USAR JSON)
# =======================================================
def calcular_contexto_inicial():
    """Calcula o contexto inicial combinando informações gerais, calendário e matriz."""
    contexto_base = "Você é um assistente acadêmico chamado Lumi, focado em ajudar alunos da UniEVANGÉLICA, Anápolis, Goiás."
    try:
        # Tenta carregar informações gerais
        caminho_info = os.path.join(os.path.dirname(__file__), "informacoes.txt")
        if os.path.exists(caminho_info):
            with open(caminho_info, "r", encoding="utf-8") as f:
                info_content = f.read().strip()
                # Remove matriz antiga se existir (melhor remover manualmente do txt)
                matriz_start_old = info_content.find("[Matriz Curricular]")
                if matriz_start_old != -1:
                    contexto_base = info_content[:matriz_start_old].strip()
                else:
                    contexto_base = info_content
            print("Informações gerais carregadas de informacoes.txt.")
        else:
            print("AVISO: 'informacoes.txt' não encontrado.")
    except Exception as e:
        print(f"Erro ao ler 'informacoes.txt': {e}")

    # --- Adiciona Calendário Acadêmico ao Contexto ---
    contexto_calendario = "\n\n[Calendário Acadêmico Resumido]\n"
    # Pega dados crus do JSON, já ordenados por data_inicio
    eventos_calendario = carregar_calendario(formatar_para_template=False)
    if eventos_calendario:
        eventos_para_contexto = []
        hoje = date.today() # Usar date para comparar apenas a data
        count = 0
        max_eventos_contexto = 15 # Limite de eventos no contexto

        for ev in eventos_calendario:
            if count >= max_eventos_contexto: break
            try:
                data_inicio_str = ev.get("data_inicio")
                if not data_inicio_str: continue

                data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
                data_fim_str = ev.get("data_fim", data_inicio_str) # Usa data_inicio se data_fim não existir
                data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()

                # Inclui eventos que ainda não terminaram
                if data_fim >= hoje:
                    evento_str = f"- {data_inicio.strftime('%d/%m/%Y')}"
                    if data_fim != data_inicio:
                        evento_str += f" a {data_fim.strftime('%d/%m/%Y')}"
                    evento_str += f": {ev.get('descricao', 'Evento sem descrição')}"
                    # Adiciona informação extra se disponível (ex: tipo, local)
                    # if ev.get('tipo'): evento_str += f" (Tipo: {ev['tipo']})"
                    eventos_para_contexto.append(evento_str)
                    count += 1
            except (ValueError, KeyError, TypeError) as e:
                 print(f"AVISO: Ignorando evento do calendário no contexto devido a erro: {ev} - {e}")
                 continue

        if eventos_para_contexto:
            contexto_calendario += "\n".join(eventos_para_contexto)
            if len(eventos_calendario) > count: # Indica se há mais eventos não mostrados
                 contexto_calendario += "\n(...e mais eventos...)"
            print(f"{count} eventos futuros/atuais do calendário adicionados ao contexto.")
        else:
             contexto_calendario += "Nenhum evento futuro/atual encontrado no calendário.\n"
    else:
        contexto_calendario += "Não foi possível carregar os dados do calendário.\n"
        print("AVISO: Falha ao carregar calendário para o contexto.")

    # --- Adiciona Matriz Curricular ao Contexto ---
    contexto_matriz = "\n\n[Matriz Curricular Resumida - Engenharia de IA]\n"
    dados_matriz_lista = carregar_matriz() # Espera uma lista de períodos
    if dados_matriz_lista:
         max_periodos_contexto = 3 # Limita períodos no contexto
         max_disciplinas_por_periodo = 5 # Limita disciplinas por período no contexto
         for i, periodo_info in enumerate(dados_matriz_lista):
             if i >= max_periodos_contexto: break
             # Garante que periodo_info seja um dicionário
             if not isinstance(periodo_info, dict):
                 print(f"AVISO: Item inválido na lista de matriz.json (esperava dicionário): {periodo_info}")
                 continue

             num_periodo = periodo_info.get('periodo', f'{i+1}º') # Usa índice se chave 'periodo' faltar
             disciplinas = periodo_info.get('disciplinas', [])
             if isinstance(disciplinas, list) and disciplinas:
                 contexto_matriz += f"\n {num_periodo} Período:\n"
                 nomes_disciplinas = [d.get('nome', '?') for d in disciplinas[:max_disciplinas_por_periodo] if isinstance(d, dict)] # Pega nomes das disciplinas
                 contexto_matriz += "  - " + "\n  - ".join(nomes_disciplinas)
                 if len(disciplinas) > max_disciplinas_por_periodo: contexto_matriz += "\n  - (...)"
                 contexto_matriz += "\n"
             else:
                  print(f"AVISO: 'disciplinas' ausente ou inválida para o período {num_periodo} em matriz.json")

         if len(dados_matriz_lista) > max_periodos_contexto: contexto_matriz += "(... e outros períodos ...)\n"
         print(f"Resumo dos primeiros {min(len(dados_matriz_lista), max_periodos_contexto)} períodos da matriz adicionado ao contexto.")
    else:
        contexto_matriz += "Não foi possível carregar os dados da matriz curricular ou formato inválido.\n"
        print("AVISO: Falha ao carregar matriz para o contexto.")

    # --- Adiciona Quiz VARK ao Contexto ---
    contexto_vark = "\n\n[Informações sobre Estilos de Aprendizagem VARK]\n"
    quiz_data = carregar_quiz_vark()
    if quiz_data and "resultados" in quiz_data:
        contexto_vark += f"Ofereço um quiz ({len(quiz_data.get('perguntas',[]))} perguntas) para identificar o estilo de aprendizagem (VARK). {quiz_data.get('descricao', '')}\nResumo dos estilos:\n";
        for tipo, detalhes in quiz_data["resultados"].items():
            desc_curta = detalhes.get('descricao', 'Sem descrição.'); ponto_final = desc_curta.find('.');
            if ponto_final != -1: desc_curta = desc_curta[:ponto_final + 1]
            contexto_vark += f"- {detalhes.get('titulo', tipo)} ({tipo}): {desc_curta}\n";
        print("Quiz VARK carregado para o contexto.")
    else:
        contexto_vark += "Ofereço um quiz para identificar o estilo de aprendizagem (Visual, Auditivo, Leitura/Escrita, Cinestésico).\n"
        print("AVISO: Falha ao carregar quiz VARK para o contexto.")

    # Combina tudo
    contexto_final = f"{contexto_base.strip()}\n{contexto_calendario.strip()}\n{contexto_matriz.strip()}\n{contexto_vark.strip()}"
    print("-" * 20 + " CONTEXTO INICIAL CALCULADO " + "-" * 20)
    # print(contexto_final) # Descomentar para ver o contexto completo no terminal
    print("-" * (40 + len(" CONTEXTO INICIAL CALCULADO ")))
    return contexto_final

CONTEXTO_INICIAL = calcular_contexto_inicial() # Calcula o contexto quando o app inicia

# =======================================================
# 3. ROTAS DE AUTENTICAÇÃO
# =======================================================
# ... (Rotas /login, /register, /logout - SEM ALTERAÇÕES) ...
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        login_identifier = request.form.get('login_identifier'); password = request.form.get('password'); remember = bool(request.form.get('remember'));
        if not login_identifier or not password: flash('Email/Matrícula e senha são obrigatórios.', 'warning'); return redirect(url_for('login'));
        user = User.query.filter( (User.email == login_identifier) | (User.matricula == login_identifier) ).first();
        if user and user.check_password(password):
            login_user(user, remember=remember); flash('Login realizado com sucesso!', 'success'); next_page = request.args.get('next'); return redirect(next_page or url_for('index'));
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
            flash('Conta criada com sucesso! Por favor, faça login.', 'success'); return redirect(url_for('login'));
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
    # Garante que o histórico existe e usa o CONTEXTO_INICIAL mais recente
    if 'historico' not in session or not session['historico'] or CONTEXTO_INICIAL not in session['historico'][0]['parts'][0]:
        session['historico'] = [{"role": "user", "parts": [CONTEXTO_INICIAL]}, {"role": "model", "parts": [f"Olá {current_user.username}! Eu sou a Lumi. Como posso te ajudar hoje?"]}]
    return render_template("index.html", current_user=current_user)

@app.route("/profile")
@login_required
def profile(): return render_template("profile.html")

@app.route("/faq")
@login_required
def faq(): dados = carregar_dados_json("faq.json") or []; return render_template("faq.html", faq_data=dados)

# **** ROTA CALENDÁRIO MODIFICADA ****
@app.route("/calendario")
@login_required
def calendario():
    # Chama a função formatando para o template
    eventos_data = carregar_calendario(formatar_para_template=True)
    if not eventos_data and carregar_dados_json("calendario.json") is not None: # Avisa apenas se o JSON foi lido mas a formatação falhou
         flash("Eventos do calendário carregados, mas houve um erro na formatação para exibição.", "warning")
    elif not eventos_data: # Avisa se o JSON não foi lido
         flash("Não foi possível carregar os eventos do calendário (verifique 'calendario.json').", "danger")
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

@app.route("/metodo_de_estudo")
@login_required
def metodo_de_estudo():
    quiz_data = carregar_quiz_vark()
    if quiz_data is None: flash("Erro ao carregar dados do quiz.", "danger"); return render_template("metodo_de_estudo.html", quiz_data=None, error=True)
    return render_template("metodo_de_estudo.html", quiz_data=quiz_data)

# =======================================================
# 5. ROTA DA API DO CHAT (Protegida)
# =======================================================
@app.route("/ask", methods=["POST"])
@login_required
def ask():
    if not model: return jsonify({"resposta": "Desculpe, o serviço de chat não está configurado."}), 500
    data = request.json; pergunta = data.get("pergunta") if data else None;
    if not pergunta: return jsonify({"resposta": "Nenhuma pergunta recebida."}), 400
    try:
        historico_chat = session.get('historico', None);
        # Garante que o histórico existe e usa o CONTEXTO_INICIAL mais recente
        if historico_chat is None or not historico_chat or CONTEXTO_INICIAL not in historico_chat[0]['parts'][0]:
            print("DEBUG: Recriando histórico na sessão para /ask")
            historico_chat = [{"role": "user", "parts": [CONTEXTO_INICIAL]}, {"role": "model", "parts": [f"Olá {current_user.username}! Como posso ajudar?"]}]

        chat = model.start_chat(history=historico_chat); response = chat.send_message(pergunta); response_text = getattr(response, 'text', 'Desculpe, não consegui gerar uma resposta.');
        historico_chat.append({"role": "user", "parts": [pergunta]}); historico_chat.append({"role": "model", "parts": [response_text]});
        session['historico'] = historico_chat; # Salva de volta na sessão
        return jsonify({"resposta": response_text});
    except Exception as e:
        print(f"Erro na API do Gemini ou processamento na rota /ask: {e}");
        traceback.print_exc();
        return jsonify({"resposta": f"Desculpe, ocorreu um erro inesperado."}), 500;

# =======================================================
# 6. FILTRO JINJA (para formatar data no template)
# =======================================================
@app.template_filter('format_date_br')
def format_date_br_filter(value):
    """Filtro Jinja para formatar data YYYY-MM-DD para DD/MM/YYYY."""
    if not value: return ""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError: return value # Retorna original se formato inválido

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

