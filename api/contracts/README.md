# Módulo de Contratos de Crédito

Este módulo gestiona la generación, firma y ciclo de vida de contratos de crédito formales vinculados a solicitudes aprobadas.

## Características

- ✅ Generación automática de contratos desde solicitudes aprobadas
- ✅ Plantillas HTML personalizables con variables dinámicas
- ✅ Generación de PDFs con WeasyPrint
- ✅ Firma digital de contratos (prestatario, garantes, institución)
- ✅ Tabla de amortización automática (sistema francés)
- ✅ Gestión del ciclo de vida del contrato
- ✅ Auditoría completa de firmas y cambios
- ✅ Multi-tenancy (aislamiento por institución)

## Modelos

### Contract
Contrato de crédito principal con términos financieros, fechas y estado.

**Estados:**
- `DRAFT`: Borrador (recién generado)
- `PENDING_SIGNATURE`: Pendiente de firma
- `PARTIALLY_SIGNED`: Parcialmente firmado
- `ACTIVE`: Activo (todas las firmas completas)
- `CANCELLED`: Cancelado
- `COMPLETED`: Completado (pagado totalmente)
- `DEFAULTED`: En mora

### ContractTemplate
Plantilla HTML personalizable para generar contratos.

**Características:**
- Plantillas por producto o por defecto
- Variables dinámicas ({{variable}})
- Términos y condiciones configurables
- Versionado

### ContractSignature
Registro de firmas digitales con auditoría completa.

**Tipos de firmantes:**
- `BORROWER`: Prestatario
- `GUARANTOR`: Garante
- `INSTITUTION`: Institución financiera

### ContractAmortizationSchedule
Tabla de amortización con detalle de cada cuota.

**Información por cuota:**
- Capital
- Interés
- Cuota total
- Saldo pendiente
- Estado de pago

### ContractDocument
Documentos adicionales adjuntos al contrato (anexos, addendums, etc.)

## API Endpoints

### Contratos

```
GET    /api/contracts/                          # Listar contratos
POST   /api/contracts/generate-from-application/ # Generar contrato
GET    /api/contracts/{id}/                     # Ver detalle
POST   /api/contracts/{id}/publish/             # Publicar contrato
POST   /api/contracts/{id}/sign/                # Firmar contrato
GET    /api/contracts/{id}/pdf/                 # Descargar PDF
GET    /api/contracts/{id}/preview/             # Vista previa HTML
POST   /api/contracts/{id}/cancel/              # Cancelar contrato
GET    /api/contracts/{id}/signature-status/    # Estado de firmas
GET    /api/contracts/{id}/payment-summary/     # Resumen de pagos
```

### Plantillas

```
GET    /api/contract-templates/           # Listar plantillas
POST   /api/contract-templates/           # Crear plantilla
GET    /api/contract-templates/{id}/      # Ver detalle
PATCH  /api/contract-templates/{id}/      # Actualizar plantilla
DELETE /api/contract-templates/{id}/      # Eliminar plantilla
GET    /api/contract-templates/{id}/preview/ # Vista previa
```

### Tabla de Amortización

```
GET    /api/contract-amortization/?contract_id={id}  # Ver tabla de amortización
```

## Uso

### 1. Crear Plantilla por Defecto

```bash
python manage.py create_default_contract_template --institution-id=1
```

### 2. Generar Contrato

```python
from api.contracts.services import ContractGeneratorService, AmortizationService, PDFGeneratorService

# Generar contrato
contract = ContractGeneratorService.generate_contract(
    loan_application=loan_application,
    generated_by=user
)

# Generar tabla de amortización
AmortizationService.generate_amortization_schedule(contract)

# Generar PDF
PDFGeneratorService.generate_and_save_contract_pdf(contract)

# Publicar contrato
ContractGeneratorService.publish_contract(contract, published_by=user)
```

### 3. Firmar Contrato

```python
from api.contracts.services import SignatureService

# Firma del prestatario
signature = SignatureService.sign_contract_as_borrower(
    contract=contract,
    user=borrower_user,
    signature_data="hash_or_signature",
    ip_address="192.168.1.1",
    device_info={"user_agent": "..."}
)

# Firma de garante
signature = SignatureService.sign_contract_as_guarantor(
    contract=contract,
    guarantor=guarantor,
    signature_data="hash_or_signature",
    ip_address="192.168.1.2"
)
```

### 4. Consultar Estado de Pagos

```python
from api.contracts.services import AmortizationService

# Resumen de pagos
summary = AmortizationService.get_payment_summary(contract)

# Siguiente cuota pendiente
next_payment = AmortizationService.get_next_payment_due(contract)

# Cuotas vencidas
overdue = AmortizationService.get_overdue_payments(contract)
```

## Servicios

### ContractGeneratorService
Generación y gestión de contratos.

