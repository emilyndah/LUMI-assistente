document.addEventListener("DOMContentLoaded", () => {

    // ========================================
    // CONTROLE DO MENU LATERAL
    // ========================================
    const menuToggle = document.querySelector(".menu-toggle");
    const sidebar = document.querySelector(".sidebar");
    const overlay = document.querySelector(".overlay");

    if (menuToggle && sidebar && overlay) {
        menuToggle.addEventListener("click", () => {
            sidebar.classList.toggle("active");
            overlay.classList.toggle("active");
        });

        overlay.addEventListener("click", () => {
            sidebar.classList.remove("active");
            overlay.classList.remove("active");
        });
    }

    // ELEMENTOS DOM
    const inicioBox = document.getElementById("inicio-box");
    const questaoBox = document.getElementById("questao-box");
    const resultadoBox = document.getElementById("resultado-box");

    const questaoNumero = document.getElementById("questao-numero");
    const questaoTexto = document.getElementById("questao-texto");
    const alternativasBox = document.getElementById("alternativas-box");
    const totalQuestoesDisplay = document.getElementById("total-questoes-display");
    const questoesRespondidasDisplay = document.getElementById("questoes-respondidas");
    const progressoFill = document.getElementById("progresso-fill");

    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const finishBtn = document.getElementById("finish-btn");

    const startBtn = document.getElementById("start-btn");
    const timerElement = document.getElementById("timer");
    const timerBox = document.getElementById("timer-box");

    const numQuestoesSelect = document.getElementById("num-questoes");
    const tempoProvaSelect = document.getElementById("tempo-prova");
    const disciplinaSelect = document.getElementById("disciplina");

    // ESTADO
    let QUESTOES = [];
    let RESPOSTAS = {};
    let pos = 0;
    let numQuestoes = 10;
    let tempoRestante = 60 * 60; // padrão 1 hora
    let timerInterval = null;

    // ========================================
    // BUSCAR QUESTÕES DO FLASK VIA AJAX
    // ========================================
    async function carregarQuestoes(quantidade) {
        try {
            // Nota: Se a rota /simulador/iniciar não existir, o código cairá no catch.
            // Certifique-se que seu app.py tem essa rota ou a rota /api/simulador_config
            const response = await fetch("/simulador/iniciar", { 
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ 
                    quantidade: quantidade,
                    disciplina: disciplinaSelect ? disciplinaSelect.value : "todas"
                })
            });

            if (!response.ok) {
                // Tenta fallback para rota de config se a rota de iniciar falhar
                console.warn("Rota /simulador/iniciar falhou, tentando carregar JSON direto...");
                const fallback = await fetch("/api/simulador_config");
                if(!fallback.ok) throw new Error(`Erro HTTP: ${response.status}`);
                const dataFallback = await fallback.json();
                return dataFallback.data.questions.slice(0, quantidade); // Retorna array direto
            }

            const data = await response.json();
            
            if (data.erro) {
                throw new Error(data.erro);
            }

            // Garante que retorna o array de questões
            return data.questoes || data.data?.questions || data;

        } catch (error) {
            console.error("❌ Erro ao carregar questões:", error);
            alert("Erro ao carregar as questões. Verifique se o servidor está rodando.");
            throw error;
        }
    }

    // ========================================
    // INICIAR SIMULADO
    // ========================================
    startBtn.addEventListener("click", async () => {
        try {
            startBtn.disabled = true;
            startBtn.innerHTML = '<span>Carregando...</span>';

            // Pegar configurações
            numQuestoes = parseInt(numQuestoesSelect.value);
            const tempoMinutos = parseInt(tempoProvaSelect.value);
            tempoRestante = tempoMinutos * 60;

            // Carrega e salva na variável global
            const dadosCarregados = await carregarQuestoes(numQuestoes);
            QUESTOES = dadosCarregados;

            if (!QUESTOES || QUESTOES.length === 0) {
                throw new Error("Nenhuma questão foi carregada.");
            }

            console.log(`✅ ${QUESTOES.length} questões prontas.`);

            // === CORREÇÃO IMPORTANTE: RESETAR O ESTADO ===
            pos = 0;          // Volta para a primeira questão
            RESPOSTAS = {};   // Limpa respostas anteriores
            // =============================================

            // Atualizar displays
            if (totalQuestoesDisplay) {
                totalQuestoesDisplay.textContent = QUESTOES.length;
            }

            inicioBox.classList.add("hidden");
            questaoBox.classList.remove("hidden");
            
            if(timerBox) timerBox.classList.remove("hidden");

            iniciarTimer();
            atualizarProgresso();
            
            // Chama a função para desenhar a primeira questão
            mostrarQuestao();

        } catch (error) {
            console.error("Erro ao iniciar simulado:", error);
            startBtn.disabled = false;
            startBtn.innerHTML = '<span>Iniciar Simulado</span><span class="btn-arrow">→</span>';
        }
    });

    // ========================================
    // TIMER
    // ========================================
    function iniciarTimer() {
        if(timerInterval) clearInterval(timerInterval); // Limpa timer anterior se houver
        
        atualizarTimerDisplay();
        timerInterval = setInterval(() => {
            tempoRestante--;
            atualizarTimerDisplay();
            
            if (tempoRestante <= 0) {
                clearInterval(timerInterval);
                alert("⏰ Tempo esgotado! O simulado será finalizado automaticamente.");
                finalizar();
            }
        }, 1000);
    }

    function atualizarTimerDisplay() {
        if(!timerElement) return;

        const horas = Math.floor(tempoRestante / 3600);
        const minutos = Math.floor((tempoRestante % 3600) / 60);
        const segundos = tempoRestante % 60;
        
        let display = '';
        if (horas > 0) {
            display = `${String(horas).padStart(2,'0')}:${String(minutos).padStart(2,'0')}:${String(segundos).padStart(2,'0')}`;
        } else {
            display = `${String(minutos).padStart(2,'0')}:${String(segundos).padStart(2,'0')}`;
        }
        
        timerElement.textContent = display;
        
        if (tempoRestante <= 300 && tempoRestante > 0) {
            if(timerBox) timerBox.style.background = '#ea4335';
        }
    }

    // ========================================
    // ATUALIZAR PROGRESSO
    // ========================================
    function atualizarProgresso() {
        const respondidas = Object.keys(RESPOSTAS).length;
        const percentual = (respondidas / QUESTOES.length) * 100;
        
        if (progressoFill) {
            progressoFill.style.width = `${percentual}%`;
        }
        
        if (questoesRespondidasDisplay) {
            questoesRespondidasDisplay.textContent = respondidas;
        }
    }

    // ========================================
    // MOSTRAR QUESTÃO
    // ========================================
    function mostrarQuestao() {
        // Proteção contra erro de índice
        if (!QUESTOES || QUESTOES.length === 0 || !QUESTOES[pos]) {
            console.error("Erro: Tentando acessar questão inexistente ou array vazio.");
            return;
        }

        const q = QUESTOES[pos];

        // CORREÇÃO DE COMPATIBILIDADE DE JSON
        // Aceita 'texto' (seu JS antigo) OU 'stem' (seu JSON de arquivo)
        const textoDaPergunta = q.texto || q.stem;
        
        // Aceita 'alternativas' OU 'options'
        const opcoesResposta = q.alternativas || q.options;

        questaoNumero.textContent = pos + 1;
        questaoTexto.textContent = textoDaPergunta;

        alternativasBox.innerHTML = "";
        
        // Itera sobre as chaves (A, B, C, D...)
        for (let letra in opcoesResposta) {
            const div = document.createElement("div");
            div.className = "alternativa";

            const input = document.createElement("input");
            input.type = "radio";
            input.name = "resp";
            input.value = letra;
            input.id = `alt-${letra}`;

            // Marca se já respondeu antes
            if (RESPOSTAS[pos] === letra) {
                input.checked = true;
            }

            // Evento ao clicar
            input.addEventListener("change", () => {
                RESPOSTAS[pos] = letra;
                atualizarProgresso();
            });

            const label = document.createElement("label");
            label.setAttribute("for", `alt-${letra}`);
            label.style.cursor = "pointer"; // Melhora UX
            label.style.width = "100%";
            label.innerHTML = `<strong>${letra})</strong> ${opcoesResposta[letra]}`;

            div.appendChild(input);
            div.appendChild(label);
            alternativasBox.appendChild(div);
        }

        // Controle dos botões
        prevBtn.disabled = pos === 0;

        if (pos === QUESTOES.length - 1) {
            nextBtn.classList.add("hidden");
            finishBtn.classList.remove("hidden");
        } else {
            nextBtn.classList.remove("hidden");
            finishBtn.classList.add("hidden");
        }

        // Scroll suave para o topo
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // ========================================
    // NAVEGAÇÃO
    // ========================================
    nextBtn.addEventListener("click", () => {
        if (pos < QUESTOES.length - 1) {
            pos++;
            mostrarQuestao();
        }
    });

    prevBtn.addEventListener("click", () => {
        if (pos > 0) {
            pos--;
            mostrarQuestao();
        }
    });

    // ========================================
    // FINALIZAR SIMULADO
    // ========================================
    finishBtn.addEventListener("click", () => {
        const respondidas = Object.keys(RESPOSTAS).length;
        const total = QUESTOES.length;
        
        let msg = "Tem certeza que deseja finalizar o simulado?";
        if (respondidas < total) {
            msg = `Você respondeu apenas ${respondidas} de ${total} questões.\n\n${msg}`;
        }
        
        if (confirm(msg)) {
            finalizar();
        }
    });

    async function finalizar() {
        clearInterval(timerInterval);

        // Calcula resultado no front-end mesmo (mais rápido e garantido)
        let acertos = 0;
        let gabaritoArr = [];

        QUESTOES.forEach((q, index) => {
            // Compatibilidade de chaves para 'correct' ou 'correta'
            const respostaCorreta = q.correct || q.correta; 
            const respostaUser = RESPOSTAS[index];
            
            if (respostaUser === respostaCorreta) {
                acertos++;
            }

            gabaritoArr.push({
                numero: index + 1,
                correta: respostaCorreta,
                usuario: respostaUser
            });
        });

        const total = QUESTOES.length;
        const percentual = ((acertos / total) * 100).toFixed(1);

        // Atualizar UI
        questaoBox.classList.add("hidden");
        inicioBox.classList.add("hidden");
        resultadoBox.classList.remove("hidden");
        if(timerBox) timerBox.classList.add("hidden");

        document.getElementById("resumo-corretas").textContent = acertos;
        document.getElementById("resumo-total").textContent = total;
        document.getElementById("resumo-percentual").textContent = `${percentual}%`;

        // Mensagem
        const mensagemDiv = document.getElementById("mensagem-resultado");
        let mensagem = '';
        if (percentual >= 70) {
            mensagem = '<h3 style="color: #4CAF50">Parabéns! Você foi aprovado! 🚀</h3>';
        } else {
            mensagem = '<h3 style="color: #F44336">Continue estudando! 📚</h3>';
        }
        mensagemDiv.innerHTML = mensagem;

        // Lista Gabarito
        const ul = document.getElementById("lista-gabarito");
        ul.innerHTML = "";
        
        gabaritoArr.forEach((item) => {
            const li = document.createElement("li");
            const acertou = item.usuario === item.correta;
            li.className = acertou ? "correto" : "incorreto";
            
            // Se o usuário não respondeu
            const respUser = item.usuario ? item.usuario : "Não respondeu";

            li.innerHTML = `
                <span><strong>Q${item.numero}:</strong> Sua resp: <b>${respUser}</b></span>
                <span>Correta: <b>${item.correta}</b> ${acertou ? '✅' : '❌'}</span>
            `;
            ul.appendChild(li);
        });

        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

});