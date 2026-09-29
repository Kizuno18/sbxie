#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$ConfigPath = 'C:\Program Files\Sandboxie-Plus\Sandboxie.ini'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$encoding = New-Object System.Text.UnicodeEncoding($false, $true)
$text = [IO.File]::ReadAllText($ConfigPath, $encoding)
$text = [regex]::Replace($text, '(?ms)\r?\n\[PXG-Isolated\].*?(?=\r?\n\[|\z)', '')
[IO.File]::WriteAllText($ConfigPath, $text.TrimEnd() + "`r`n", $encoding)
Write-Output 'Invalid Sandboxie box section removed'
