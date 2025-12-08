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
            // Enviar também a disciplina selecionada
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
                throw new Error(`Erro HTTP: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.erro) {
                throw new Error(data.erro);
            }

            QUESTOES = data.questoes;
            console.log(`✅ ${QUESTOES.length} questões carregadas com sucesso!`);
            
        } catch (error) {
            console.error("❌ Erro ao carregar questões:", error);
            alert("Erro ao carregar as questões do simulado. Tente novamente.");
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

            await carregarQuestoes(numQuestoes);

            if (QUESTOES.length === 0) {
                throw new Error("Nenhuma questão foi carregada.");
            }

            // Atualizar displays
            if (totalQuestoesDisplay) {
                totalQuestoesDisplay.textContent = QUESTOES.length;
            }

            inicioBox.classList.add("hidden");
            questaoBox.classList.remove("hidden");
            timerBox.classList.remove("hidden");

            iniciarTimer();
            atualizarProgresso();
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
        
        // Alerta visual quando faltam 5 minutos
        if (tempoRestante <= 300 && tempoRestante > 0) {
            timerBox.style.background = '#ea4335';
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
        const q = QUESTOES[pos];

        questaoNumero.textContent = pos + 1;
        questaoTexto.textContent = q.texto;

        alternativasBox.innerHTML = "";
        
        for (let letra in q.alternativas) {
            const div = document.createElement("div");
            div.className = "alternativa";

            const input = document.createElement("input");
            input.type = "radio";
            input.name = "resp";
            input.value = letra;
            input.id = `alt-${letra}`;

            if (RESPOSTAS[pos] === letra) {
                input.checked = true;
            }

            input.addEventListener("change", () => {
                RESPOSTAS[pos] = letra;
                atualizarProgresso();
            });

            const label = document.createElement("label");
            label.setAttribute("for", `alt-${letra}`);
            label.innerHTML = `<strong>${letra})</strong> ${q.alternativas[letra]}`;

            div.appendChild(input);
            div.appendChild(label);
            alternativasBox.appendChild(div);
        }

        prevBtn.disabled = pos === 0;

        if (pos === QUESTOES.length - 1) {
            nextBtn.classList.add("hidden");
            finishBtn.classList.remove("hidden");
        } else {
            nextBtn.classList.remove("hidden");
            finishBtn.classList.add("hidden");
        }

        // Scroll para o topo
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
        
        if (respondidas < total) {
            const confirma = confirm(
                `Você respondeu ${respondidas} de ${total} questões.\n\nTem certeza que deseja finalizar o simulado?`
            );
            if (!confirma) return;
        } else {
            const confirma = confirm("Tem certeza que deseja finalizar o simulado?");
            if (!confirma) return;
        }
        
        finalizar();
    });

    async function finalizar() {
        clearInterval(timerInterval);

        try {
            const response = await fetch("/simulador/resultado", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({ respostas: RESPOSTAS })
            });

            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }

            const data = await response.json();

            questaoBox.classList.add("hidden");
            inicioBox.classList.add("hidden");
            resultadoBox.classList.remove("hidden");
            timerBox.classList.add("hidden");

            // Atualizar estatísticas
            document.getElementById("resumo-corretas").textContent = data.acertos;
            document.getElementById("resumo-total").textContent = data.total;
            
            const percentual = ((data.acertos / data.total) * 100).toFixed(1);
            document.getElementById("resumo-percentual").textContent = `${percentual}%`;

            // Mensagem personalizada
            const mensagemDiv = document.getElementById("mensagem-resultado");
            let mensagem = '';
            
            if (percentual >= 80) {
                mensagem = '🎉 <strong>Excelente!</strong> Você está muito bem preparado(a). Continue assim!';
            } else if (percentual >= 60) {
                mensagem = '💪 <strong>Bom desempenho!</strong> Revise os tópicos onde errou para consolidar o conteúdo.';
            } else if (percentual >= 40) {
                mensagem = '📚 <strong>Razoável.</strong> Vale reforçar os estudos nessas matérias antes da prova real.';
            } else {
                mensagem = '📖 <strong>Continue estudando!</strong> Use este resultado como guia para focar nos temas que precisa revisar.';
            }
            
            mensagemDiv.innerHTML = mensagem;

            // Gabarito detalhado
            const ul = document.getElementById("lista-gabarito");
            ul.innerHTML = "";
            
            data.gabarito.forEach((item, index) => {
                const li = document.createElement("li");
                const respostaUsuario = RESPOSTAS[index] || "—";
                const classe = respostaUsuario === item.correta ? "correto" : "incorreto";
                
                li.className = classe;
                li.innerHTML = `
                    <span><strong>Questão ${item.numero}:</strong> Sua resposta: <span class="resposta-user">${respostaUsuario}</span></span>
                    <span>Correta: <span class="resposta-correta">${item.correta}</span></span>
                `;
                ul.appendChild(li);
            });

            // Scroll para o topo
            window.scrollTo({ top: 0, behavior: 'smooth' });

        } catch (error) {
            console.error("❌ Erro ao finalizar simulado:", error);
            alert("Erro ao processar o resultado. Tente novamente.");
        }
    }

});