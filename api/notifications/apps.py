"""
Notificaciones Push - App configuration.
"""
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.notifications'
    verbose_name = 'Notificaciones Push'

    def ready(self):
        """
        Se ejecuta cuando Django termina de inicializar.

        Inicia el thread de background para alertas de mora.
        Solo se ejecuta en un worker para evitar duplicación.
        """
        from .scheduler_thread import start_scheduler
        import os
        import sys

        should_start = False

        if 'runserver' in sys.argv:
            should_start = True
        elif len(sys.argv) > 0 and ('gunicorn' in sys.argv[0] or os.environ.get('RAILWAY_ENVIRONMENT')):
            worker_id = os.environ.get('GUNICORN_WORKER_ID', '1')
            should_start = worker_id == '1'

            if not should_start and not os.environ.get('GUNICORN_WORKER_ID'):
                lock_file = '/tmp/mora_scheduler.lock'
                try:
                    if not os.path.exists(lock_file):
                        with open(lock_file, 'w') as f:
                            f.write(str(os.getpid()))
                        should_start = True
                except Exception:
                    pass

        if should_start:
            try:
                start_scheduler()
                logger.info(f"Scheduler de mora alerts iniciado (PID: {os.getpid()})")
            except Exception as e:
                logger.error(f"Error iniciando scheduler de mora: {str(e)}", exc_info=True)
        else:
            logger.info(f"Scheduler de mora alerts no iniciado en este worker (PID: {os.getpid()})")
