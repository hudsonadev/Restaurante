const $ = (selector) => document.querySelector(selector);
const fmt = (number, digits = 3) => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: digits}).format(number);
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const normalizar = (value) => value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

async function api(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.erro || 'Não foi possível carregar os dados.');
    return data;
}

const estimarTempo = (pratos, fila) => api('/api/prever', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pratos, pedidos_na_fila: fila})});

function renderEstimativa(r) {
    const principal = r.multipla.disponivel ? r.multipla : r.simples;
    const modelos = [['Regressão múltipla', r.multipla], ['Regressão simples', r.simples]].map(([nome, m]) => m.disponivel
        ? `<div><dt>${nome}</dt><dd><strong>${fmt(m.previsao_minutos, 1)} min</strong><code>${escapeHtml(m.calculo)}</code></dd></div>`
        : `<div><dt>${nome}</dt><dd>${escapeHtml(m.aviso)}</dd></div>`).join('');
    // Conferência da regressão simples: mesma previsão pelo cálculo manual e pelo numpy.polyfit.
    const conferencia = r.simples.disponivel
        ? `<p class="note">Regressão simples conferida: manual ${fmt(r.simples.previsao_bruta, 4)} min × numpy.polyfit ${fmt(r.simples.previsao_polyfit, 4)} min (diferença ${r.simples.diferenca_polyfit.toExponential(1).replace('.', ',')}).</p>` : '';
    return `<p class="estimate"><strong>${fmt(principal.previsao_minutos, 1)} min</strong>
        <span>tempo estimado de preparo${r.multipla.disponivel ? ' pela regressão múltipla' : ''}</span></p>
        <p class="muted">Tempo base dos pratos: ${fmt(r.entrada.tempo_base_itens, 1)} min (${r.quantidade_itens} itens). A cozinha trabalha em paralelo, por isso o pedido não leva a soma inteira.</p>
        <dl class="estimate-detail">${modelos}</dl>${conferencia}
        ${r.avisos.map(a => `<p class="note">${escapeHtml(a)}</p>`).join('')}`;
}
