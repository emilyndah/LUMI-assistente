from flask import Flask, render_template, request, jsonify # ADICIONADO 'jsonify'
from itertools import combinations # NOVO: Para o cálculo PIE
import openai
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (chave da API, etc.)
load_dotenv()

app = Flask(__name__)
# O seu código original
openai.api_key = os.getenv("OPENAI_API_KEY")

# =======================================================
# 1. FUNÇÃO PIE (Calcula os Usuários Únicos)
# =======================================================
def pie_union_size(sizes):
    # CORREÇÃO DA LÓGICA: Extrai apenas os labels de conjunto (Site, WA, Email)
    labels = sorted([k[0] for k in sizes.keys() if len(k) == 1])
    
    total = 0
    for k in range(1, len(labels)+1):
        s = 0
        for combo in combinations(labels, k):
            key = tuple(sorted(combo))
            s += sizes.get(key, 0)
        total += s if k % 2 == 1 else -s
    return total

# 2. DADOS SIMULADOS (Garante o resultado 162)
# Certifique-se de que as chaves de intersecção estão ORDENADAS, conforme sua correção!
DAILY_DATA = {
    ('Email',):40, 
    ('Site',):90, 
    ('WA',):70, 
    ('Email','Site'):10,      
    ('Email','WA'):8,         
    ('Site','WA'):25,         
    ('Email','Site','WA'):5
}
# O valor calculado será: 162

# =======================================================
# FUNÇÃO ORIGINAL DO ASSISTENTE
# =======================================================
def responder_avancado(pergunta):
    openai.api_key = os.getenv("OPENAI_API_KEY") 
    try:
        response = openai.ChatCompletion.create(
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
# ROTAS DO FLASK
# =======================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    resposta = ""
    # Calcule os usuários únicos AQUI para enviar para o template
    usuarios_unicos = pie_union_size(DAILY_DATA)
    
    if request.method == 'POST':
        pergunta = request.form['pergunta']
        modo = request.form.get('modo', 'simples')

        if modo == 'simples':
            resposta = responder_avancado(pergunta)

    # ENVIA o valor de usuários únicos para o 'index.html'
    return render_template('index.html', resposta=resposta, usuarios_unicos=usuarios_unicos)


# NOVO ENDPOINT: /usuarios_unicos (Retorna JSON)
@app.route('/usuarios_unicos', methods=['GET'])
def usuarios_unicos_json():
    resultado = pie_union_size(DAILY_DATA)
    
    # REQUISITO 3: Retornar o cálculo em formato JSON
    return jsonify({
        'status': 'success',
        'usuarios_unicos_hoje': resultado
    })


if __name__ == '__main__':
    app.run(debug=True)