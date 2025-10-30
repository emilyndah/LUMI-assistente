// Espera o documento carregar antes de rodar o script
document.addEventListener('DOMContentLoaded', () => {

    // --- Seleção dos Elementos do DOM ---
    const timerRelogio = document.getElementById('timer-relogio');
    const botoesTempoContainer = document.getElementById('botoes-tempo');
    const controlesTimerContainer = document.getElementById('controles-timer');
    const btnParar = document.getElementById('btn-parar');
    const focoHeader = document.querySelector('.foco-header');

    // Variáveis para controlar o timer
    let cronometro; // Vai guardar o setInterval
    let segundosTotais;

    // --- Funções Principais ---

    /**
     * Inicia o timer com base nos minutos fornecidos.
     */
    function iniciarTimer(minutos) {
        segundosTotais = minutos * 60;
        
        // Esconde a seleção de tempo e o cabeçalho
        botoesTempoContainer.classList.add('escondido');
        focoHeader.classList.add('escondido');

        // Mostra o botão de parar
        controlesTimerContainer.classList.remove('escondido');

        // Atualiza o relógio imediatamente
        atualizarRelogio();

        // Inicia a contagem regressiva a cada segundo
        cronometro = setInterval(() => {
            segundosTotais--;
            atualizarRelogio();

            // Quando o tempo acabar
            if (segundosTotais <= 0) {
                pararTimer();
                // Alerta simples para "desativar notificações" (in-app)
                alert('Sessão de foco concluída! Ótimo trabalho.');
            }
        }, 1000);
    }

    /**
     * Para o timer e reseta a interface.
     */
    function pararTimer() {
        clearInterval(cronometro); // Para o setInterval

        // Mostra a seleção de tempo e o cabeçalho
        botoesTempoContainer.classList.remove('escondido');
        focoHeader.classList.remove('escondido');

        // Esconde o botão de parar
        controlesTimerContainer.classList.add('escondido');

        // Reseta o relógio para o padrão (30:00)
        timerRelogio.textContent = "30:00";
        document.title = "Lumi - Modo Foco"; // Reseta o título da aba
    }

    /**
     * Formata e exibe o tempo restante no relógio e no título da aba.
     */
    function atualizarRelogio() {
        const minutos = Math.floor(segundosTotais / 60);
        const segundos = segundosTotais % 60;
        
        // Formata os segundos para sempre terem dois dígitos (ex: "05" em vez de "5")
        const segundosFormatados = segundos < 10 ? '0' + segundos : segundos;
        const minutosFormatados = minutos < 10 ? '0' + minutos : minutos;

        const display = `${minutosFormatados}:${segundosFormatados}`;
        
        timerRelogio.textContent = display;
        document.title = `${display} - Foco`; // Atualiza o título da aba
    }

    // --- Configuração Inicial e Event Listeners ---

    // 1. Esconde os controles do timer ao carregar a página
    controlesTimerContainer.classList.add('escondido');
    // 2. Define o relógio inicial
    timerRelogio.textContent = "30:00"; // Padrão

    // 3. Adiciona o clique nos botões de tempo
    botoesTempoContainer.addEventListener('click', (evento) => {
        // Verifica se o clique foi em um botão com a classe 'btn-tempo'
        if (evento.target.classList.contains('btn-tempo')) {
            // Pega o valor do atributo 'data-minutos'
            const minutos = parseInt(evento.target.dataset.minutos, 10);
            iniciarTimer(minutos);
        }
    });

    // 4. Adiciona o clique no botão de parar
    btnParar.addEventListener('click', pararTimer);

});