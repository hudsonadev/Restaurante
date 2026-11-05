// Gráfico real × previsto da regressão múltipla, em SVG gerado localmente.
(() => {
    const dados = JSON.parse(document.querySelector('#dados-analises').textContent);
    const ns = 'http://www.w3.org/2000/svg';
    const criar = (tag, atributos = {}, texto) => {
        const node = document.createElementNS(ns, tag);
        Object.entries(atributos).forEach(([k, v]) => node.setAttribute(k, v));
        if (texto !== undefined) node.textContent = texto;
        return node;
    };
    const pontos = dados.observacoes.filter(p => Number.isFinite(p.tempo_preparo) && Number.isFinite(p.previsao_multipla));
    const dominio = valores => {
        const minimo = Math.min(0, ...valores), maximo = Math.max(1, ...valores);
        const margem = (maximo - minimo) * 0.06;
        return [minimo < 0 ? minimo - margem : 0, maximo + margem];
    };
    // Pedidos novos concluídos (página Cozinha): real medido pelo botão "Pronto" × previsão feita na criação.
    const novos = (dados.acompanhados || []).filter(p => Number.isFinite(p.tempo_real_min) && Number.isFinite(p.previsao_min));
    // Mesma escala nos dois eixos, para a diagonal y = x ser a previsão perfeita.
    const escala = dominio([...pontos.flatMap(p => [p.tempo_preparo, p.previsao_multipla]),
                            ...novos.flatMap(p => [p.tempo_real_min, p.previsao_min])]);
    document.querySelectorAll('[data-chart="multipla"]').forEach((container, index) => {
        if (!pontos.length) { container.textContent = 'Não há observações válidas para este gráfico.'; return; }
        const px = x => 80 + (x - escala[0]) / (escala[1] - escala[0]) * 600;
        const py = y => 350 - (y - escala[0]) / (escala[1] - escala[0]) * 300;
        const svg = criar('svg', {viewBox: '0 0 720 420', role: 'group', 'aria-labelledby': `chart-title-${index} chart-desc-${index}`});
        svg.append(criar('title', {id: `chart-title-${index}`}, 'Regressão múltipla: tempos reais e previstos'));
        svg.append(criar('desc', {id: `chart-desc-${index}`}, 'Cada ponto é um link para um pedido. Os mesmos valores estão na tabela de pedidos.'));
        for (let i = 0; i <= 5; i++) {
            const v = escala[0] + (escala[1] - escala[0]) * i / 5;
            svg.append(criar('line', {x1: 80, x2: 680, y1: py(v), y2: py(v), class: 'chart-grid'}));
            svg.append(criar('text', {x: 68, y: py(v) + 5, 'text-anchor': 'end'}, fmt(v, 0)));
            svg.append(criar('text', {x: px(v), y: 375, 'text-anchor': 'middle'}, fmt(v, 0)));
        }
        svg.append(criar('path', {d: 'M80 50 V350 H680', class: 'chart-axis'}));
        svg.append(criar('text', {x: 380, y: 410, 'text-anchor': 'middle'}, 'Tempo real (min)'));
        svg.append(criar('text', {transform: 'translate(20 200) rotate(-90)', 'text-anchor': 'middle'}, 'Tempo previsto (min)'));
        svg.append(criar('line', {x1: px(escala[0]), y1: py(escala[0]), x2: px(escala[1]), y2: py(escala[1]), class: 'chart-fit'}));
        const info = document.createElement('p');
        info.className = 'chart-detail muted'; info.setAttribute('aria-live', 'polite');
        info.textContent = 'Passe sobre um ponto ou navegue com Tab para consultar seus valores.';
        pontos.forEach(p => {
            const label = `Pedido #${p.id}, ${p.cliente}: real ${fmt(p.tempo_preparo, 1)} min; previsto ${fmt(p.previsao_multipla, 1)} min. Abrir pedido.`;
            const link = criar('a', {href: `/pedidos/${p.id}`, 'aria-label': label});
            link.append(criar('title', {}, label));
            link.append(criar('circle', {cx: px(p.tempo_preparo), cy: py(p.previsao_multipla), r: 5, class: 'chart-point'}));
            link.addEventListener('mouseenter', () => info.textContent = label);
            link.addEventListener('focus', () => info.textContent = label);
            svg.append(link);
        });
        novos.forEach(p => {
            const label = `Pedido novo N${p.id}: real ${fmt(p.tempo_real_min, 1)} min; previsto ${fmt(p.previsao_min, 1)} min.`;
            const grupo = criar('g', {tabindex: 0, 'aria-label': label});
            grupo.append(criar('title', {}, label));
            const cx = px(p.tempo_real_min), cy = py(p.previsao_min);
            grupo.append(criar('path', {d: `M${cx} ${cy - 7} L${cx + 7} ${cy} L${cx} ${cy + 7} L${cx - 7} ${cy} Z`, class: 'chart-point-novo'}));
            grupo.addEventListener('mouseenter', () => info.textContent = label);
            grupo.addEventListener('focus', () => info.textContent = label);
            svg.append(grupo);
        });
        container.append(svg, info);
    });
})();
