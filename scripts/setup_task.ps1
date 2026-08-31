param (
    [string]$Action = "register",
    [int]$IntervalMinutes = 2,
    [string]$Username = "piloto",
    [string]$Password = "piloto@gd04"
)

$TaskName = "AISlopStudio_AutoRecovery"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = Get-Location }
if ((Split-Path -Leaf $ScriptDir) -eq "scripts") {
    $ProjectDir = Split-Path -Parent $ScriptDir
} else {
    $ProjectDir = $ScriptDir
}

$TargetBat = Join-Path $ProjectDir "scripts\auto_recovery.bat"
if (-not (Test-Path $TargetBat)) {
    $TargetBat = Join-Path $ProjectDir "auto_recovery.bat"
}

$WatchdogPy = Join-Path $ProjectDir "src\watchdog.py"
if (-not (Test-Path $WatchdogPy)) {
    $WatchdogPy = Join-Path $ProjectDir "watchdog.py"
}

$StartupFolder = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Startup)
$ShortcutPath = Join-Path $StartupFolder "AISlopStudio_AutoRecovery.lnk"

function Register-AutoStartup {
    param ([int]$Interval = $IntervalMinutes)

    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  CONFIGURANDO WATCHDOG E RECUPERACAO AUTOMATICA" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[*] Diretorio do Projeto: $ProjectDir" -ForegroundColor Gray
    Write-Host "[*] Script Alvo         : $TargetBat" -ForegroundColor Gray
    Write-Host "[*] Intervalo de Checagem: A cada $Interval minuto(s)" -ForegroundColor Gray
    Write-Host ""

    $taskRegistered = $false

    # Metodo 1: PowerShell ScheduledTasks API nativa (suporta multiplos triggers: Logon + Repeticao)
    Write-Host "[*] Registrando tarefa avancada com triggers (Logon + Intervalo de $Interval min)..." -ForegroundColor White
    try {
        $actionObj = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"`"$TargetBat`"`"" -WorkingDirectory $ProjectDir
        
        # Trigger 1: Ao Fazer Logon
        $trigLogon = New-ScheduledTaskTrigger -AtLogon
        
        # Trigger 2: Repeticao periodica (Watchdog a cada X minutos)
        $trigInterval = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes $Interval) -RepetitionDuration (New-TimeSpan -Days 3650)
        
        # Settings: Nao empilhar instancias (IgnoreNew), permitir na bateria, iniciar quando disponivel
        $settingsObj = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 72)
        
        # Principal: Execucao interativa como usuario logado
        $principalObj = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
        
        Register-ScheduledTask -TaskName $TaskName -Action $actionObj -Trigger @($trigLogon, $trigInterval) -Settings $settingsObj -Principal $principalObj -Force -ErrorAction Stop | Out-Null
        
        Write-Host "[OK] Tarefa '$TaskName' registrada com sucesso no Agendador de Tarefas!" -ForegroundColor Green
        Write-Host "     - Gatilho 1 : Ao fazer logon no Windows (AtLogon)" -ForegroundColor Green
        Write-Host "     - Gatilho 2 : Verificacao a cada $Interval minuto(s) para reabrir caso tenha sido fechado!" -ForegroundColor Green
        Write-Host "     - Politica  : Se ja estiver rodando, nao duplica; se fechado, reabre na hora." -ForegroundColor Green
        $taskRegistered = $true
    } catch {
        Write-Host "[INFO] Tentando registro via schtasks CLI com privilégios elevados..." -ForegroundColor Yellow
        
        # Fallback via schtasks CLI
        $cmd = "schtasks /Create /TN `"$TaskName`" /TR `"`"$TargetBat`"`" /SC MINUTE /MO $Interval /RL HIGHEST /F"
        $res = cmd.exe /c $cmd 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Tarefa registrada via schtasks (Intervalo: $Interval min)!" -ForegroundColor Green
            $taskRegistered = $true
        } else {
            try {
                $elevateCmd = "/c schtasks /Create /TN `"$TaskName`" /TR `"`"$TargetBat`"`" /SC MINUTE /MO $Interval /RL HIGHEST /F"
                $p = Start-Process -FilePath "cmd.exe" -ArgumentList $elevateCmd -Verb RunAs -PassThru -Wait
                if ($p.ExitCode -eq 0) {
                    Write-Host "[OK] Registrado via schtasks com privilegios elevados!" -ForegroundColor Green
                    $taskRegistered = $true
                }
            } catch {
                Write-Host "[AVISO] Falha ao registrar via schtasks: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
    }

    # Limpeza de atalhos redundantes na pasta Startup
    if (Test-Path $ShortcutPath) {
        Remove-Item $ShortcutPath -Force -ErrorAction SilentlyContinue
        Write-Host "[LIMPEZA] Atalho antigo na pasta Inicializar removido para evitar duplicidade." -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "[SUCESSO] Watchdog configurado com sucesso no Agendador de Tarefas!" -ForegroundColor Green
    Write-Host "  O gerador agora reiniciará sozinho sempre que for fechado ou após reinicialização." -ForegroundColor Yellow
}

function Register-BootStartup {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  CONFIGURANDO TAREFA NO BOOT DO SISTEMA (ONSTART)" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "[*] Registrando tarefa no Agendador para iniciar no Boot do SO..." -ForegroundColor White
    try {
        $elevateCmd = "/c schtasks /Create /TN `"$TaskName`" /TR `"`"$TargetBat`" --boot`" /SC ONSTART /RU `"$Username`" /RP `"$Password`" /RL HIGHEST /F"
        $p = Start-Process -FilePath "cmd.exe" -ArgumentList $elevateCmd -Verb RunAs -PassThru -Wait
        if ($p.ExitCode -eq 0) {
            Write-Host "[OK] Tarefa no Agendador criada para iniciar no BOOT (ONSTART) com a conta $Username!" -ForegroundColor Green
            if (Test-Path $ShortcutPath) {
                Remove-Item $ShortcutPath -Force -ErrorAction SilentlyContinue
            }
        } else {
            Write-Host "[ERRO] Nao foi possivel criar a tarefa de Boot com as credenciais fornecidas." -ForegroundColor Red
        }
    } catch {
        Write-Host "[ERRO] Falha ao executar elevacao: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Unregister-AutoStartup {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host "  REMOVENDO TAREFA DO WATCHDOG DO AGENDADOR DE TAREFAS" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host ""
    
    if (Test-Path $ShortcutPath) {
        Remove-Item $ShortcutPath -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Atalho removido da pasta Inicializar (Startup)." -ForegroundColor Green
    }

    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "[OK] Tarefa '$TaskName' removida do Agendador de Tarefas via PowerShell." -ForegroundColor Green
    } catch {
        $cmd = "schtasks /Delete /TN `"$TaskName`" /F"
        $res = cmd.exe /c $cmd 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Tarefa '$TaskName' removida via schtasks." -ForegroundColor Green
        } else {
            try {
                Start-Process -FilePath "cmd.exe" -ArgumentList "/c schtasks /Delete /TN `"$TaskName`" /F" -Verb RunAs -Wait
                Write-Host "[OK] Tarefa '$TaskName' removida com elevacao." -ForegroundColor Green
            } catch {
                Write-Host "[INFO] Nao foi possivel remover ou tarefa nao existia." -ForegroundColor Gray
            }
        }
    }
}

