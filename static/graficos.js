(() => {
    const dados = JSON.parse(document.querySelector('#dados-analises').textContent);
    const ns = 'http://www.w3.org/2000/svg';
    const criar = (tag, atributos = {}, texto) => {
        const node = document.createElementNS(ns, tag);
        Object.entries(atributos).forEach(([k, v]) => node.setAttribute(k, v));
        if (texto !== undefined) node.textContent = texto;
        return node;
    };
    const validos = dados.observacoes.filter(p => Number.isFinite(p.tempo_plataforma) && Number.isFinite(p.tempo_assistindo));
    const comparaveis = validos.flatMap(p => [p.tempo_assistindo, p.previsao_simples, p.previsao_multipla]).filter(Number.isFinite);
    const dominio = valores => {
        const minimo = Math.min(0, ...valores), maximo = Math.max(1, ...valores);
        const margem = (maximo - minimo) * 0.06;
        return [minimo < 0 ? minimo - margem : 0, maximo + margem];
    };
    const dominioComum = dominio(comparaveis);
    document.querySelectorAll('[data-chart]').forEach((container, index) => {
        const simples = container.dataset.chart === 'simples';
        const modelo = simples ? 'simples' : container.dataset.chart.replace('comparacao-', '');
        const pontos = validos.filter(p => simples || Number.isFinite(p[`previsao_${modelo}`]));
        if (!pontos.length) { container.textContent = 'Não há observações válidas para este gráfico.'; return; }
        const xs = simples ? dominio(pontos.map(p => p.tempo_plataforma)) : dominioComum;
        const minX = Math.min(...pontos.map(p => p.tempo_plataforma));
        const maxX = Math.max(...pontos.map(p => p.tempo_plataforma));
        const reta = x => dados.simples.intercepto + dados.simples.coeficiente * x;
        const ys = simples ? dominio([...pontos.map(p => p.tempo_assistindo), reta(minX), reta(maxX)]) : dominioComum;
        const px = x => 80 + (x - xs[0]) / (xs[1] - xs[0]) * 600;
        const py = y => 350 - (y - ys[0]) / (ys[1] - ys[0]) * 300;
        const svg = criar('svg', {viewBox: '0 0 720 420', role: 'group', 'aria-labelledby': `chart-title-${index} chart-desc-${index}`});
        svg.append(criar('title', {id: `chart-title-${index}`}, simples ? 'Horas na plataforma e horas assistidas, com reta ajustada' : `Regressão ${modelo}: horas observadas e previstas`));
        svg.append(criar('desc', {id: `chart-desc-${index}`}, 'Cada ponto é um link para um perfil. Os mesmos valores estão disponíveis na tabela de usuários abaixo.'));
        for (let i = 0; i <= 5; i++) {
            const x = xs[0] + (xs[1] - xs[0]) * i / 5;
            const y = ys[0] + (ys[1] - ys[0]) * i / 5;
            svg.append(criar('line', {x1:80, x2:680, y1:py(y), y2:py(y), class:'chart-grid'}));
            svg.append(criar('text', {x:68, y:py(y)+5, 'text-anchor':'end'}, fmt(y,1)));
            svg.append(criar('text', {x:px(x), y:375, 'text-anchor':'middle'}, fmt(x,1)));
        }
        svg.append(criar('path', {d:'M80 50 V350 H680', class:'chart-axis'}));
        svg.append(criar('text', {x:380, y:410, 'text-anchor':'middle'}, simples ? 'Horas na plataforma / dia' : 'Horas observadas / dia'));
        svg.append(criar('text', {transform:'translate(20 200) rotate(-90)', 'text-anchor':'middle'}, simples ? 'Horas assistidas / dia' : 'Horas previstas / dia'));
        svg.append(criar('line', {x1:px(simples ? minX : xs[0]), y1:py(simples ? reta(minX) : xs[0]), x2:px(simples ? maxX : xs[1]), y2:py(simples ? reta(maxX) : xs[1]), class:'chart-fit'}));
        const info = document.createElement('p');
        info.className = 'chart-detail muted'; info.setAttribute('aria-live','polite');
        info.textContent = 'Passe sobre um ponto ou navegue com Tab para consultar seus valores.';
        pontos.forEach(p => {
            const x = simples ? p.tempo_plataforma : p.tempo_assistindo;
            const y = simples ? p.tempo_assistindo : p[`previsao_${modelo}`];
            const label = `${p.nome}, ID ${p.id}: ${simples ? 'plataforma' : 'observado'} ${fmt(x)} h; ${simples ? 'assistidas' : 'previsto'} ${fmt(y)} h. Abrir perfil.`;
            const link = criar('a', {href:`/usuarios/${p.id}`, 'aria-label':label});
            link.append(criar('title', {}, label));
            link.append(criar('circle', {cx:px(x), cy:py(y), r:5, class:'chart-point'}));
            link.addEventListener('mouseenter', () => info.textContent = label);
            link.addEventListener('focus', () => info.textContent = label);
            svg.append(link);
        });
        container.append(svg, info);
    });
})();
