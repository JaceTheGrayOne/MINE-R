Write-Host "========== GROUNDED 2 DATA PIPELINE STARTING =========="
$ErrorActionPreference = "Stop"

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

try {
    Write-Host "`n[1/5] Converting IoStore to Legacy Assets..."
    & (Join-Path $PSScriptRoot "1_convert_iostore.ps1") # <-- Renamed

    Write-Host "`n[2/5] Filtering Data Tables..."
    & (Join-Path $PSScriptRoot "2_filter_datatables.ps1")

    Write-Host "`n[3/5] Converting UAssets to JSON..."
    & (Join-Path $PSScriptRoot "3_convert_uassets.ps1")
    
    Write-Host "`n[4/5] Processing Manifest (Detecting Changes)..."
    python (Join-Path $PSScriptRoot "4_process_manifest.py")
    
    Write-Host "`n[5/5] Updating Database..."
    python (Join-Path $PSScriptRoot "5_update_database.py")
    
    Write-Host "`n========== PIPELINE COMPLETED SUCCESSFULLY =========="

} catch {
    Write-Host "`n==========!!! PIPELINE FAILED!!! =========="
    
    if ($_.InvocationInfo.MyCommand) {
        Write-Host "Error occurred at step: $($_.InvocationInfo.MyCommand.Name)"
    } else {
        Write-Host "Error occurred at step: $($_.TargetObject)"
    }
    
    Write-Host "Error message: $($_.Exception.Message)"
    exit 1
}
