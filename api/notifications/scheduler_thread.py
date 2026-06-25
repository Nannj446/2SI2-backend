"""
Thread de background para ejecutar alertas de mora automáticamente.

Este módulo inicia un thread en background cuando Django arranca,
que verifica y envía alertas de mora cada día a las 8:00 AM.

No requiere configuración externa (cron, Celery, etc).
"""
import threading
import time
import logging
from datetime import time as datetime_time
from django.conf import settings

logger = logging.getLogger(__name__)

_scheduler_thread = None
_scheduler_running = False


class MoraAlertSchedulerThread(threading.Thread):
    """
    Thread que ejecuta alertas de mora en background.

    Se ejecuta diariamente a la hora configurada (default: 8:00 AM).
    """

    def __init__(self):
        super().__init__(daemon=True, name='MoraAlertSchedulerThread')
        self.stop_event = threading.Event()
        logger.info("MoraAlertSchedulerThread inicializado")

    def run(self):
        """Ejecuta el loop principal del scheduler."""
        global _scheduler_running
        _scheduler_running = True

        check_interval = getattr(settings, 'MORA_SCHEDULER_CHECK_INTERVAL', 60)
        default_hour = getattr(settings, 'MORA_SCHEDULER_DEFAULT_HOUR', 8)
        default_minute = getattr(settings, 'MORA_SCHEDULER_DEFAULT_MINUTE', 0)

        logger.info(
            f"MoraAlertSchedulerThread iniciado - "
            f"verificando a las {default_hour:02d}:{default_minute:02d} "
            f"cada {check_interval} segundos"
        )

        time.sleep(10)

        last_run_date = None

        while not self.stop_event.is_set():
            try:
                from datetime import datetime
                now = datetime.now()

                should_run_today = (
                    last_run_date is None or
                    last_run_date.date() < now.date()
                )

                is_time = (
                    now.hour == default_hour and
                    now.minute < check_interval // 60 + 1
                )

                if should_run_today and is_time:
                    self._send_mora_alerts()
                    last_run_date = now

            except Exception as e:
                logger.error(f"Error en MoraAlertSchedulerThread: {str(e)}", exc_info=True)

            self.stop_event.wait(check_interval)

        _scheduler_running = False
        logger.info("MoraAlertSchedulerThread detenido")

    def _send_mora_alerts(self):
        """Envía alertas de mora a todos los tenants."""
        try:
            from .services import MoraAlertService

            minimum_days = getattr(settings, 'MORA_ALERT_MINIMUM_DAYS', 1)

            service = MoraAlertService()
            result = service.send_all_mora_alerts(minimum_overdue_days=minimum_days)

            logger.info(
                f"Mora alerts sent: {result['total_sent']} "
                f"to {result['total_clients']} clients "
                f"across {result['total_institutions']} institutions"
            )

        except Exception as e:
            logger.error(f"Error enviando mora alerts: {str(e)}", exc_info=True)


def start_scheduler():
    """
    Inicia el thread del scheduler si no está corriendo.

    Esta función es llamada automáticamente cuando Django arranca.
    """
    global _scheduler_thread, _scheduler_running

    if getattr(settings, 'TESTING', False):
        logger.info("Modo testing detectado - MoraAlertSchedulerThread no iniciado")
        return

    if _scheduler_running:
        logger.debug("MoraAlertSchedulerThread ya está corriendo")
        return

    if not getattr(settings, 'ENABLE_MORA_SCHEDULER', True):
        logger.info("MoraAlertSchedulerThread deshabilitado en settings")
        return

    try:
        _scheduler_thread = MoraAlertSchedulerThread()
        _scheduler_thread.start()
        logger.info("MoraAlertSchedulerThread iniciado exitosamente")
    except Exception as e:
        logger.error(f"Error iniciando MoraAlertSchedulerThread: {str(e)}", exc_info=True)


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
        logger.info("MoraAlertSchedulerThread detenido exitosamente")


def is_scheduler_running():
    """Verifica si el scheduler está corriendo."""
    return _scheduler_running
