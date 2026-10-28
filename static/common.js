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
    return `<p class="estimate"><strong>${fmt(principal.previsao_minutos, 1)} min</strong>
        <span>tempo estimado de preparo${r.multipla.disponivel ? ' pela regressão múltipla' : ''}</span></p>
        <dl class="estimate-detail">${modelos}</dl>
        ${r.avisos.map(a => `<p class="note">${escapeHtml(a)}</p>`).join('')}`;
}
