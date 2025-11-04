# --- CONFIG ---
# Path to retoc.exe
$RETOC_EXE_PATH = "G:\Development\MINE-R\tools\retoc\retoc.exe"

# Game Paks directory
$GAME_PAKS_PATH = "E:\SteamLibrary\steamapps\common\Grounded2\Augusta\Content\Paks"

# The Unreal Engine version for retoc
$UE_VERSION = "UE5_4"

$AES_KEY = ""
# --- END CONFIG ---

$ErrorActionPreference = "Stop"

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_ROOT = Resolve-Path (Join-Path $PSScriptRoot "..")
$OUTPUT_DIR = Join-Path $PROJECT_ROOT "legacy_assets" # Renamed for clarity

# Validate paths
if (-not (Test-Path $RETOC_EXE_PATH)) {
    Write-Host "Error: Retoc.exe not found at $RETOC_EXE_PATH"
    exit 1
}
if (-not (Test-Path $GAME_PAKS_PATH)) {
    Write-Host "Error: Game Paks directory not found at $GAME_PAKS_PATH"
    exit 1
}

Write-Host "Starting IoStore to Legacy asset conversion..."
Write-Host "Source: $GAME_PAKS_PATH"
Write-Host "Destination: $OUTPUT_DIR"

if (Test-Path $OUTPUT_DIR) {
    Write-Host "Clearing old legacy assets directory..."
    Remove-Item -Recurse -Force $OUTPUT_DIR
}
New-Item -ItemType Directory -Force -Path $OUTPUT_DIR | Out-Null

try {
    $arguments = @()
    if ($AES_KEY) {
        $arguments += "--aes-key", $AES_KEY
    }
    
    $arguments += "to-legacy", "--version", $UE_VERSION, "`"$GAME_PAKS_PATH`"", "`"$OUTPUT_DIR`""

    Write-Host "Running command: $RETOC_EXE_PATH $($arguments -join ' ')"
    
    $process = Start-Process -FilePath $RETOC_EXE_PATH -ArgumentList $arguments -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) {
        throw "Retoc failed with exit code $($process.ExitCode)."
    }
    
    Write-Host "Success: Legacy assets converted to $OUTPUT_DIR"
} catch {
    Write-Host "Error running Retoc: $_"
    exit 1
}
