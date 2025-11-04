$ErrorActionPreference = "Stop"

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Resolve-Path (Join-Path $PSScriptRoot "..")

$SOURCE_DIR = Join-Path $PROJECT_ROOT "legacy_assets\Augusta\Content"
$DEST_DIR = Join-Path $PROJECT_ROOT "datatables_filtered"

Write-Host "Filtering data tables from $SOURCE_DIR..."

if (Test-Path $DEST_DIR) {
    Write-Host "Clearing old filtered tables in $DEST_DIR..."
    Remove-Item -Recurse -Force $DEST_DIR
}
New-Item -ItemType Directory -Force -Path $DEST_DIR | Out-Null

# Find all relevant.uasset files
try {
    $filesToCopy = Get-ChildItem -Path $SOURCE_DIR -Recurse -File | Where-Object { 
        ($_.Name -like "DT_*" -or $_.Name -like "Table_*" -or $_.Name -eq "Text_enus.uasset") -and $_.Extension -eq ".uasset" 
    }

    Write-Host "Found $($filesToCopy.Count) data table files to copy."

    # Copy files
    foreach ($file in $filesToCopy) {
        $relativePath = $file.FullName.Substring($SOURCE_DIR.Length)
        $destinationPath = Join-Path $DEST_DIR $relativePath
        
        # Ensure the destination subdirectory exists
        New-Item -ItemType Directory -Force -Path (Split-Path $destinationPath) | Out-Null
        
        Copy-Item -Path $file.FullName -Destination $destinationPath
    }

    Write-Host "Success: Data tables filtered to $DEST_DIR"
} catch {
    Write-Host "Error: Failed to filter data tables. Is '$SOURCE_DIR' populated?"
    Write-Host $_
    exit 1
}

