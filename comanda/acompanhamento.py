"""Pedidos novos acompanhados: previsão na criação × tempo real ao marcar "Pronto".

Os pedidos acompanhados NÃO entram no treino do modelo: são um teste independente,
com pedidos que o modelo nunca viu.

De onde vem o tempo real (MODO_TEMPO):
- 'simulado' (padrão): a cozinha decide. No ENVIO, o tempo real é sorteado pela MESMA regra
  da cozinha que criou o histórico (cozinha.tempo_real: paralelismo, fila, categorias e
  ruído). Um relógio acelerado (ACELERACAO_SIMULACAO) corre até esse tempo; só então o pedido
  fica "pronto para sair" e o botão Pronto libera. Os pedidos novos ficam comparáveis aos de treino.
- 'relogio': o tempo real é o intervalo entre o envio e o clique (para uso numa cozinha de verdade).
"""
import random
from datetime import datetime
from comanda.db import conectar
from comanda.cozinha import GRUPOS, sortear_pratos, tempo_real
from comanda.modelo import prever_tempo

MODO_TEMPO = 'simulado'
# Relógio simulado da Cozinha: 120 = 1 segundo real vale 2 minutos simulados.
ACELERACAO_SIMULACAO = 120
_aleatorio = random.Random()   # ruído novo a cada pedido (sem semente fixa)


def agora():
    """Relógio do sistema (isolado numa função para os testes poderem controlá-lo)."""
    return datetime.now()


def registrar(entrada, quantidade_itens, prato_ids, previsao_min, personalizado, rng=None):
    """Grava o pedido. No modo simulado, já sorteia quanto a cozinha vai levar."""
    with conectar() as db:
        cursor = db.execute('''INSERT INTO pedidos_acompanhados (criado_em, pronto_em, pedidos_na_fila,
            quantidade_itens, quantidade_categorias, tempo_maior_prato, tempo_demais_pratos,
            previsao_min, personalizado) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)''',
            (agora().isoformat(timespec='seconds'), entrada['pedidos_na_fila'], quantidade_itens,
             entrada['quantidade_categorias'], entrada['tempo_maior_prato'], entrada['tempo_demais_pratos'],
             previsao_min, int(personalizado)))
        novo = cursor.lastrowid
        db.executemany('INSERT INTO pedidos_acompanhados_itens VALUES (?, ?)', [(novo, p) for p in prato_ids])
    if MODO_TEMPO == 'simulado':
        with conectar() as db:
            db.execute('UPDATE pedidos_acompanhados SET tempo_sorteado_min=? WHERE id=?',
                       (_tempo_simulado(novo, rng or _aleatorio), novo))
    return obter(novo)


def minutos_simulados(criado_em):
    """Tempo simulado desde o envio (relógio acelerado)."""
    return (agora() - datetime.fromisoformat(criado_em)).total_seconds() / 60 * ACELERACAO_SIMULACAO


def _tempo_simulado(acompanhado_id, rng):
    """Aplica a regra da cozinha aos pratos e à fila deste pedido."""
    with conectar() as db:
        fila = db.execute('SELECT pedidos_na_fila FROM pedidos_acompanhados WHERE id=?', (acompanhado_id,)).fetchone()[0]
        pratos = db.execute('''SELECT p.tempo_prato_min, p.categoria_id FROM pedidos_acompanhados_itens i
                               JOIN pratos p ON p.id=i.prato_id WHERE i.acompanhado_id=?''', (acompanhado_id,)).fetchall()
    return tempo_real([t for t, _ in pratos], fila, len({c for _, c in pratos}), rng)


class AindaEmPreparo(ValueError):
    pass


