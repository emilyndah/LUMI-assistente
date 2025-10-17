# =======================================================
# IMPORTAÇÕES
# =======================================================
from flask import Flask, render_template, request, jsonify, session
from itertools import combinations
import requests
import json

# =======================================================
# CONFIGURAÇÃO DO APLICATIVO FLASK
# =======================================================
app = Flask(__name__)
app.secret_key = "segredo_da_lumi"  # Necessário para armazenar o histórico de mensagens na sessão

# =======================================================
# 1. CONSTANTES DO OLLAMA (CONFIGURAÇÃO DO MODELO)
# =======================================================
OLLAMA_URL = "http://localhost:11434/api/chat"  # URL do servidor Ollama
OLLAMA_MODELO = "qwen3:0.6b"  # Nome do modelo usado no Ollama

# =======================================================
# 2. FUNÇÃO PIE (CÁLCULO DE USUÁRIOS ÚNICOS)
# =======================================================
def pie_union_size(sizes):
    """
    Calcula o número de usuários únicos com base nas combinações de plataformas.
    """
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
# 3. DADOS SIMULADOS (PARA TESTES)
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
# 4. FUNÇÃO DO ASSISTENTE (INTEGRAÇÃO COM OLLAMA)
# =======================================================
def responder_avancado(pergunta):
    """
    Envia uma pergunta para o modelo de linguagem local via Ollama
    e retorna a resposta do modelo.
    """
    try:
        # Monta o corpo da requisição (payload)
        payload = {
            "model": OLLAMA_MODELO,
            "messages": [
                {"role": "system", "content": "Você é um assistente acadêmico simpático da UniEVANGÉLICA."},
                {"role": "user", "content": pergunta}
            ],
            "stream": False  # Retorna a resposta completa (não por partes)
        }

        # Envia a requisição POST para o Ollama
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()  # Gera erro se o Ollama não responder corretamente

        # Extrai o conteúdo da resposta JSON
        resposta_json = response.json()
        return resposta_json['message']['content'].strip()

    except requests.exceptions.ConnectionError:
        return "❌ Não foi possível conectar ao Ollama. Verifique se ele está em execução."
    except Exception as e:
        return f"⚠️ Ocorreu um erro: {e}"

# =======================================================
# 5. ROTA PRINCIPAL (INDEX)
# =======================================================
@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Rota principal do site.
    Exibe o chat e o painel de funcionalidades, e armazena o histórico de mensagens.
    """
    usuarios_unicos = pie_union_size(DAILY_DATA)

    # Cria o histórico de conversa na sessão se ainda não existir
    if "historico" not in session:
        session["historico"] = []

    # Quando o usuário envia uma pergunta
    if request.method == 'POST':
        pergunta = request.form['pergunta']
        if pergunta.strip():
            resposta = responder_avancado(pergunta)
            # Salva a nova interação no histórico da sessão
            session["historico"].append({
                "usuario": pergunta,
                "lumi": resposta
            })
            session.modified = True  # Atualiza a sessão

    # Renderiza a página HTML com o histórico de mensagens
    return render_template(
        'index.html',
        historico=session["historico"],
        usuarios_unicos=usuarios_unicos
    )

# =======================================================
# 6. ROTA PARA RETORNAR USUÁRIOS ÚNICOS (JSON)
# =======================================================
@app.route('/usuarios_unicos', methods=['GET'])
def usuarios_unicos_json():
    """
    Retorna o número de usuários únicos em formato JSON.
    """
    resultado = pie_union_size(DAILY_DATA)
    return jsonify({
        'status': 'success',
        'usuarios_unicos_hoje': resultado
    })

# =======================================================
# 7. ROTA PARA LIMPAR O CHAT
# =======================================================
@app.route('/limpar_chat')
def limpar_chat():
    """
    Limpa o histórico do chat armazenado na sessão.
    """
    session.pop("historico", None)
    return render_template('index.html', historico=[])

# =======================================================
# 8. EXECUÇÃO DO SERVIDOR FLASK
# =======================================================
if __name__ == '__main__':
    app.run(debug=True)
