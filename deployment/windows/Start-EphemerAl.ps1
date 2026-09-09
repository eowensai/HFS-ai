[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu-24.04',
    [ValidatePattern('^(8501|8503)(,(8501|8503))*$')]
    [string]$UiPorts = '8501'
)
$ErrorActionPreference = 'Stop'
$netsh = Join-Path $env:SystemRoot 'System32\netsh.exe'
$wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
# Existing host uses -UiPorts '8501,8503'. Standalone EphemerAI uses 8501.
# Firewall rules are provisioned separately. Never create/widen them at logon.
$addresses = (& $wsl -d $Distro -- hostname -I) -join ' '
if ($LASTEXITCODE -ne 0) { throw 'WSL address discovery failed.' }
$wslIP = $addresses.Trim().Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries) |
    Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' } | Select-Object -First 1
$parsed = $null
if (-not $wslIP -or -not [System.Net.IPAddress]::TryParse($wslIP, [ref]$parsed)) {
    throw 'No valid WSL IPv4 address was found.'
}
foreach ($port in ($UiPorts.Split(',') | Select-Object -Unique)) {
    & $netsh interface portproxy delete v4tov4 listenport=$port listenaddress=0.0.0.0 2>$null
    & $netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$wslIP
    if ($LASTEXITCODE -ne 0) { throw "Could not refresh the TCP $port forwarding entry." }
}
# Docker/systemd + existing container restart policies start the stack as WSL boots.
& $wsl -d $Distro -- sleep infinity
