# =======================================================
# TÍTULO: SERVIDOR FLASK (APP.PY) - ASSISTENTE LUMI
# (ADAPTADO PARA GOOGLE GEMINI)
# =======================================================

# =======================================================
# IMPORTAÇÕES
# =======================================================
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import json
import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv  # <<< MUDANÇA: Para carregar o .env

# Carrega variáveis de ambiente do arquivo .env (se ele existir)
load_dotenv()

# =======================================================
# CONFIGURAÇÃO DA APLICAÇÃO FLASK
# =======================================================
app = Flask(__name__)
# Em produção, use uma chave forte e secreta
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "segredo_da_lumi_para_desenvolvimento"
)

# =======================================================
# 1. CONSTANTES DO GEMINI
# =======================================================

# --- Configuração do Gemini ---
try:
    # Tenta carregar a chave de um variável de ambiente (MAIS SEGURO)
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
except KeyError:
    # Se não encontrar, o app não pode funcionar.
    print("=" * 80)
    print(" [ ERRO CRÍTICO ] ".center(80, "="))
    print("A variável de ambiente 'GEMINI_API_KEY' não foi definida.")
    print("Crie um arquivo chamado '.env' neste diretório e adicione a linha:")
    print("GEMINI_API_KEY=SUA_CHAVE_REAL_AQUI")
    print("=" * 80)
    # Define como None para que a próxima etapa falhe de forma controlada
    GEMINI_API_KEY = None  # CORREÇÃO: Usar None em vez de ()

GEMINI_MODELO = "gemini-2.5-flash"  # Rápido e eficiente para chat

# Configura a biblioteca do Gemini
try:
    ### CORREÇÃO PRINCIPAL AQUI ###
    # A checagem anterior (GEMINI_API_KEY is GEMINI_API_KEY) estava errada.
    # A forma correta é checar se a chave é nula ou vazia.
    if not GEMINI_API_KEY:
        raise ValueError(
            "API Key não foi fornecida. Verifique as mensagens de erro."
        )

    genai.configure(api_key=GEMINI_API_KEY)
    print("API Key do Gemini carregada com sucesso.")

except Exception as e:
    print(f"ERRO ao configurar a API do Gemini: {e}")
    print("Verifique se a API Key é válida.")
    GEMINI_API_KEY = None  # CORREÇÃO: Usar None em vez de ()


# =======================================================
# 2. FUNÇÕES DE CARREGAMENTO DE DADOS
# =======================================================


