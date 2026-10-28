const form = $('#pedido-form');
const caixas = [...form.querySelectorAll('input[name="pratos"]')];
let requisicao = 0;

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
    $('#resumo-lista').innerHTML = marcadas.map(c => `<li>${escapeHtml(c.closest('.menu-item').dataset.nome)}</li>`).join('')
        || '<li class="muted">Nenhum prato selecionado.</li>';
    // Um resultado antigo não deve parecer válido para a nova composição.
    requisicao++;
    $('#resultado').replaceChildren();
}

form.addEventListener('change', event => { if (event.target.name === 'pratos' || event.target.id === 'fila') atualizarResumo(); });
$('#fila').addEventListener('input', atualizarResumo);
$('#busca-prato').addEventListener('input', filtrar);
$('#filtro-categoria').addEventListener('change', filtrar);
form.addEventListener('reset', () => setTimeout(() => { atualizarResumo(); filtrar(); }));

form.addEventListener('submit', async event => {
    event.preventDefault();
    const pratos = caixas.filter(c => c.checked).map(c => Number(c.value));
    const fila = $('#fila').value.trim();
    $('#erro-pedido').textContent = '';
    if (!pratos.length) { $('#erro-pedido').textContent = 'Selecione ao menos um prato.'; return; }
    if (!/^\d+$/.test(fila) || Number(fila) > Number($('#fila').max)) {
        $('#erro-pedido').textContent = `Informe a fila como número inteiro entre 0 e ${$('#fila').max}.`;
        $('#fila').focus();
        return;
    }
    const versao = ++requisicao, botao = form.querySelector('[type="submit"]');
    botao.disabled = true;
    $('#resultado').textContent = 'Calculando…';
    try {
        const r = await estimarTempo(pratos, Number(fila));
        if (versao === requisicao) $('#resultado').innerHTML = renderEstimativa(r);
    } catch (erro) {
        if (versao === requisicao) { $('#resultado').replaceChildren(); $('#erro-pedido').textContent = erro.message; }
    } finally { botao.disabled = false; }
});

atualizarResumo();
filtrar();
