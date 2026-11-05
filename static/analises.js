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

// Coeficientes personalizados: valem em todo o sistema até voltar aos calculados.
const formCoeficientes = $('#coeficientes-form');
if (formCoeficientes) {
    formCoeficientes.addEventListener('submit', async event => {
        event.preventDefault();
        const valores = Object.fromEntries([...formCoeficientes.querySelectorAll('.beta-input')].map(c => [c.name, c.value.trim()]));
        if (Object.values(valores).some(v => v === '' || !Number.isFinite(Number(v)))) {
            $('#erro-coeficientes').textContent = 'Preencha os cinco coeficientes com números.';
            return;
        }
        try {
            await api('/api/coeficientes', {method: 'PUT', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(Object.fromEntries(Object.entries(valores).map(([k, v]) => [k, Number(v)])))});
            location.hash = 'coeficientes'; location.reload();
        } catch (erro) { $('#erro-coeficientes').textContent = erro.message; }
    });
    $('#restaurar-coeficientes')?.addEventListener('click', async () => {
        try { await api('/api/coeficientes', {method: 'DELETE'}); location.hash = 'coeficientes'; location.reload(); }
        catch (erro) { $('#erro-coeficientes').textContent = erro.message; }
    });
}
api('/api/clusters').then(dados => { clusters = dados; renderClusters(); }).catch(erro => { $('#grupos').textContent = erro.message; });
