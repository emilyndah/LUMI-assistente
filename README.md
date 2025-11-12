# 🌟 Lumi – Assistente Acadêmica Inteligente

A **Lumi** é uma assistente web desenvolvida em um contexto acadêmico para apoiar estudantes em sua jornada universitária. O projeto combina respostas automáticas com recursos de organização pessoal, propondo um ambiente unificado para tirar dúvidas, planejar estudos, acompanhar eventos e revisar conteúdos.

[🔗 Acesse a versão hospedada na Render](https://lumi-assistente.onrender.com)

## Índice
- [Visão Geral](#visão-geral)
- [Funcionalidades Principais](#funcionalidades-principais)
- [Arquitetura e Arquivos Importantes](#arquitetura-e-arquivos-importantes)
- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Configuração do Ambiente](#configuração-do-ambiente)
- [Execução Local](#execução-local)
- [Testes Automatizados](#testes-automatizados)
- [Próximos Passos](#próximos-passos)
- [Orientadores](#orientadores)
- [Pessoas Desenvolvedoras](#pessoas-desenvolvedoras)

## Visão Geral
- **Objetivo:** agilizar a busca por informações acadêmicas e reforçar o aprendizado com apoio de IA.
- **Público:** estudantes de diferentes cursos e níveis de ensino.
- **Interface:** layout responsivo e intuitivo desenvolvido com HTML/CSS e componentes reutilizáveis.
- **Entrega acadêmica:** projeto universitário orientado por docentes, com foco em colaboração e aplicação prática.

## Funcionalidades Principais
- **Autenticação de Usuários**
  - Registro, login e logout seguros via Flask-Login.
  - Armazenamento de senhas utilizando hashing com Werkzeug.
  - Sessões protegidas e acesso condicional às rotas internas.
- **Chat com Inteligência Artificial (Gemini 2.5 Flash)**
  - Integração com a API do Google Gemini para responder perguntas em linguagem natural.
  - Contextualização baseada no arquivo `informacoes.txt` e nos dados acadêmicos do projeto.
- **Método de Estudo VARK**
  - Questionário interativo que identifica o estilo de aprendizagem (Visual, Auditivo, Leitor/Escritor e Cinestésico).
  - Resultado persistido no banco e exibido no perfil do usuário autenticado.
- **Calendário Acadêmico**
  - Eventos carregados de `calendario.json` e apresentados por data/categoria.
  - Interface que facilita a visualização de prazos e atividades importantes.
- **Flashcards de Estudo**
  - Baralhos digitais a partir de `flashcards.json` para memorização ativa.
- **Modo Foco (Pomodoro)**
  - Temporizador configurável com contagem regressiva implementada em `static/js/foco.js`.
  - Estilos dedicados em `static/css/foco.css` para uma experiência focada.
- **FAQ e Materiais Complementares**
  - Perguntas frequentes consumidas do arquivo `faq.json`.
  - Informações institucionais e conteúdos de apoio reunidos em `informacoes.txt` e `matriz.json`.

## Arquitetura e Arquivos Importantes
Estrutura dos principais diretórios e arquivos utilizados no desenvolvimento (organização pensada para uso no VS Code ou IDE similar):

```text
LUMI-assistente/
├── app.py                  # Aplicação Flask: rotas, lógica de negócios, integração com Gemini e banco de dados
├── create_db.py            # Script auxiliar para criação de tabelas em ambientes locais
├── requirements.txt        # Dependências Python
├── informacoes.txt         # Contexto base utilizado pelo chatbot
├── calendario.json         # Fonte de eventos do calendário acadêmico
├── faq.json                # Conteúdo das perguntas frequentes
├── flashcards.json         # Dados para geração dos flashcards
├── metodo_estudo.json      # Questionário VARK exibido na interface
├── matriz.json             # Conteúdo adicional consumido em rotas específicas
├── static/
│   ├── style.css           # Estilos globais da interface
│   ├── lumi_logo.jpg       # Identidade visual utilizada nas páginas
│   ├── css/foco.css        # Estilos do modo foco (Pomodoro)
│   └── js/foco.js          # Lógica do temporizador de estudos
├── templates/
│   ├── index.html          # Dashboard principal com chat da assistente
│   ├── calendario.html     # Página para visualizar eventos
│   ├── faq.html            # Perguntas frequentes
│   ├── flashcards.html     # Revisão com flashcards
│   ├── foco.html           # Tela dedicada ao modo foco
│   ├── login.html          # Formulário de autenticação
│   ├── register.html       # Cadastro de novos usuários
│   ├── metodo_de_estudo.html # Questionário VARK
│   └── profile.html        # Perfil com resultados personalizados
└── tests/
    └── test_app.py         # Testes automatizados das rotas e fluxo de autenticação
```

## Tecnologias Utilizadas
- 🐍 **Python** – linguagem principal do backend.
- ⚙️ **Flask** – framework web responsável pelas rotas e integração com a IA.
- 🧠 **Google Gemini 2.5 Flash** – modelo de IA para o chatbot acadêmico.
- 🗄️ **SQLite + SQLAlchemy** – banco de dados relacional (padrão) com ORM para persistência.
- 🔐 **Flask-Login** – gerenciamento de sessão e autenticação.
- 🌐 **HTML / CSS / JavaScript** – construção da interface responsiva (incluindo modo foco).
- 🧪 **Pytest** – suíte de testes automatizados para validar rotas e fluxo de login.
- 🧰 **VS Code** – ambiente utilizado pela equipe para edição e depuração do código.
- 🌿 **Git & GitHub** – versionamento e colaboração.
- ☁️ **Render** – plataforma de deploy utilizada para disponibilizar a aplicação online.
- 📋 **Trello** – organização das tarefas e acompanhamento do progresso.

## Configuração do Ambiente
1. **Clonar o repositório**
   ```bash
   git clone https://github.com/<usuario>/LUMI-assistente.git
   cd LUMI-assistente
   ```
2. **(Opcional) Criar ambiente virtual**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate    # Windows
   ```
3. **Instalar dependências**
   ```bash
   pip install -r requirements.txt
   ```
4. **Variáveis de ambiente necessárias**
   Crie um arquivo `.env` na raiz com as chaves abaixo:
   ```ini
   GEMINI_API_KEY=seu_token_do_google_generative_ai
   FLASK_SECRET_KEY=uma_chave_segura_para_sessoes
   # Opcional em produção (ex.: Render)
   # DATABASE_URL=sqlite:///lumi_database.db  # ou URL do PostgreSQL gerenciado
   ```
   > Certifique-se de que o serviço escolhido (ex.: Ollama ou API Gemini) esteja acessível localmente ou pela nuvem.

## Execução Local
1. Garanta que o banco de dados foi criado:
   ```bash
   flask db-create-all
   ```
   ou, alternativamente:
   ```bash
   python create_db.py
   ```
2. Inicie o servidor Flask:
   ```bash
   python app.py
   ```
3. Acesse pelo navegador em [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Dados e Conteúdos Personalizáveis
- **Calendário:** edite `calendario.json` para adicionar ou remover eventos.
- **Flashcards:** atualize `flashcards.json` com novas perguntas e respostas.
- **Método VARK:** ajuste `metodo_estudo.json` conforme novas perguntas.
- **FAQ:** mantenha `faq.json` com as dúvidas mais recorrentes.
- **Contexto do Chatbot:** personalize `informacoes.txt` para refinar o conhecimento base da Lumi.

## Testes Automatizados
Execute a suíte de testes com:
```bash
pytest
```
Os testes em `tests/test_app.py` validam o fluxo de autenticação (registro, login e controle de acesso) e garantem que as rotas críticas estejam funcionando.

## Próximos Passos
- Aprimorar o modelo de IA com contextualização acadêmica avançada.
- Disponibilizar painel administrativo para gerenciamento dos flashcards.
- Evoluir a interface com componentes modernos e acessíveis.
- Personalizar recomendações e experiências com base no perfil do aluno.
- Concluir a implementação de todas as funcionalidades planejadas no início do projeto.

## Orientadores
- Henrique Lima
- Eder José
- Fábio Botelho
- Jeferson Silva

## Pessoas Desenvolvedoras
Agradecimento especial a todas as pessoas que colaboraram com o desenvolvimento da Lumi:

- [@EmilyRodrigues](https://github.com/emilyndah)
- [@FrancielleGoncalves](https://github.com/Francielle84)
- [@JordanVidal](https://github.com/JordanVidall)
- [@JoaoPedroCarlos](https://github.com/joaopcds77-max)
- [@Laviniacarvalhaes](https://github.com/Laviniacarvalhaes)
- [@RafaelOliveira](https://github.com/rafaeloliveira2902)
- [@Samuelfaleiro](https://github.com/Samukreuviski)

---
> 🧩 Projeto desenvolvido no contexto acadêmico, promovendo aprendizado colaborativo e aplicação prática de tecnologias emergentes.
