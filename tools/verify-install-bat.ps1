$ErrorActionPreference = 'Stop'

$installBat = Join-Path $PSScriptRoot 'install.bat'
$content = Get-Content $installBat -Raw
$bytes = [System.IO.File]::ReadAllBytes($installBat)

$checks = @(
    @{
        Name = 'supports PIP_INDEX_URL override'
        Pattern = 'PIP_INDEX_URL'
    }
    @{
        Name = 'defines pip fallback installer label'
        Pattern = ':install_with_fallback'
    }
    @{
        Name = 'extends pip timeout'
        Pattern = '--default-timeout'
    }
    @{
        Name = 'defines progress helper'
        Pattern = ':show_progress'
    }
    @{
        Name = 'defines info logging helper'
        Pattern = ':log_info'
    }
    @{
        Name = 'logs step details with timestamps'
        Pattern = '[INFO !TS!]'
    }
    @{
        Name = 'defines log file initializer'
        Pattern = ':init_log_file'
    }
    @{
        Name = 'uses configurable log file path'
        Pattern = 'INSTALL_LOG_FILE'
    }
    @{
        Name = 'prewarms rembg model cache'
        Pattern = 'new_session(model)'
    }
    @{
        Name = 'warns when rembg prewarm fails'
        Pattern = '首次抠图时会自动下载'
    }
)

$failed = @()
foreach ($check in $checks) {
    if ($content -notmatch [regex]::Escape($check.Pattern)) {
        $failed += $check.Name
    }
}

if ($failed.Count -gt 0) {
    Write-Error ("install.bat verification failed: missing " + ($failed -join ', '))
}

if ($content -match 'npm install --silent') {
    Write-Error 'install.bat verification failed: npm install is still silent'
}

if ($content -match '--quiet') {
    Write-Error 'install.bat verification failed: pip install is still quiet'
}

if ($content -match 'python -m pip install --disable-pip-version-check --default-timeout 60 --retries 2 --index-url "!PIP_SOURCE!" %\*') {
    Write-Error 'install.bat verification failed: pip helper still passes %* directly after source argument'
}

$crlf = 0
$loneLf = 0
for ($i = 0; $i -lt $bytes.Length; $i++) {
    if ($bytes[$i] -eq 10) {
        if ($i -gt 0 -and $bytes[$i - 1] -eq 13) {
            $crlf++
        } else {
            $loneLf++
        }
    }
}

if ($loneLf -gt 0) {
    Write-Error "install.bat verification failed: found $loneLf lone LF line endings"
}

Write-Host 'install.bat verification passed'