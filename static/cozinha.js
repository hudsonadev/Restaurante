// Cronômetro dos pedidos em preparo e botão "Pronto" (Cozinha e Início).
// Modo simulado: corre acelerado (data-aceleracao: 120 = 1 s real vale 2 min) até o tempo sorteado pela
// cozinha no envio (data-sorteado); aí para, o pedido fica "pronto para sair" e o botão Pronto libera.
const atualizarCronometros = () => document.querySelectorAll('.cronometro').forEach(c => {
    let minutos = (Date.now() - new Date(c.dataset.criado).getTime()) / 60000 * Number(c.dataset.aceleracao || 1);
    const sorteado = c.dataset.sorteado === undefined ? null : Number(c.dataset.sorteado);
    const pronto = sorteado !== null && minutos >= sorteado;
    if (pronto) minutos = sorteado;
    c.textContent = `${fmt(Math.max(0, minutos), 1)} min`;
    c.classList.toggle('atrasado', minutos > Number(c.dataset.previsto));
    if (sorteado === null) return;
    c.classList.toggle('pronto-para-sair', pronto);
    const linha = c.closest('tr, li');
    const status = linha?.querySelector('.status-cozinha');
    if (status) {
        status.dataset.original ??= status.textContent;
        status.textContent = pronto ? 'pronto para sair' : status.dataset.original;
    }
    const botao = linha?.querySelector('[data-pronto]');
    if (botao && pronto && botao.disabled && !botao.dataset.enviando) { botao.disabled = false; botao.removeAttribute('title'); }
});
atualizarCronometros();
setInterval(atualizarCronometros, 250);

// Pedido recém-enviado pelo Novo pedido: leva a página até ele.
document.querySelector('#pedido-novo')?.scrollIntoView({block: 'center'});

const botaoSimular = document.querySelector('#simular');
botaoSimular?.addEventListener('click', async () => {
    botaoSimular.disabled = true;
    try {
        await api('/api/acompanhados/simular', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({quantidade: 10})});
        location.reload();
    } catch (erro) {
        $('#erro-cozinha').textContent = erro.message;
        botaoSimular.disabled = false;
    }
});

document.addEventListener('click', async event => {
    const botao = event.target.closest('[data-pronto]');
    if (!botao) return;
    botao.disabled = true;
    botao.dataset.enviando = '1';
    try {
        await api(`/api/acompanhados/${botao.dataset.pronto}/pronto`, {method: 'POST'});
        location.href = '/cozinha';
    } catch (erro) {
        $('#erro-cozinha').textContent = erro.message;
        botao.disabled = false;
        delete botao.dataset.enviando;
    }
});
