"""
Módulo clients - Gestión de clientes/prestatarios.

IMPORTANTE: No importamos modelos aquí para evitar problemas de carga circular.
Los modelos deben importarse directamente desde sus módulos:
    from api.clients.models import Client, ClientDocument
"""

default_app_config = 'api.clients.apps.ClientsConfig'