def marcar_pronto(acompanhado_id, rng=None, forcar=False):
    """Conclui o pedido. Devolve None se não existir; ValueError se já estiver pronto;
    AindaEmPreparo se, no modo simulado, a cozinha ainda não terminou (forcar=True ignora)."""
    atual = obter(acompanhado_id)
    if atual is None:
        return None
    if atual['pronto']:
        raise ValueError('Este pedido já foi marcado como pronto.')
    momento = agora()
    if MODO_TEMPO == 'simulado':
        sorteado = atual['tempo_sorteado_min']
        if sorteado is None:                       # pedido enviado antes de a cozinha decidir no envio
            sorteado = _tempo_simulado(acompanhado_id, rng or _aleatorio)
        elif not forcar and not atual['pronto_para_sair']:
            raise AindaEmPreparo('A cozinha ainda está preparando este pedido.')
        real, origem = sorteado, 'simulado'
    else:
        real = round((momento - datetime.fromisoformat(atual['criado_em'])).total_seconds() / 60, 1)
        origem = 'relogio'
    with conectar() as db:
        db.execute('UPDATE pedidos_acompanhados SET pronto_em=?, tempo_real_min=?, origem_tempo=? WHERE id=?',
                   (momento.isoformat(timespec='seconds'), real, origem, acompanhado_id))
    return obter(acompanhado_id)


def simular(quantidade, rng=None):
    """Cria e conclui pedidos sorteados como os do histórico (1 a 8 pratos, fila de 0 a 12).

    Cada um é previsto pelo modelo em uso e concluído pela regra da cozinha.
    Serve para encher o painel previsão × realidade sem esperar pedidos de verdade."""
    rng = rng or _aleatorio
    with conectar() as db:
        pratos = {i: (c, t) for i, c, t in db.execute('SELECT id, categoria_id, tempo_prato_min FROM pratos')}
    categoria_por_prato = {i: c for i, (c, _) in pratos.items()}
    criados = []
    for _ in range(quantidade):
        preferidas = rng.choice(GRUPOS)
        escolhidos = sortear_pratos(rng, categoria_por_prato, preferidas, rng.randint(1, 8))
        fila = rng.randint(0, 12)
        tempos = [pratos[p][1] for p in escolhidos]
        previsao = prever_tempo(tempos, fila, len({pratos[p][0] for p in escolhidos}))
        novo = registrar(previsao['entrada'], len(escolhidos), escolhidos,
                         previsao['multipla']['previsao_minutos'], previsao['multipla']['personalizado'], rng)
        criados.append(marcar_pronto(novo['id'], rng, forcar=True))
    return criados


def _montar(linha, pratos):
    p = dict(linha)
    p['pronto'] = p['pronto_em'] is not None
    p['personalizado'] = bool(p['personalizado'])
    p['pratos'] = pratos
    p['erro_min'] = p['tempo_real_min'] - p['previsao_min'] if p['pronto'] else None
    p['decorrido_min'] = (agora() - datetime.fromisoformat(p['criado_em'])).total_seconds() / 60 if not p['pronto'] else None
    # Modo simulado: o relógio acelerado corre até o tempo sorteado; aí o pedido está pronto para sair.
    p['simulado_min'] = min(minutos_simulados(p['criado_em']), p['tempo_sorteado_min'] or float('inf')) if not p['pronto'] else None
    p['pronto_para_sair'] = (not p['pronto'] and (p['tempo_sorteado_min'] is None
                             or minutos_simulados(p['criado_em']) >= p['tempo_sorteado_min']))
    return p


def listar():
    with conectar() as db:
        linhas = db.execute('SELECT * FROM pedidos_acompanhados ORDER BY id DESC').fetchall()
        nomes = {}
        for aid, nome in db.execute('''SELECT i.acompanhado_id, p.nome FROM pedidos_acompanhados_itens i
                                       JOIN pratos p ON p.id=i.prato_id ORDER BY p.id'''):
            nomes.setdefault(aid, []).append(nome)
    return [_montar(l, nomes.get(l['id'], [])) for l in linhas]


def obter(acompanhado_id):
    return next((p for p in listar() if p['id'] == acompanhado_id), None)


def resumo():
    """Métricas dos pedidos concluídos: o teste do modelo com pedidos novos."""
    todos = listar()
    concluidos = [p for p in todos if p['pronto']]
    r = {'modo_tempo': MODO_TEMPO, 'aceleracao': ACELERACAO_SIMULACAO if MODO_TEMPO == 'simulado' else 1,
         'em_preparo': [p for p in todos if not p['pronto']],
         'concluidos': concluidos, 'quantidade': len(concluidos)}
    if concluidos:
        erros = [p['erro_min'] for p in concluidos]
        r.update(erro_absoluto_medio=sum(abs(e) for e in erros) / len(erros),
                 vies_medio=sum(erros) / len(erros),
                 maior_erro=max(erros, key=abs))
    return r
