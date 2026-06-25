# ============================================================================
# CONFIGURACIÓN DE TASK SCHEDULER PARA BACKUPS AUTOMÁTICOS (WINDOWS)
# ============================================================================
# 
# Este script PowerShell configura tareas programadas en Windows para backups automáticos.
# 
# INSTALACIÓN:
# 1. Abrir PowerShell como Administrador
# 2. Editar las rutas según tu instalación
# 3. Ejecutar este script: .\task-scheduler-backups-example.ps1
#
# ============================================================================

# Variables de configuración (EDITAR SEGÚN TU INSTALACIÓN)
$ProjectPath = "d:\Moondancer\hard2\proyecto\SI2-backend"
$VenvPath = "d:\Moondancer\hard2\proyecto\SI2-backend\venv"
$PythonExe = "$VenvPath\Scripts\python.exe"
$ManagePy = "$ProjectPath\manage.py"
$LogPath = "d:\logs\si2"

# Crear directorio de logs si no existe
if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force
    Write-Host "✅ Directorio de logs creado: $LogPath"
}

# ============================================================================
# TAREA 1: BACKUP DIARIO (Metadata Only)Get-ScheduledTask -TaskName "SI2 Backup Testing (3 min)"

# ============================================================================
Write-Host "`n📅 Configurando backup diario..."

$TaskName = "SI2 Backup Diario"
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "$ManagePy create_scheduled_backups --backup-type metadata_only --parallel --workers 4" `
    -WorkingDirectory $ProjectPath

$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Eliminar tarea existente si existe
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Crear nueva tarea
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Backup diario automático de metadata (sin archivos físicos)" `
    -User "SYSTEM" `
    -RunLevel Highest

Write-Host "✅ Tarea '$TaskName' creada exitosamente"

# ============================================================================
# TAREA 2: BACKUP SEMANAL COMPLETO
# ============================================================================
Write-Host "`n📅 Configurando backup semanal completo..."

$TaskName = "SI2 Backup Semanal Completo"
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "$ManagePy create_scheduled_backups --backup-type full --parallel --workers 2" `
    -WorkingDirectory $ProjectPath

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Eliminar tarea existente si existe
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Crear nueva tarea
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Backup semanal completo incluyendo archivos físicos" `
    -User "SYSTEM" `
    -RunLevel Highest

Write-Host "✅ Tarea '$TaskName' creada exitosamente"

# ============================================================================
# TAREA 3: LIMPIEZA DE BACKUPS EXPIRADOS
# ============================================================================
Write-Host "`n📅 Configurando limpieza de backups..."

$TaskName = "SI2 Limpieza de Backups"
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "$ManagePy cleanup_backups" `
    -WorkingDirectory $ProjectPath

$Trigger = New-ScheduledTaskTrigger -Daily -At 4:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

# Eliminar tarea existente si existe
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Crear nueva tarea
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Limpieza diaria de backups expirados" `
    -User "SYSTEM" `
    -RunLevel Highest

Write-Host "✅ Tarea '$TaskName' creada exitosamente"

# ============================================================================
# RESUMEN
# ============================================================================
Write-Host "`n" + "="*80
Write-Host "✅ CONFIGURACIÓN COMPLETADA"
Write-Host "="*80

Write-Host "`nTareas programadas creadas:"
Write-Host "  1. SI2 Backup Diario - Todos los días a las 2:00 AM"
Write-Host "  2. SI2 Backup Semanal Completo - Domingos a las 3:00 AM"
Write-Host "  3. SI2 Limpieza de Backups - Todos los días a las 4:00 AM"

Write-Host "`nPara ver las tareas:"
Write-Host "  Get-ScheduledTask | Where-Object {`$_.TaskName -like 'SI2*'}"

Write-Host "`nPara ejecutar manualmente:"
Write-Host "  Start-ScheduledTask -TaskName 'SI2 Backup Diario'"

Write-Host "`nPara eliminar las tareas:"
Write-Host "  Unregister-ScheduledTask -TaskName 'SI2 Backup Diario' -Confirm:`$false"

Write-Host "`nLogs se guardarán en: $LogPath"
Write-Host ""

# ============================================================================
# COMANDOS ÚTILES
# ============================================================================
<#

# Ver todas las tareas de SI2
Get-ScheduledTask | Where-Object {$_.TaskName -like 'SI2*'} | Format-Table TaskName, State, LastRunTime, NextRunTime

# Ver detalles de una tarea
Get-ScheduledTask -TaskName "SI2 Backup Diario" | Get-ScheduledTaskInfo

# Ejecutar tarea manualmente
Start-ScheduledTask -TaskName "SI2 Backup Diario"

# Deshabilitar tarea
Disable-ScheduledTask -TaskName "SI2 Backup Diario"

# Habilitar tarea
Enable-ScheduledTask -TaskName "SI2 Backup Diario"

# Eliminar tarea
Unregister-ScheduledTask -TaskName "SI2 Backup Diario" -Confirm:$false

# Ver historial de ejecución
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" | 
    Where-Object {$_.Message -like "*SI2*"} | 
    Select-Object TimeCreated, Message -First 10

# Probar comando manualmente
& $PythonExe $ManagePy create_scheduled_backups --dry-run

#>

# ============================================================================
# NOTAS IMPORTANTES
# ============================================================================
<#

1. PERMISOS:
   - Ejecutar PowerShell como Administrador
   - Las tareas se ejecutan con usuario SYSTEM

2. LOGS:
   - Los logs se guardan en la carpeta especificada en $LogPath
   - Revisar logs regularmente para detectar errores

3. NOTIFICACIONES:
   - Configurar EMAIL_HOST y ADMIN_EMAIL en .env
   - Se enviarán emails automáticos si hay errores

4. MONITOREO:
   - Revisar el endpoint /api/saas/backups/health/ para ver estado
   - Configurar alertas si el healthcheck muestra errores

5. TROUBLESHOOTING:
   - Si las tareas no se ejecutan, verificar:
     * Rutas correctas en las variables
     * Python y manage.py accesibles
     * Permisos de escritura en directorio de logs
     * Estado de la tarea: Get-ScheduledTask -TaskName "SI2 Backup Diario"

#>
