from banco import conectar, inicializar_banco

if __name__ == '__main__':
    inicializar_banco()
    with conectar() as db:
        for r in db.execute('''SELECT p.id,p.cliente,p.tempo_preparo_min,COUNT(i.prato_id) AS itens
            FROM pedidos p LEFT JOIN itens_pedido i ON p.id=i.pedido_id GROUP BY p.id ORDER BY p.id'''):
            print(f"{r['id']:03} | {r['cliente']} | {r['itens']} itens | {r['tempo_preparo_min']} min")