**Métodos principales:**
- `generate_contract()`: Genera contrato desde solicitud
- `publish_contract()`: Publica contrato para firma
- `cancel_contract()`: Cancela contrato
- `get_contract_variables()`: Obtiene variables para plantilla

### PDFGeneratorService
Generación de PDFs desde plantillas HTML.

**Métodos principales:**
- `generate_contract_pdf()`: Genera PDF del contrato
- `save_contract_pdf()`: Guarda PDF en storage
- `generate_and_save_contract_pdf()`: Genera y guarda en un paso
- `preview_contract_html()`: Vista previa HTML

### SignatureService
Gestión de firmas digitales.

**Métodos principales:**
- `sign_contract_as_borrower()`: Firma como prestatario
- `sign_contract_as_guarantor()`: Firma como garante
- `sign_contract_as_institution()`: Firma como institución
- `get_signature_status()`: Estado de firmas del contrato

### AmortizationService
Cálculo y gestión de tablas de amortización.

**Métodos principales:**
- `generate_amortization_schedule()`: Genera tabla de amortización
- `mark_payment_as_paid()`: Marca cuota como pagada
- `get_payment_summary()`: Resumen de pagos
- `calculate_early_payoff_amount()`: Calcula pago anticipado

## Permisos

- `CanViewContract`: Ver contratos (staff, prestatario, garantes)
- `CanGenerateContract`: Generar contratos (staff)
- `CanManageContractTemplates`: Gestionar plantillas (admin)
- `CanSignContract`: Firmar contratos (prestatario, garantes, staff)
- `CanCancelContract`: Cancelar contratos (admin)
- `CanPublishContract`: Publicar contratos (staff)
- `CanDownloadContractPDF`: Descargar PDF (staff, prestatario, garantes)

## Variables de Plantilla

Las plantillas HTML pueden usar las siguientes variables:

**Institución:**
- `{{institution_name}}`
- `{{institution_address}}`
- `{{institution_nit}}`
- `{{institution_phone}}`
- `{{institution_email}}`

**Prestatario:**
- `{{borrower_name}}`
- `{{borrower_document}}`
- `{{borrower_address}}`
- `{{borrower_email}}`
- `{{borrower_phone}}`

**Contrato:**
- `{{contract_number}}`
- `{{contract_date}}`
- `{{start_date}}`
- `{{end_date}}`

**Términos Financieros:**
- `{{principal_amount}}` (formateado: "Bs. 50,000.00")
- `{{principal_amount_raw}}` (sin formato: "50000.00")
- `{{interest_rate}}` (formateado: "12.5%")
- `{{interest_rate_raw}}` (sin formato: "12.5")
- `{{term_months}}`
- `{{monthly_payment}}`
- `{{total_amount}}`

**Fechas de Pago:**
- `{{first_payment_date}}`
- `{{last_payment_date}}`

**Producto:**
- `{{product_name}}`
- `{{product_description}}`

## Dependencias

```
weasyprint>=60.1        # Generación de PDFs
python-dateutil>=2.8.2  # Cálculo de fechas
```

## Integración con Otros Módulos

### Loans (Solicitudes)
- Contrato se genera desde `LoanApplication` en estado `APPROVED`
- Campo `contract_generated` indica si tiene contrato

### Garantías
- Garantes pueden firmar contratos
- Plantilla puede requerir firmas de garantes

### Storage
- PDFs se almacenan en Supabase Storage
- URLs firmadas para descarga segura

### Audit
- Todas las acciones se auditan automáticamente
- Registro completo de firmas y cambios

## Testing

```bash
# Ejecutar tests del módulo
python manage.py test api.contracts

# Ejecutar test específico
python manage.py test api.contracts.tests.test_models.ContractModelTest
```

## Notas de Implementación

1. **Firma Digital Simple**: La implementación actual usa firma digital simple (hash + validación de identidad). Para firma digital avanzada, integrar con DocuSign o Adobe Sign.

2. **Generación de PDF**: Usa WeasyPrint que requiere dependencias del sistema (Cairo, Pango). Ver documentación de WeasyPrint para instalación.

3. **Tabla de Amortización**: Usa sistema francés (cuota fija). Para otros sistemas (alemán, americano), extender `AmortizationService`.

4. **Multi-tenancy**: Todos los modelos heredan de `TenantModel` para aislamiento automático por institución.

5. **Auditoría**: Los signals automáticos registran cambios. No es necesario llamar manualmente al sistema de auditoría.

## Roadmap

- [ ] Integración con DocuSign/Adobe Sign
- [ ] Firma biométrica
- [ ] Renovación/refinanciamiento de contratos
- [ ] Plantillas con editor visual
- [ ] Notificaciones automáticas de firma
- [ ] Integración con módulo de pagos
- [ ] Reportes de contratos
- [ ] Exportación masiva de contratos

## Soporte

Para preguntas o problemas, contactar al equipo de desarrollo.
