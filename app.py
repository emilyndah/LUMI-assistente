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
from dotenv import load_dotenv  # Para carregar o .env

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
# 1. CONSTANTES E CONFIGURAÇÃO DO GEMINI
# =======================================================

# --- Configuração da API Key ---
try:
    # Tenta carregar a chave de um variável de ambiente (MAIS SEGURO)
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
except KeyError:
    # Se não encontrar, o app não pode funcionar.
    print("=" * 80)
    print("ERRO: Variável de ambiente GEMINI_API_KEY não encontrada.")
    print("Por favor, crie um arquivo .env e adicione a linha:")
    print("GEMINI_API_KEY=SUA_CHAVE_AQUI")
    print("=" * 80)
    GEMINI_API_KEY = None  # Define como None para checagem posterior

# --- Configuração do Modelo ---
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

    generation_config = {
        "temperature": 0.8,
        "top_p": 0.9,
        "top_k": 40,
        "max_output_tokens": 1500,
    }

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest", # Ou o modelo que preferir
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        print("Modelo Gemini inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar o modelo Gemini: {e}")
        GEMINI_API_KEY = None # Falha na inicialização
else:
    print("API Key do Gemini não encontrada. O Chatbot não funcionará.")


# --- Contexto Inicial (Sistema) ---
def carregar_contexto_inicial():
    """Carrega o contexto base do arquivo informacoes.txt."""
    try:
        with open("informacoes.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print("Aviso: 'informacoes.txt' não encontrado. O chatbot pode não ter contexto.")
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
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Arquivo {arquivo} não encontrado.")
        return {}
    except json.JSONDecodeError:
        print(f"Erro ao decodificar o JSON em {arquivo}.")
        return {}
    except Exception as e:
        print(f"Erro inesperado ao ler {arquivo}: {e}")
        return {}

# ===================================================
# FUNÇÃO DO CALENDÁRIO (JÁ MODIFICADA)
# ===================================================
def carregar_calendario():
    """Carrega, formata e ordena os eventos do calendário a partir de um TXT.

    Retorna:
        list: Lista de dicionários, cada um contendo 'data', 'evento',
              'data_obj' (para ordenação), 'data_iso' (para JS) e 'mes_curto'.
    """
    eventos = []
    meses_map = {
        1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
        7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
    }

    try:
        with open("calendario.txt", "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue

                # Divide a linha no primeiro ":" encontrado
                partes = linha.split(":", 1)
                if len(partes) < 2:
                    continue  # Ignora linhas mal formatadas

                data_str = partes[0].strip()
                evento_str = partes[1].strip()

                try:
                    # Tenta analisar a data no formato DD/MM/YYYY
                    data_obj = datetime.strptime(data_str, "%d/%m/%Y")
                    
                    eventos.append({
                        "data": data_str,                      # Formato original: DD/MM/YYYY
                        "evento": evento_str,                  # Texto do evento
                        "data_obj": data_obj,                  # Objeto datetime para ordenar
                        "data_iso": data_obj.strftime("%Y-%m-%d"), # Formato YYYY-MM-DD para o FullCalendar
                        "mes_curto": meses_map.get(data_obj.month) # Mês abreviado para a lista
                    })
                except ValueError:
                    print(f"Formato de data inválido ignorado: {data_str}")

    except FileNotFoundError:
        print("Arquivo calendario.txt não encontrado.")
        return []
    except Exception as e:
        print(f"Erro ao ler o calendário: {e}")
        return []

    # Ordena os eventos pela data
    eventos_ordenados = sorted(eventos, key=lambda x: x["data_obj"])
    return eventos_ordenados

# =======================================================
# 3. ROTAS PRINCIPAIS (PÁGINAS HTML)
# =======================================================

@app.route("/")
def index():
    """Renderiza a página inicial do chat."""
    # Limpa/Inicia o histórico de sessão
    if "historico" not in session:
        session["historico"] = [
            {"role": "user", "parts": [CONTEXTO_INICIAL]},
            {"role": "model", "parts": ["Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje?"]}
        ]
    return render_template("index.html")


@app.route("/faq")
def faq():
    """Renderiza a página de FAQ."""
    dados = carregar_dados_json("faq.json")
    return render_template("faq.html", faq_data=dados)


@app.route("/calendario")
def calendario():
    """Renderiza a página do Calendário Acadêmico."""
    eventos_data = carregar_calendario()
    return render_template("calendario.html", eventos_data=eventos_data)


@app.route("/flashcards")
def flashcards():
    """Renderiza a página de Flashcards."""
    dados = carregar_dados_json("flashcards.json")
    # Pega a chave "flash_cards" dentro do JSON
    flashcard_data = dados.get("flash_cards", dados)
    return render_template("flashcards.html", flashcard_data=flashcard_data)


# =======================================================
# ============ ROTA PARA LIMPAR O CHAT (CORRIGIDA) ======
# =======================================================
@app.route("/limpar")
def limpar_chat():
    """Limpa o histórico do chat da sessão e redireciona para o início."""
    
    # Reinicia o histórico da sessão para o estado inicial
    session["historico"] = [
        {"role": "user", "parts": [CONTEXTO_INICIAL]},
        {"role": "model", "parts": ["Olá! Eu sou a Lumi, sua assistente acadêmica da UniEVANGÉLICA. Como posso te ajudar hoje?"]}
    ]
    
    # Redireciona o usuário de volta para a página principal (index)
    return redirect(url_for('index'))


# =======================================================
# ============ ROTA DO MÉTODO DE ESTUDO (VARK) ============
# =======================================================
@app.route("/metodo_de_estudo")
def metodo_de_estudo():
    """Renderiza o quiz para descobrir o método de estudo (VARK)."""
    return render_template("metodo_de_estudo.html")


# =======================================================
# 4. ROTA DA API DO CHAT (LÓGICA DO GEMINI)
# =======================================================
@app.route("/ask", methods=["POST"])
def ask():
    """Recebe perguntas do usuário e retorna respostas do Gemini."""
    
    # Verifica se a API Key está configurada e o modelo foi carregado
    if not model:
        return jsonify({"resposta": "Desculpe, o serviço de chat não está configurado. O administrador precisa verificar a API Key do Gemini."}), 500

    data = request.json
    pergunta = data.get("pergunta")

    if not pergunta:
        return jsonify({"resposta": "Nenhuma pergunta recebida."}), 400

    try:
        # Pega o histórico da sessão
        historico_chat = session.get("historico", [])

        # Inicia uma nova sessão de chat com o histórico
        chat = model.start_chat(history=historico_chat)

        # Envia a nova pergunta para o Gemini
        response = chat.send_message(pergunta)

        # Atualiza o histórico na sessão
        historico_chat.append({"role": "user", "parts": [pergunta]})
        historico_chat.append({"role": "model", "parts": [response.text]})
        
        session["historico"] = historico_chat

        return jsonify({"resposta": response.text})

    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        return jsonify({"resposta": f"Desculpe, ocorreu um erro ao processar sua solicitação: {e}"}), 500


# =======================================================
# 5. EXECUÇÃO DO SERVIDOR FLASK
# =======================================================
if __name__ == "__main__":
    # Checa se a API Key foi carregada antes de iniciar
    if GEMINI_API_KEY is None:
        print("Servidor Flask NÃO foi iniciado. Verifique o erro da API Key acima.")
    else:
        # Executa o app
        print("Iniciando servidor Flask em http://127.0.0.1:5000")
        app.run(debug=True, host="0.0.0.0", port=5000)