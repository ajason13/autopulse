#requires -Version 7.0
<#
.SYNOPSIS
Verify one native Windows x64 CPython cell in a clean, spaced-path checkout.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$Commit,
    [Parameter(Mandatory)][string]$WorkRoot
)

$ErrorActionPreference = 'Stop'
# Explicit checks also work when the caller disables PowerShell's native error preference.
$PSNativeCommandUseErrorActionPreference = $false

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    Write-Host ('> ' + $Executable + ' ' + ($Arguments -join ' '))
    & $Executable @Arguments
    $code = $LASTEXITCODE
    Write-Host "Exit code: $code"
    if ($code -ne 0) { throw "Native command failed with exit code ${code}: $Executable" }
}

$savedEnvironment = @{}
foreach ($name in @('PYTHONPATH', 'PYTHONHOME', 'TEMP', 'TMP')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$originalLocation = Get-Location
$transcribing = $false
try {
    if (-not $IsWindows) { throw 'Run on native Windows, not WSL.' }
    $repository = Split-Path $PSScriptRoot -Parent
    $Python = (Resolve-Path -LiteralPath $Python).Path
    $WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
    if ($WorkRoot -notmatch ' ') { throw 'WorkRoot must contain a space.' }
    if (Test-Path -LiteralPath $WorkRoot) { throw 'WorkRoot must not already exist.' }
    # Probe before creating any work: unsupported interpreters fail closed.
    Invoke-Checked $Python @('-I', '-c', 'import platform, sys; assert sys.platform == "win32"; assert platform.python_implementation() == "CPython"; assert sys.version_info[:2] in ((3,13),(3,14)); assert platform.machine() == "AMD64"; print(sys.version); print(sys.executable)')
    New-Item -ItemType Directory -Path $WorkRoot | Out-Null
    Start-Transcript -LiteralPath (Join-Path $WorkRoot 'commands.log') | Out-Null
    $transcribing = $true
    $os = Get-CimInstance Win32_OperatingSystem
    $version = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    Write-Host "OS: $($os.Caption); $($os.Version).$($version.UBR); $($version.DisplayVersion); $($os.OSArchitecture)"
    Write-Host "PowerShell: $($PSVersionTable.PSVersion); tested commit: $Commit"
    Invoke-Checked $Python @('-I', '-c', 'import platform, sys; print(platform.platform()); print(sys.version); print(sys.executable)')
    $source = Join-Path $WorkRoot 'source checkout'
    Invoke-Checked 'git' @('clone', '--no-hardlinks', '--no-checkout', '--', $repository, $source)
    Set-Location -LiteralPath $source
    Invoke-Checked 'git' @('checkout', '--detach', $Commit)
    $actual = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $actual -ne $Commit) { throw 'Checkout commit mismatch.' }
    $dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'Expected clean checkout.' }

    [Environment]::SetEnvironmentVariable('PYTHONPATH', $null, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONHOME', $null, 'Process')
    $outside = Join-Path $WorkRoot 'outside checkout'
    New-Item -ItemType Directory -Path $outside | Out-Null
    $env:TEMP = $outside
    $env:TMP = $outside
    $development = Join-Path $WorkRoot 'development environment'
    Invoke-Checked $Python @('-m', 'venv', $development)
    $devPython = Join-Path $development 'Scripts\python.exe'
    Invoke-Checked $devPython @('-m', 'pip', 'install', '--upgrade', 'pip')
    Invoke-Checked $devPython @('-m', 'pip', 'install', '-e', '.[dev]', '-r', 'requirements-release.txt')
    Invoke-Checked $devPython @('-m', 'pip', 'check')
    $requirements = Join-Path $WorkRoot 'locked requirements.txt'
    $wheelhouse = Join-Path $WorkRoot 'wheelhouse'
    $artifacts = Join-Path $WorkRoot 'artifacts'
    Invoke-Checked $devPython @('-m', 'uv', 'export', '--locked', '--all-extras', '--no-emit-project', '--format', 'requirements-txt', '--output-file', $requirements)
    Invoke-Checked $devPython @('-m', 'pip', 'download', '--only-binary=:all:', '--dest', $wheelhouse, '-r', $requirements)
    Invoke-Checked $devPython @('scripts/build_release_artifacts.py', '--output', $artifacts, '--source-date-epoch', '0')
    $wheel = Join-Path $artifacts 'autopulse-0.1.0-py3-none-any.whl'
    $sdist = Join-Path $artifacts 'autopulse-0.1.0.tar.gz'
    Invoke-Checked $devPython @('-m', 'twine', 'check', $wheel, $sdist)
    Invoke-Checked $devPython @('-m', 'check_wheel_contents', $wheel)
    $installed = Join-Path $WorkRoot 'installed environment'
    Invoke-Checked $devPython @('scripts/verify_release_cell.py', '--wheel', $wheel, '--sdist', $sdist, '--wheelhouse', $wheelhouse, '--locked-requirements', $requirements, '--environment', $installed, '--summary', (Join-Path $WorkRoot 'cell-summary.md'), '--manifest-output', (Join-Path $WorkRoot 'wheelhouse.json'))

    Set-Location -LiteralPath $outside
    $installedPython = Join-Path $installed 'Scripts\python.exe'
    $cli = Join-Path $installed 'Scripts\autopulse-debug.exe'
    Invoke-Checked $installedPython @('-I', '-c', 'from importlib.resources import files; assert all(files("autopulse.schemas").joinpath(name + "_obd_frame.schema.json").is_file() for name in ("engine", "ev"))')
    Invoke-Checked $cli @('--help')
    $ice = @{timestamp='2026-05-26T10:00:00Z'; vin_hashed=('a' * 64); protocol='SAE_J1979'; engine_rpm=900; vehicle_speed=0; coolant_temp=88; engine_load=5; stft_bank1=0; ltft_bank1=0}
    $ev = @{timestamp='2026-05-26T10:00:00Z'; vin_hashed=('b' * 64); protocol='SAE_J1979-3'; powertrain_type='EV'; payload=@{battery_soh=95; battery_soce=90; battery_temp_avg=25}}
    foreach ($cell in @(@('ICE', $ice, 'replay-ice'), @('EV', $ev, 'replay-ev'))) {
        $fixture = Join-Path $outside ($cell[0] + '.jsonl')
        $cell[1] | ConvertTo-Json -Compress | Set-Content -LiteralPath $fixture -Encoding utf8NoBOM
        $validation = Invoke-Checked $cli @('validate-frame', '--powertrain', $cell[0], '--file', $fixture) | ConvertFrom-Json
        if ($validation.ok -ne $true) { throw 'Installed validation failed.' }
        $replay = Invoke-Checked $cli @($cell[2], '--jsonl', $fixture) | ConvertFrom-Json
        Write-Host ($replay | ConvertTo-Json -Compress -Depth 10)
        if ($replay.accepted_frames -ne 1 -or $replay.rejected_frames -ne 0 -or $replay.security_violations -ne 0) { throw 'Installed replay accounting failed.' }
    }
    Set-Location -LiteralPath $source
    Invoke-Checked $devPython @('-m', 'pytest', '-q', '-ra', '--junitxml', (Join-Path $WorkRoot 'pytest.xml'))
    Write-Host 'Native Windows Python cell: PASS'
} catch {
    Write-Error -ErrorAction Continue $_
    exit 1
} finally {
    Set-Location -LiteralPath $originalLocation
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    if ($transcribing) { Stop-Transcript | Out-Null }
}
