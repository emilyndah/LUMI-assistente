# 🌟 Lumi – Assistente Acadêmica Inteligente

## 🧾 Descrição Geral
A **Lumi** é uma assistente acadêmica inteligente desenvolvida como projeto universitário para apoiar estudantes em suas rotinas acadêmicas. A plataforma combina automação de respostas, recursos de organização pessoal e materiais de apoio interativos, permitindo que discentes encontrem informações institucionais, consultem um calendário acadêmico dinâmico e obtenham recomendações de estudo personalizadas em um único ambiente web.

## 🤖 Funcionalidades Principais
- **Chat inteligente com IA local gemini 2.5 flash** para responder dúvidas sobre a vida universitária e conteúdos acadêmicos.
- **Calendário acadêmico interativo** com ordenação automática de eventos e descrição detalhada de atividades.
- **FAQ dinâmico** alimentado por arquivo JSON para garantir facilidade de manutenção das perguntas frequentes.
- **Flashcards personalizáveis** para revisão rápida de conteúdos e disciplinas.
- **Questionário de estilo de aprendizagem** que sugere métodos de estudo individualizados com base nas respostas do estudante.
- **Integração completa com Flask** para gerenciamento de rotas, sessões e comunicação com o modelo de linguagem.

## 🗂️ Estrutura do Projeto
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
    ├── calendario.html   # Visualização do calendário acadêmico
    ├── faq.html          # Página de perguntas frequentes
    ├── flashcards.html   # Lista de flashcards interativos
    └── metodo_estudo.html# Questionário para recomendações personalizadas de estudo
```

## 🛠️ Tecnologias Utilizadas
- **Python** – linguagem principal do backend.
- **Flask** – framework web para roteamento, templates e sessões.
- **HTML5 & CSS** – estrutura e estilo das páginas.
- **gemini 2.5** – plataforma local para execução do modelo de linguagem utilizado pela assistente.
- **Jinja2** – engine de templates empregada pelo Flask.

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
- Integrar um banco de dados relacional para persistência de histórico de conversas, eventos e usuários.
- Disponibilizar painel administrativo para edição de FAQs, flashcards e calendário diretamente pela web.
- Desenvolver uma interface responsiva aprimorada com componentes modernos e acessíveis.
- Implementar autenticação de usuários e personalização de experiências baseadas no perfil acadêmico.

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





