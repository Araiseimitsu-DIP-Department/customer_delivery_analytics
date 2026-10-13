# PostgreSQL 運用向け PyInstaller ビルド
param([string]$OutputDirectory = 'dist')

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $VenvPython) {
    $PythonPath = $VenvPython
} else {
    $PythonPath = (Get-Command python -ErrorAction Stop).Source
}
& $PythonPath -m PyInstaller --version
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller がありません。選択した Python 環境へ導入してください。'
}
$BuildDirectory = Join-Path $Root ('build\run-' + [guid]::NewGuid().ToString('N'))
if (-not [System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $Root $OutputDirectory
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$Verifier = Join-Path $Root 'scripts\verify_build.py'
$AccessModules = @(& $PythonPath $Verifier --excluded-modules)
if ($LASTEXITCODE -ne 0) { throw 'Access 依存の除外一覧を取得できませんでした。' }

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
    '--specpath', (Join-Path $BuildDirectory 'pyi_spec'),
    '--workpath', (Join-Path $BuildDirectory 'pyi_work'),
    '--distpath', $OutputDirectory,
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

foreach ($Module in $AccessModules) {
    $PyInstallerArgs += @('--exclude-module', $Module)
}

if (Test-Path $IconIco) {
    $PyInstallerArgs += @('--icon', $IconIco)
}

if (Test-Path $EnvFile) {
    $PyInstallerArgs += @('--add-data', "$EnvFile;.")
}

$PyInstallerArgs += "$Root\app\main.py"

& $PythonPath -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller ビルドに失敗しました。' }
$Executable = Join-Path $OutputDirectory ($ExeName + '.exe')
& $PythonPath $Verifier $Executable
if ($LASTEXITCODE -ne 0) { throw 'ビルド成果物の同梱物検査に失敗しました。' }
Write-Host ('ビルド・同梱物検査完了: {0}' -f $Executable)
