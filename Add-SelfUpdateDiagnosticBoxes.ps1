#requires -RunAsAdministrator
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$diagnosticPaths = @('C:\Program Files\Sandboxie-Plus\Sandboxie.ini', 'C:\Windows\Sandboxie.ini')
$diagnosticSections = @"

[SelfUpdateDiagV1]
Enabled=y
BlockNetworkFiles=y
DropAdminRights=y
ConfigLevel=10
UseFileDeleteV2=n
UseRegDeleteV2=n

[SelfUpdateDiagV2]
Enabled=y
BlockNetworkFiles=y
DropAdminRights=y
ConfigLevel=10
UseFileDeleteV2=y
UseRegDeleteV2=n
"@
$diagnosticUpdates = foreach ($diagnosticPath in $diagnosticPaths) {
    $diagnosticBytes = [IO.File]::ReadAllBytes($diagnosticPath)
    if ($diagnosticBytes.Length -lt 2 -or $diagnosticBytes[0] -ne 255 -or $diagnosticBytes[1] -ne 254) {
        throw "Expected UTF-16LE configuration: $diagnosticPath"
    }
    $diagnosticText = [IO.File]::ReadAllText($diagnosticPath)
    if ($diagnosticText -match '(?m)^\[SelfUpdateDiagV[12]\]') {
        throw "Diagnostic box name already exists: $diagnosticPath"
    }
    [pscustomobject]@{
        Path = $diagnosticPath
        Original = $diagnosticText
        Updated = $diagnosticText.TrimEnd() + "`r`n" + ($diagnosticSections -replace '\r?\n', "`r`n") + "`r`n"
    }
}
foreach ($diagnosticUpdate in $diagnosticUpdates) {
    if ([IO.File]::ReadAllText($diagnosticUpdate.Path) -cne $diagnosticUpdate.Original) {
        throw "Configuration changed during preparation: $($diagnosticUpdate.Path)"
    }
    $diagnosticBackup = $diagnosticUpdate.Path + '.before-selfupdate-' + [Guid]::NewGuid().ToString('N') + '.bak'
    Copy-Item -LiteralPath $diagnosticUpdate.Path -Destination $diagnosticBackup
    [IO.File]::WriteAllText($diagnosticUpdate.Path, $diagnosticUpdate.Updated, [Text.Encoding]::Unicode)
    if ([IO.File]::ReadAllText($diagnosticUpdate.Path) -cne $diagnosticUpdate.Updated) {
        throw "Configuration verification failed: $($diagnosticUpdate.Path)"
    }
}
$diagnosticReload = Start-Process -FilePath 'C:\Program Files\Sandboxie-Plus\32\Start.exe' -ArgumentList '/reload' -Wait -PassThru -WindowStyle Hidden
if ($diagnosticReload.ExitCode -ne 0) { throw 'Sandboxie configuration reload failed' }
