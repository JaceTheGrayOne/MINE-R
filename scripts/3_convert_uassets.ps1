# --- CONFIG ---
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Resolve-Path (Join-Path $PSScriptRoot "..")

# Path to converter
$CONVERTER_EXE = Join-Path $PROJECT_ROOT "tools\uasset_converter\bin\Release\net8.0\UAssetToJson.exe"

# Grounded 2 Engine Version
$ENGINE_VERSION = "VER_UE5_4"

# Path to mapping file
$USMAP_PATH = Join-Path $PROJECT_ROOT "tools\mappings\Grounded2.usmap"
# --- END CONFIG ---

$ErrorActionPreference = "Stop"

$SOURCE_DIR = Join-Path $PROJECT_ROOT "datatables_filtered"
$STAGING_DIR = Join-Path $PROJECT_ROOT "json_staging"

$CONVERTER_WORKING_DIR = Split-Path $CONVERTER_EXE

Write-Host "Starting UAsset to JSON conversion..."
Write-Host "Source: $SOURCE_DIR"

# Validate paths
if (-not (Test-Path $CONVERTER_EXE)) {
    Write-Host "Error: Converter tool not found at $CONVERTER_EXE"
    Write-Host "Please build the C# project first."
    exit 1
}
if (-not (Test-Path $SOURCE_DIR)) {
    Write-Host "Error: Filtered datatables not found at $SOURCE_DIR"
    Write-Host "Please run script 2 first."
    exit 1
}
if ($USMAP_PATH -and (-not (Test-Path $USMAP_PATH))) {
    Write-Host "Error: .usmap file not found at $USMAP_PATH"
    Write-Host "Please update the path in this script."
    exit 1
}

# Clear/create the staging directory
if (Test-Path $STAGING_DIR) {
    Write-Host "Clearing old JSON staging directory..."
    Remove-Item -Recurse -Force $STAGING_DIR
}
New-Item -ItemType Directory -Force -Path $STAGING_DIR | Out-Null

# Get .uasset files
$uassetFiles = Get-ChildItem -Path $SOURCE_DIR -Recurse -File -Filter "*.uasset"
Write-Host "Found $($uassetFiles.Count) .uasset files to convert."

foreach ($file in $uassetFiles) {
    $relativePath = $file.FullName.Substring($SOURCE_DIR.Length)
    $jsonOutputPath = Join-Path $STAGING_DIR $relativePath
    $jsonOutputPath = [System.IO.Path]::ChangeExtension($jsonOutputPath, ".json")

    # Ensure the output directory exists
    New-Item -ItemType Directory -Force -Path (Split-Path $jsonOutputPath) | Out-Null

    $arguments = @(
        "`"$ENGINE_VERSION`"",
        "`"$($file.FullName)`"",
        "`"$jsonOutputPath`""
    )
    if ($USMAP_PATH) {
        $arguments += "`"$USMAP_PATH`""
    }
    
    # --- UPDATED EXECUTION LOGIC ---
    Write-Host "Converting $($file.Name)..."
    try {
        $process = Start-Process -FilePath $CONVERTER_EXE -ArgumentList $arguments -WorkingDirectory $CONVERTER_WORKING_DIR -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -ne 0) {
            throw "Failed to convert $($file.Name). Exit code: $($process.ExitCode)"
        }
    } catch {
        Write-Host "Error: Failed to convert $($file.Name)."
        Write-Host $_
        throw "Conversion failed."
    }
}

Write-Host "Success: JSON conversion complete. Files are in $STAGING_DIR"

