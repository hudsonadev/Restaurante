let clusters = null;
function renderProximidade() {
    const genero = clusters.generos.find(g => String(g.id) === $('#genero-proximidade').value);
    $('#proximos').innerHTML = genero ? genero.proximos.map(g => `<li><div class="distance-row"><span>${escapeHtml(g.nome)}</span><span>${fmt(g.distancia)}</span></div><div class="bar"><span style="width:${g.similaridade * 100}%"></span></div></li>`).join('') : '';
}

function renderClusters() {
    $('#grupos').innerHTML = clusters.grupos.map(g => `<article class="cluster"><h3>Grupo ${g.id}</h3>${g.generos.map(item => `<span class="tag">${escapeHtml(item.nome)}</span>`).join('')}</article>`).join('');
    const selecionado = $('#genero-proximidade').value;
    $('#genero-proximidade').innerHTML = clusters.generos.map(g => `<option value="${g.id}">${escapeHtml(g.nome)}</option>`).join('');
    if (selecionado) $('#genero-proximidade').value = selecionado;
    renderProximidade();
}

$('#genero-proximidade').addEventListener('change', renderProximidade);
$('#previsao-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try {
        const dados = Object.fromEntries(new FormData(event.currentTarget));
        const r = await api('/api/prever', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(dados)});
        $('#resultado').innerHTML = `<strong>${fmt(r.previsao_horas,2)} horas/dia</strong><p class="muted">Estimativa linear bruta: ${fmt(r.previsao_bruta,2)} horas. ${r.avisos.map(escapeHtml).join(' ')}</p>`;
    } catch (erro) { $('#resultado').textContent = erro.message; }
    finally { button.disabled = false; }
});

async function carregarModelo() {
    try {
        const m = await api('/api/modelo');
        if (!m.disponivel) {
            $('#modelo').textContent = m.aviso;
            $('#previsao-form').querySelector('button').disabled = true;
            return;
        }
        $('#modelo').innerHTML = `<div class="metrics"><span>Amostra <strong>${m.quantidade_registros}</strong></span><span>R² <strong>${m.r_quadrado === null ? 'Indefinido' : fmt(m.r_quadrado)}</strong></span><span>Variáveis <strong>3</strong></span></div><code class="equation">${escapeHtml(m.formula)}</code><p class="muted">R² descreve o ajuste à amostra, não a precisão em novos usuários. Associação não implica causalidade.</p>`;
        $('#previsao-form').querySelector('button').disabled = false;
    } catch (erro) { $('#modelo').textContent = erro.message; }
}


carregarModelo();
api('/api/clusters').then(dados => { clusters = dados; renderClusters(); }).catch(erro => { $('#grupos').textContent = erro.message; });
