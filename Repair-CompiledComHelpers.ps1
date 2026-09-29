#requires -RunAsAdministrator
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$package = Join-Path $PSScriptRoot 'Compiled-Sandboxie\Package\x64\SbieRelease'
$destination = 'C:\Program Files\Sandboxie-Plus'
foreach ($name in @('SandboxieRpcSs.exe', 'SandboxieDcomLaunch.exe')) {
    $source = Join-Path $package $name
    $target = Join-Path $destination $name
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing compiled helper: $source"
    }
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
            throw "Refusing to overwrite an existing different helper: $target"
        }
    } else {
        Copy-Item -LiteralPath $source -Destination $target
    }
    if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
        throw "Helper verification failed: $target"
    }
}
