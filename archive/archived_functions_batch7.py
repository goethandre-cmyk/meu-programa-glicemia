"""
Arquivo de archive: cópias das funções arquivadas no batch 7 (app.py helpers).

Contém implementações originais de filtros/utilitários usados pelos templates
e outras rotinas pequenas. Mantido para auditabilidade e restauração rápida.
"""
import json
from datetime import datetime


def get_glicemia_class_original(valor):
    if valor is None:
        return 'bg-secondary'
    try:
        v = float(str(valor).replace(',', '.'))
        if v < 70:
            return 'bg-danger'
        if v <= 140:
            return 'bg-success'
        if v <= 180:
            return 'bg-warning'
        return 'bg-danger'
    except (ValueError, TypeError):
        return 'bg-secondary'


def get_agendamento_class_original(status):
    if not status:
        return 'light'
    s = str(status).lower()
    mapa = {
        'agendado': 'info',
        'confirmado': 'success',
        'cancelado': 'danger',
        'realizado': 'secondary'
    }
    return mapa.get(s, 'light')


def get_status_class_original(value):
    try:
        float(str(value).replace(',', '.'))
        return get_glicemia_class_original(value)
    except (ValueError, TypeError):
        return get_agendamento_class_original(value)


def from_json_filter_original(json_string):
    if json_string:
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return []
    return []
