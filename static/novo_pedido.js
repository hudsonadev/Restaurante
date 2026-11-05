// Novo pedido: estimativa ao vivo a cada prato marcado e um único botão "Enviar para a cozinha".
const form = $('#pedido-form');
const caixas = [...form.querySelectorAll('input[name="pratos"]')];
const botaoEnviar = form.querySelector('[type="submit"]');
let requisicao = 0;   // descarta respostas de composições antigas
let espera = null;

const pedidoAtual = () => ({
    pratos: caixas.filter(c => c.checked).map(c => Number(c.value)),
    fila: $('#fila').value.trim(),
});
const filaValida = fila => /^\d+$/.test(fila) && Number(fila) <= Number($('#fila').max);

function filtrar() {
    const busca = normalizar($('#busca-prato').value.trim());
    const categoria = $('#filtro-categoria').value;
    let visiveis = 0;
    form.querySelectorAll('fieldset[data-categoria]').forEach(grupo => {
        const itens = [...grupo.querySelectorAll('.menu-item')];
        itens.forEach(item => item.hidden = (categoria && grupo.dataset.categoria !== categoria) ||
            !normalizar(item.dataset.nome).includes(busca));
        const quantos = itens.filter(item => !item.hidden).length;
        grupo.hidden = quantos === 0;
        visiveis += quantos;
    });
    $('#total-visiveis').textContent = `${visiveis} de ${caixas.length} pratos`;
}

function atualizarResumo() {
    const marcadas = caixas.filter(c => c.checked);
    $('#resumo-itens').textContent = marcadas.length;
    $('#resumo-categorias').textContent = new Set(marcadas.map(c => c.dataset.categoria)).size;
    $('#resumo-tempo').textContent = fmt(marcadas.reduce((soma, c) => soma + Number(c.dataset.tempo), 0), 1);
    $('#resumo-maior').textContent = fmt(Math.max(0, ...marcadas.map(c => Number(c.dataset.tempo))), 1);
    $('#resumo-lista').innerHTML = marcadas.map(c => `<li><span>${escapeHtml(c.closest('.menu-item').dataset.nome)}</span><small class="muted">${fmt(Number(c.dataset.tempo), 1)} min</small></li>`).join('');
    $('#erro-pedido').textContent = '';
    clearTimeout(espera);
    espera = setTimeout(estimar, 200);
}

async function estimar() {
    const {pratos, fila} = pedidoAtual();
    const versao = ++requisicao;
    botaoEnviar.disabled = true;
    if (!pratos.length) {
        $('#estimativa').innerHTML = '<p class="estimativa-vazia">Marque os pratos ao lado para ver o tempo estimado.</p>';
        $('#calculo').replaceChildren();
        return;
    }
    if (!filaValida(fila)) {
        $('#erro-pedido').textContent = `Informe a fila como número inteiro entre 0 e ${$('#fila').max}.`;
        return;
    }
    $('#estimativa').classList.add('atualizando');
    try {
        const r = await estimarTempo(pratos, Number(fila));
        if (versao !== requisicao) return;
        const m = r.multipla;
        $('#estimativa').innerHTML = `<p class="estimate"><strong>${fmt(m.previsao_minutos, 1)} min</strong><span>tempo estimado · ${r.quantidade_itens} ${r.quantidade_itens === 1 ? 'prato' : 'pratos'}, fila de ${fila}</span></p>`
            + r.avisos.map(a => `<p class="note">${escapeHtml(a)}</p>`).join('');
        $('#calculo').innerHTML = `<code class="equation">${escapeHtml(m.calculo)}</code>` + (m.personalizado
            ? `<p class="note">Usando β personalizados. Com os β calculados, seriam ${fmt(m.previsao_calculada, 1)} min.</p>`
            : `<p class="note">Conferida com numpy.linalg.lstsq: diferença de ${m.diferenca_numpy.toExponential(1).replace('.', ',')} min.</p>`);
        botaoEnviar.disabled = false;
    } catch (erro) {
        if (versao === requisicao) $('#erro-pedido').textContent = erro.message;
    } finally {
        if (versao === requisicao) $('#estimativa').classList.remove('atualizando');
    }
}

// Envia com a previsão do momento e leva à Cozinha, com o pedido destacado.
form.addEventListener('submit', async event => {
    event.preventDefault();
    const {pratos, fila} = pedidoAtual();
    if (!pratos.length || !filaValida(fila)) return;
    botaoEnviar.disabled = true;
    botaoEnviar.textContent = 'Enviando…';
    try {
        const r = await api('/api/acompanhados', {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pratos, pedidos_na_fila: Number(fila)})});
        location.href = `/cozinha?novo=${r.id}`;
    } catch (erro) {
        $('#erro-pedido').textContent = erro.message;
        botaoEnviar.textContent = 'Enviar para a cozinha';
        botaoEnviar.disabled = false;
    }
});

form.addEventListener('change', event => { if (event.target.name === 'pratos') atualizarResumo(); });
$('#fila').addEventListener('input', atualizarResumo);
$('#busca-prato').addEventListener('input', filtrar);
$('#filtro-categoria').addEventListener('change', filtrar);
form.addEventListener('reset', () => setTimeout(() => { atualizarResumo(); filtrar(); }));

atualizarResumo();
filtrar();
