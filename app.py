from flask import Flask, render_template, request, jsonify
from itertools import combinations
from openai import OpenAI # MODIFICADO: Importa o novo cliente
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (chave da API, etc.)
load_dotenv()

# Instancia o cliente da OpenAI com a chave da API
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

# =======================================================
# 1. FUNÇÃO PIE (Calcula os Usuários Únicos) - Sem alterações
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

# 2. DADOS SIMULADOS - Sem alterações
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
# FUNÇÃO DO ASSISTENTE - ATUALIZADA PARA A NOVA API
# =======================================================
def responder_avancado(pergunta):
    try:
        # USA A NOVA SINTAXE DO CLIENTE
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente acadêmico da UniEVANGÉLICA."},
                {"role": "user", "content": pergunta}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Erro ao acessar a API: {str(e)}"

# =======================================================
# ROTAS DO FLASK - Sem alterações
# =======================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    resposta = ""
    usuarios_unicos = pie_union_size(DAILY_DATA)
    
    if request.method == 'POST':
        pergunta = request.form['pergunta']
        resposta = responder_avancado(pergunta)

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

