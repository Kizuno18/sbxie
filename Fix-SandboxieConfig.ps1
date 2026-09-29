#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$ConfigPath = 'C:\Windows\Sandboxie.ini'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$encoding = New-Object System.Text.UnicodeEncoding($false, $true)
$text = [IO.File]::ReadAllText($ConfigPath, $encoding)
$text = [regex]::Replace($text, '(?ms)^\[PXG-Isolated\]\r?\n.*?(?=^\[|\z)', '')
[IO.File]::WriteAllText($ConfigPath, $text, $encoding)
Stop-Service -Name SbieSvc -Force -ErrorAction SilentlyContinue
Stop-Service -Name SbieDrv -Force -ErrorAction SilentlyContinue
Start-Service -Name SbieDrv
Start-Service -Name SbieSvc
Write-Output 'Sandboxie configuration repaired and services restarted'
