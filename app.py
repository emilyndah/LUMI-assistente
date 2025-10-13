import os
from flask import Flask, render_template, request
import openai
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

app = Flask(__name__)


def responder_avancado(pergunta):
    # Pega a chave de API diretamente do ambiente (do arquivo .env)
    openai.api_key = os.getenv("OPENAI_API_KEY")

    # Verifica se a chave foi carregada corretamente
    if not openai.api_key:
        return "Erro: A chave da API da OpenAI não foi encontrada. Verifique seu arquivo .env."

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente acadêmico da UniEVANGÉLICA."},
                {"role": "user", "content": pergunta}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # A mensagem de erro da API (como a de 'quota insuficiente') será mostrada aqui
        return f"Erro ao acessar a API: {str(e)}"


# Rota principal da aplicação
@app.route('/', methods=['GET', 'POST'])
def index():
    resposta = ""
    if request.method == 'POST':
        pergunta = request.form['pergunta']
        # No Modo Avançado, a resposta virá da nossa função
        resposta = responder_avancado(pergunta)

    # Renderiza o HTML e envia a resposta para ser exibida
    return render_template('index.html', resposta=resposta)


if __name__ == '__main__':
    app.run(debug=True)