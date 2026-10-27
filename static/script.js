const $ = (selector) => document.querySelector(selector);
const fmt = (number, digits = 3) => new Intl.NumberFormat('pt-BR', {maximumFractionDigits: digits}).format(number);
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let catalogo = [], clusters = null, requisicao = 0, salvando = false, carregando = true;
const normalizar = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

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

async function api(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.erro || 'Não foi possível carregar os dados.');
    return data;
}

function card(item, ranking) {
    return `<article class="card ${item.visto ? 'is-watched' : ''}" style="--hue:${(item.genero_id * 33 + 70) % 360}">
        <div class="card-art"><span class="tag">${escapeHtml(item.genero)}</span>${ranking ? `<span class="rank">${String(ranking).padStart(2,'0')}</span>` : ''}</div>
        <div class="card-body"><h3>${escapeHtml(item.titulo)}</h3>
        ${item.motivos ? `<details class="reason"><summary>Por que esta sugestão?</summary><p>${item.motivos.map(escapeHtml).join(' ')}</p><small>Índice de afinidade: ${fmt(item.pontuacao)}. Não representa probabilidade.</small></details>` : `<p class="watch-state">${item.visto ? '✓ No seu histórico' : 'Disponível para descobrir'}</p>`}
        <button type="button" ${carregando || salvando ? 'disabled' : ''} data-conteudo="${item.id}" data-visto="${!item.visto}" aria-label="${item.visto ? 'Desmarcar' : 'Marcar como visto'}: ${escapeHtml(item.titulo)}">${item.visto ? 'Desmarcar' : '<span aria-hidden="true">＋</span> Marcar como visto'}</button></div></article>`;
}

function renderCatalogo() {
    const genero = $('#filtro-genero').value;
    const busca = normalizar($('#busca').value.trim());
    const estado = $('#filtro-visto').value;
    const itens = catalogo.filter(c => (!genero || String(c.genero_id) === genero) &&
        normalizar(c.titulo).includes(busca) && (estado === 'todos' || (estado === 'vistos' ? c.visto : !c.visto)));
    $('#total-resultados').textContent = `${itens.length} de ${catalogo.length} títulos`;
    $('#lista-catalogo').innerHTML = itens.map(c => card(c)).join('') || '<p class="empty">Nenhum título encontrado. Tente outra busca ou limpe os filtros.</p>';
    const vistos = catalogo.filter(c => c.visto);
    $('#total-vistos').textContent = vistos.length;
    $('#historico').innerHTML = vistos.map(c => card(c)).join('') || '<p class="empty">Seu histórico está vazio. Marque um conteúdo para começar.</p>';
}

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

async function carregarUsuario() {
    const versao = ++requisicao, usuario = $('#usuario').value;
    carregando = true;
    document.querySelectorAll('.view').forEach(view => view.setAttribute('aria-busy', 'true'));
    $('#status').textContent = 'Atualizando recomendações…';
    document.querySelectorAll('[data-conteudo]').forEach(b => b.disabled = true);
    try {
        const [conteudos, recomendacoes, grupos] = await Promise.all([
            api(`/api/conteudos?usuario_id=${usuario}`),
            api(`/api/usuarios/${usuario}/recomendacoes`), api('/api/clusters')]);
        if (versao !== requisicao) return;
        catalogo = conteudos; clusters = grupos;
        carregando = false;
        $('#recomendacoes').innerHTML = recomendacoes.recomendacoes.map((c,i) => card(c,i+1)).join('') || '<p class="empty">Você já assistiu a todo o catálogo.</p>';
        $('#recomendacoes-titulo').textContent = `Sugestões para ${recomendacoes.usuario.nome.split(' ')[0]}`;
        $('#recomendacoes-nota').textContent = recomendacoes.sem_historico ? 'Comece pelos mais assistidos. Marque o que já viu para personalizar suas sugestões.' : 'Selecionadas a partir do que você assiste e de pessoas com gostos parecidos.';
        $('#vizinhos').innerHTML = recomendacoes.usuarios_semelhantes.map(u => `<div class="neighbor">${escapeHtml(u.nome)}<small>Similaridade ${fmt(u.similaridade)}</small></div>`).join('') || '<p class="muted">Ainda não há usuários com consumo semelhante.</p>';
        renderCatalogo(); renderClusters();
        $('#erro').textContent = '';
        $('#status').textContent = `Seleção de ${recomendacoes.usuario.nome} atualizada.`;
    } catch (erro) {
        if (versao !== requisicao) return;
        catalogo = [];
        $('#total-vistos').textContent = '0';
        $('#total-resultados').textContent = '';
        ['#recomendacoes','#lista-catalogo','#historico','#vizinhos'].forEach(s => $(s).replaceChildren());
        $('#erro').textContent = erro.message;
        $('#status').textContent = 'Falha na atualização. Selecione um usuário para tentar novamente.';
    } finally {
        if (versao === requisicao) {
            carregando = false;
            document.querySelectorAll('.view').forEach(view => view.setAttribute('aria-busy', 'false'));
        }
    }
}

document.addEventListener('click', async (event) => {
    const botao = event.target.closest('[data-conteudo]');
    if (!botao || salvando || carregando) return;
    const painel = botao.closest('.view');
    const conteudoId = botao.dataset.conteudo;
    salvando = true;
    $('#usuario').disabled = true;
    $('#filtro-genero').disabled = true;
    document.querySelectorAll('[data-conteudo]').forEach(b => b.disabled = true);
    try {
        await api(`/api/usuarios/${$('#usuario').value}/vistos/${botao.dataset.conteudo}`, {
            method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({visto:botao.dataset.visto === 'true'})});
        await carregarUsuario();
    } catch (erro) {
        $('#erro').textContent = erro.message;
    } finally {
        salvando = false;
        $('#usuario').disabled = false;
        $('#filtro-genero').disabled = false;
        document.querySelectorAll('[data-conteudo]').forEach(b => b.disabled = false);
        const proximo = painel.querySelector(`[data-conteudo="${conteudoId}"]`) || painel.querySelector('[data-conteudo]') || painel;
        proximo.focus({preventScroll: true});
    }
});

$('#usuario').addEventListener('change', carregarUsuario);
$('#filtro-genero').addEventListener('change', renderCatalogo);
$('#busca').addEventListener('input', renderCatalogo);
$('#filtro-visto').addEventListener('change', renderCatalogo);
$('#limpar-filtros').addEventListener('click', () => {
    $('#busca').value = '';
    $('#filtro-genero').value = '';
    $('#filtro-visto').value = 'todos';
    renderCatalogo();
    $('#busca').focus();
});
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
    } catch (erro) { $('#modelo').textContent = erro.message; }
}

async function iniciar() {
    carregarModelo();
    try {
        const [usuarios, grupos] = await Promise.all([api('/api/usuarios'), api('/api/clusters')]);
        $('#usuario').innerHTML = usuarios.map(u => `<option value="${u.id}">${escapeHtml(u.nome)}</option>`).join('');
        $('#filtro-genero').innerHTML += grupos.generos.map(g => `<option value="${g.id}">${escapeHtml(g.nome)}</option>`).join('');
        $('#usuario').disabled = false;
        await carregarUsuario();
    } catch (erro) { $('#erro').textContent = erro.message; $('#status').textContent = 'Não foi possível iniciar a aplicação.'; }
}
iniciar();
