"""
URLs para el módulo de reportes.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReportCatalogViewSet,
    ReportTemplateViewSet,
    ReportGenerationViewSet,
    GeneratedReportViewSet,
    VoiceReportViewSet
)
from .views_manual import ManualReportViewSet

app_name = 'reports'

router = DefaultRouter()
router.register(r'catalog', ReportCatalogViewSet, basename='report-catalog')
router.register(r'templates', ReportTemplateViewSet, basename='report-template')
router.register(r'generate', ReportGenerationViewSet, basename='report-generation')
router.register(r'generated', GeneratedReportViewSet, basename='generated-report')
router.register(r'voice', VoiceReportViewSet, basename='voice-report')

urlpatterns = [
    path('', include(router.urls)),
    
    # Endpoints para reportes manuales independientes
    path('manual/<str:report_type>/', ManualReportViewSet.as_view({'get': 'list'}), name='manual-report'),
    path('manual/export/csv/', ManualReportViewSet.as_view({'post': 'export_csv'}), name='manual-export-csv'),
    path('manual/export/xlsx/', ManualReportViewSet.as_view({'post': 'export_xlsx'}), name='manual-export-xlsx'),
    path('manual/export/pdf/', ManualReportViewSet.as_view({'post': 'export_pdf'}), name='manual-export-pdf'),
    path('manual-available/', ManualReportViewSet.as_view({'get': 'available'}), name='manual-available'),
    path('manual-filter-options/', ManualReportViewSet.as_view({'get': 'filter_options'}), name='manual-filter-options'),
]
