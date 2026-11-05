"""Tarefas de linha de comando do Comanda.

    python gerenciar.py inicializar      cria o banco (ou aplica migrações pendentes)
    python gerenciar.py consultar        lista os pedidos do banco
    python gerenciar.py modelo           fórmula, R² e a conferência manual × NumPy
    python gerenciar.py dados            regenera os CSVs de dados/ (não mexe no banco)
    python gerenciar.py resetar [--sim]  apaga o banco e recria a partir dos CSVs

Pare o servidor (Ctrl + C) antes de resetar: no Windows, o arquivo fica travado enquanto o app roda.
"""
import sys
from comanda import db as banco
from comanda.migracoes import contar, inicializar_banco, resetar_banco


def inicializar(_):
    print(f'{inicializar_banco()} pedidos disponíveis no banco.')
    return 0


def consultar(_):
    inicializar_banco()
    with banco.conectar() as db:
        for r in db.execute('''SELECT p.id,p.cliente,p.tempo_preparo_min,COUNT(i.prato_id) AS itens
            FROM pedidos p LEFT JOIN itens_pedido i ON p.id=i.pedido_id GROUP BY p.id ORDER BY p.id'''):
            print(f"{r['id']:03} | {r['cliente']} | {r['itens']} itens | {r['tempo_preparo_min']} min")
    return 0


def modelo(_):
    from comanda.modelo import obter_resumo_modelo
    inicializar_banco()
    resumo = obter_resumo_modelo()
    print(resumo['formula'], '| R²', resumo['r_quadrado'])
    print('Manual × numpy.linalg.lstsq:', resumo['comparacao_numpy']['diferencas'])
    return 0


def dados(_):
    from comanda.dados import preparar
    preparar()
    print('CSVs gerados em dados/.')
    return 0


def resetar(argumentos):
    caminho = banco.CAMINHO_BANCO
    if caminho.exists() and '--sim' not in argumentos:
        atual = contar(['coeficientes_personalizados', 'pedidos_acompanhados'])
        print(f'Isto apaga {caminho.name} e recria o banco a partir dos CSVs.')
        print(f'Serão perdidos: itens editados, {atual["coeficientes_personalizados"]} β personalizados '
              f'e {atual["pedidos_acompanhados"]} pedidos da Cozinha.')
        if input('Digite "sim" para continuar: ').strip().lower() != 'sim':
            print('Cancelado. Nada foi apagado.')
            return 1
    try:
        novo = resetar_banco()
    except RuntimeError as erro:
        print(f'Erro: {erro}')
        return 2
    print(f'Banco recriado: {novo["pedidos"]} pedidos, {novo["pratos"]} pratos, {novo["categorias"]} categorias, '
          f'{novo["itens_pedido"]} itens; sem β personalizados nem pedidos da Cozinha.')
    return 0


COMANDOS = {'inicializar': inicializar, 'consultar': consultar, 'modelo': modelo, 'dados': dados, 'resetar': resetar}


def main(argumentos):
    sys.stdout.reconfigure(encoding='utf-8')  # o console do Windows (cp1252) não imprime "ŷ" nem "β"
    if not argumentos or argumentos[0] not in COMANDOS:
        print(__doc__)
        return 1
    return COMANDOS[argumentos[0]](argumentos[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
