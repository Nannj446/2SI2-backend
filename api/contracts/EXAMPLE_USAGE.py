"""
Ejemplos de uso del módulo de contratos

Este archivo muestra cómo usar el módulo de contratos en diferentes escenarios.
"""

# ============================================================
# EJEMPLO 1: Generar un contrato desde una solicitud aprobada
# ============================================================

from api.contracts.services import (
    ContractGeneratorService,
    AmortizationService,
    PDFGeneratorService
)
from api.loans.models import LoanApplication

# Obtener solicitud aprobada
loan_application = LoanApplication.objects.get(id=123)

# Generar contrato
contract = ContractGeneratorService.generate_contract(
    loan_application=loan_application,
    generated_by=request.user  # Usuario que genera
)

# Generar tabla de amortización
schedule = AmortizationService.generate_amortization_schedule(contract)

# Generar PDF
pdf_file = PDFGeneratorService.generate_and_save_contract_pdf(contract)

print(f"Contrato generado: {contract.contract_number}")
print(f"PDF guardado: {pdf_file.file_name}")
print(f"Cuotas generadas: {len(schedule)}")


# ============================================================
# EJEMPLO 2: Publicar un contrato para firma
# ============================================================

# Publicar contrato (cambia de DRAFT a PENDING_SIGNATURE)
ContractGeneratorService.publish_contract(
    contract=contract,
    published_by=request.user
)

print(f"Contrato publicado. Estado: {contract.status}")


# ============================================================
# EJEMPLO 3: Firmar un contrato como prestatario
# ============================================================

from api.contracts.services import SignatureService

# Firma del prestatario
signature = SignatureService.sign_contract_as_borrower(
    contract=contract,
    user=borrower_user,
    signature_data="hash_de_la_firma_o_datos_biometricos",
    ip_address="192.168.1.100",
    signature_method="DIGITAL",
    device_info={
        "user_agent": "Mozilla/5.0...",
        "platform": "Windows",
        "browser": "Chrome"
    },
    geolocation={
        "latitude": -16.5000,
        "longitude": -68.1500,
        "city": "La Paz"
    },
    verification_method="2FA"
)

print(f"Contrato firmado por: {signature.get_signer_name()}")
print(f"Estado del contrato: {contract.status}")


# ============================================================
# EJEMPLO 4: Firmar como garante
# ============================================================

from api.garantias.models import Guarantor

# Obtener garante
guarantor = Guarantor.objects.get(id=456)

# Firma del garante
signature = SignatureService.sign_contract_as_guarantor(
    contract=contract,
    guarantor=guarantor,
    signature_data="hash_de_firma_garante",
    ip_address="192.168.1.101",
    device_info={"user_agent": "..."}
)

print(f"Garante firmó: {guarantor.full_name}")


# ============================================================
# EJEMPLO 5: Verificar estado de firmas
# ============================================================

status = SignatureService.get_signature_status(contract)

print(f"Prestatario firmó: {status['borrower_signed']}")
print(f"Garantes requeridos: {status['guarantors_required']}")
print(f"Garantes que firmaron: {status['guarantors_signed']}")
print(f"Todas las firmas completas: {status['all_signatures_complete']}")
print(f"Firmas pendientes: {status['pending_signatures']}")


# ============================================================
# EJEMPLO 6: Consultar tabla de amortización
# ============================================================

# Resumen de pagos
summary = AmortizationService.get_payment_summary(contract)

print(f"Total de cuotas: {summary['total_payments']}")
print(f"Cuotas pagadas: {summary['paid_payments']}")
print(f"Cuotas pendientes: {summary['pending_payments']}")
print(f"Cuotas vencidas: {summary['overdue_payments']}")
print(f"Total pagado: Bs. {summary['total_paid']}")
print(f"Total pendiente: Bs. {summary['total_pending']}")
print(f"Progreso: {summary['completion_percentage']:.2f}%")

# Siguiente cuota
next_payment = AmortizationService.get_next_payment_due(contract)
if next_payment:
    print(f"\nSiguiente pago:")
    print(f"  Cuota #{next_payment.payment_number}")
    print(f"  Fecha: {next_payment.due_date}")
    print(f"  Monto: Bs. {next_payment.total_payment}")

# Cuotas vencidas
overdue = AmortizationService.get_overdue_payments(contract)
if overdue.exists():
    print(f"\nCuotas vencidas: {overdue.count()}")
    for payment in overdue:
        print(f"  Cuota #{payment.payment_number} - {payment.days_overdue} días")


# ============================================================
# EJEMPLO 7: Marcar una cuota como pagada
# ============================================================

from decimal import Decimal

# Obtener cuota
payment = contract.amortization_schedule.get(payment_number=1)

# Marcar como pagada
AmortizationService.mark_payment_as_paid(
    schedule_item=payment,
    paid_amount=Decimal('2356.78'),
    payment_reference='PAY-2026-001',
    notes='Pago realizado por transferencia bancaria'
)

print(f"Cuota #{payment.payment_number} marcada como pagada")


# ============================================================
# EJEMPLO 8: Calcular pago anticipado
# ============================================================

payoff = AmortizationService.calculate_early_payoff_amount(contract)

