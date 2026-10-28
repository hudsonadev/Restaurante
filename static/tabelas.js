document.querySelectorAll('[data-filter-table]').forEach(section => {
    const input = section.querySelector('[data-search]');
    const genre = section.querySelector('[data-genre]');
    const rows = [...section.querySelectorAll('[data-row]')];
    const filter = () => {
        const query = normalizar(input.value.trim());
        rows.forEach(row => row.hidden = !normalizar(row.dataset.searchValue).includes(query) || Boolean(genre?.value && row.dataset.genreValue !== genre.value));
        const count = rows.filter(row => !row.hidden).length;
        section.querySelector('[data-filter-status]').textContent = count ? `${count} de ${rows.length} registros` : 'Nenhum registro encontrado.';
    };
    input.addEventListener('input', filter);
    genre?.addEventListener('change', filter);
    filter();
});
