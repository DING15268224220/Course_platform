param(
    [ValidateSet("menu", "web", "desktop", "install", "check", "test", "build")]
    [string]$Action = "menu"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $ProjectRoot "backend"
$DesktopDir = Join-Path $ProjectRoot "desktop"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$WebPort = 5080

function Find-Python {
    if ($env:PLATFORM_PYTHON -and (Test-Path -LiteralPath $env:PLATFORM_PYTHON)) {
        return $env:PLATFORM_PYTHON
    }
    if (Test-Path -LiteralPath "D:\Anaconda\python.exe") {
        return "D:\Anaconda\python.exe"
    }
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $command = Get-Command py -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    return $null
}

function Pause-Launcher {
    if ($Action -eq "menu") {
        Write-Host ""
        [void](Read-Host "按 Enter 键返回菜单")
    }
}

function Assert-Python {
    $python = Find-Python
    if (-not $python) {
        throw "未找到 Python。请安装 Python 3.10 或更高版本。"
    }
    return $python
}

function Install-PythonRuntime {
    $python = Assert-Python
    & $python -c "import flask, waitress, openpyxl" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "正在安装 Python 运行依赖..." -ForegroundColor Cyan
        & $python -m pip install -r (Join-Path $BackendDir "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Python 运行依赖安装失败。" }
    }
    return $python
}

function Assert-Npm {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "未找到 npm。请安装 Node.js 22.12 或更高版本。"
    }
    return $npm.Source
}

function Start-Web {
    $python = Install-PythonRuntime
    $env:PORT = [string]$WebPort
    $url = "http://127.0.0.1:$WebPort/?version=3.1.0"
    Write-Host "正在启动网页版：$url" -ForegroundColor Green
    Write-Host "运行期间请保持此窗口开启；按 Ctrl+C 可停止服务。" -ForegroundColor DarkGray

    $currentPowerShell = (Get-Process -Id $PID).Path
    $waitCommand = "for (`$i=0; `$i -lt 30; `$i++) { try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:$WebPort/api/session' -TimeoutSec 1 | Out-Null; Start-Process '$url'; break } catch { Start-Sleep -Milliseconds 500 } }"
    Start-Process -FilePath $currentPowerShell -WindowStyle Hidden -ArgumentList @("-NoLogo", "-NoProfile", "-Command", $waitCommand) | Out-Null
    & $python (Join-Path $BackendDir "app.py")
    if ($LASTEXITCODE -ne 0) { throw "网页版启动失败。" }
}

function Start-Desktop {
    [void](Install-PythonRuntime)
    $npm = Assert-Npm
    Push-Location $DesktopDir
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $DesktopDir "node_modules\electron\dist\electron.exe"))) {
            Write-Host "首次运行，正在按照 package-lock.json 安装桌面端依赖..." -ForegroundColor Cyan
            & $npm install
            if ($LASTEXITCODE -ne 0) { throw "桌面端依赖安装失败。" }
        }
        & $npm run desktop
        if ($LASTEXITCODE -ne 0) { throw "桌面版启动失败。" }
    }
    finally {
        Pop-Location
    }
}

