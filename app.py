from flask import Flask, render_template, request, jsonify
from itertools import combinations
import requests # MODIFICADO: Importa a biblioteca para fazer requisições HTTP
import json     # MODIFICADO: Importa a biblioteca para lidar com JSON

app = Flask(__name__)

# =======================================================
# 1. CONSTANTES DO OLLAMA
# =======================================================
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODELO = "qwen3:0.6b"
# A variável ATRASO não é necessária para requisições não-streaming.

# =======================================================
# 2. FUNÇÃO PIE (Calcula os Usuários Únicos) - Sem alterações
# =======================================================
def pie_union_size(sizes):
    labels = sorted([k[0] for k in sizes.keys() if len(k) == 1])
    total = 0
    for k in range(1, len(labels) + 1):
        s = 0
        for combo in combinations(labels, k):
            key = tuple(sorted(combo))
            s += sizes.get(key, 0)
        total += s if k % 2 == 1 else -s
    return total

# =======================================================
# 3. DADOS SIMULADOS - Sem alterações
# =======================================================
DAILY_DATA = {
    ('Email',): 40,
    ('Site',): 90,
    ('WA',): 70,
    ('Email', 'Site'): 10,
    ('Email', 'WA'): 8,
    ('Site', 'WA'): 25,
    ('Email', 'Site', 'WA'): 5
}

# =======================================================
# 4. FUNÇÃO DO ASSISTENTE - ATUALIZADA PARA OLLAMA
# =======================================================
def responder_avancado(pergunta):
    """
    Envia uma pergunta para o modelo de linguagem local via Ollama e retorna a resposta.
    """
    try:
        # Monta o payload para a API do Ollama
        payload = {
            "model": OLLAMA_MODELO,
            "messages": [
                {"role": "system", "content": "Você é um assistente acadêmico da UniEVANGÉLICA."},
                {"role": "user", "content": pergunta}
            ],
            "stream": False  # Para obter a resposta completa de uma vez
        }

        # Envia a requisição POST para o endpoint do Ollama
        response = requests.post(OLLAMA_URL, json=payload)
        
        # Lança um erro se a resposta não for bem-sucedida (ex: status 404, 500)
        response.raise_for_status()

        # Extrai o conteúdo da mensagem da resposta JSON
        resposta_json = response.json()
        return resposta_json['message']['content'].strip()

    except requests.exceptions.ConnectionError as e:
        # Erro específico para quando o servidor do Ollama não está acessível
        print(f"Erro de conexão: {e}")
        return "Não foi possível conectar ao servidor Ollama. Verifique se ele está em execução."
    except requests.exceptions.RequestException as e:
        # Captura outros erros relacionados a requisições HTTP
        print(f"Erro na requisição: {e}")
        return f"Ocorreu um erro na comunicação com o Ollama: {e}"
    except KeyError:
        # Erro se a resposta do Ollama não vier no formato esperado
        print(f"Resposta inesperada do Ollama: {response.text}")
        return "A resposta do Ollama não pôde ser processada. Verifique o formato."
    except Exception as e:
        # Captura qualquer outro erro inesperado
        print(f"Erro inesperado: {e}")
        return f"Ocorreu um erro inesperado: {e}"


# =======================================================
# 5. ROTAS DO FLASK - Sem alterações
# =======================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    resposta = ""
    usuarios_unicos = pie_union_size(DAILY_DATA)

    if request.method == 'POST':
        pergunta = request.form['pergunta']
        if pergunta: # Verifica se a pergunta não está vazia
             resposta = responder_avancado(pergunta)

    # Assume que você tem um template 'index.html' na pasta 'templates'
    return render_template('index.html', resposta=resposta, usuarios_unicos=usuarios_unicos)

@app.route('/usuarios_unicos', methods=['GET'])
def usuarios_unicos_json():
    resultado = pie_union_size(DAILY_DATA)
    return jsonify({
        'status': 'success',
        'usuarios_unicos_hoje': resultado
    })

if __name__ == '__main__':
    app.run(debug=True)