def carregar_dados_json(nome_ficheiro):
    """Função genérica para carregar dados de um ficheiro JSON."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, nome_ficheiro)
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"AVISO: O ficheiro {nome_ficheiro} não foi encontrado.")
        return {}  # Retorna dict vazio para .get() funcionar
    except json.JSONDecodeError:
        print(f"ERRO: O ficheiro {nome_ficheiro} contém JSON inválido.")
        return {}
    except Exception as e:
        print(f"ERRO desconhecido ao carregar {nome_ficheiro}: {e}")
        return {}


def carregar_calendario():
    """Lê o ficheiro calendario.txt e retorna uma lista de eventos ordenados."""
    eventos = []
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        txt_path = os.path.join(base_dir, "calendario.txt")
        with open(txt_path, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if ":" in linha:
                    partes = linha.split(":", 1)
                    data_str, evento_desc = partes[0].strip(
                    ), partes[1].strip()
                    data_obj = datetime.strptime(data_str, "%d/%m/%Y")
                    eventos.append(
                        {
                            "data_obj": data_obj,
                            "data_str": data_str,
                            "evento": evento_desc,
                        }
                    )
        eventos.sort(key=lambda x: x["data_obj"])
        return eventos
    except FileNotFoundError:
        print("AVISO: O ficheiro calendario.txt não foi encontrado.")
        return []
    except Exception as e:
        print(f"ERRO ao carregar calendario.txt: {e}")
        return []


# =======================================================
# 3. FUNÇÃO DO ASSISTENTE (GEMINI)
# =======================================================
def responder_avancado(pergunta, historico_conversa):
    """Envia uma pergunta para o modelo de linguagem do Gemini."""

    # Verifica se a API Key foi carregada corretamente
    # Esta checagem agora funciona, pois padronizamos para None
    if GEMINI_API_KEY is None:
        return "⚠️ Desculpe, o serviço de IA não está configurado. O administrador precisa definir a GEMINI_API_KEY."

    try:
        now = datetime.now()
        data_hora_atual = now.strftime("%A, %d de %B de %Y, %H:%M")

        # --- Prompt do Sistema para o Gemini ---
        prompt_sistema = (
            f"Você é a Lumi, uma assistente académica da UniEVANGÉLICA. "
            f"A data e hora atuais são: {data_hora_atual}. "
            f"Seja sempre simpática, prestativa e inteligente. "
            f"Não repita palavras desnecessariamente e mantenha as respostas concisas."
        )

        # --- Inicializa o modelo do Gemini ---
        model = genai.GenerativeModel(
            model_name=GEMINI_MODELO, system_instruction=prompt_sistema
        )

        # --- Converte o histórico para o formato do Gemini ---
        # Formato Flask Session: [{"usuario": "...", "lumi": "..."}]
        # Formato Gemini: [{"role": "user", "parts": ["..."]}, {"role": "model", "parts": ["..."]}]
        historico_gemini = []
        for interacao in historico_conversa:
            historico_gemini.append(
                {"role": "user", "parts": [interacao["usuario"]]})
            # Importante: Ollama usa "assistant", Gemini usa "model"
            historico_gemini.append(
                {"role": "model", "parts": [interacao["lumi"]]})

        # Inicia o chat com o histórico convertido
        chat = model.start_chat(history=historico_gemini)

        # Envia a nova pergunta
        response = chat.send_message(pergunta)

        return response.text.strip()

    # <<< MUDANÇA: Captura de exceção genérica da API do Gemini
    except Exception as e:
        print(f"ERRO de conexão com o Gemini: {e}")
        if "API_KEY_INVALID" in str(e):
            return "⚠️ Desculpe, sua API Key do Gemini parece ser inválida. Verifique a configuração."
        return f"⚠️ Desculpe, não consegui me conectar ao meu cérebro (Gemini). Ocorreu um erro: {e}"


# =======================================================
# 4. ROTAS DO SITE
# =======================================================
@app.route("/")
def index():
    """Renderiza a página inicial com o chat."""
    if "historico" not in session:
        session["historico"] = []
    return render_template("index.html", historico=session.get("historico", []))


@app.route("/ask", methods=["POST"])
def ask():
    """Processa a pergunta do usuário e retorna a resposta da IA."""
    if "historico" not in session:
        session["historico"] = []

    pergunta = request.json.get("pergunta")

    if not pergunta or not pergunta.strip():
        return jsonify({"erro": "Pergunta vazia"}), 400
    
    # Esta função agora chama o Gemini
    resposta = responder_avancado(pergunta, session.get("historico", []))

    session["historico"].append({"usuario": pergunta, "lumi": resposta})
    session.modified = True

    return jsonify({"resposta": resposta})


@app.route("/limpar_chat")
def limpar_chat():
    """Limpa o histórico do chat na sessão."""
    session.pop("historico", None)
    return redirect(url_for("index"))


@app.route("/faq")
def faq():
    """Renderiza a página de Perguntas Frequentes (FAQ)."""
    faq_data = carregar_dados_json("faq.json")
    if not isinstance(faq_data, list):
        faq_data = []
    return render_template("faq.html", faq_data=faq_data)


@app.route("/calendario")
def calendario():
    """Renderiza a página do Calendário Acadêmico."""
    eventos_data = carregar_calendario()
    return render_template("calendario.html", eventos_data=eventos_data)


@app.route("/flashcards")
def flashcards():
    """Renderiza a página de Flashcards."""
    dados = carregar_dados_json("flashcards.json")
    flashcard_data = dados.get("flash_cards", dados)
    return render_template("flashcards.html", flashcard_data=flashcard_data)


# =======================================================
# ============ ROTA DO MÉTODO DE ESTUDO (VARK) ============
# =======================================================
@app.route("/metodo_de_estudo")
def metodo_de_estudo():
    """Renderiza o quiz para descobrir o método de estudo (VARK)."""
    # Apenas renderiza o HTML. Os dados estão dentro dele.
    return render_template("metodo_estudo.html")


# =======================================================
# ================== FIM DA ROTA ===================
# =======================================================


# =======================================================
# 5. EXECUÇÃO DO SERVIDOR FLASK
# =======================================================
if __name__ == "__main__":
    # Esta checagem agora funciona, pois padronizamos para None
    if GEMINI_API_KEY is None:
        print("Servidor Flask NÃO foi iniciado. Verifique o erro da API Key acima.")
    else:
        # Executa escutando em todos IPs locais na porta 5000 com debug
        app.run(host="0.0.0.0", port=5000, debug=True)