print(f"\nPago anticipado:")
print(f"  Monto a pagar: Bs. {payoff['payoff_amount']}")
print(f"  Capital pendiente: Bs. {payoff['remaining_principal']}")
print(f"  Intereses pendientes: Bs. {payoff['remaining_interest']}")
print(f"  Ahorro en intereses: Bs. {payoff['savings']}")
print(f"  Cuotas pendientes: {payoff['pending_payments']}")


# ============================================================
# EJEMPLO 9: Cancelar un contrato
# ============================================================

ContractGeneratorService.cancel_contract(
    contract=contract,
    cancellation_reason="Cliente solicitó cancelación antes del desembolso",
    cancelled_by=request.user
)

print(f"Contrato cancelado: {contract.contract_number}")


# ============================================================
# EJEMPLO 10: Crear plantilla personalizada
# ============================================================

from api.contracts.models import ContractTemplate

template = ContractTemplate.objects.create(
    institution=institution,
    name='Plantilla para Crédito Hipotecario',
    code='MORTGAGE_TEMPLATE',
    product=mortgage_product,  # Producto específico
    template_content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Contrato Hipotecario</title>
    </head>
    <body>
        <h1>CONTRATO DE CRÉDITO HIPOTECARIO</h1>
        <p>Contrato No. {{contract_number}}</p>
        
        <h2>Prestatario</h2>
        <p>{{borrower_name}} - {{borrower_document}}</p>
        
        <h2>Términos</h2>
        <p>Monto: {{principal_amount}}</p>
        <p>Tasa: {{interest_rate}}</p>
        <p>Plazo: {{term_months}} meses</p>
        
        <!-- Más contenido HTML -->
    </body>
    </html>
    """,
    is_active=True,
    is_default=False,
    requires_guarantor_signature=True,  # Requiere garantes
    terms_and_conditions="Términos específicos para hipotecas...",
    legal_clauses=[
        {
            "title": "Garantía Hipotecaria",
            "content": "El inmueble queda en garantía..."
        }
    ]
)

print(f"Plantilla creada: {template.name}")


# ============================================================
# EJEMPLO 11: Vista previa de contrato
# ============================================================

# Vista previa HTML (para mostrar en navegador)
html_preview = PDFGeneratorService.preview_contract_html(contract)

# Guardar en archivo temporal para ver
with open('preview.html', 'w', encoding='utf-8') as f:
    f.write(html_preview)

print("Vista previa guardada en preview.html")


# ============================================================
# EJEMPLO 12: Obtener variables de un contrato
# ============================================================

variables = ContractGeneratorService.get_contract_variables(contract)

print("\nVariables disponibles:")
for key, value in variables.items():
    print(f"  {key}: {value}")


# ============================================================
# EJEMPLO 13: Uso desde API REST
# ============================================================

"""
# Generar contrato (POST)
POST /api/contracts/generate-from-application/
{
    "loan_application_id": 123,
    "template_id": 1,  // opcional
    "contract_date": "2026-05-30",  // opcional
    "start_date": "2026-06-05",  // opcional
    "special_clauses": {
        "clause_1": "Cláusula especial..."
    },
    "notes": "Notas internas"
}

# Publicar contrato (POST)
POST /api/contracts/{id}/publish/

# Firmar contrato (POST)
POST /api/contracts/{id}/sign/
{
    "signature_method": "DIGITAL",
    "signature_data": "hash_o_datos_de_firma",
    "device_info": {
        "user_agent": "...",
        "platform": "Windows"
    },
    "geolocation": {
        "latitude": -16.5,
        "longitude": -68.15
    },
    "verification_method": "2FA"
}

# Descargar PDF (GET)
GET /api/contracts/{id}/pdf/

# Ver estado de firmas (GET)
GET /api/contracts/{id}/signature-status/

# Ver resumen de pagos (GET)
GET /api/contracts/{id}/payment-summary/

# Cancelar contrato (POST)
POST /api/contracts/{id}/cancel/
{
    "cancellation_reason": "Motivo de cancelación"
}
"""


# ============================================================
# EJEMPLO 14: Crear plantilla por defecto con comando
# ============================================================

"""
# Desde terminal:
python manage.py create_default_contract_template --institution-id=1

# Con sobrescritura:
python manage.py create_default_contract_template --institution-id=1 --force
"""


# ============================================================
# EJEMPLO 15: Filtrar contratos por estado
# ============================================================

from api.contracts.models import Contract

# Contratos activos
active_contracts = Contract.objects.filter(
    institution=institution,
    status=Contract.Status.ACTIVE
)

# Contratos pendientes de firma
pending_signature = Contract.objects.filter(
    institution=institution,
    status__in=[
        Contract.Status.PENDING_SIGNATURE,
        Contract.Status.PARTIALLY_SIGNED
    ]
)

# Contratos del mes actual
from django.utils import timezone
current_month = Contract.objects.filter(
    institution=institution,
    contract_date__year=timezone.now().year,
    contract_date__month=timezone.now().month
)

print(f"Contratos activos: {active_contracts.count()}")
print(f"Pendientes de firma: {pending_signature.count()}")
print(f"Contratos este mes: {current_month.count()}")
