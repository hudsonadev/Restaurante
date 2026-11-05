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
    const m = r.multipla;
    // Conferência: a mesma previsão com os coeficientes do numpy.linalg.lstsq.
    const conferencia = m.personalizado
        ? `<p class="note">Usando β personalizados. Com os β calculados, seriam ${fmt(m.previsao_calculada, 1)} min.</p>`
        : `<p class="note">Conferida com numpy.linalg.lstsq: diferença de ${m.diferenca_numpy.toExponential(1).replace('.', ',')} min.</p>`;
    return `<p class="estimate"><strong>${fmt(m.previsao_minutos, 1)} min</strong>
        <span>tempo estimado (regressão múltipla)</span></p>
        <details class="detalhes"><summary>Como calculamos</summary><code class="equation">${escapeHtml(m.calculo)}</code>${conferencia}</details>
        ${r.avisos.map(a => `<p class="note">${escapeHtml(a)}</p>`).join('')}`;
}
