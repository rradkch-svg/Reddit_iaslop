# Guia Prático: Watchdog e Recuperação Automática Contínua

Este guia explica como funciona o sistema de **Watchdog Supervisor** e a **Recuperação Automática pelo Agendador de Tarefas do Windows**, garantindo que o gerador de vídeos do AI Slop Studio seja reaberto automaticamente caso seja fechado acidentalmente, sofra pane ou após reinicialização do computador.

---

## 1. Modos de Operação do Watchdog

O sistema oferece duas camadas integradas de alta resiliência:

### Camada 1: Watchdog Supervisor em Tempo Real (`src/watchdog.py`)
- **Execução**: Execute `scripts/iniciar_watchdog.bat` ou `py -3.11 src/watchdog.py`.
- **Como funciona**:
  - Inicia o gerador autônomo (`src/auto_pipeline.py`) como processo filho monitorado.
  - Se a janela for fechada, o processo cair ou houver erro não tratado, o Watchdog detecta imediatamente e reabre o gerador em 3 segundos.
  - Possui **cooldown de segurança progressivo** se houver falhas consecutivas ultrarrápidas (<8s), evitando loops descontrolados.
  - Para encerrar em definitivo, basta fechar a janela do Watchdog ou pressionar `Ctrl+C`.

### Camada 2: Agendador de Tarefas Inteligente do Windows (`scripts/setup_task.ps1`)
- **Tarefa**: `AISlopStudio_AutoRecovery`
- **Gatilhos**:
  1. **Ao Fazer Logon (`AtLogon`)**: Inicia o gerador assim que o usuário faz login no Windows.
  2. **Repetição Periódica**: Dispara a cada 2 minutos indefinidamente.
- **Checagem Não-Invasiva**:
  - A cada disparo, o script `scripts/auto_recovery.bat` consulta o `src/watchdog.py --check-only`.
  - Se a instância **JÁ ESTIVER RODANDO**: encerra instantaneamente em silêncio (0ms de impacto, sem abrir janelas duplicadas).
  - Se a instância **TIVER SIDO FECHADA**: abre automaticamente uma nova janela de terminal visível com o gerador!

---

## 2. Comandos e Scripts Rápidos

| Script / Comando | Descrição |
|---|---|
| `scripts/iniciar_watchdog.bat` (ou `iniciar_watchdog.bat`) | Inicia o gerador com supervisão contínua em tempo real |
| `scripts/registrar_agendador_tarefas.bat` (ou `registrar_agendador_tarefas.bat`) | Registra a tarefa com Logon + Repetição de 2 minutos no Windows |
| `scripts/verificar_agendador_tarefas.bat` (ou `verificar_agendador_tarefas.bat`) | Exibe o status da tarefa no Windows e o status do processo em tempo real |
| `scripts/remover_agendador_tarefas.bat` (ou `remover_agendador_tarefas.bat`) | Remove a tarefa do Agendador de Tarefas |
| `py -3.11 src/watchdog.py --status` | Mostra se o gerador está rodando (PID) ou parado |

---

## 3. Configuração Personalizada de Intervalo

Se desejar alterar o intervalo de checagem do Agendador de Tarefas:

```powershell
# Checagem a cada 5 minutos
powershell -ExecutionPolicy Bypass -File scripts\setup_task.ps1 -Action register -IntervalMinutes 5
```
