from banco import conectar, inicializar_banco

if __name__ == '__main__':
    inicializar_banco()
    with conectar() as db:
        for r in db.execute('''SELECT u.id,u.nome,COUNT(v.conteudo_id) AS vistos
            FROM usuarios u LEFT JOIN visualizacoes v ON u.id=v.usuario_id GROUP BY u.id ORDER BY u.id'''):
            print(f"{r['id']:03} | {r['nome']} | {r['vistos']} conteúdos vistos")
