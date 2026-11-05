"""Filtros e variáveis globais dos templates."""
from datetime import date

DIAS = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho',
         'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def data_por_extenso(dia):
    """Data para o cabeçalho de jornal, sem depender do locale do sistema."""
    return f'{DIAS[dia.weekday()]}, {dia.day} de {MESES[dia.month - 1]} de {dia.year}'


def numero(valor, casas=1):
    return 'Indefinido' if valor is None else f'{valor:.{casas}f}'.replace('.', ',')


def cientifico(valor):
    return 'Indefinido' if valor is None else f'{valor:.1e}'.replace('.', ',')


def registrar(app):
    app.add_template_filter(numero, 'numero')
    app.add_template_filter(cientifico, 'cientifico')
    app.context_processor(lambda: {'data_hoje': data_por_extenso(date.today())})
