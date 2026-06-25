"""
Configuración de la app backups.
"""
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class BackupsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.backups'
    verbose_name = 'Backups de Tenants'
    
    def ready(self):
        """
        Se ejecuta cuando Django termina de inicializar.
        
        Inicia el thread de background para backups programados.
        Solo se ejecuta en un worker para evitar duplicación.
        """
        # Importar aquí para evitar problemas de importación circular
        from api.backups.scheduler_thread import start_scheduler
        import os
        import sys
        
        # Solo iniciar en el proceso principal
        should_start = False
        
        if 'runserver' in sys.argv:
            # Desarrollo con runserver - siempre iniciar
            should_start = True
        elif len(sys.argv) > 0 and ('gunicorn' in sys.argv[0] or os.environ.get('RAILWAY_ENVIRONMENT')):
            # Producción con gunicorn o Railway
            # Usar variable de entorno para controlar qué worker ejecuta backups
            worker_id = os.environ.get('GUNICORN_WORKER_ID', '1')
            should_start = worker_id == '1'
            
            # Alternativa: usar el PID del proceso
            # Solo el primer proceso que se inicia ejecutará backups
            if not should_start and not os.environ.get('GUNICORN_WORKER_ID'):
                # Si no hay WORKER_ID definido, usar un archivo de lock
                lock_file = '/tmp/backup_scheduler.lock'
                try:
                    # Intentar crear el archivo de lock
                    if not os.path.exists(lock_file):
                        with open(lock_file, 'w') as f:
                            f.write(str(os.getpid()))
                        should_start = True
                except Exception:
                    pass
        
        if should_start:
            try:
                start_scheduler()
                logger.info(f"Scheduler de backups automáticos iniciado (PID: {os.getpid()})")
            except Exception as e:
                logger.error(f"Error iniciando scheduler de backups: {str(e)}", exc_info=True)
        else:
            logger.info(f"Scheduler de backups no iniciado en este worker (PID: {os.getpid()})")
