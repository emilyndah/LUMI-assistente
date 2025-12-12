# 🌟 Lumi – Assistente Acadêmica Inteligente

# 🌐 Acesse o Projeto Online 
🔗 Lumi – Assistente Acadêmico: 👉 https://lumi-assistente.onrender.com

## 🧾 Descrição Geral
A **Lumi** é uma assistente acadêmica inteligente desenvolvida como projeto universitário para apoiar estudantes em suas rotinas acadêmicas. A plataforma combina automação de respostas, recursos de organização pessoal e materiais de apoio interativos, permitindo que discentes encontrem informações institucionais, consultem um calendário acadêmico dinâmico e obtenham recomendações de estudo personalizadas em um único ambiente web.

## 🤖 Funcionalidades Principais
- **Chat inteligente com IA** para responder dúvidas sobre a vida universitária e conteúdos acadêmicos.
- **Calendário acadêmico** com ordenação automática de eventos e descrição detalhada de atividades.
- **FAQ dinâmico** alimentado por arquivo JSON para garantir facilidade de manutenção das perguntas frequentes.
- **Flashcards** para revisão rápida de conteúdos e disciplinas.
- **Metodo de estudo** que sugere métodos de estudo individualizados com base nas respostas do estudante.
- **Modo Foco** ambiente dedicado à concentração, reduzindo distrações e auxiliando o aluno a manter o foco durante os estudos.


## 🗂️ Estrutura Principal do Projeto
```text
LUMI-assistente/
├── app.py                # Aplicação Flask com rotas, integração com IA e regras de negócio
├── requirements.txt      # Lista de dependências Python necessárias para execução
├── calendario.txt        # Fonte textual dos eventos exibidos no calendário acadêmico
├── faq.json              # Perguntas frequentes consumidas pela rota /faq
├── flashcards.json       # Conteúdos utilizados na página de flashcards
├── informacoes.txt       # Materiais complementares e anotações do projeto
├── static/
│   ├── style.css         # Estilos visuais da interface web
│   └── lumi_logo.jpg     # Identidade visual utilizada no frontend
└── templates/
    ├── index.html        # Página principal com o chat da assistente Lumi
    ├── motivacional.html # Chat com foco em acolhimento e motivação
    ├── calendario.html   # Visualização do calendário acadêmico
    ├── faq.html          # Página de perguntas frequentes
    ├── flashcards.html   # Lista de flashcards interativos
    └── metodo_estudo.html# Questionário para recomendações personalizadas de estudo
```

## 🛠️ Tecnologias Utilizadas
- 🐍 Python: Linguagem principal utilizada no desenvolvimento do backend e integração com a IA.
- 🌐 HTML / CSS: Estrutura e estilização da interface web.
- ⚙️ Flask: Framework web em Python usado para gerenciar rotas, autenticação e integração com o modelo de IA.
- 🧠 Gemini 2.5 Flash: Modelo de inteligência artificial utilizado para o chatbot e processamento de linguagem natural.
- 🧪 Pytest: Biblioteca de testes automatizados aplicada para garantir estabilidade das rotas e funcionalidades.
- 🗄️ SQLite (SQLAlchemy): Banco de dados relacional utilizado para armazenar usuários e resultados de quizzes (vem junto com Flask).
- 🧰 VS Code: Ambiente de desenvolvimento usado para edição e execução do código.
- 📋 Trello: Ferramenta de gestão de tarefas utilizada para organização das entregas e controle do progresso da equipe.
- ☁️ Render: Plataforma de deploy para hospedagem e execução online da aplicação.
- 🌿 Git e GitHub: Controle de versão e armazenamento do código-fonte, permitindo colaboração entre os integrantes do grupo.

## 🚀 Como Executar o Projeto Localmente
1. **Clone o repositório e acesse a pasta:**
   ```bash
   git clone https://github.com/<usuario>/LUMI-assistente.git
   cd LUMI-assistente
   ```
2. **(Opcional) Crie e ative um ambiente virtual:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate    # Windows PowerShell
   ```
3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Certifique-se de que o serviço Ollama esteja em execução** e que o modelo configurado em `app.py` esteja disponível localmente.
5. **Inicie o servidor Flask:**
   ```bash
   python app.py
   ```
6. **Acesse a aplicação no navegador:**
   - URL padrão: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 📈 Próximos Passos e Melhorias Futuras
- Aperfeiçoar o modelo de IA com técnicas avançadas de NLP e contextualização acadêmica.
- Disponibilizar painel administrativo para edição de FAQs, flashcards e calendário diretamente pela web.
- Desenvolver uma interface responsiva aprimorada com componentes modernos e acessíveis.
- Implementar autenticação de usuários e personalização de experiências baseadas no perfil acadêmico.

# 📈 Próximos Passos e Melhorias Futuras 
- Aperfeiçoar o modelo de IA com técnicas avançadas de NLP e contextualização acadêmica. 
- Disponibilizar painel administrativo para edição de FAQs, flashcards e calendário diretamente pela web. 
- Desenvolver uma interface responsiva aprimorada com componentes modernos e acessíveis. 
- Implementar autenticação de usuários e personalização de experiências baseadas no perfil acadêmico. 
- Executar todas as funcionalidas planejatas no inicio do projeto

## **👥 Orientadores**

  - Henrique Lima
  - Eder José
  - Fábio Botelho 
  - Jeferson Silva

### 👥 **Pessoas Desenvolvedoras**

Agradecimento especial a todos que contribuíram para o desenvolvimento do projeto **Lumi – Assistente Acadêmica Inteligente** 💡  

- [@EmilyRodrigues](https://github.com/emilyndah)  
- [@FrancielleGoncalves](https://github.com/Francielle84)  
- [@JordanVidal](https://github.com/JordanVidall)  
- [@JoaoPedroCarlos](https://github.com/joaopcds77-max)  
- [@Laviniacarvalhaes](https://github.com/Laviniacarvalhaes)  
- [@RafaelOliveira](https://github.com/rafaeloliveira2902)  
- [@Samuelfaleiro](https://github.com/Samukreuviski)

  ---

> 🧩 Projeto desenvolvido no contexto acadêmico, promovendo aprendizado colaborativo e aplicação prática de tecnologias emergentes.