function Test-WatchdogCheck {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "        TESTE IMEDIATO DE CHECAGEM DO WATCHDOG" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "[*] Executando auto_recovery.bat..." -ForegroundColor White
    & cmd.exe /c "`"$TargetBat`""
    Write-Host "[OK] Teste de checagem concluido." -ForegroundColor Green
}

function Show-Status {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "      STATUS DO WATCHDOG E AGENDADOR DE TAREFAS" -ForegroundColor Cyan
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # 1. Checa status do processo gerador em tempo real
    Write-Host "  --- [STATUS DO PROCESSO EM TEMPO REAL] ---" -ForegroundColor White
    try {
        & py -3.11 "$WatchdogPy" --status
    } catch {
        try {
            & python "$WatchdogPy" --status
        } catch {
            Write-Host "  [Processo] Nao foi possivel consultar o status via Python." -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "  --- [CONFIGURACAO DO SISTEMA WINDOWS] ---" -ForegroundColor White
    
    # 2. Status no Agendador de Tarefas
    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-Host "  [Agendador de Tarefas]  : ATIVO (REGISTRADO)" -ForegroundColor Green
        Write-Host "    • Estado da Tarefa    : $($task.State)" -ForegroundColor White
        Write-Host "    • Acao                : $($task.Actions.Execute) $($task.Actions.Arguments)" -ForegroundColor Gray
        
        $trigDesc = @()
        foreach ($t in $task.Triggers) {
            if ($t.CimClass.CimClassName -match "Logon") {
                $trigDesc += "Ao Fazer Logon (AtLogon)"
            } elseif ($t.Repetition.Interval) {
                $trigDesc += "Repeticao a cada $($t.Repetition.Interval)"
            } else {
                $trigDesc += "$($t.CimClass.CimClassName)"
            }
        }
        Write-Host "    • Gatilhos Config     : $($trigDesc -join ' + ')" -ForegroundColor Cyan
    } catch {
        $cmd = "schtasks /Query /TN `"$TaskName`" /FO LIST"
        $res = cmd.exe /c $cmd 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [Agendador de Tarefas]  : ATIVO (schtasks)" -ForegroundColor Green
            Write-Host "$res" -ForegroundColor Gray
        } else {
            Write-Host "  [Agendador de Tarefas]  : INATIVO (Nao registrado)" -ForegroundColor Gray
        }
    }

    # 3. Status AutoLogon
    $RegPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    $auto = (Get-ItemProperty -Path $RegPath -Name "AutoAdminLogon" -ErrorAction SilentlyContinue).AutoAdminLogon
    $user = (Get-ItemProperty -Path $RegPath -Name "DefaultUserName" -ErrorAction SilentlyContinue).DefaultUserName
    if ($auto -eq "1") {
        Write-Host "  [Windows AutoLogon]     : ATIVO (Usuario: $user)" -ForegroundColor Green
        Write-Host "                            (O Windows fara login automatico ao ligar)" -ForegroundColor Gray
    } else {
        Write-Host "  [Windows AutoLogon]     : INATIVO (O Windows para na tela de senha)" -ForegroundColor Yellow
    }
    Write-Host ""
}

if ($Action -eq "register") {
    Register-AutoStartup -Interval $IntervalMinutes
} elseif ($Action -eq "register-interval") {
    Register-AutoStartup -Interval $IntervalMinutes
} elseif ($Action -eq "register-boot") {
    Register-BootStartup
} elseif ($Action -eq "unregister") {
    Unregister-AutoStartup
} elseif ($Action -eq "check") {
    Test-WatchdogCheck
} elseif ($Action -eq "status") {
    Show-Status
} else {
    Register-AutoStartup -Interval $IntervalMinutes
}
