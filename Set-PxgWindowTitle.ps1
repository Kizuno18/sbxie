#requires -RunAsAdministrator
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
foreach ($path in @('C:\Program Files\Sandboxie-Plus\Sandboxie.ini', 'C:\Windows\Sandboxie.ini')) {
    $bytes = [IO.File]::ReadAllBytes($path)
    if ($bytes[0] -ne 255 -or $bytes[1] -ne 254) {
        throw "Expected UTF-16LE configuration: $path"
    }
    $text = [IO.File]::ReadAllText($path)
    $section = [regex]::new('(?ms)^\[PXG_Isolated\]\r?\n.*?(?=^\[|\z)')
    if ($section.Matches($text).Count -ne 1) {
        throw "Expected exactly one PXG_Isolated section: $path"
    }
    $updated = $section.Replace($text, [Text.RegularExpressions.MatchEvaluator]{
        param($match)
        $body = [regex]::Replace($match.Value, '(?m)^BoxNameTitle=[^\r\n]*\r?\n?', '')
        return $body.TrimEnd() + "`r`nBoxNameTitle=-`r`n"
    })
    if ($updated -cne $text) {
        $backup = $path + '.before-title-' + [Guid]::NewGuid().ToString('N') + '.bak'
        Copy-Item -LiteralPath $path -Destination $backup
        [IO.File]::WriteAllText($path, $updated, [Text.Encoding]::Unicode)
    }
    if ([IO.File]::ReadAllText($path) -cne $updated) {
        throw "Configuration verification failed: $path"
    }
}
$reload = Start-Process -FilePath 'C:\Program Files\Sandboxie-Plus\32\Start.exe' -ArgumentList '/reload' -Wait -PassThru
if ($reload.ExitCode -ne 0) { throw 'Sandboxie configuration reload failed' }
