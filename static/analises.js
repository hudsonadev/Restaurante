let clusters = null;
function renderProximidade() {
    const categoria = clusters.categorias.find(c => String(c.id) === $('#categoria-proximidade').value);
    $('#proximos').innerHTML = categoria ? categoria.proximos.map(c => `<li><div class="distance-row"><span>${escapeHtml(c.nome)}</span><span>${fmt(c.distancia)}</span></div><div class="bar"><span style="width:${c.similaridade * 100}%"></span></div></li>`).join('') : '';
}

function renderClusters() {
    $('#grupos').innerHTML = clusters.grupos.map(g => `<article class="cluster"><h3>Grupo ${g.id}</h3>${g.categorias.map(item => `<span class="tag">${escapeHtml(item.nome)}</span>`).join('')}</article>`).join('');
    const selecionada = $('#categoria-proximidade').value;
    $('#categoria-proximidade').innerHTML = clusters.categorias.map(c => `<option value="${c.id}">${escapeHtml(c.nome)}</option>`).join('');
    if (selecionada) $('#categoria-proximidade').value = selecionada;
    renderProximidade();
}

$('#categoria-proximidade').addEventListener('change', renderProximidade);
api('/api/clusters').then(dados => { clusters = dados; renderClusters(); }).catch(erro => { $('#grupos').textContent = erro.message; });
