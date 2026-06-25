"""
Servicio para generar manifests de backups.
"""
import logging
import hashlib
import json
from typing import Dict, List, Any
from django.utils import timezone
from api.backups.models import TenantBackup, BackupManifest

logger = logging.getLogger(__name__)


class ManifestService:
    """
    Servicio para generar manifests de backups.
    
    Crea metadata detallada sobre el contenido del backup:
    - Tablas incluidas
    - Conteo de registros
    - Checksums de archivos
    - Metadata adicional
    """
    
    SCHEMA_VERSION = '1.0'
    
    def __init__(self, backup: TenantBackup):
        """
        Inicializa el servicio.
        
        Args:
            backup: Instancia de TenantBackup
        """
        self.backup = backup
        logger.debug(f"ManifestService inicializado para backup {backup.id}")
    
    def generate_manifest(
        self, 
        exported_data: Dict[str, Any],
        file_list: List[str] = None,
        storage_paths: Dict[str, str] = None
    ) -> BackupManifest:
        """
        Genera manifest completo del backup.
        
        Args:
            exported_data: Datos exportados por ExportService
            file_list: Lista de archivos físicos incluidos (opcional)
            storage_paths: Diccionario con rutas de archivos en Storage (opcional)
        
        Returns:
            Instancia de BackupManifest creada
        """
        logger.info(f"Generando manifest para backup {self.backup.id}")
        
        # Extraer información de los datos exportados
        included_tables = list(exported_data.get('data', {}).keys())
        record_counts = self._extract_record_counts(exported_data)
        
        # Calcular checksum de los datos
        data_checksum = self._calculate_data_checksum(exported_data)
        
        # Preparar checksums
        checksums = {
            'data.json': data_checksum
        }
        
        # Crear manifest en la base de datos
        manifest = BackupManifest.objects.create(
            backup=self.backup,
            schema_version=self.SCHEMA_VERSION,
            included_tables=included_tables,
            record_counts=record_counts,
            storage_paths=storage_paths or {},
            file_list=file_list or [],
            checksums=checksums,
            metadata={
                'tenant_id': self.backup.tenant.id,
                'tenant_name': self.backup.tenant.name,
                'backup_type': self.backup.backup_type,
                'total_records': sum(record_counts.values()),
                'total_tables': len(included_tables),
                'total_files': len(file_list) if file_list else 0,
                'export_timestamp': exported_data.get('export_timestamp'),
            }
        )
        
        logger.info(
            f"Manifest generado: {manifest.id} "
            f"({manifest.total_records} registros, {manifest.total_files} archivos)"
        )
        
        return manifest
    
    def _extract_record_counts(self, exported_data: Dict) -> Dict[str, int]:
        """
        Extrae conteo de registros de los datos exportados.
        
        Args:
            exported_data: Datos exportados con estructura:
                {'data': {'model.Name': [records...]}}
        
        Returns:
            Diccionario con conteos por tabla:
                {'clients.Client': 100, 'branches.Branch': 5}
        """
        counts = {}
        
        for model_path, records in exported_data.get('data', {}).items():
            if isinstance(records, list):
                counts[model_path] = len(records)
            else:
                counts[model_path] = 0
        
        return counts
    
    def _calculate_data_checksum(self, data: Dict) -> str:
        """
        Calcula checksum SHA-256 de los datos.
        
        Args:
            data: Datos a hashear
        
        Returns:
            Checksum hexadecimal (64 caracteres)
        """
        # Serializar a JSON con orden consistente y manejo de datetime
        json_str = json.dumps(
            data, 
            sort_keys=True, 
            ensure_ascii=False,
            default=str  # Convertir datetime y otros objetos no serializables a string
        )
        
        # Calcular SHA-256
        checksum = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        
        logger.debug(f"Checksum calculado: {checksum[:16]}...")
        
        return checksum
    
    def generate_manifest_json(self) -> Dict[str, Any]:
        """
        Genera representación JSON del manifest para exportar.
        
        Returns:
            Diccionario con toda la información del manifest
        """
        if not hasattr(self.backup, 'manifest'):
            raise ValueError(f"Backup {self.backup.id} no tiene manifest")
        
        manifest = self.backup.manifest
        
        return {
            'schema_version': manifest.schema_version,
            'backup_id': self.backup.id,
            'tenant_id': self.backup.tenant.id,
            'tenant_name': self.backup.tenant.name,
            'backup_type': self.backup.backup_type,
            'generated_at': manifest.generated_at.isoformat(),
            'included_tables': manifest.included_tables,
            'record_counts': manifest.record_counts,
            'storage_paths': manifest.storage_paths,
            'file_list': manifest.file_list,
            'checksums': manifest.checksums,
            'metadata': manifest.metadata,
            'totals': {
                'records': manifest.total_records,
                'files': manifest.total_files,
                'tables': len(manifest.included_tables)
            }
        }
    
    def verify_manifest_integrity(self, exported_data: Dict) -> bool:
        """
        Verifica la integridad del manifest comparando checksums.
        
        Args:
            exported_data: Datos exportados originales
        
        Returns:
            True si el checksum coincide, False si no
        """
        if not hasattr(self.backup, 'manifest'):
            logger.error(f"Backup {self.backup.id} no tiene manifest")
            return False
        
        manifest = self.backup.manifest
        stored_checksum = manifest.checksums.get('data.json')
        
        if not stored_checksum:
            logger.error("No hay checksum almacenado en el manifest")
            return False
        
        # Calcular checksum actual
        calculated_checksum = self._calculate_data_checksum(exported_data)
        
        # Comparar
        is_valid = stored_checksum == calculated_checksum
        
        if is_valid:
            logger.info("Integridad del manifest verificada correctamente")
        else:
            logger.error(
                f"Integridad comprometida: "
                f"stored={stored_checksum[:16]}... "
                f"calculated={calculated_checksum[:16]}..."
            )
        
        return is_valid
