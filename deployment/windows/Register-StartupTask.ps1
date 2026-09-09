[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu-24.04',
    [ValidatePattern('^(8501|8503)(,(8501|8503))*$')]
    [string]$UiPorts = '8501',
    [string]$TaskName = 'Monitor WSL Kiosk Service'
)
$ErrorActionPreference = 'Stop'
if ($Distro -notmatch '^[A-Za-z0-9._-]+$') { throw 'Invalid distro name.' }
# Run from an elevated PowerShell window. No passwords or stored credentials.
$scriptPath = 'C:\Scripts\Start-EphemerAl.ps1'
New-Item -ItemType Directory -Path 'C:\Scripts' -Force | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'Start-EphemerAl.ps1') $scriptPath -Force
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`" -Distro $Distro -UiPorts $UiPorts"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn
$trigger.Delay = 'PT30S'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Output "Registered $TaskName for logon. Firewall rules were not modified."
