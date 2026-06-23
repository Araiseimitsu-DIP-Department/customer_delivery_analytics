# Customer Delivery Analytics - PyInstaller build script

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
Set-Location $Root

foreach ($path in @(
    (Join-Path $Root 'build'),
    (Join-Path $Root 'dist')
)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

$VenvPyInstaller = Join-Path $Root '.venv\Scripts\pyinstaller.exe'
$PyInstallerPath = $null
if (Test-Path -LiteralPath $VenvPyInstaller) {
    $PyInstallerPath = $VenvPyInstaller
} else {
    $Command = Get-Command pyinstaller -ErrorAction SilentlyContinue
    if ($Command) {
        $PyInstallerPath = $Command.Source
    }
}
if (-not $PyInstallerPath) {
    Write-Error 'PyInstaller was not found. Run .\.venv\Scripts\python.exe -m pip install pyinstaller and retry.'
}

$ExeName = -join @(
    [char]0x9867,
    [char]0x5ba2,
    [char]0x5225,
    [char]0x7d0d,
    [char]0x5165,
    [char]0x5206,
    [char]0x6790,
    [char]0x30b7,
    [char]0x30b9,
    [char]0x30c6,
    [char]0x30e0
)
$IconPng = Join-Path $Root 'docs\icon.png'
$IconIco = Join-Path $Root 'docs\icon.ico'
$EnvFile = Join-Path $Root '.env'
$PyInstallerArgs = @(
    '--noconfirm',
    '--windowed',
    '--onefile',
    '--name', $ExeName,
    '--specpath', (Join-Path $Root 'build\pyi_spec'),
    '--workpath', (Join-Path $Root 'build\pyi_work'),
    '--paths', $Root,
    '--hidden-import', 'app.webview_app',
    '--hidden-import', 'webview',
    '--hidden-import', 'psycopg',
    '--hidden-import', 'psycopg_binary',
    '--exclude-module', 'scipy',
    '--exclude-module', 'sklearn',
    '--exclude-module', 'pytest',
    '--exclude-module', 'pyarrow',
    '--add-data', "$IconPng;docs",
    '--add-data', "$Root\app\web;app\web",
    '--add-data', "$Root\docs\DESIGN\arai_logo.png;docs\DESIGN",
    '--clean'
)

if (Test-Path $IconIco) {
    $PyInstallerArgs += @('--icon', $IconIco)
}

if (Test-Path $EnvFile) {
    $PyInstallerArgs += @('--add-data', "$EnvFile;.")
}

$PyInstallerArgs += "$Root\app\main.py"

& $PyInstallerPath @PyInstallerArgs
Write-Host ('Done (onefile): dist\{0}.exe only - no extra files required beside the .exe.' -f $ExeName)
