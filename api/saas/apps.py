from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class SaaSConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.saas'
    verbose_name = 'SaaS Management'
    
    def ready(self):
        """
        Se ejecuta cuando Django termina de inicializar.
        Inicia el thread de background para procesar cambios de suscripción pendientes.
        """
        from api.saas.scheduler_thread import start_scheduler
        import os
        import sys
        
        should_start = False
        
        if 'runserver' in sys.argv:
            should_start = True
        elif len(sys.argv) > 0 and ('gunicorn' in sys.argv[0] or os.environ.get('RAILWAY_ENVIRONMENT')):
            # En producción con gunicorn o Railway, solo arrancar en el primer worker
            worker_id = os.environ.get('GUNICORN_WORKER_ID', '1')
            should_start = worker_id == '1'
            
        if should_start:
            try:
                start_scheduler()
                logger.info(f"SaaS subscription scheduler thread started (PID: {os.getpid()})")
            except Exception as e:
                logger.error(f"Error starting SaaS scheduler: {str(e)}", exc_info=True)
