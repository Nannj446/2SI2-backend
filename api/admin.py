from django.contrib import admin

from .models import FinancialInstitution, FinancialInstitutionMembership, Permission, Role


@admin.register(FinancialInstitution)
class FinancialInstitutionAdmin(admin.ModelAdmin):
	list_display = ('id', 'name', 'slug', 'institution_type', 'is_active', 'created_at')
	list_filter = ('institution_type', 'is_active', 'created_at')
	search_fields = ('name', 'slug')
	readonly_fields = ('created_at', 'updated_at')


@admin.register(FinancialInstitutionMembership)
class FinancialInstitutionMembershipAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'institution', 'is_active', 'created_at')
	list_filter = ('is_active', 'created_at')
	search_fields = ('user__username', 'user__email', 'institution__name')
	readonly_fields = ('created_at', 'updated_at')


# Parte erick sprint 0
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
	list_display = ('id', 'code', 'name', 'is_active', 'created_at')
	list_filter = ('is_active', 'created_at')
	search_fields = ('code', 'name')
	readonly_fields = ('created_at', 'updated_at')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
	list_display = ('id', 'name', 'institution', 'is_active', 'created_at')
	list_filter = ('is_active', 'created_at', 'institution')
	search_fields = ('name', 'institution__name', 'institution__slug')
	filter_horizontal = ('permissions',)
	readonly_fields = ('created_at', 'updated_at')
