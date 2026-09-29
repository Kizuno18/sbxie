#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$PackageRoot = 'C:\Users\Big\Desktop\sbxie\Compiled-Sandboxie\Package',
    [string]$InstallRoot = 'C:\Program Files\Sandboxie-Plus'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$x64 = Join-Path $PackageRoot 'x64\SbieRelease'
$win32 = Join-Path $PackageRoot 'Win32\SbieRelease'
$required = @(
    (Join-Path $x64 'SbieDrv.sys'),
    (Join-Path $x64 'SbieSvc.exe'),
    (Join-Path $x64 'SbieDll.dll'),
    (Join-Path $x64 'SbieMsg.dll'),
    (Join-Path $x64 'KmdUtil.exe'),
    (Join-Path $x64 'SandboxieRpcSs.exe'),
    (Join-Path $x64 'SandboxieDcomLaunch.exe'),
    (Join-Path $win32 'SbieDll.dll'),
    (Join-Path $win32 'SbieMsg.dll'),
    (Join-Path $win32 'SboxHostDll.dll')
)

foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required compiled file is missing: $path"
    }
}

New-Item -ItemType Directory -Force -Path $InstallRoot, (Join-Path $InstallRoot '32') | Out-Null
Copy-Item -LiteralPath "$x64\SbieDrv.sys", "$x64\SbieSvc.exe", "$x64\SbieDll.dll", "$x64\SbieMsg.dll", "$x64\KmdUtil.exe" -Destination $InstallRoot -Force
Copy-Item -LiteralPath "$x64\SandboxieRpcSs.exe", "$x64\SandboxieDcomLaunch.exe" -Destination $InstallRoot -Force
Copy-Item -LiteralPath "$win32\SbieDll.dll", "$win32\SbieMsg.dll", "$win32\SboxHostDll.dll" -Destination (Join-Path $InstallRoot '32') -Force

$kmd = Join-Path $InstallRoot 'KmdUtil.exe'
& bcdedit.exe /set testsigning on
if ($LASTEXITCODE -ne 0) {
    throw "Could not enable Windows test signing"
}

& $kmd install SbieDrv (Join-Path $InstallRoot 'SbieDrv.sys') type=kernel start=demand ("msgfile=" + (Join-Path $InstallRoot 'SbieMsg.dll')) altitude=86900
if ($LASTEXITCODE -ne 0) {
    throw "Could not install SbieDrv"
}

$serviceImage = '"' + (Join-Path $InstallRoot 'SbieSvc.exe') + '"'
& $kmd install SbieSvc $serviceImage type=own start=auto 'display=Sandboxie Service' group=UIGroup ("msgfile=" + (Join-Path $InstallRoot 'SbieMsg.dll'))
if ($LASTEXITCODE -ne 0) {
    throw "Could not install SbieSvc"
}

New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\SbieSvc' -Name Language -PropertyType DWord -Value 1033 -Force | Out-Null
New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\SbieSvc' -Name PreferExternalManifest -PropertyType DWord -Value 1 -Force | Out-Null
Write-Output 'Compiled Sandboxie installed. Reboot is required before starting PXG'
