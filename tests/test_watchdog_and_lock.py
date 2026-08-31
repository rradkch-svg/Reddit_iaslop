import os
import sys
import tempfile
import unittest
from src.watchdog import is_pid_running, is_generator_running, LOCK_FILE
from src.auto_pipeline import PipelineLockManager

class TestWatchdogAndLock(unittest.TestCase):
    def test_pid_running_current_process(self):
        """Verifica que o PID do processo atual é detectado como em execução."""
        current_pid = os.getpid()
        self.assertTrue(is_pid_running(current_pid))
        # PID inválido não deve estar em execução
        self.assertFalse(is_pid_running(99999999))

    def test_pipeline_lock_manager_lifecycle(self):
        """Testa o ciclo de vida de aquisição, detecção e liberação do lock."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_lock = os.path.join(tmp_dir, ".test.lock")
            mgr1 = PipelineLockManager(test_lock)
            mgr2 = PipelineLockManager(test_lock)

            # 1. Primeira aquisição deve ter sucesso
            self.assertTrue(mgr1.acquire())
            self.assertTrue(os.path.exists(test_lock))

            # 2. Segunda aquisição concorrente deve falhar
            self.assertFalse(mgr2.acquire())

            # 3. Liberação
            mgr1.release()

            # 4. Agora mgr2 deve conseguir adquirir
            self.assertTrue(mgr2.acquire())
            mgr2.release()

    def test_is_generator_running_detection(self):
        """Verifica a detecção de processo em execução pelo Watchdog."""
        is_running, pid, reason = is_generator_running()
        self.assertIsInstance(is_running, bool)
        self.assertIsInstance(reason, str)
        if is_running:
            self.assertIsNotNone(pid)
            self.assertGreater(pid, 0)

if __name__ == "__main__":
    unittest.main()
