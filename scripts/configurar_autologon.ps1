param (
    [string]$Action = "enable",
    [string]$Username = "piloto",
    [string]$Password = "piloto@gd04"
)

function Test-Admin {
    $user = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal $user
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "[*] Solicitando privilegios de Administrador para configurar o Registro do Windows..." -ForegroundColor Yellow
    $scriptPath = $MyInvocation.MyCommand.Path
    $argList = "-ExecutionPolicy Bypass -File `"$scriptPath`" -Action $Action -Username `"$Username`" -Password `"$Password`""
    Start-Process powershell -Verb RunAs -ArgumentList $argList -Wait
    exit
}

$RegPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

if ($Action -eq "enable") {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "       CONFIGURANDO AUTOLOGON DO WINDOWS" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Set-ItemProperty -Path $RegPath -Name "AutoAdminLogon" -Value "1" -Type String
    Set-ItemProperty -Path $RegPath -Name "DefaultUserName" -Value $Username -Type String
    Set-ItemProperty -Path $RegPath -Name "DefaultPassword" -Value $Password -Type String
    if (-not (Get-ItemProperty -Path $RegPath -Name "DefaultDomainName" -ErrorAction SilentlyContinue)) {
        Set-ItemProperty -Path $RegPath -Name "DefaultDomainName" -Value $env:COMPUTERNAME -Type String
    }
    
    Write-Host "[OK] AutoLogon ATIVADO com sucesso para o usuario: $Username" -ForegroundColor Green
    Write-Host "     O computador agora fara login automaticamente ao ligar na tomada." -ForegroundColor White
    Write-Host ""
} elseif ($Action -eq "disable") {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host "       DESATIVANDO AUTOLOGON DO WINDOWS" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host ""
    
    Set-ItemProperty -Path $RegPath -Name "AutoAdminLogon" -Value "0" -Type String
    Remove-ItemProperty -Path $RegPath -Name "DefaultPassword" -ErrorAction SilentlyContinue
    
    Write-Host "[OK] AutoLogon DESATIVADO com sucesso." -ForegroundColor Green
    Write-Host ""
} elseif ($Action -eq "status") {
    $auto = (Get-ItemProperty -Path $RegPath -Name "AutoAdminLogon" -ErrorAction SilentlyContinue).AutoAdminLogon
    $user = (Get-ItemProperty -Path $RegPath -Name "DefaultUserName" -ErrorAction SilentlyContinue).DefaultUserName
    
    Write-Host ""
    Write-Host "Status do AutoLogon:" -ForegroundColor Cyan
    if ($auto -eq "1") {
        Write-Host "  AutoAdminLogon : ATIVO (Usuario: $user)" -ForegroundColor Green
    } else {
        Write-Host "  AutoAdminLogon : INATIVO" -ForegroundColor Yellow
    }
    Write-Host ""
}
