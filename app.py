from flask import Flask, render_template, request
import openai
import os

app = Flask(__name__)

# Modo avançado com OpenAI (requer chave)
def responder_avancado(pergunta):
    openai.api_key = os.getenv("OPENAI_API_KEY")  # coloque sua chave no ambiente
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

@app.route('/', methods=['GET', 'POST'])
def index():
    resposta = ""
    if request.method == 'POST':
        pergunta = request.form['pergunta']
        modo = request.form.get('modo', 'simples')

        if modo == 'simples':
            resposta = responder_simples(pergunta)
        else:
            resposta = responder_avancado(pergunta)

    return render_template('index.html', resposta=resposta)

if __name__ == '__main__':
    app.run(debug=True)