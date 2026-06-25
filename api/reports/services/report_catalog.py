"""
Catálogo de reportes disponibles.

Este servicio define todos los tipos de reportes disponibles en el sistema,
sus configuraciones, columnas, filtros, agrupaciones y ordenamientos permitidos.
"""
from typing import Dict, List, Optional, Any


class ReportCatalogService:
    """
    Servicio de catálogo de reportes.
    
    Proporciona acceso al catálogo completo de reportes disponibles,
    validación de tipos de reportes, y metadatos de configuración.
    """
    
    # Catálogo completo de reportes
    CATALOG = {
        'TENANT': {
            'CREDITS': {
                'loans_by_status': {
                    'name': 'Créditos por Estado',
                    'description': 'Créditos agrupados por estado',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST', 'OFFICER'],
                    'available_columns': [
                        # Identificación
                        'application_number', 'status', 'risk_level', 'credit_score',
                        # Cliente
                        'client_name', 'client_document', 'client_email', 'client_phone',
                        # Producto
                        'product_name', 'product_code', 'product_type',
                        # Montos y términos
                        'requested_amount', 'approved_amount', 'term_months', 
                        'approved_term_months', 'approved_interest_rate', 'monthly_payment',
                        # Información económica
                        'monthly_income', 'employment_type', 'debt_to_income_ratio',
                        # Sucursal y asignación
                        'branch_name', 'assigned_to_name', 'reviewed_by_name', 
                        'approved_by_name', 'created_by_name',
                        # Estados de verificación
                        'identity_verification_status', 'documents_status',
                        # Fechas
                        'created_at', 'submitted_at', 'reviewed_at', 'approved_at', 
                        'rejected_at', 'disbursed_at', 'updated_at',
                        # Propósito y notas
                        'purpose', 'notes', 'observation_reason', 'rejection_reason',
                        # Metadata
                        'is_active'
                    ],
                    'available_filters': {
                        # ===== FILTROS PERSONALIZADOS ESPECÍFICOS =====
                        # Producto crediticio
                        'product_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        # Sucursal
                        'branch_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        # Nivel de riesgo
                        'risk_level': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH']
                        },
                        # Monto solicitado (rango)
                        'requested_amount_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        },
                        'requested_amount_max': {
                            'operators': ['lte'],
                            'type': 'decimal'
                        },
                        # Monto aprobado (rango)
                        'approved_amount_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        },
                        'approved_amount_max': {
                            'operators': ['lte'],
                            'type': 'decimal'
                        },
                        # Puntaje de crédito (rango)
                        'credit_score_min': {
                            'operators': ['gte'],
                            'type': 'integer'
                        },
                        'credit_score_max': {
                            'operators': ['lte'],
                            'type': 'integer'
                        },
                        # Tipo de empleo
                        'employment_type': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['EMPLOYED', 'SELF_EMPLOYED', 'BUSINESS_OWNER', 
                                      'RETIRED', 'UNEMPLOYED', 'STUDENT', 'OTHER']
                        },
                        # Fecha de creación (rango)
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Fecha de envío (rango)
                        'submitted_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'submitted_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Fecha de aprobación (rango)
                        'approved_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'approved_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Asignado a
                        'assigned_to_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        # Solo activos
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        }
                    },
                    'available_groupings': [
                        'status', 'risk_level', 'branch_name', 'product_name',
                        'employment_type', 'identity_verification_status', 'documents_status',
                        'month', 'quarter', 'year'
                    ],
                    'available_sort_fields': [
                        'application_number', 'client_name', 'client_document',
                        'requested_amount', 'approved_amount', 'monthly_payment',
                        'credit_score', 'debt_to_income_ratio', 'monthly_income',
                        'created_at', 'submitted_at', 'reviewed_at', 'approved_at', 
                        'rejected_at', 'disbursed_at', 'updated_at',
                        'term_months', 'approved_term_months'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'loans_by_date_range': {
                    'name': 'Créditos por Rango de Fechas',
                    'description': 'Créditos por rango de fechas',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST'],
                    'available_columns': [
                        # Identificación
                        'application_number', 'status', 'risk_level', 'credit_score',
                        # Cliente
                        'client_name', 'client_document', 'client_email', 'client_phone',
                        # Producto
                        'product_name', 'product_code', 'product_type',
                        # Montos y términos
                        'requested_amount', 'approved_amount', 'term_months',
                        'approved_term_months', 'monthly_payment',
                        # Información económica
                        'monthly_income', 'employment_type',
                        # Sucursal
                        'branch_name', 'branch_city',
                        # Fechas
                        'created_at', 'submitted_at', 'reviewed_at', 'approved_at',
                        'rejected_at', 'disbursed_at'
                    ],
                    'available_filters': {
                        'date_field': {
                            'operators': ['equals'],
                            'type': 'choice',
                            'values': ['created_at', 'submitted_at', 'approved_at', 
                                      'reviewed_at', 'rejected_at', 'disbursed_at']
                        },
                        'date_range': {
                            'operators': ['between'],
                            'type': 'date',
                            'required': True
                        },
                        'status': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['DRAFT', 'SUBMITTED', 'IN_REVIEW', 'APPROVED',
                                      'REJECTED', 'DISBURSED', 'CANCELLED']
                        },
                        'risk_level': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH']
                        },
                        'employment_type': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['EMPLOYED', 'SELF_EMPLOYED', 'BUSINESS_OWNER', 
                                      'RETIRED', 'UNEMPLOYED', 'STUDENT', 'OTHER']
                        },
                        'branch_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'product_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        }
                    },
                    'available_groupings': [
                        'status', 'branch_name', 'product_name', 'risk_level',
                        'employment_type', 'day', 'week', 'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'created_at', 'submitted_at', 'reviewed_at', 'approved_at',
                        'rejected_at', 'disbursed_at', 'requested_amount', 
                        'approved_amount', 'client_name', 'client_document',
                        'application_number', 'credit_score', 'monthly_income'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'loans_by_branch': {
                    'name': 'Créditos por Sucursal',
                    'description': 'Créditos agrupados por sucursal',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'branch_name', 'branch_city', 'total_applications',
                        'approved_count', 'rejected_count', 'pending_count',
                        'total_requested_amount', 'total_approved_amount',
                        'avg_requested_amount', 'avg_approved_amount', 'approval_rate'
                    ],
                    'available_filters': {
                        # ===== FILTROS PERSONALIZADOS ESPECÍFICOS =====
                        # Sucursales específicas
                        'branch_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        # Estado de créditos
                        'status': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['DRAFT', 'SUBMITTED', 'IN_REVIEW', 'APPROVED',
                                      'REJECTED', 'DISBURSED']
                        },
                        # Productos
                        'product_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        # Período (rango)
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Monto solicitado (rango)
                        'requested_amount_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        },
                        'requested_amount_max': {
                            'operators': ['lte'],
                            'type': 'decimal'
                        },
                        # Tasa de aprobación (rango)
                        'approval_rate_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        },
                        'approval_rate_max': {
                            'operators': ['lte'],
                            'type': 'decimal'
                        }
                    },
                    'available_groupings': [
                        'branch_name', 'branch_city', 'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'branch_name', 'total_applications', 'approved_count',
                        'total_approved_amount', 'approval_rate'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'loans_by_product': {
                    'name': 'Créditos por Producto',
                    'description': 'Créditos agrupados por producto financiero',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'product_name', 'product_code', 'product_type',
                        'total_applications', 'approved_count', 'rejected_count',
                        'pending_count', 'total_requested_amount', 'total_approved_amount',
                        'avg_requested_amount', 'avg_approved_amount', 'avg_term_months',
                        'approval_rate'
                    ],
                    'available_filters': {
                        # ===== FILTROS PERSONALIZADOS ESPECÍFICOS =====
                        # Productos específicos
                        'product_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        # Tipo de producto
                        'product_type': {
                            'operators': ['in', 'contains'],
                            'type': 'string'
                        },
                        # Estado de créditos
                        'status': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['SUBMITTED', 'IN_REVIEW', 'APPROVED',
                                      'REJECTED', 'DISBURSED']
                        },
                        # Sucursales
                        'branch_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        # Período (rango)
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Monto solicitado (rango)
                        'requested_amount_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        },
                        'requested_amount_max': {
                            'operators': ['lte'],
                            'type': 'decimal'
                        },
                        # Plazo (rango)
                        'term_months_min': {
                            'operators': ['gte'],
                            'type': 'integer'
                        },
                        'term_months_max': {
                            'operators': ['lte'],
                            'type': 'integer'
                        },
                        # Tipo de empleo del solicitante
                        'employment_type': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['EMPLOYED', 'SELF_EMPLOYED', 'BUSINESS_OWNER',
                                      'RETIRED', 'UNEMPLOYED', 'STUDENT', 'OTHER']
                        },
                        # Tasa de aprobación (rango)
                        'approval_rate_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        }
                    },
                    'available_groupings': [
                        'product_name', 'product_type', 'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'product_name', 'total_applications', 'approved_count',
                        'total_approved_amount', 'approval_rate'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'active_loans': {
                    'name': 'Créditos Activos',
                    'description': 'Créditos activos (aprobados y desembolsados)',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST'],
                    'available_columns': [
                        'application_number', 'client_name', 'client_document',
                        'product_name', 'approved_amount', 'term_months',
                        'branch_name', 'approved_at', 'disbursed_at',
                        'days_since_disbursement'
                    ],
                    'available_filters': {
                        'status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['APPROVED', 'DISBURSED'],
                            'default': ['APPROVED', 'DISBURSED']
                        },
                        'approved_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'branch_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'product_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'approved_amount': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        }
                    },
                    'available_groupings': [
                        'product_name', 'branch_name', 'month'
                    ],
                    'available_sort_fields': [
                        'approved_at', 'disbursed_at', 'approved_amount', 'client_name'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'CUSTOMERS': {
                'customers_registered': {
                    'name': 'Clientes Registrados',
                    'description': 'Clientes registrados por período',
                    'datasource': 'Client',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        # Identificación
                        'document_number', 'document_type', 'document_extension',
                        # Información personal
                        'full_name', 'first_name', 'last_name', 'email', 'birth_date',
                        'gender', 'client_type',
                        # Contacto
                        'mobile_phone', 'phone', 'address', 'city', 'department', 
                        'country', 'postal_code',
                        # Información laboral
                        'employment_status', 'employer_name', 'employer_nit', 
                        'job_title', 'employment_start_date', 'monthly_income', 
                        'additional_income',
                        # Estados
                        'kyc_status', 'status', 'risk_level', 'is_active',
                        # Fechas
                        'created_at', 'verified_at', 'updated_at',
                        # Verificación
                        'verified_by_name'
                    ],
                    'available_filters': {
                        # ===== FILTROS PERSONALIZADOS ESPECÍFICOS =====
                        # Estado KYC
                        'kyc_status': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED']
                        },
                        # Estado de empleo
                        'employment_status': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['EMPLOYED', 'SELF_EMPLOYED', 'BUSINESS_OWNER',
                                      'RETIRED', 'UNEMPLOYED', 'OTHER']
                        },
                        # Tipo de cliente
                        'client_type': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['NATURAL', 'JURIDICA']
                        },
                        # Tipo de documento
                        'document_type': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['CI', 'NIT', 'PASSPORT', 'RUC']
                        },
                        # Género
                        'gender': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['M', 'F', 'O']
                        },
                        # Nivel de riesgo
                        'risk_level': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['LOW', 'MEDIUM', 'HIGH']
                        },
                        # Ciudad
                        'city': {
                            'operators': ['in', 'contains'],
                            'type': 'string'
                        },
                        # Departamento
                        'department': {
                            'operators': ['in', 'contains'],
                            'type': 'string'
                        },
                        # Ingreso mensual (rango)
                        'monthly_income_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        },
                        'monthly_income_max': {
                            'operators': ['lte'],
                            'type': 'decimal'
                        },
                        # Fecha de registro (rango)
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Fecha de verificación (rango)
                        'verified_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'verified_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Fecha de nacimiento (rango)
                        'birth_date_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'birth_date_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Solo activos
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        # Con créditos activos
                        'has_active_loans': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        }
                    },
                    'available_groupings': [
                        'kyc_status', 'employment_status', 'risk_level', 'client_type',
                        'document_type', 'gender', 'city', 'department', 'is_active',
                        'month', 'quarter', 'year'
                    ],
                    'available_sort_fields': [
                        'created_at', 'verified_at', 'updated_at', 'full_name', 
                        'first_name', 'last_name', 'document_number', 'email', 
                        'mobile_phone', 'phone', 'birth_date', 'monthly_income',
                        'additional_income', 'employment_start_date'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'customers_by_status': {
                    'name': 'Clientes por Estado',
                    'description': 'Clientes agrupados por estado de KYC y actividad',
                    'datasource': 'Client',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'document_number', 'document_type', 'full_name', 'email',
                        'mobile_phone', 'phone', 'kyc_status', 'status', 'is_active',
                        'employment_status', 'risk_level', 'created_at', 'verified_at',
                        'last_activity_at', 'last_login', 'active_time', 'device_type'
                    ],
                    'available_filters': {
                        'kyc_status': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED']
                        },
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'employment_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['EMPLOYED', 'SELF_EMPLOYED', 'BUSINESS_OWNER',
                                      'RETIRED', 'UNEMPLOYED', 'OTHER']
                        },
                        'risk_level': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['LOW', 'MEDIUM', 'HIGH']
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'verified_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'kyc_status', 'is_active', 'employment_status', 'risk_level',
                        'month', 'quarter', 'year'
                    ],
                    'available_sort_fields': [
                        'created_at', 'verified_at', 'last_activity_at', 'last_login',
                        'full_name', 'email', 'document_number'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'customers_with_active_loans': {
                    'name': 'Clientes con Créditos Activos',
                    'description': 'Clientes con créditos activos',
                    'datasource': 'Client',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST'],
                    'available_columns': [
                        'client_document', 'client_name', 'client_email', 'client_phone',
                        'total_active_loans', 'total_approved_amount', 'avg_credit_score',
                        'latest_loan_date', 'risk_level'
                    ],
                    'available_filters': {
                        'loan_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['APPROVED', 'DISBURSED'],
                            'default': ['APPROVED', 'DISBURSED']
                        },
                        'approved_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'total_approved_amount': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        },
                        'risk_level': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['LOW', 'MEDIUM', 'HIGH']
                        }
                    },
                    'available_groupings': [
                        'risk_level', 'month'
                    ],
                    'available_sort_fields': [
                        'client_name', 'total_active_loans', 'total_approved_amount',
                        'latest_loan_date'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'DOCUMENTS': {
                'applications_with_pending_documents': {
                    'name': 'Solicitudes con Documentos Pendientes',
                    'description': 'Solicitudes con documentos pendientes',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST'],
                    'available_columns': [
                        'application_number', 'client_name', 'client_email', 'client_phone',
                        'product_name', 'total_documents_required', 'pending_documents_count',
                        'pending_document_types', 'completion_percentage', 'application_status',
                        'days_since_submission', 'created_at'
                    ],
                    'available_filters': {
                        # ===== FILTROS PERSONALIZADOS ESPECÍFICOS =====
                        # Estado de documentos
                        'document_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['PENDING', 'UPLOADED', 'UNDER_REVIEW'],
                            'default': ['PENDING']
                        },
                        # Estado de solicitud
                        'application_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['SUBMITTED', 'IN_REVIEW', 'OBSERVED']
                        },
                        # Tipo de documento
                        'document_type_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Producto
                        'product_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Sucursal
                        'branch_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Días desde envío (rango)
                        'days_since_submission_min': {
                            'operators': ['gte'],
                            'type': 'integer'
                        },
                        'days_since_submission_max': {
                            'operators': ['lte'],
                            'type': 'integer'
                        },
                        # Porcentaje de completitud (rango)
                        'completion_percentage_min': {
                            'operators': ['gte'],
                            'type': 'decimal'
                        },
                        'completion_percentage_max': {
                            'operators': ['lte'],
                            'type': 'decimal'
                        },
                        # Fecha de creación (rango)
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'product_name', 'application_status', 'month'
                    ],
                    'available_sort_fields': [
                        'days_since_submission', 'pending_documents_count', 'created_at',
                        'application_number', 'client_name', 'completion_percentage'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'IDENTITY_VERIFICATION': {
                'verifications_by_status': {
                    'name': 'Verificaciones por Estado',
                    'description': 'Verificaciones de identidad por estado',
                    'datasource': 'IdentityVerification',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST'],
                    'available_columns': [
                        'client_name', 'client_document', 'application_number',
                        'status', 'decision', 'provider', 'started_at', 'completed_at',
                        'processing_time_minutes', 'branch_name'
                    ],
                    'available_filters': {
                        # Decisión
                        'decision': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['APPROVED', 'DECLINED', 'PENDING', 'MANUAL_REVIEW']
                        },
                        # Sucursal
                        'branch_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Fecha inicio desde
                        'started_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fecha inicio hasta
                        'started_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Fecha completado desde
                        'completed_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fecha completado hasta
                        'completed_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Tiempo procesamiento mínimo (minutos)
                        'processing_time_min': {
                            'operators': ['gte'],
                            'type': 'integer'
                        },
                        # Tiempo procesamiento máximo (minutos)
                        'processing_time_max': {
                            'operators': ['lte'],
                            'type': 'integer'
                        }
                    },
                    'available_groupings': [
                        'status', 'decision', 'provider', 'branch_name', 'month'
                    ],
                    'available_sort_fields': [
                        'started_at', 'completed_at', 'processing_time_minutes',
                        'client_name', 'client_document', 'application_number'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'PRODUCTS': {
                'credit_products_catalog': {
                    'name': 'Catálogo de Productos Crediticios',
                    'description': 'Lista de productos crediticios con sus parámetros y configuración',
                    'datasource': 'CreditProduct',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST', 'OFFICER'],
                    'available_columns': [
                        # Información básica del producto
                        'product_name', 'product_code', 'product_type', 'description',
                        'is_active', 'display_order',
                        # Parámetros de montos
                        'min_amount', 'max_amount',
                        # Parámetros de plazos
                        'min_term_months', 'max_term_months',
                        # Tasas de interés
                        'min_interest_rate', 'max_interest_rate', 'interest_rate_type',
                        # Comisiones
                        'commission_rate_min', 'commission_rate_max',
                        # Seguros
                        'insurance_rate_min', 'insurance_rate_max',
                        # Penalidad por pago anticipado
                        'early_payment_penalty_min', 'early_payment_penalty_max',
                        # Período de gracia
                        'grace_period_months_min', 'grace_period_months_max',
                        # Financiamiento
                        'max_financing_percentage',
                        # Garantías
                        'requires_guarantor', 'requires_collateral',
                        # Información de marketing
                        'target_audience', 'benefits',
                        # Conjunto de reglas
                        'rule_set_name', 'rule_set_code',
                        # Fechas
                        'created_at', 'updated_at'
                    ],
                    'available_filters': {
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'product_type': {
                            'operators': ['in'],
                            'type': 'string'
                        },
                        'institution_name': {
                            'operators': ['equals', 'contains'],
                            'type': 'string',
                            'saas_only': True  # Solo para reportes SAAS
                        },
                        'min_amount': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        },
                        'max_amount': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        },
                        'min_term_months': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'integer'
                        },
                        'max_term_months': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'integer'
                        },
                        'min_interest_rate': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        },
                        'max_interest_rate': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        },
                        'requires_guarantor': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'requires_collateral': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'product_type', 'is_active', 'rule_set_name', 'interest_rate_type',
                        'requires_guarantor', 'requires_collateral'
                    ],
                    'available_sort_fields': [
                        'product_name', 'product_code', 'display_order',
                        'min_amount', 'max_amount',
                        'min_term_months', 'max_term_months',
                        'min_interest_rate', 'max_interest_rate',
                        'commission_rate_min', 'commission_rate_max',
                        'created_at', 'updated_at'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'BRANCHES': {
                'branches_performance': {
                    'name': 'Rendimiento de Sucursales',
                    'description': 'Análisis comparativo del rendimiento de sucursales',
                    'datasource': 'Branch',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'branch_name', 'branch_city', 'branch_address',
                        'is_active', 'assigned_users_count',
                        'total_applications', 'approved_count', 'rejected_count', 'pending_count',
                        'total_requested_amount', 'total_approved_amount',
                        'avg_requested_amount', 'avg_approved_amount',
                        'approval_rate', 'avg_processing_days',
                        'total_clients', 'active_clients',
                        'created_at'
                    ],
                    'available_filters': {
                        'branch_id': {
                            'operators': ['in', 'not_in'],
                            'type': 'integer'
                        },
                        'city': {
                            'operators': ['in'],
                            'type': 'string'
                        },
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'approved_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'branch_name', 'city', 'month', 'quarter', 'year'
                    ],
                    'available_sort_fields': [
                        'branch_name', 'total_applications', 'approved_count',
                        'total_approved_amount', 'approval_rate', 'avg_processing_days'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'branches_by_city': {
                    'name': 'Sucursales por Ciudad',
                    'description': 'Distribución y estadísticas de sucursales por ciudad',
                    'datasource': 'Branch',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'city', 'branch_count', 'active_branches', 'inactive_branches',
                        'total_users_assigned', 'total_applications',
                        'total_approved_amount'
                    ],
                    'available_filters': {
                        'city': {
                            'operators': ['in'],
                            'type': 'string'
                        },
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        }
                    },
                    'available_groupings': [
                        'city'
                    ],
                    'available_sort_fields': [
                        'city', 'branch_count', 'total_applications', 'total_approved_amount'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'AUDIT': {
                'audit_logs_by_action': {
                    'name': 'Logs de Auditoría por Acción',
                    'description': 'Registro de acciones del sistema para auditoría',
                    'datasource': 'AuditLog',
                    'roles': ['ADMIN'],
                    'available_columns': [
                        'user_email', 'user_name',
                        'action', 'action_display',
                        'resource_type', 'resource_id',
                        'description', 'severity',
                        'ip_address', 'user_agent',
                        'institution_name',
                        'timestamp'
                    ],
                    'available_filters': {
                        # Acción realizada
                        'action': {
                            'operators': ['equals', 'contains'],
                            'type': 'string'
                        },
                        # Usuario
                        'user_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Tipo de evento
                        'event_type': {
                            'operators': ['equals', 'contains'],
                            'type': 'string'
                        },
                        # Severidad
                        'severity': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['info', 'warning', 'error', 'critical']
                        },
                        # Dirección IP
                        'ip_address': {
                            'operators': ['equals', 'contains'],
                            'type': 'string'
                        },
                        # Fecha desde
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fecha hasta
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Tipo de recurso
                        'resource_type': {
                            'operators': ['equals', 'contains'],
                            'type': 'string'
                        },
                        # ID de recurso
                        'resource_id': {
                            'operators': ['equals'],
                            'type': 'integer'
                        }
                    },
                    'available_groupings': [
                        'action', 'resource_type', 'severity', 'user_email',
                        'institution_name', 'day', 'hour'
                    ],
                    'available_sort_fields': [
                        'timestamp', 'user_email', 'action', 'severity'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'security_events_by_type': {
                    'name': 'Eventos de Seguridad por Tipo',
                    'description': 'Eventos de seguridad y amenazas detectadas',
                    'datasource': 'SecurityEvent',
                    'roles': ['ADMIN'],
                    'available_columns': [
                        'event_type', 'event_type_display',
                        'user_email', 'email_attempted',
                        'ip_address', 'user_agent',
                        'description', 'resolved',
                        'resolved_at', 'resolved_by_name',
                        'timestamp'
                    ],
                    'available_filters': {
                        'event_type': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['failed_login', 'account_locked', 'suspicious_activity',
                                      'unauthorized_access', 'permission_escalation', 'rate_limit_exceeded']
                        },
                        'user_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'email': {
                            'operators': ['equals'],
                            'type': 'string'
                        },
                        'ip_address': {
                            'operators': ['equals'],
                            'type': 'string'
                        },
                        'resolved': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'timestamp': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'datetime'
                        }
                    },
                    'available_groupings': [
                        'event_type', 'ip_address', 'resolved',
                        'day', 'hour'
                    ],
                    'available_sort_fields': [
                        'timestamp', 'event_type', 'ip_address'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'USERS': {
                'users_by_role': {
                    'name': 'Usuarios por Rol',
                    'description': 'Distribución de usuarios por roles y actividad',
                    'datasource': 'User',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'full_name', 'email', 'username',
                        'role_name', 'role_code',
                        'institution_name',
                        'is_active', 'is_staff', 'is_superuser',
                        'last_login', 'date_joined',
                        'login_count', 'last_activity_at',
                        'created_at'
                    ],
                    'available_filters': {
                        # Solo activos
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        # Solo staff
                        'is_staff': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        # Tenant
                        'tenant_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Rol
                        'role': {
                            'operators': ['equals', 'contains'],
                            'type': 'string'
                        },
                        # Fecha registro desde
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fecha registro hasta
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Último login desde
                        'last_login_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Último login hasta
                        'last_login_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Email verificado
                        'email_verified': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        }
                    },
                    'available_groupings': [
                        'role_name', 'institution_name', 'is_active',
                        'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'full_name', 'email', 'last_login', 'date_joined', 'login_count'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'users_activity_report': {
                    'name': 'Reporte de Actividad de Usuarios',
                    'description': 'Actividad y uso del sistema por usuario',
                    'datasource': 'User',
                    'roles': ['ADMIN'],
                    'available_columns': [
                        'user_name', 'user_email', 'role_name',
                        'institution_name',
                        'last_login', 'login_count',
                        'total_actions', 'actions_this_month',
                        'most_common_action',
                        'last_activity_at', 'days_since_last_activity',
                        'is_active'
                    ],
                    'available_filters': {
                        'institution_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'role_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'last_login': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'datetime'
                        },
                        'last_activity_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'datetime'
                        }
                    },
                    'available_groupings': [
                        'role_name', 'institution_name',
                        'month'
                    ],
                    'available_sort_fields': [
                        'user_name', 'last_login', 'login_count', 'total_actions', 'last_activity_at'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'STORAGE': {
                'file_storage_usage': {
                    'name': 'Uso de Almacenamiento',
                    'description': 'Análisis de uso de almacenamiento por institución',
                    'datasource': 'FileResource',
                    'roles': ['ADMIN'],
                    'available_columns': [
                        'institution_name',
                        'resource_type', 'category',
                        'total_files', 'total_size_gb',
                        'active_files', 'archived_files', 'deleted_files',
                        'avg_file_size_mb',
                        'oldest_file_date', 'newest_file_date'
                    ],
                    'available_filters': {
                        'institution_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'resource_type': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['branding', 'document', 'profile_picture', 'report']
                        },
                        'category': {
                            'operators': ['in'],
                            'type': 'string'
                        },
                        'status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['active', 'archived', 'deleted']
                        },
                        'visibility': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['private', 'public', 'tenant_only']
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'datetime'
                        }
                    },
                    'available_groupings': [
                        'institution_name', 'resource_type', 'category', 'status',
                        'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'institution_name', 'total_files', 'total_size_gb', 'oldest_file_date'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'RULES': {
                'rule_sets_by_product': {
                    'name': 'Conjuntos de Reglas por Producto',
                    'description': 'Configuración de reglas aplicadas a productos',
                    'datasource': 'TenantRuleSet',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'rule_set_name', 'rule_set_code', 'rule_set_description',
                        'product_name', 'product_code', 'product_type',
                        'is_active', 'is_default',
                        'eligibility_rules_count', 'parameters_count', 'thresholds_count',
                        'created_at', 'updated_at'
                    ],
                    'available_filters': {
                        'product_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'is_default': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'product_name', 'product_type', 'is_active'
                    ],
                    'available_sort_fields': [
                        'rule_set_name', 'product_name', 'created_at', 'updated_at'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'product_parameters_analysis': {
                    'name': 'Análisis de Parámetros de Productos',
                    'description': 'Parámetros configurados para productos crediticios',
                    'datasource': 'CreditProductParameter',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'product_name', 'rule_set_name',
                        'min_amount', 'max_amount', 'default_amount',
                        'min_term_months', 'max_term_months', 'default_term_months',
                        'min_interest_rate', 'max_interest_rate', 'default_interest_rate',
                        'interest_rate_type',
                        'commission_rate_min', 'commission_rate_max',
                        'requires_guarantor', 'requires_collateral',
                        'is_active'
                    ],
                    'available_filters': {
                        'product_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'rule_set_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'min_amount': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        },
                        'max_amount': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        },
                        'requires_guarantor': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'requires_collateral': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        }
                    },
                    'available_groupings': [
                        'product_name', 'interest_rate_type',
                        'requires_guarantor', 'requires_collateral'
                    ],
                    'available_sort_fields': [
                        'product_name', 'min_amount', 'max_amount', 'min_interest_rate'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'ANALYTICS': {
                'conversion_funnel_analysis': {
                    'name': 'Análisis de Embudo de Conversión',
                    'description': 'Análisis del embudo desde registro hasta desembolso',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER'],
                    'available_columns': [
                        'stage', 'stage_order',
                        'total_count', 'conversion_rate',
                        'drop_off_count', 'drop_off_rate',
                        'avg_time_to_next_stage_days'
                    ],
                    'available_filters': {
                        'product_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'branch_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'product_name', 'branch_name',
                        'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'stage_order', 'total_count', 'conversion_rate', 'drop_off_rate'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'risk_analysis_report': {
                    'name': 'Análisis de Riesgo Crediticio',
                    'description': 'Distribución y análisis de niveles de riesgo',
                    'datasource': 'LoanApplication',
                    'roles': ['ADMIN', 'MANAGER', 'ANALYST'],
                    'available_columns': [
                        'risk_level', 'risk_level_display',
                        'total_applications', 'approved_count', 'rejected_count',
                        'avg_credit_score', 'avg_requested_amount', 'avg_approved_amount',
                        'avg_debt_to_income_ratio',
                        'approval_rate'
                    ],
                    'available_filters': {
                        'risk_level': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH']
                        },
                        'status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['SUBMITTED', 'IN_REVIEW', 'APPROVED', 'REJECTED']
                        },
                        'credit_score': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'integer'
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'approved_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'risk_level', 'product_name', 'branch_name',
                        'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'risk_level', 'total_applications', 'approval_rate', 'avg_credit_score'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            }
        },
        'SAAS': {
            'TENANTS': {
                'tenants_by_status': {
                    'name': 'Tenants por Estado',
                    'description': 'Instituciones financieras por estado',
                    'datasource': 'FinancialInstitution',
                    'roles': ['saas_admin'],
                    'available_columns': [
                        'name', 'slug', 'institution_type', 'is_active', 'created_at',
                        'subscription_status', 'plan_name', 'user_count', 'branch_count',
                        'active_loans_count', 'total_clients'
                    ],
                    'available_filters': {
                        # Estado de suscripción
                        'subscription_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['TRIAL', 'ACTIVE', 'SUSPENDED', 'CANCELLED', 'EXPIRED']
                        },
                        # Tipo de institución
                        'institution_type': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['BANKING', 'MICROFINANCE', 'COOPERATIVE', 'FINTECH']
                        },
                        # Plan de suscripción
                        'plan_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Solo activos
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        # Fecha creación desde
                        'created_at_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fecha creación hasta
                        'created_at_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Usuarios mínimos
                        'users_count_min': {
                            'operators': ['gte'],
                            'type': 'integer'
                        },
                        # Usuarios máximos
                        'users_count_max': {
                            'operators': ['lte'],
                            'type': 'integer'
                        },
                        # Sucursales mínimas
                        'branches_count_min': {
                            'operators': ['gte'],
                            'type': 'integer'
                        },
                        # Sucursales máximas
                        'branches_count_max': {
                            'operators': ['lte'],
                            'type': 'integer'
                        }
                    },
                    'available_groupings': [
                        'institution_type', 'is_active', 'subscription_status',
                        'plan_name', 'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'name', 'created_at', 'user_count', 'branch_count', 'active_loans_count',
                        'total_clients', 'slug'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'USERS': {
                'users_by_tenant': {
                    'name': 'Usuarios por Tenant',
                    'description': 'Usuarios registrados por tenant',
                    'datasource': 'User',
                    'roles': ['saas_admin'],
                    'available_columns': [
                        'tenant_name', 'tenant_slug', 'total_users', 'active_users',
                        'inactive_users', 'admin_count', 'manager_count', 'analyst_count',
                        'officer_count', 'client_count', 'last_user_created_at'
                    ],
                    'available_filters': {
                        'tenant_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'created_at': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'tenant_name', 'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'tenant_name', 'total_users', 'active_users', 'last_user_created_at',
                        'inactive_users', 'admin_count', 'manager_count', 'analyst_count',
                        'officer_count', 'client_count'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            },
            'SUBSCRIPTIONS': {
                'subscriptions_by_status': {
                    'name': 'Suscripciones por Estado',
                    'description': 'Suscripciones por estado',
                    'datasource': 'Subscription',
                    'roles': ['saas_admin'],
                    'available_columns': [
                        'tenant_name', 'plan_name', 'status', 'payment_status',
                        'start_date', 'end_date', 'trial_end_date', 'next_billing_date',
                        'amount_due', 'total_paid', 'current_users', 'current_branches',
                        'days_active'
                    ],
                    'available_filters': {
                        # Estado
                        'subscription_status': {
                            'operators': ['in', 'not_in'],
                            'type': 'choice',
                            'values': ['TRIAL', 'ACTIVE', 'SUSPENDED', 'CANCELLED', 'EXPIRED']
                        },
                        # Estado de pago
                        'payment_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['PENDING', 'PAID', 'OVERDUE', 'FAILED']
                        },
                        # Plan
                        'plan_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Tenant
                        'tenant_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        # Ciclo de facturación
                        'billing_cycle': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['MONTHLY', 'QUARTERLY', 'ANNUAL']
                        },
                        # Fecha inicio desde
                        'start_date_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fecha inicio hasta
                        'start_date_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Fecha fin desde
                        'end_date_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fecha fin hasta
                        'end_date_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Fin de prueba desde
                        'trial_end_date_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Fin de prueba hasta
                        'trial_end_date_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        },
                        # Próxima facturación desde
                        'next_billing_date_start': {
                            'operators': ['gte'],
                            'type': 'date'
                        },
                        # Próxima facturación hasta
                        'next_billing_date_end': {
                            'operators': ['lte'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'status', 'payment_status', 'plan_name', 'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'tenant_name', 'start_date', 'end_date', 'next_billing_date',
                        'amount_due', 'total_paid', 'trial_end_date', 'plan_name',
                        'days_active'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'subscription_plans_comparison': {
                    'name': 'Comparación de Planes de Suscripción',
                    'description': 'Análisis de planes disponibles y sus características',
                    'datasource': 'SubscriptionPlan',
                    'roles': ['saas_admin'],
                    'available_columns': [
                        'name', 'slug', 'description',
                        'price', 'billing_cycle', 'billing_cycle_display',
                        'trial_days', 'setup_fee',
                        'max_users', 'max_branches', 'max_products',
                        'max_loans_per_month', 'max_storage_gb',
                        'has_ai_scoring', 'has_workflows', 'has_reporting',
                        'has_mobile_app', 'has_api_access', 'has_white_label',
                        'has_priority_support', 'has_custom_integrations',
                        'is_active', 'is_featured', 'display_order',
                        'price_per_month'
                    ],
                    'available_filters': {
                        'is_active': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'is_featured': {
                            'operators': ['equals'],
                            'type': 'boolean'
                        },
                        'billing_cycle': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['MONTHLY', 'QUARTERLY', 'ANNUAL']
                        },
                        'price': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'decimal'
                        }
                    },
                    'available_groupings': [
                        'billing_cycle', 'is_featured'
                    ],
                    'available_sort_fields': [
                        'name', 'price', 'display_order', 'max_users', 'max_branches'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'subscriptions_usage_analysis': {
                    'name': 'Análisis de Uso de Suscripciones',
                    'description': 'Uso actual vs límites de las suscripciones',
                    'datasource': 'Subscription',
                    'roles': ['saas_admin'],
                    'available_columns': [
                        'institution_name', 'institution_slug',
                        'plan_name', 'status', 'status_display',
                        'payment_status', 'payment_status_display',
                        'start_date', 'end_date', 'trial_end_date', 'next_billing_date',
                        'amount_due', 'total_paid',
                        'current_users', 'max_users', 'users_percentage',
                        'current_branches', 'max_branches', 'branches_percentage',
                        'current_products', 'max_products', 'products_percentage',
                        'current_month_loans', 'max_loans_per_month', 'loans_percentage',
                        'current_storage_gb', 'max_storage_gb', 'storage_percentage',
                        'is_within_limits', 'days_until_renewal'
                    ],
                    'available_filters': {
                        'status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['TRIAL', 'ACTIVE', 'SUSPENDED', 'CANCELLED', 'EXPIRED']
                        },
                        'payment_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['PENDING', 'PAID', 'OVERDUE', 'FAILED']
                        },
                        'plan_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'institution_id': {
                            'operators': ['in'],
                            'type': 'integer'
                        },
                        'start_date': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'end_date': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'next_billing_date': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'status', 'payment_status', 'plan_name',
                        'month', 'quarter'
                    ],
                    'available_sort_fields': [
                        'institution_name', 'users_percentage', 'branches_percentage',
                        'storage_percentage', 'days_until_renewal', 'total_paid'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                },
                'subscriptions_revenue_analysis': {
                    'name': 'Análisis de Ingresos por Suscripciones',
                    'description': 'Análisis financiero de suscripciones',
                    'datasource': 'Subscription',
                    'roles': ['saas_admin'],
                    'available_columns': [
                        'institution_name', 'plan_name',
                        'status', 'payment_status',
                        'billing_cycle',
                        'monthly_revenue',
                        'total_paid', 'amount_due',
                        'start_date', 'next_billing_date',
                        'days_active'
                    ],
                    'available_filters': {
                        'status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['TRIAL', 'ACTIVE', 'SUSPENDED', 'CANCELLED', 'EXPIRED']
                        },
                        'payment_status': {
                            'operators': ['in'],
                            'type': 'choice',
                            'values': ['PENDING', 'PAID', 'OVERDUE', 'FAILED']
                        },
                        'start_date': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        },
                        'next_billing_date': {
                            'operators': ['gte', 'lte', 'between'],
                            'type': 'date'
                        }
                    },
                    'available_groupings': [
                        'plan_name', 'status', 'payment_status',
                        'month', 'quarter', 'year'
                    ],
                    'available_sort_fields': [
                        'institution_name', 'monthly_revenue', 'total_paid', 'amount_due', 'days_active'
                    ],
                    'formats': ['csv', 'xlsx', 'pdf']
                }
            }
        }
    }
    
    @classmethod
    def get_report_definition(
        cls,
        scope: str,
        category: str,
        report_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene la definición de un tipo de reporte.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            
        Returns:
            Definición del reporte o None si no existe
        """
        try:
            return cls.CATALOG[scope][category][report_type]
        except KeyError:
            return None
    
    @classmethod
    def get_categories(cls, scope: str) -> List[str]:
        """
        Obtiene las categorías disponibles para un scope.
        
        Args:
            scope: TENANT o SAAS
            
        Returns:
            Lista de categorías
        """
        return list(cls.CATALOG.get(scope, {}).keys())
    
    @classmethod
    def get_report_types(cls, scope: str, category: str) -> List[str]:
        """
        Obtiene los tipos de reportes disponibles para una categoría.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            
        Returns:
            Lista de tipos de reportes
        """
        return list(cls.CATALOG.get(scope, {}).get(category, {}).keys())
    
    @classmethod
    def get_full_catalog(cls, scope: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene el catálogo completo o filtrado por scope.
        
        Args:
            scope: TENANT, SAAS o None para todos
            
        Returns:
            Catálogo completo o filtrado
        """
        if scope:
            return {scope: cls.CATALOG.get(scope, {})}
        return cls.CATALOG
    
    @classmethod
    def validate_report_type(
        cls,
        scope: str,
        category: str,
        report_type: str
    ) -> bool:
        """
        Valida que un tipo de reporte exista.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            
        Returns:
            True si existe, False si no
        """
        return cls.get_report_definition(scope, category, report_type) is not None
    
    @classmethod
    def get_available_columns(
        cls,
        scope: str,
        category: str,
        report_type: str
    ) -> List[str]:
        """
        Obtiene las columnas disponibles para un tipo de reporte.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            
        Returns:
            Lista de columnas disponibles
        """
        definition = cls.get_report_definition(scope, category, report_type)
        return definition.get('available_columns', []) if definition else []
    
    @classmethod
    def get_available_filters(
        cls,
        scope: str,
        category: str,
        report_type: str
    ) -> Dict[str, Any]:
        """
        Obtiene los filtros disponibles para un tipo de reporte.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            
        Returns:
            Diccionario de filtros disponibles
        """
        definition = cls.get_report_definition(scope, category, report_type)
        return definition.get('available_filters', {}) if definition else {}
    
    @classmethod
    def get_available_groupings(
        cls,
        scope: str,
        category: str,
        report_type: str
    ) -> List[str]:
        """
        Obtiene las agrupaciones disponibles para un tipo de reporte.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            
        Returns:
            Lista de agrupaciones disponibles
        """
        definition = cls.get_report_definition(scope, category, report_type)
        return definition.get('available_groupings', []) if definition else []
    
    @classmethod
    def get_available_sort_fields(
        cls,
        scope: str,
        category: str,
        report_type: str
    ) -> List[str]:
        """
        Obtiene los campos de ordenamiento disponibles para un tipo de reporte.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            
        Returns:
            Lista de campos de ordenamiento disponibles
        """
        definition = cls.get_report_definition(scope, category, report_type)
        return definition.get('available_sort_fields', []) if definition else []
    
    @classmethod
    def get_allowed_roles(
        cls,
        scope: str,
        category: str,
        report_type: str
    ) -> List[str]:
        """
        Obtiene los roles permitidos para un tipo de reporte.
        
        Args:
            scope: TENANT o SAAS
            category: Categoría del reporte
            report_type: Tipo específico de reporte
            
        Returns:
            Lista de roles permitidos
        """
        definition = cls.get_report_definition(scope, category, report_type)
        return definition.get('roles', []) if definition else []

    @classmethod
    def get_available_reports(
        cls,
        scope: str,
        user_roles: List[str]
    ) -> Dict[str, Any]:
        """
        Obtiene los reportes disponibles para un scope y roles de usuario.
        
        Filtra el catálogo completo para mostrar solo los reportes
        a los que el usuario tiene acceso según sus roles.
        
        Args:
            scope: TENANT o SAAS
            user_roles: Lista de roles del usuario
            
        Returns:
            Diccionario con categorías y lista de reportes disponibles
        """
        if scope not in cls.CATALOG:
            return {}
        
        # Normalizar roles a mayúsculas para comparación
        normalized_roles = [role.upper() for role in user_roles]
        
        available = {}
        scope_catalog = cls.CATALOG[scope]
        
        for category, reports in scope_catalog.items():
            category_reports = []
            
            for report_type, definition in reports.items():
                # Verificar si el usuario tiene algún rol permitido
                allowed_roles = [r.upper() for r in definition.get('roles', [])]
                
                # Si no hay roles definidos o el usuario tiene al menos un rol permitido
                if not allowed_roles or any(role in allowed_roles for role in normalized_roles):
                    # Retornar información completa del reporte para el frontend
                    category_reports.append({
                        'type': report_type,
                        'name': definition['name'],
                        'description': definition['description'],
                        'datasource': definition.get('datasource', ''),
                        'roles': definition.get('roles', []),
                        'available_columns': definition.get('available_columns', []),
                        'available_filters': definition.get('available_filters', {}),
                        'available_groupings': definition.get('available_groupings', []),
                        'available_sort_fields': definition.get('available_sort_fields', []),
                        'formats': definition.get('formats', ['csv', 'xlsx'])
                    })
            
            if category_reports:
                available[category] = category_reports
        
        return available
