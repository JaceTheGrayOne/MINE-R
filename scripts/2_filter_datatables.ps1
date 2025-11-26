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

try {
    $filterPatterns = @("DT_*.uasset", "Table_*.uasset", "Text_enus.uasset")
    $uassetFiles = @()

    foreach ($pattern in $filterPatterns) {
        $uassetFiles += Get-ChildItem -Path $SOURCE_DIR -Recurse -File -Filter $pattern
    }

    $uassetFiles = $uassetFiles | Sort-Object -Property FullName -Unique
    Write-Host "Found $($uassetFiles.Count) data table .uasset files to copy (filtered by individual filters)."

    $totalFilesCopied = 0

    # Copy .uasset files and their companion .uexp files
    foreach ($file in $uassetFiles) {
        $relativePath = $file.FullName.Substring($SOURCE_DIR.Length).TrimStart('\','/')
        $destinationPath = Join-Path $DEST_DIR $relativePath

        # Ensure the destination subdirectory exists
        New-Item -ItemType Directory -Force -Path (Split-Path $destinationPath -Parent) | Out-Null

        # Copy the .uasset file
        Copy-Item -LiteralPath $file.FullName -Destination $destinationPath -Force
        $totalFilesCopied++

        # Copy the companion .uexp file if it exists
        $uexpPath = [System.IO.Path]::ChangeExtension($file.FullName, ".uexp")
        if (Test-Path $uexpPath) {
            $uexpDestPath = [System.IO.Path]::ChangeExtension($destinationPath, ".uexp")
            Copy-Item -LiteralPath $uexpPath -Destination $uexpDestPath -Force
            $totalFilesCopied++
        }
    }

    Write-Host "Success: Copied $totalFilesCopied total files (including .uexp companions) to $DEST_DIR"
} catch {
    Write-Host "Error: Failed to filter data tables. Is '$SOURCE_DIR' populated?"
    Write-Host $_
    exit 1
}
