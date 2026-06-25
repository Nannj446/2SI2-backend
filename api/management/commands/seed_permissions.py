"""
Comando para crear el catálogo completo de permisos del sistema.
"""

from django.core.management.base import BaseCommand
from api.models import Permission


class Command(BaseCommand):
    help = 'Crea el catálogo completo de permisos del sistema'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== CREANDO CATÁLOGO DE PERMISOS ===\n'))
        
        permissions_created = 0
        permissions_existing = 0
        
        # Definir catálogo completo de permisos
        permissions_catalog = self._get_permissions_catalog()
        
        for category, perms in permissions_catalog.items():
            self.stdout.write(f'\n📁 {category}')
            
            for perm_data in perms:
                permission, created = Permission.objects.get_or_create(
                    code=perm_data['code'],
                    defaults={
                        'name': perm_data['name'],
                        'description': perm_data['description']
                    }
                )
                
                if created:
                    permissions_created += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {perm_data["code"]} - {perm_data["name"]}'))
                else:
                    permissions_existing += 1
                    self.stdout.write(f'  - {perm_data["code"]} (ya existe)')
        
        self.stdout.write(self.style.SUCCESS(f'\n=== RESUMEN ==='))
        self.stdout.write(f'Permisos creados: {permissions_created}')
        self.stdout.write(f'Permisos existentes: {permissions_existing}')
        self.stdout.write(f'Total: {permissions_created + permissions_existing}\n')

    def _get_permissions_catalog(self):
        """
        Retorna el catálogo completo de permisos organizados por categoría.
        """
        return {
            'Usuarios': [
                {
                    'code': 'users.view',
                    'name': 'Ver Usuarios',
                    'description': 'Permite ver la lista de usuarios y sus detalles'
                },
                {
                    'code': 'users.create',
                    'name': 'Crear Usuarios',
                    'description': 'Permite crear nuevos usuarios en el sistema'
                },
                {
                    'code': 'users.edit',
                    'name': 'Editar Usuarios',
                    'description': 'Permite editar información de usuarios existentes'
                },
                {
                    'code': 'users.delete',
                    'name': 'Eliminar Usuarios',
                    'description': 'Permite desactivar o eliminar usuarios'
                },
                {
                    'code': 'users.assign_roles',
                    'name': 'Asignar Roles',
                    'description': 'Permite asignar y remover roles de usuarios'
                },
                {
                    'code': 'users.view_audit',
                    'name': 'Ver Auditoría de Usuarios',
                    'description': 'Permite ver el historial de acciones de usuarios'
                },
            ],
            
            'Roles y Permisos': [
                {
                    'code': 'roles.view',
                    'name': 'Ver Roles',
                    'description': 'Permite ver la lista de roles y sus detalles'
                },
                {
                    'code': 'roles.create',
                    'name': 'Crear Roles',
                    'description': 'Permite crear nuevos roles'
                },
                {
                    'code': 'roles.edit',
                    'name': 'Editar Roles',
                    'description': 'Permite editar roles existentes'
                },
                {
                    'code': 'roles.delete',
                    'name': 'Eliminar Roles',
                    'description': 'Permite eliminar roles'
                },
                {
                    'code': 'roles.assign_permissions',
                    'name': 'Asignar Permisos',
                    'description': 'Permite asignar permisos a roles'
                },
            ],
            
            'Institución': [
                {
                    'code': 'institution.view',
                    'name': 'Ver Institución',
                    'description': 'Permite ver información de la institución'
                },
                {
                    'code': 'institution.edit',
                    'name': 'Editar Institución',
                    'description': 'Permite editar configuración de la institución'
                },
                {
                    'code': 'institution.view_stats',
                    'name': 'Ver Estadísticas',
                    'description': 'Permite ver estadísticas de la institución'
                },
            ],
            
            'Créditos': [
                {
                    'code': 'credits.view',
                    'name': 'Ver Créditos',
                    'description': 'Permite ver la lista de créditos y sus detalles'
                },
                {
                    'code': 'credits.create',
                    'name': 'Crear Créditos',
                    'description': 'Permite crear nuevas solicitudes de crédito'
                },
                {
                    'code': 'credits.edit',
                    'name': 'Editar Créditos',
                    'description': 'Permite editar información de créditos'
                },
                {
                    'code': 'credits.delete',
                    'name': 'Eliminar Créditos',
                    'description': 'Permite eliminar créditos'
                },
                {
                    'code': 'credits.approve',
                    'name': 'Aprobar Créditos',
                    'description': 'Permite aprobar solicitudes de crédito'
                },
                {
                    'code': 'credits.reject',
                    'name': 'Rechazar Créditos',
                    'description': 'Permite rechazar solicitudes de crédito'
                },
                {
                    'code': 'credits.disburse',
                    'name': 'Desembolsar Créditos',
                    'description': 'Permite realizar desembolsos de créditos aprobados'
                },
                {
                    'code': 'credits.view_documents',
                    'name': 'Ver Documentos',
                    'description': 'Permite ver documentos adjuntos a créditos'
                },
                {
                    'code': 'credits.upload_documents',
                    'name': 'Subir Documentos',
                    'description': 'Permite subir documentos a créditos'
                },
            ],
            
            'Clientes/Prestatarios': [
                {
                    'code': 'borrowers.view',
                    'name': 'Ver Clientes',
                    'description': 'Permite ver la lista de clientes y sus detalles'
                },
                {
                    'code': 'borrowers.create',
                    'name': 'Crear Clientes',
                    'description': 'Permite registrar nuevos clientes'
                },
                {
                    'code': 'borrowers.edit',
                    'name': 'Editar Clientes',
                    'description': 'Permite editar información de clientes'
                },
                {
                    'code': 'borrowers.delete',
                    'name': 'Eliminar Clientes',
                    'description': 'Permite eliminar clientes'
                },
                {
                    'code': 'borrowers.view_history',
                    'name': 'Ver Historial',
                    'description': 'Permite ver historial crediticio de clientes'
                },
                {
                    'code': 'borrowers.view_documents',
                    'name': 'Ver Documentos de Clientes',
                    'description': 'Permite ver documentos de identificación y otros'
                },
            ],
            
            'Cobranza': [
                {
                    'code': 'collection.view',
                    'name': 'Ver Cobranza',
                    'description': 'Permite ver información de cobranza'
                },
                {
                    'code': 'collection.create_payment',
                    'name': 'Registrar Pagos',
                    'description': 'Permite registrar pagos de clientes'
                },
                {
                    'code': 'collection.send_reminders',
                    'name': 'Enviar Recordatorios',
                    'description': 'Permite enviar recordatorios de pago'
                },
                {
                    'code': 'collection.manage_overdue',
                    'name': 'Gestionar Mora',
                    'description': 'Permite gestionar créditos en mora'
                },
                {
                    'code': 'collection.restructure',
                    'name': 'Reestructurar Créditos',
                    'description': 'Permite reestructurar créditos en mora'
                },
                {
                    'code': 'collection.write_off',
                    'name': 'Castigar Créditos',
                    'description': 'Permite castigar créditos incobrables'
                },
            ],
            
            'Garantías y Garantes': [
                {
                    'code': 'collaterals.view',
                    'name': 'Ver Garantías',
                    'description': 'Permite ver la lista de garantías y sus detalles'
                },
                {
                    'code': 'collaterals.create',
                    'name': 'Crear Garantías',
                    'description': 'Permite registrar nuevas garantías'
                },
                {
                    'code': 'collaterals.edit',
                    'name': 'Editar Garantías',
                    'description': 'Permite modificar garantías existentes'
                },
                {
                    'code': 'collaterals.delete',
                    'name': 'Eliminar Garantías',
                    'description': 'Permite eliminar o desactivar garantías'
                },
                {
                    'code': 'collaterals.approve',
                    'name': 'Aprobar Garantías',
                    'description': 'Permite aprobar, rechazar o liberar garantías, y verificar documentos'
                },
                {
                    'code': 'collaterals.manage_valuations',
                    'name': 'Gestionar Valuaciones',
                    'description': 'Permite registrar y aprobar valuaciones de garantías'
                },
                {
                    'code': 'guarantors.view',
                    'name': 'Ver Garantes',
                    'description': 'Permite ver la lista de garantes y sus detalles'
                },
                {
                    'code': 'guarantors.create',
                    'name': 'Crear Garantes',
                    'description': 'Permite registrar nuevos garantes'
                },
                {
                    'code': 'guarantors.edit',
                    'name': 'Editar Garantes',
                    'description': 'Permite modificar o eliminar garantes existentes'
                },
                {
                    'code': 'guarantors.approve',
                    'name': 'Aprobar Garantes',
                    'description': 'Permite aprobar o rechazar garantes'
                },
            ],
            
            'Reportes': [
                {
                    'code': 'reports.view',
                    'name': 'Ver Reportes',
                    'description': 'Permite ver reportes del sistema'
                },
                {
                    'code': 'reports.create',
                    'name': 'Crear Reportes',
                    'description': 'Permite crear reportes personalizados'
                },
                {
                    'code': 'reports.export',
                    'name': 'Exportar Reportes',
                    'description': 'Permite exportar reportes a Excel/PDF'
                },
                {
                    'code': 'reports.financial',
                    'name': 'Reportes Financieros',
                    'description': 'Permite ver reportes financieros sensibles'
                },
                {
                    'code': 'reports.audit',
                    'name': 'Reportes de Auditoría',
                    'description': 'Permite ver reportes de auditoría del sistema'
                },
            ],
            
            'Configuración': [
                {
                    'code': 'config.view',
                    'name': 'Ver Configuración',
                    'description': 'Permite ver configuración del sistema'
                },
                {
                    'code': 'config.edit',
                    'name': 'Editar Configuración',
                    'description': 'Permite editar configuración del sistema'
                },
                {
                    'code': 'config.products',
                    'name': 'Gestionar Productos',
                    'description': 'Permite gestionar productos de crédito'
                },
                {
                    'code': 'config.interest_rates',
                    'name': 'Gestionar Tasas',
                    'description': 'Permite gestionar tasas de interés'
                },
            ],
            
            'Administración de Reglas (CU-09)': [
                {
                    'code': 'loans.manage_credit_rules',
                    'name': 'Can manage credit rules and parameters',
                    'description': 'Permite administrar reglas de crédito, parámetros de productos, reglas de elegibilidad y requisitos documentales'
                },
            ],
            
            'Gestión Documental (CU-12)': [
                {
                    'code': 'loans.review_loan_documents',
                    'name': 'Can review and approve loan documents',
                    'description': 'Permite revisar, aprobar y rechazar documentos de solicitudes de crédito'
                },
            ],
            
            'Contratos de Crédito': [
                {
                    'code': 'contracts.view',
                    'name': 'Ver Contratos',
                    'description': 'Permite ver contratos de crédito'
                },
                {
                    'code': 'contracts.generate',
                    'name': 'Generar Contratos',
                    'description': 'Permite generar contratos desde solicitudes aprobadas'
                },
                {
                    'code': 'contracts.publish',
                    'name': 'Publicar Contratos',
                    'description': 'Permite publicar contratos para firma'
                },
                {
                    'code': 'contracts.sign',
                    'name': 'Firmar Contratos',
                    'description': 'Permite firmar contratos digitalmente'
                },
                {
                    'code': 'contracts.cancel',
                    'name': 'Cancelar Contratos',
                    'description': 'Permite cancelar contratos'
                },
                {
                    'code': 'contracts.download',
                    'name': 'Descargar Contratos',
                    'description': 'Permite descargar PDFs de contratos'
                },
                {
                    'code': 'contracts.view_signatures',
                    'name': 'Ver Firmas',
                    'description': 'Permite ver estado y detalles de firmas'
                },
                {
                    'code': 'contracts.view_amortization',
                    'name': 'Ver Tabla de Amortización',
                    'description': 'Permite ver tabla de amortización de contratos'
                },
            ],
            
            'Plantillas de Contratos': [
                {
                    'code': 'contract_templates.view',
                    'name': 'Ver Plantillas',
                    'description': 'Permite ver plantillas de contratos'
                },
                {
                    'code': 'contract_templates.create',
                    'name': 'Crear Plantillas',
                    'description': 'Permite crear nuevas plantillas de contratos'
                },
                {
                    'code': 'contract_templates.edit',
                    'name': 'Editar Plantillas',
                    'description': 'Permite editar plantillas de contratos existentes'
                },
                {
                    'code': 'contract_templates.delete',
                    'name': 'Eliminar Plantillas',
                    'description': 'Permite eliminar plantillas de contratos'
                },
                {
                    'code': 'contract_templates.preview',
                    'name': 'Vista Previa de Plantillas',
                    'description': 'Permite ver vista previa de plantillas'
                },
            ],
            
            'Auditoría y Seguridad': [
                {
                    'code': 'audit.view',
                    'name': 'Ver Auditoría',
                    'description': 'Permite ver logs de auditoría'
                },
                {
                    'code': 'audit.export',
                    'name': 'Exportar Auditoría',
                    'description': 'Permite exportar logs de auditoría'
                },
                {
                    'code': 'security.view_events',
                    'name': 'Ver Eventos de Seguridad',
                    'description': 'Permite ver eventos de seguridad'
                },
                {
                    'code': 'security.resolve_events',
                    'name': 'Resolver Eventos',
                    'description': 'Permite marcar eventos de seguridad como resueltos'
                },
            ],
        }
