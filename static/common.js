const $ = (selector) => document.querySelector(selector);
const fmt = (number, digits = 3) => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: digits}).format(number);
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const normalizar = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

async function api(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.erro || 'Não foi possível carregar os dados.');
    return data;
}

