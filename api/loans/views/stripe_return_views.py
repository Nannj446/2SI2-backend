"""
Páginas HTML de retorno de Stripe Checkout para pagos móviles.

Cuando el pago se completa en Stripe desde el navegador externo de la app,
el usuario ve esta página. Debe presionar el botón atrás del navegador
para volver a la app, donde el WidgetsBindingObserver detecta el regreso
y verifica el pago automáticamente.
"""
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def stripe_success(request):
    html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pago Exitoso</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f0fdf4; color: #166534; text-align: center; padding: 20px; }
  .card { background: white; border-radius: 20px; padding: 36px 28px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); max-width: 360px; width: 100%; }
  .check { width: 64px; height: 64px; background: #16a34a; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
  .check::after { content: '\\2713'; color: white; font-size: 36px; font-weight: bold; }
  h2 { font-size: 20px; margin-bottom: 8px; color: #166534; }
  p { font-size: 14px; color: #4b5563; margin-bottom: 12px; line-height: 1.5; }
  .hint { font-size: 13px; color: #9ca3af; background: #f9fafb; border-radius: 10px; padding: 12px; }
  .hint strong { color: #6b7280; }
</style>
</head>
<body>
<div class="card">
  <div class="check"></div>
  <h2>Pago completado</h2>
  <p>Tu pago fue procesado exitosamente.</p>
  <div class="hint">
    Presiona el <strong>boton atras</strong> del navegador para volver a la app y verificar el pago.
  </div>
</div>
</body>
</html>"""
    return HttpResponse(html, content_type='text/html; charset=utf-8')


@csrf_exempt
def stripe_cancel(request):
    html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pago Cancelado</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #fef2f2; color: #991b1b; text-align: center; padding: 20px; }
  .card { background: white; border-radius: 20px; padding: 36px 28px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); max-width: 360px; width: 100%; }
  .cross { width: 64px; height: 64px; background: #dc2626; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
  .cross::after { content: '\\2715'; color: white; font-size: 36px; font-weight: bold; }
  h2 { font-size: 20px; margin-bottom: 8px; color: #991b1b; }
  p { font-size: 14px; color: #4b5563; margin-bottom: 12px; line-height: 1.5; }
  .hint { font-size: 13px; color: #9ca3af; background: #f9fafb; border-radius: 10px; padding: 12px; }
  .hint strong { color: #6b7280; }
</style>
</head>
<body>
<div class="card">
  <div class="cross"></div>
  <h2>Pago cancelado</h2>
  <p>No se realizo ningun cobro.</p>
  <div class="hint">
    Presiona el <strong>boton atras</strong> del navegador para volver a la app e intentarlo de nuevo.
  </div>
</div>
</body>
</html>"""
    return HttpResponse(html, content_type='text/html; charset=utf-8')