function Install-All {
    $python = Assert-Python
    Write-Host "正在安装 Python 运行与测试依赖..." -ForegroundColor Cyan
    & $python -m pip install -r (Join-Path $BackendDir "requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) { throw "Python 测试依赖安装失败。" }
    Write-Host "正在安装桌面打包依赖..." -ForegroundColor Cyan
    & $python -m pip install -r (Join-Path $DesktopDir "requirements-desktop.txt")
    if ($LASTEXITCODE -ne 0) { throw "桌面打包依赖安装失败。" }
    $npm = Assert-Npm
    Push-Location $DesktopDir
    try {
        & $npm install
        if ($LASTEXITCODE -ne 0) { throw "Node.js 依赖安装失败。" }
    }
    finally {
        Pop-Location
    }
    Write-Host "全部环境安装完成。" -ForegroundColor Green
}

function Check-Environment {
    Write-Host ""
    Write-Host "[Python]" -ForegroundColor Cyan
    $python = Find-Python
    if ($python) {
        & $python --version
        & $python -m pip --version
    }
    else {
        Write-Host "未安装 Python" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "[Node.js]" -ForegroundColor Cyan
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($node) { & $node.Source --version } else { Write-Host "未安装 Node.js" -ForegroundColor Yellow }
    if ($npm) { & $npm.Source --version } else { Write-Host "未安装 npm" -ForegroundColor Yellow }

    Write-Host ""
    Write-Host "[项目文件]" -ForegroundColor Cyan
    $checks = @(
        @{ Name = "后端"; Path = (Join-Path $BackendDir "app.py") },
        @{ Name = "前端"; Path = (Join-Path $FrontendDir "index.html") },
        @{ Name = "桌面端"; Path = (Join-Path $DesktopDir "main.cjs") },
        @{ Name = "环境清单"; Path = (Join-Path $ProjectRoot "1、环境清单.txt") },
        @{ Name = "系统说明"; Path = (Join-Path $ProjectRoot "3、系统说明.txt") }
    )
    foreach ($check in $checks) {
        $status = if (Test-Path -LiteralPath $check.Path) { "正常" } else { "缺失" }
        Write-Host ("{0}：{1}" -f $check.Name, $status)
    }
}

function Invoke-Tests {
    $python = Assert-Python
    & $python -c "import pytest" 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $python -m pip install -r (Join-Path $BackendDir "requirements-dev.txt")
        if ($LASTEXITCODE -ne 0) { throw "pytest 安装失败。" }
    }
    $previousBytecode = $env:PYTHONDONTWRITEBYTECODE
    $env:PYTHONDONTWRITEBYTECODE = "1"
    try {
        & $python -m pytest (Join-Path $BackendDir "tests") -q -p no:cacheprovider
        if ($LASTEXITCODE -ne 0) { throw "后端测试失败。" }
    }
    finally {
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
    }
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        & $node.Source --check (Join-Path $FrontendDir "app.js")
        & $node.Source --check (Join-Path $DesktopDir "main.cjs")
        if ($LASTEXITCODE -ne 0) { throw "JavaScript 语法检查失败。" }
    }
    Write-Host "全部测试通过。" -ForegroundColor Green
}

function Build-Desktop {
    $python = Assert-Python
    $npm = Assert-Npm
    & $python -m pip install -r (Join-Path $DesktopDir "requirements-desktop.txt")
    if ($LASTEXITCODE -ne 0) { throw "桌面打包依赖安装失败。" }
    Push-Location $DesktopDir
    try {
        & $npm install
        if ($LASTEXITCODE -ne 0) { throw "Node.js 依赖安装失败。" }
        & $npm run dist:win
        if ($LASTEXITCODE -ne 0) { throw "桌面便携版构建失败。" }
    }
    finally {
        Pop-Location
    }
    Write-Host "构建完成，产物位于 desktop\release。" -ForegroundColor Green
}

function Invoke-Action([string]$SelectedAction) {
    switch ($SelectedAction) {
        "web" { Start-Web }
        "desktop" { Start-Desktop }
        "install" { Install-All; Pause-Launcher }
        "check" { Check-Environment; Pause-Launcher }
        "test" { Invoke-Tests; Pause-Launcher }
        "build" { Build-Desktop; Pause-Launcher }
    }
}

if ($Action -ne "menu") {
    try {
        Invoke-Action $Action
        exit 0
    }
    catch {
        Write-Host ""
        Write-Host ("操作失败：{0}" -f $_.Exception.Message) -ForegroundColor Red
        exit 1
    }
}

while ($true) {
    Clear-Host
    Write-Host "==================================================" -ForegroundColor Blue
    Write-Host "   高校课程项目协作与评审平台 V3.1" -ForegroundColor White
    Write-Host "==================================================" -ForegroundColor Blue
    Write-Host "  1. 启动网页版"
    Write-Host "  2. 启动桌面版"
    Write-Host "  3. 安装或更新运行环境"
    Write-Host "  4. 检查环境"
    Write-Host "  5. 运行自动化测试"
    Write-Host "  6. 构建 Windows 桌面便携版"
    Write-Host "  Q. 退出"
    Write-Host "==================================================" -ForegroundColor Blue
    $choice = (Read-Host "请输入选项").Trim().ToUpperInvariant()
    if ($choice -eq "Q") { break }
    $actionMap = @{ "1" = "web"; "2" = "desktop"; "3" = "install"; "4" = "check"; "5" = "test"; "6" = "build" }
    if (-not $actionMap.ContainsKey($choice)) { continue }
    try {
        Invoke-Action $actionMap[$choice]
    }
    catch {
        Write-Host ""
        Write-Host ("操作失败：{0}" -f $_.Exception.Message) -ForegroundColor Red
        [void](Read-Host "按 Enter 键返回菜单")
    }
}
