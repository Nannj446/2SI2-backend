"""
Thread de background para aplicar cambios de suscripción pendientes automáticamente.
"""
import threading
import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Variable global para controlar el thread
_scheduler_thread = None
_scheduler_running = False


class SaaSSubscriptionSchedulerThread(threading.Thread):
    """
    Thread que aplica downgrades y cancelaciones pendientes.
    Verifica periódicamente (cada 5 minutos por defecto).
    """
    
    def __init__(self):
        super().__init__(daemon=True, name='SaaSSubscriptionSchedulerThread')
        self.stop_event = threading.Event()
        logger.info("SaaSSubscriptionSchedulerThread inicializado")
    
    def run(self):
        global _scheduler_running
        _scheduler_running = True
        
        interval = getattr(settings, 'SAAS_SCHEDULER_INTERVAL', 300) # 5 minutos
        logger.info(f"SaaSSubscriptionSchedulerThread iniciado - verificando cada {interval} segundos")
        
        # Esperar 45 segundos para que Django termine de cargar
        time.sleep(45)
        
        while not self.stop_event.is_set():
            try:
                self._apply_pending_changes()
            except Exception as e:
                logger.error(f"Error en SaaSSubscriptionSchedulerThread: {str(e)}", exc_info=True)
            
            self.stop_event.wait(interval)
        
        _scheduler_running = False
        logger.info("SaaSSubscriptionSchedulerThread detenido")
    
    def _apply_pending_changes(self):
        try:
            from api.saas.services import StripeSubscriptionService
            
            stripe_service = StripeSubscriptionService()
            results = stripe_service.apply_pending_changes()
            
            if results['total_processed'] > 0:
                logger.info(
                    f"Cambios de suscripción procesados: {results['total_processed']} "
                    f"(downgrades: {results['downgrades_applied']}, cancelaciones: {results['cancellations_applied']})"
                )
        except Exception as e:
            logger.error(f"Error procesando cambios de suscripción pendientes: {str(e)}", exc_info=True)
    
    def stop(self):
        logger.info("Deteniendo SaaSSubscriptionSchedulerThread...")
        self.stop_event.set()


def start_scheduler():
    global _scheduler_thread, _scheduler_running
    
    if getattr(settings, 'TESTING', False):
        logger.info("Modo testing detectado - SaaSSubscriptionSchedulerThread no iniciado")
        return
        
    if _scheduler_running:
        logger.debug("SaaSSubscriptionSchedulerThread ya está corriendo")
        return
        
    _scheduler_thread = SaaSSubscriptionSchedulerThread()
    _scheduler_thread.start()
