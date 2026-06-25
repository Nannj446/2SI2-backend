"""
Modelos para gestión de sucursales.
"""

from django.conf import settings
from django.db import models

from api.core.models import TenantModel


class Branch(TenantModel):
    """
    Modelo de sucursal perteneciente a una institución financiera (tenant).
    """

    name = models.CharField(
        max_length=150,
        verbose_name='Nombre',
        help_text='Nombre de la sucursal',
    )
    address = models.CharField(
        max_length=255,
        verbose_name='Dirección',
        help_text='Dirección física de la sucursal',
    )
    city = models.CharField(
        max_length=120,
        verbose_name='Ciudad',
        help_text='Ciudad donde se ubica la sucursal',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Indica si la sucursal está activa',
    )

    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='assigned_branches',
        verbose_name='Usuarios Asignados',
        help_text='Usuarios internos asignados a esta sucursal',
    )
    assigned_loan_applications = models.ManyToManyField(
        'loans.LoanApplication',
        blank=True,
        related_name='assigned_branches',
        verbose_name='Solicitudes Asignadas',
        help_text='Solicitudes de crédito asociadas a esta sucursal',
    )

    class Meta:
        db_table = 'branches'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'name'],
                name='uniq_branch_name_per_institution',
            )
        ]
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['institution', 'city']),
        ]
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'

    def __str__(self) -> str:
        return f'{self.name} ({self.institution.slug})'

    @property
    def assigned_users_count(self) -> int:
        return self.assigned_users.count()

    @property
    def assigned_operations_count(self) -> int:
        return self.assigned_loan_applications.count()
