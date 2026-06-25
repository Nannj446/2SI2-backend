"""
Thread de background para ejecutar backups programados automáticamente.

Este módulo inicia un thread en background cuando Django arranca,
que verifica y ejecuta backups programados cada minuto.

No requiere configuración externa (cron, Celery, etc).
"""
import threading
import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Variable global para controlar el thread
_scheduler_thread = None
_scheduler_running = False


class BackupSchedulerThread(threading.Thread):
    """
    Thread que ejecuta backups programados en background.
    
    Se ejecuta cada minuto verificando si hay backups pendientes.
    """
    
    def __init__(self):
        super().__init__(daemon=True, name='BackupSchedulerThread')
        self.stop_event = threading.Event()
        logger.info("BackupSchedulerThread inicializado")
    
    def run(self):
        """Ejecuta el loop principal del scheduler."""
        global _scheduler_running
        _scheduler_running = True
        
        # Obtener intervalo de configuración
        interval = getattr(settings, 'BACKUP_SCHEDULER_INTERVAL', 60)
        
        logger.info(f"BackupSchedulerThread iniciado - verificando backups cada {interval} segundos")
        
        # Esperar 30 segundos antes de la primera ejecución
        # para dar tiempo a que Django termine de inicializar
        time.sleep(30)
        
        while not self.stop_event.is_set():
            try:
                self._check_and_run_backups()
            except Exception as e:
                logger.error(f"Error en BackupSchedulerThread: {str(e)}", exc_info=True)
            
            # Esperar el intervalo configurado antes de la próxima verificación
            # Usar wait() en lugar de sleep() para poder interrumpir el thread
            self.stop_event.wait(interval)
        
        _scheduler_running = False
        logger.info("BackupSchedulerThread detenido")
    
    def _check_and_run_backups(self):
        """Verifica y ejecuta backups pendientes."""
        try:
            from api.backups.services.scheduler_service import BackupSchedulerService
            
            scheduler_service = BackupSchedulerService()
            results = scheduler_service.run_pending_backups()
            
            if results['executed'] > 0:
                logger.info(
                    f"Backups ejecutados: {results['executed']} "
                    f"(exitosos: {results['successful']}, fallidos: {results['failed']})"
                )
        except Exception as e:
            logger.error(f"Error ejecutando backups programados: {str(e)}", exc_info=True)
    
    def stop(self):
        """Detiene el thread de forma segura."""
        logger.info("Deteniendo BackupSchedulerThread...")
        self.stop_event.set()


def start_scheduler():
    """
    Inicia el thread del scheduler si no está corriendo.
    
    Esta función es llamada automáticamente cuando Django arranca.
    """
    global _scheduler_thread, _scheduler_running
    
    # No iniciar en modo de testing
    if getattr(settings, 'TESTING', False):
        logger.info("Modo testing detectado - BackupSchedulerThread no iniciado")
        return
    
    # No iniciar si ya está corriendo
    if _scheduler_running:
        logger.debug("BackupSchedulerThread ya está corriendo")
        return
    
    # No iniciar si está deshabilitado en settings
    if not getattr(settings, 'ENABLE_BACKUP_SCHEDULER', True):
        logger.info("BackupSchedulerThread deshabilitado en settings")
        return
    
    try:
        _scheduler_thread = BackupSchedulerThread()
        _scheduler_thread.start()
        logger.info("BackupSchedulerThread iniciado exitosamente")
    except Exception as e:
        logger.error(f"Error iniciando BackupSchedulerThread: {str(e)}", exc_info=True)


def stop_scheduler():
    """
    Detiene el thread del scheduler si está corriendo.
    
    Esta función es llamada automáticamente cuando Django se apaga.
    """
    global _scheduler_thread, _scheduler_running
    
    if _scheduler_thread and _scheduler_running:
        _scheduler_thread.stop()
        _scheduler_thread.join(timeout=5)
        _scheduler_thread = None
        logger.info("BackupSchedulerThread detenido exitosamente")


def is_scheduler_running():
    """Verifica si el scheduler está corriendo."""
    return _scheduler_running
