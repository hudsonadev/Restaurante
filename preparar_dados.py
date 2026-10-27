"""Gera uma vez os CSVs demonstrativos. Não modifica o banco nem roda na aplicação."""
import csv
import random
from banco import DIRETORIO_DADOS

BASE = DIRETORIO_DADOS


def escrever(nome, campos, linhas):
    with (BASE / nome).open('w', encoding='utf-8', newline='') as arquivo:
        writer = csv.writer(arquivo)
        writer.writerow(campos)
        writer.writerows(linhas)


def preparar():
    with (BASE / 'dataset_streaming.csv').open(encoding='utf-8', newline='') as arquivo:
        usuarios = list(csv.DictReader(arquivo))
    nomes = ['Ana', 'Bruno', 'Camila', 'Diego', 'Elisa', 'Felipe', 'Gabriela', 'Hugo', 'Isabela', 'João']
    sobrenomes = ['Almeida', 'Barros', 'Costa', 'Dias', 'Esteves', 'Freitas', 'Gomes', 'Lima', 'Moura', 'Nunes']
    escrever('dataset_streaming.csv', ['usuario_id', 'nome', 'tempo_plataforma_horas', 'tempo_assistindo_horas'], [
        (u['usuario_id'], nomes[(int(u['usuario_id']) - 1) % 10] + ' ' + sobrenomes[(int(u['usuario_id']) - 1) // 10],
         u['tempo_plataforma_horas'], u['tempo_assistindo_horas']) for u in usuarios])
    generos = ['Ação', 'Aventura', 'Ficção científica', 'Fantasia', 'Comédia', 'Romance', 'Drama', 'Suspense', 'Terror', 'Documentário']
    titulos = [
        ['Operação Horizonte', 'Última Missão', 'Código de Aço', 'Rota de Fuga', 'Impacto Final', 'Linha de Frente'],
        ['Além das Montanhas', 'A Ilha Perdida', 'Travessia Selvagem', 'O Mapa Esquecido', 'Expedição Aurora', 'Estrada do Sol'],
        ['Órbita Distante', 'Memórias do Futuro', 'Colônia Marte', 'Sinal do Infinito', 'Depois da Terra', 'Fronteira Temporal'],
        ['O Reino de Vidro', 'Guardiões da Névoa', 'A Última Feiticeira', 'Floresta de Cristal', 'O Livro das Marés', 'Dragões do Norte'],
        ['Vizinhos por Acaso', 'Férias em Família', 'Plano Quase Perfeito', 'Confusão no Escritório', 'Um Dia de Sorte', 'Receita de Risadas'],
        ['Cartas de Outono', 'Encontro na Estação', 'Entre Duas Cidades', 'O Nosso Verão', 'Café com Saudade', 'Antes do Amanhã'],
        ['Casa de Memórias', 'Dias de Recomeço', 'Retratos da Vida', 'Caminhos de Casa', 'O Silêncio do Pai', 'Pequenas Coragens'],
        ['A Porta Fechada', 'Testemunha Oculta', 'O Último Bilhete', 'Sombras da Cidade', 'Segredo na Estrada', 'Depois da Meia-Noite'],
        ['Vozes no Porão', 'A Casa do Lago', 'Noite Sem Fim', 'O Visitante', 'Ecos do Escuro', 'A Vila Esquecida'],
        ['Oceanos Vivos', 'Histórias do Sertão', 'Por Dentro da Ciência', 'O Mundo das Árvores', 'Música sem Fronteiras', 'Cidades do Amanhã']]
    escrever('generos.csv', ['genero_id', 'nome'], enumerate(generos, 1))
    escrever('conteudos.csv', ['conteudo_id', 'titulo', 'genero_id'], [
        (g * 6 + j + 1, titulo, g + 1) for g, lista in enumerate(titulos) for j, titulo in enumerate(lista)])
    rng = random.Random(20261027)
    grupos = [[1, 2, 3, 4], [5, 6, 7], [8, 9, 10]]
    historico = []
    for u in usuarios:
        uid = int(u['usuario_id'])
        if uid % 20 == 0:
            continue
        preferidos = grupos[(uid - 1) % 3]
        quantidade = rng.randint(3, 17)
        candidatos = list(range(1, 61))
        for _ in range(quantidade):
            pesos = [9 if (c - 1) // 6 + 1 in preferidos else 0.4 for c in candidatos]
            cid = rng.choices(candidatos, weights=pesos, k=1)[0]
            candidatos.remove(cid)
            historico.append((uid, cid))
    escrever('historico_inicial.csv', ['usuario_id', 'conteudo_id'], sorted(historico))


if __name__ == '__main__':
    preparar()
