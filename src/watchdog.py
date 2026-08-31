import os
import sys
import time
import signal
import logging
import argparse
import subprocess
from datetime import datetime
from typing import Optional, Tuple

# Forçar UTF-8 no Windows stdout/stderr
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "src" else CURRENT_DIR
CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "checkpoint")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
LOCK_FILE = os.path.join(CHECKPOINT_DIR, ".pipeline.lock")
WATCHDOG_LOG_FILE = os.path.join(LOGS_DIR, "watchdog.log")

os.makedirs(CHECKPOINT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Logger específico do Watchdog
watchdog_logger = logging.getLogger("watchdog")
watchdog_logger.setLevel(logging.INFO)
if not watchdog_logger.handlers:
    _formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    _fh = logging.FileHandler(WATCHDOG_LOG_FILE, encoding="utf-8")
    _fh.setFormatter(_formatter)
    _sh = logging.StreamHandler(sys.stdout)
    _sh.setFormatter(_formatter)
    watchdog_logger.addHandler(_fh)
    watchdog_logger.addHandler(_sh)

# Flag de controle de execução graciosa
RUNNING = True
CHILD_PROCESS = None

def sig_handler(sig, frame):
    global RUNNING, CHILD_PROCESS
    watchdog_logger.info("🛑 [Watchdog] Sinal de interrupção recebido (Ctrl+C / SIGINT / SIGTERM). Encerrando...")
    RUNNING = False
    if CHILD_PROCESS and CHILD_PROCESS.poll() is None:
        try:
            watchdog_logger.info(f"⏳ [Watchdog] Encerrando processo gerador filho (PID {CHILD_PROCESS.pid})...")
            CHILD_PROCESS.terminate()
            try:
                CHILD_PROCESS.wait(timeout=5)
            except subprocess.TimeoutExpired:
                CHILD_PROCESS.kill()
        except Exception as e:
            watchdog_logger.warning(f"⚠️ [Watchdog] Erro ao encerrar processo filho: {e}")
    sys.exit(0)

signal.signal(signal.SIGINT, sig_handler)
try:
    signal.signal(signal.SIGTERM, sig_handler)
except Exception:
    pass


def is_pid_running(pid: int) -> bool:
    """Verifica se um PID existe e está em execução no sistema operacional."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                kernel32.CloseHandle(handle)
                # STILL_ACTIVE = 259
                return exit_code.value == 259
            kernel32.CloseHandle(handle)
            return False
        except Exception:
            try:
                res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                     capture_output=True, text=True, timeout=3)
                return str(pid) in res.stdout
            except Exception:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def is_generator_running() -> Tuple[bool, Optional[int], str]:
    """
    Verifica de forma ultra-confiável se o gerador (auto_pipeline.py) já está ativo.
    Testa o bloqueio de arquivo (lock do SO) e o PID registrado.
    Retorna (is_running, pid, reason).
    """
    if not os.path.exists(LOCK_FILE):
        return False, None, "Arquivo de lock inexistente"

    # Tenta ler o PID do arquivo de lock
    recorded_pid = None
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content.isdigit():
                recorded_pid = int(content)
    except Exception:
        pass

    # Testa se o arquivo está bloqueado pelo msvcrt (Windows) ou fcntl (Linux)
    if sys.platform == "win32":
        import msvcrt
        test_handle = None
        try:
            test_handle = open(LOCK_FILE, "a+")
            test_handle.seek(0)
            # Tenta aplicar trava de 1 byte sem bloquear
            msvcrt.locking(test_handle.fileno(), msvcrt.LK_NBLCK, 1)
            # Se conseguiu travar, significa que nenhuma outra instância segura a trava
            msvcrt.locking(test_handle.fileno(), msvcrt.LK_UNLCK, 1)
            test_handle.close()
            # Se havia um PID registrado mas a trava estava livre, checa se o processo morreu
            if recorded_pid and not is_pid_running(recorded_pid):
                return False, recorded_pid, f"Processo anterior (PID {recorded_pid}) encerrou; lock livre"
            return False, recorded_pid, "Lock livre (nenhum processo retém trava do SO)"
        except (IOError, OSError, PermissionError):
            # Não conseguiu travar porque outro processo ativo está segurando a trava
            if test_handle:
                try:
                    test_handle.close()
                except Exception:
                    pass
            return True, recorded_pid, f"Instância ativa detectada com lock do SO (PID: {recorded_pid})"
    else:
        import fcntl
        test_handle = None
        try:
            test_handle = open(LOCK_FILE, "w+")
            fcntl.flock(test_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(test_handle.fileno(), fcntl.LOCK_UN)
            test_handle.close()
            return False, recorded_pid, "Lock livre"
        except (IOError, OSError, BlockingIOError):
            if test_handle:
                try:
                    test_handle.close()
                except Exception:
                    pass
            return True, recorded_pid, f"Instância ativa detectada (PID: {recorded_pid})"


def find_python_executable() -> str:
    """Encontra o interpretador Python 3.11+ adequado no sistema."""
    candidates = [
        "py -3.11",
        "py",
        "python",
        sys.executable
    ]
    for cand in candidates:
        try:
            cmd = cand.split() + ["-c", "import google.genai, edge_tts, yt_dlp, PIL; print('OK')"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and "OK" in res.stdout:
                return cand
        except Exception:
            continue
    return sys.executable


def spawn_generator_new_window():
    """Abre uma nova janela de terminal visível executando o gerador."""
    target_bat = os.path.join(PROJECT_ROOT, "scripts", "iniciar_auto_geracao.bat")
    if not os.path.exists(target_bat):
        target_bat = os.path.join(PROJECT_ROOT, "iniciar_auto_geracao.bat")
    watchdog_logger.info(f"🚀 [Watchdog] Disparando nova janela de console para o gerador: {target_bat}")
    if sys.platform == "win32":
        cmd = f'start "AI Slop Studio - Gerador Autônomo (9:16)" cmd /k "{target_bat}"'
        subprocess.Popen(cmd, shell=True, cwd=PROJECT_ROOT)
    else:
        subprocess.Popen(["bash", target_bat], cwd=PROJECT_ROOT)


def run_continuous_watchdog(poll_interval: int = 5):
    """
    Loop contínuo de supervisão (Watchdog Principal).
    Mantém o gerador sempre em execução. Se ele fechar ou travar, reabre imediatamente.
    """
    global CHILD_PROCESS, RUNNING

    print("=" * 75)
    print("🛡️  AI SLOP STUDIO - WATCHDOG SUPERVISOR DE ALTA RESILIÊNCIA")
    print("=" * 75)
    print(f"📁 Diretório Raiz do Projeto : {PROJECT_ROOT}")
    print(f"⏱️ Intervalo de Checagem     : {poll_interval}s")
    print(f"📝 Log do Watchdog          : {WATCHDOG_LOG_FILE}")
    print("=" * 75)
    print()

    watchdog_logger.info("[Watchdog] Supervisor contínuo iniciado.")
    py_exec = find_python_executable()
    watchdog_logger.info(f"[Watchdog] Interpretador Python selecionado: {py_exec}")

    consecutive_fast_crashes = 0
    total_restarts = 0

    while RUNNING:
        is_running, pid, reason = is_generator_running()

        if is_running and pid and (not CHILD_PROCESS or CHILD_PROCESS.pid != pid):
            watchdog_logger.info(f"👀 [Watchdog] Detectada instância já em execução (PID {pid}). Monitorando integridade...")
            while RUNNING:
                running_check, cur_pid, _ = is_generator_running()
                if not running_check:
                    watchdog_logger.warning(f"⚠️ [Watchdog] A instância (PID {pid}) encerrou ou a janela foi fechada!")
                    break
                time.sleep(poll_interval)

            if not RUNNING:
                break

        # Se chegamos aqui, nenhuma instância está rodando. Precisamos iniciar!
        total_restarts += 1
        watchdog_logger.info(f"▶️ [Watchdog] (Ciclo #{total_restarts}) Iniciando processo do gerador auto_pipeline.py...")

        start_time = time.time()
        pipeline_py = os.path.join(CURRENT_DIR, "auto_pipeline.py")
        if not os.path.exists(pipeline_py):
            pipeline_py = os.path.join(PROJECT_ROOT, "src", "auto_pipeline.py")

        cmd = py_exec.split() + [pipeline_py]
        try:
            CHILD_PROCESS = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT
            )
            watchdog_logger.info(f"✅ [Watchdog] Gerador iniciado com sucesso (PID: {CHILD_PROCESS.pid})")
        except Exception as e:
            watchdog_logger.error(f"❌ [Watchdog] Falha ao iniciar auto_pipeline.py: {e}")
            time.sleep(10)
            continue

        # Monitora a execução do processo filho
        while RUNNING:
            ret_code = CHILD_PROCESS.poll()
            if ret_code is not None:
                elapsed = time.time() - start_time
                watchdog_logger.warning(
                    f"⚠️ [Watchdog] Processo gerador finalizou após {elapsed:.1f}s com código de saída: {ret_code}"
                )

                if elapsed < 8.0:
                    consecutive_fast_crashes += 1
                    cooldown = min(consecutive_fast_crashes * 5, 30)
                    watchdog_logger.warning(
                        f"🚨 [Watchdog] Encerramento rápido consecutivo ({consecutive_fast_crashes}x). "
                        f"Aguardando cooldown de segurança de {cooldown}s antes de reabrir..."
                    )
                    time.sleep(cooldown)
                else:
                    consecutive_fast_crashes = 0
                    watchdog_logger.info("♻️ [Watchdog] Reiniciando gerador em 3 segundos...")
                    time.sleep(3)

                CHILD_PROCESS = None
                break

            time.sleep(poll_interval)

    watchdog_logger.info("[Watchdog] Supervisor encerrado.")


def main():
    parser = argparse.ArgumentParser(description="Watchdog Supervisor do AI Slop Studio")
    parser.add_argument("--check-only", action="store_true", help="Apenas checa se está rodando e retorna exit code (0 se rodando, 1 se fechado)")
    parser.add_argument("--check-and-spawn", action="store_true", help="Checa se está rodando; se fechado, abre em nova janela visível")
    parser.add_argument("--status", action="store_true", help="Exibe o status atual do gerador e watchdog")
    parser.add_argument("--poll-interval", type=int, default=5, help="Intervalo de polling em segundos (padrão: 5)")
    args = parser.parse_args()

    if args.status:
        is_running, pid, reason = is_generator_running()
        print("=" * 60)
        print("📊 STATUS DO WATCHDOG & GERADOR")
        print("=" * 60)
        if is_running:
            print(f"  • Status do Gerador : 🟢 EM EXECUÇÃO (PID: {pid})")
            print(f"  • Detalhes          : {reason}")
        else:
            print("  • Status do Gerador : 🔴 FECHADO / PARADO")
            print(f"  • Detalhes          : {reason}")
        print(f"  • Lock File         : {LOCK_FILE}")
        print(f"  • Log Watchdog      : {WATCHDOG_LOG_FILE}")
        print("=" * 60)
        sys.exit(0 if is_running else 1)

    if args.check_only:
        is_running, pid, reason = is_generator_running()
        if is_running:
            watchdog_logger.info(f"[Watchdog Check] Gerador em execução (PID: {pid}).")
            sys.exit(0)
        else:
            watchdog_logger.info(f"[Watchdog Check] Gerador FECHADO / PARADO ({reason}).")
            sys.exit(1)

    if args.check_and_spawn:
        is_running, pid, reason = is_generator_running()
        if is_running:
            watchdog_logger.info(f"[Watchdog Check] Instância já ativa (PID: {pid}). Nenhuma ação necessária.")
            sys.exit(0)
        else:
            watchdog_logger.warning(f"⚠️ [Watchdog Check] Instância fechada detectada ({reason}). Reabrindo gerador...")
            spawn_generator_new_window()
            sys.exit(0)

    # Modo supervisor contínuo padrão
    run_continuous_watchdog(poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
