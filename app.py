# =======================================================
# TÍTULO: SERVIDOR FLASK (APP.PY) - ASSISTENTE LUMI
# =======================================================

# =======================================================
# IMPORTAÇÕES
# =======================================================
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import requests
import json
import os
from datetime import datetime

# =======================================================
# CONFIGURAÇÃO DA APLICAÇÃO FLASK
# =======================================================
app = Flask(__name__)
app.secret_key = "segredo_da_lumi" # Em produção, use uma chave forte e secreta

# =======================================================
# 1. CONSTANTES DO OLLAMA
# =======================================================
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODELO = "gemma:2b"

# =======================================================
# 2. FUNÇÕES DE CARREGAMENTO DE DADOS
# =======================================================
def carregar_dados_json(nome_ficheiro):
    """Função genérica para carregar dados de um ficheiro JSON."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, nome_ficheiro)
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"AVISO: O ficheiro {nome_ficheiro} não foi encontrado.")
        return {} # Retorna dict vazio para .get() funcionar
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
        txt_path = os.path.join(base_dir, 'calendario.txt')
        with open(txt_path, 'r', encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if ':' in linha:
                    partes = linha.split(':', 1)
                    data_str, evento_desc = partes[0].strip(), partes[1].strip()
                    data_obj = datetime.strptime(data_str, '%d/%m/%Y')
                    eventos.append({"data_obj": data_obj, "data_str": data_str, "evento": evento_desc})
        eventos.sort(key=lambda x: x["data_obj"])
        return eventos
    except FileNotFoundError:
        print("AVISO: O ficheiro calendario.txt não foi encontrado.")
        return []
    except Exception as e:
        print(f"ERRO ao carregar calendario.txt: {e}")
        return []

# =======================================================
# 3. FUNÇÃO DO ASSISTENTE (OLLAMA)
# =======================================================
def responder_avancado(pergunta, historico_conversa):
    """Envia uma pergunta para o modelo de linguagem local via Ollama."""
    try:
        now = datetime.now()
        data_hora_atual = now.strftime("%A, %d de %B de %Y, %H:%M")
        prompt_sistema = (
            f"Você é a Lumi, uma assistente académica da UniEVANGÉLICA. "
            f"A data e hora atuais são: {data_hora_atual}. "
            "Seja sempre extremamente simpática, prestativa e use emojis de forma apropriada. 😊"
        )
        mensagens = [{"role": "system", "content": prompt_sistema}]
        if historico_conversa:
            for interacao in historico_conversa:
                mensagens.append({"role": "user", "content": interacao["usuario"]})
                mensagens.append({"role": "assistant", "content": interacao["lumi"]})
        mensagens.append({"role": "user", "content": pergunta})
        payload = {"model": OLLAMA_MODELO, "messages": mensagens, "stream": False}
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status() 
        return response.json()['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"ERRO de conexão com o Ollama: {e}")
        return "⚠️ Desculpe, não consegui me conectar ao meu cérebro (Ollama). Verifique se o serviço está em execução."
    except Exception as e:
        print(f"ERRO desconhecido na IA: {e}")
        return f"⚠️ Ocorreu um erro inesperado ao processar sua pergunta: {e}"

# =======================================================
# 4. ROTAS DO SITE
# =======================================================
@app.route('/')
def index():
    """Renderiza a página inicial com o chat."""
    if "historico" not in session:
        session["historico"] = []
    return render_template('index.html', historico=session.get("historico", []))

@app.route('/ask', methods=['POST'])
def ask():
    """Processa a pergunta do usuário e retorna a resposta da IA."""
    if "historico" not in session:
        session["historico"] = []
    pergunta = request.json.get('pergunta')
    if not pergunta or not pergunta.strip():
        return jsonify({'erro': 'Pergunta vazia'}), 400
    resposta = responder_avancado(pergunta, session.get("historico", []))
    session["historico"].append({"usuario": pergunta, "lumi": resposta})
    session.modified = True
    return jsonify({'resposta': resposta})

@app.route('/limpar_chat')
def limpar_chat():
    """Limpa o histórico do chat na sessão."""
    session.pop("historico", None)
    return redirect(url_for('index'))

@app.route('/faq')
def faq():
    """Renderiza a página de Perguntas Frequentes (FAQ)."""
    
    # --- CORREÇÃO DO ATTRIBUTEERROR ---
    # Seu faq.json é uma LISTA, então apenas carregamos e passamos.
    faq_data = carregar_dados_json('faq.json')
    # --- FIM DA CORREÇÃO ---
    
    # Garante que, se o arquivo falhar ao carregar, passamos uma lista vazia
    if not isinstance(faq_data, list):
        faq_data = []

    return render_template('faq.html', faq_data=faq_data)

@app.route('/calendario')
def calendario():
    """Renderiza a página do Calendário Acadêmico."""
    eventos_data = carregar_calendario()
    return render_template('calendario.html', eventos_data=eventos_data)

@app.route('/flashcards')
def flashcards():
    """Renderiza a página de Flashcards."""
    dados = carregar_dados_json('flashcards.json')
    
    # Esta lógica está CORRETA para flashcards (que é um dict)
    # Isso corrige o erro "Nenhuma disciplina..."
    flashcard_data = dados.get('flash_cards', dados)
    
    return render_template('flashcards.html', flashcard_data=flashcard_data)

# =======================================================
# 5. EXECUÇÃO DO SERVIDOR FLASK
# =======================================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)