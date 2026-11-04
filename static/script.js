let cardapio = [], requisicao = 0, salvando = false, carregando = true;
const pedidoId = () => $('#pedido').value;

function selecionarAba(nome, foco = false) {
    document.querySelectorAll('[data-view]').forEach(tab => {
        const ativa = tab.dataset.view === nome;
        tab.setAttribute('aria-selected', String(ativa));
        tab.tabIndex = ativa ? 0 : -1;
        if (ativa && foco) tab.focus();
    });
    document.querySelectorAll('.view').forEach(view => view.hidden = view.id !== `view-${nome}`);
}

document.querySelector('.tabs').addEventListener('click', event => {
    const tab = event.target.closest('[data-view]');
    if (tab) selecionarAba(tab.dataset.view);
});
document.querySelector('.tabs').addEventListener('keydown', event => {
    const tabs = [...document.querySelectorAll('[data-view]')];
    const index = tabs.indexOf(event.target);
    if (index < 0 || !['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 :
        (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    selecionarAba(tabs[next].dataset.view, true);
});

function card(item, ranking) {
    return `<article class="card ${item.incluido ? 'is-watched' : ''}" style="--hue:${(item.categoria_id * 33 + 70) % 360}">
        <div class="card-art"><span class="tag">${escapeHtml(item.categoria)}</span>${ranking ? `<span class="rank">${ranking}</span>` : ''}</div>
        <div class="card-body"><h3>${escapeHtml(item.nome)}</h3><p class="muted">${fmt(item.tempo_prato_min, 1)} min de preparo</p>
        ${item.motivos ? `<details class="reason"><summary>Por que foi sugerido</summary><p>${item.motivos.map(escapeHtml).join(' ')}</p><small>Pontuação ${fmt(item.pontuacao)} (ordenação, não probabilidade).</small></details>` : `<p class="watch-state">${item.incluido ? 'No pedido' : 'Fora do pedido'}</p>`}
        <button type="button" ${carregando || salvando ? 'disabled' : ''} data-prato="${item.id}" data-incluir="${!item.incluido}" aria-label="${item.incluido ? 'Remover' : 'Adicionar ao pedido'}: ${escapeHtml(item.nome)}">${item.incluido ? 'Remover' : 'Adicionar ao pedido'}</button></div></article>`;
}

async function atualizarEstimativa(versao) {
    const pratos = cardapio.filter(p => p.incluido).map(p => p.id);
    if (!pratos.length) { $('#estimativa-atual').innerHTML = '<p class="empty">Pedido sem itens: adicione um prato para estimar o tempo.</p>'; return; }
    try {
        const r = await estimarTempo(pratos, Number($('#pedido').dataset.fila));
        if (versao === requisicao) $('#estimativa-atual').innerHTML = renderEstimativa(r);
    } catch (erro) {
        if (versao === requisicao) $('#estimativa-atual').textContent = erro.message;
    }
}

function renderCardapio() {
    const categoria = $('#filtro-categoria').value;
    const busca = normalizar($('#busca').value.trim());
    const estado = $('#filtro-incluido').value;
    const itens = cardapio.filter(p => (!categoria || String(p.categoria_id) === categoria) &&
        normalizar(p.nome).includes(busca) && (estado === 'todos' || (estado === 'no-pedido' ? p.incluido : !p.incluido)));
    $('#total-resultados').textContent = `${itens.length} de ${cardapio.length} pratos`;
    $('#lista-cardapio').innerHTML = itens.map(p => card(p)).join('') || '<p class="empty">Nenhum prato encontrado. Tente outra busca ou limpe os filtros.</p>';
    const incluidos = cardapio.filter(p => p.incluido);
    $('#total-itens').textContent = incluidos.length;
    $('#atual-itens').textContent = incluidos.length;
    $('#atual-tempo-base').textContent = fmt(incluidos.reduce((soma, p) => soma + p.tempo_prato_min, 0), 1);
    $('#itens').innerHTML = incluidos.map(p => card(p)).join('') || '<p class="empty">Pedido sem itens. Adicione pratos pelo cardápio.</p>';
}

async function carregarPedido() {
    const versao = ++requisicao;
    carregando = true;
    document.querySelectorAll('.view').forEach(view => view.setAttribute('aria-busy', 'true'));
    $('#status').textContent = 'Carregando…';
    document.querySelectorAll('[data-prato]').forEach(b => b.disabled = true);
    try {
        const [pratos, sugestoes] = await Promise.all([
            api(`/api/pratos?pedido_id=${pedidoId()}`),
            api(`/api/pedidos/${pedidoId()}/sugestoes`)]);
        if (versao !== requisicao) return;
        cardapio = pratos;
        carregando = false;
        $('#sugestoes').innerHTML = sugestoes.sugestoes.map((p, i) => card(p, i + 1)).join('') || '<p class="empty">O pedido já inclui todo o cardápio.</p>';
        $('#sugestoes-nota').textContent = sugestoes.pedido_vazio ? 'Pedido sem itens: pratos mais populares.' : 'Combinam com as categorias do pedido e com pedidos parecidos.';
        $('#vizinhos').innerHTML = sugestoes.pedidos_semelhantes.map(p => `<div class="neighbor"><a href="/pedidos/${p.id}">#${p.id} ${escapeHtml(p.cliente)}</a><small>Similaridade ${fmt(p.similaridade)}</small></div>`).join('') || '<p class="muted">Nenhum pedido com composição semelhante.</p>';
        renderCardapio();
        $('#erro').textContent = '';
        $('#status').textContent = `Pedido #${sugestoes.pedido.id} atualizado.`;
        atualizarEstimativa(versao);
    } catch (erro) {
        if (versao !== requisicao) return;
        cardapio = [];
        $('#total-itens').textContent = '0';
        $('#atual-itens').textContent = '—';
    $('#atual-tempo-base').textContent = '—';
        $('#total-resultados').textContent = '';
        ['#sugestoes', '#lista-cardapio', '#itens', '#vizinhos', '#estimativa-atual'].forEach(s => $(s).replaceChildren());
        $('#erro').textContent = erro.message;
        $('#status').textContent = 'Falha na atualização. Recarregue a página para tentar novamente.';
    } finally {
        if (versao === requisicao) {
            carregando = false;
            document.querySelectorAll('.view').forEach(view => view.setAttribute('aria-busy', 'false'));
        }
    }
}

document.addEventListener('click', async (event) => {
    const botao = event.target.closest('[data-prato]');
    if (!botao || salvando || carregando) return;
    const painel = botao.closest('.view');
    const pratoId = botao.dataset.prato;
    salvando = true;
    $('#filtro-categoria').disabled = true;
    document.querySelectorAll('[data-prato]').forEach(b => b.disabled = true);
    try {
        await api(`/api/pedidos/${pedidoId()}/itens/${pratoId}`, {
            method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({incluido: botao.dataset.incluir === 'true'})});
        await carregarPedido();
    } catch (erro) {
        $('#erro').textContent = erro.message;
    } finally {
        salvando = false;
        $('#filtro-categoria').disabled = false;
        document.querySelectorAll('[data-prato]').forEach(b => b.disabled = false);
        const proximo = painel.querySelector(`[data-prato="${pratoId}"]`) || painel.querySelector('[data-prato]') || painel;
        proximo.focus({preventScroll: true});
    }
});

$('#filtro-categoria').addEventListener('change', renderCardapio);
$('#busca').addEventListener('input', renderCardapio);
$('#filtro-incluido').addEventListener('change', renderCardapio);
$('#limpar-filtros').addEventListener('click', () => {
    $('#busca').value = '';
    $('#filtro-categoria').value = '';
    $('#filtro-incluido').value = 'todos';
    renderCardapio();
    $('#busca').focus();
});
async function iniciar() {
    try {
        const pratos = await api(`/api/pratos?pedido_id=${pedidoId()}`);
        const categorias = [...new Map(pratos.map(p => [p.categoria_id, p.categoria])).entries()];
        $('#filtro-categoria').innerHTML += categorias.map(([id, nome]) => `<option value="${id}">${escapeHtml(nome)}</option>`).join('');
        await carregarPedido();
    } catch (erro) { $('#erro').textContent = erro.message; $('#status').textContent = 'Não foi possível carregar o pedido. Recarregue para tentar novamente.'; }
}
iniciar();
