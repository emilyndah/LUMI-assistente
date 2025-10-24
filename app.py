# =======================================================
# TÍTULO: SERVIDOR FLASK (APP.PY) - ASSISTENTE LUMI
# =======================================================

# =======================================================
# IMPORTAÇÕES
# =======================================================
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, Response, stream_with_context
import requests
import json
import os
from datetime import datetime
import time  # Adicionado para simulação de lentidão em debug, se necessário

# =======================================================
# CONFIGURAÇÃO DA APLICAÇÃO FLASK
# =======================================================
app = Flask(__name__)
app.secret_key = "segredo_da_lumi"  # Em produção, use uma chave forte e secreta

# =======================================================
# 1. CONSTANTES DO OLLAMA
# =======================================================
OLLAMA_URL_CHAT = "http://localhost:11434/api/chat"
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
        txt_path = os.path.join(base_dir, 'calendario.txt')
        with open(txt_path, 'r', encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if ':' in linha:
                    partes = linha.split(':', 1)
                    data_str, evento_desc = partes[0].strip(
                    ), partes[1].strip()
                    data_obj = datetime.strptime(data_str, '%d/%m/%Y')
                    eventos.append(
                        {"data_obj": data_obj, "data_str": data_str, "evento": evento_desc})
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


def construir_mensagens_ia(pergunta, historico_conversa):
    """Constrói a lista de mensagens no formato exigido pelo Ollama/OpenAI."""
    now = datetime.now()
    data_hora_atual = now.strftime("%A, %d de %B de %Y, %H:%M")
    prompt_sistema = (
        f"Você é a Lumi, uma assistente académica da UniEVANGÉLICA. "
        f"A data e hora atuais são: {data_hora_atual}. "
        f"Seja sempre simpática, prestativa e inteligente. "
        f"Não repita palavras desnecessariamente e mantenha as respostas concisas."
    )
    mensagens = [{"role": "system", "content": prompt_sistema}]

    # Adiciona o histórico da sessão
    if historico_conversa:
        for interacao in historico_conversa:
            mensagens.append({"role": "user", "content": interacao["usuario"]})
            mensagens.append(
                {"role": "assistant", "content": interacao["lumi"]})

    mensagens.append({"role": "user", "content": pergunta})
    return mensagens


def generate_stream(pergunta_usuario):
    """
    Função Geradora que envia a pergunta para o Ollama
    e retorna a resposta em pedaços (chunks) para o streaming.
    """
    historico = session.get("historico", [])
    mensagens = construir_mensagens_ia(pergunta_usuario, historico)

    # O payload deve ter "stream": True para que o Ollama envie dados em chunks
    payload = {
        "model": OLLAMA_MODELO,
        "messages": mensagens,
        "stream": True
    }

    full_response = ""
    try:
        # requests.post com stream=True é crucial
        response = requests.post(
            OLLAMA_URL_CHAT, json=payload, stream=True, timeout=120)
        response.raise_for_status()

        # Itera sobre o stream de linhas da resposta HTTP
        for line in response.iter_lines():
            if line:
                try:
                    # Cada linha é um objeto JSON que contém um pedaço da resposta
                    chunk = json.loads(line.decode('utf-8'))
                    token = chunk.get("message", {}).get("content", "")

                    # O "done": true sinaliza o fim da resposta, ignoramos o metadado final.
                    if chunk.get("done") is False and token:
                        full_response += token
                        # Envia o pedaço (token) de volta ao cliente imediatamente
                        yield token

                except json.JSONDecodeError:
                    continue

        # Após o streaming, atualiza o histórico na sessão com a resposta completa
        # Isso é fundamental para manter o contexto da conversa
        if full_response.strip():
            session["historico"].append(
                {"usuario": pergunta_usuario, "lumi": full_response.strip()})
            session.modified = True

    except requests.exceptions.RequestException as e:
        error_msg = f"⚠️ ERRO de conexão com o Ollama: {e}. Verifique se o serviço está em execução."
        print(error_msg)
        yield error_msg
    except Exception as e:
        error_msg = f"⚠️ Ocorreu um erro inesperado na IA: {e}"
        print(error_msg)
        yield error_msg


# =======================================================
# 4. ROTAS DO SITE
# =======================================================
@app.route('/')
def index():
    """Renderiza a página inicial com o chat."""
    if "historico" not in session:
        session["historico"] = []
    # Nota: A rota index só renderiza a página. O JavaScript fará a chamada POST para /stream_ask
    return render_template('index.html', historico=session.get("historico", []))


@app.route('/stream_ask', methods=['POST'])
def stream_ask():
    """
    NOVA ROTA: Processa a pergunta do usuário e envia a resposta
    em tempo real (streaming) para o navegador.
    """
    pergunta = request.form.get('pergunta')
    if not pergunta or not pergunta.strip():
        # Retorna uma resposta simples de erro para o streaming
        return Response(stream_with_context(iter(["Pergunta vazia ou inválida."])), mimetype='text/event-stream', status=400)

    # Cria a resposta como um stream de texto
    return Response(stream_with_context(generate_stream(pergunta)),
                    mimetype='text/event-stream')


@app.route('/ask', methods=['POST'])
def ask():
    """
    ROTA ANTIGA (SEM STREAMING): Mantida por conveniência ou para uso futuro 
    com Cache. Por enquanto, redireciona para o streaming.
    """
    # Para usar o streaming, o front-end deve chamar /stream_ask.
    # Esta rota pode ser usada para um cache futuro (não implementado aqui).
    # Por agora, está configurada para retornar erro, forçando o uso do streaming.
    return jsonify({'erro': 'Use a rota /stream_ask para interagir com a IA.'}), 400


@app.route('/limpar_chat')
def limpar_chat():
    """Limpa o histórico do chat na sessão."""
    session.pop("historico", None)
    return redirect(url_for('index'))


@app.route('/faq')
def faq():
    """Renderiza a página de Perguntas Frequentes (FAQ)."""
    faq_data = carregar_dados_json('faq.json')
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
    flashcard_data = dados.get('flash_cards', dados)
    return render_template('flashcards.html', flashcard_data=flashcard_data)

# =======================================================
# ============ ROTA DO MÉTODO DE ESTUDO (VARK) ============
# =======================================================


@app.route('/metodo_de_estudo')
def metodo_de_estudo():
    """Renderiza o quiz para descobrir o método de estudo (VARK)."""
    return render_template('metodo_estudo.html')
# =======================================================
# ================== FIM DA ROTA ===================
# =======================================================


# =======================================================
# 5. EXECUÇÃO DO SERVIDOR FLASK
# =======================================================
if __name__ == '__main__':
    # Executa escutando em todos IPs locais na porta 5000 com debug
    app.run(host='0.0.0.0', port=5000, debug=True)
# ========================================================
