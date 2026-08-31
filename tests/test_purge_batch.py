import os
import sys
import unittest
import tempfile
import json
import shutil

# Ajusta caminhos
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from checkpoint_manager import CheckpointManager
from algorithm_memory import AlgorithmMemorySystem

class TestPurgeBatch(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.mkdtemp()
        self.cp_dir = os.path.join(self.temp_root, "checkpoint")
        self.mem_dir = os.path.join(self.temp_root, "memory")
        os.makedirs(self.cp_dir, exist_ok=True)
        os.makedirs(self.mem_dir, exist_ok=True)

        self.cp_mgr = CheckpointManager(root_dir=self.cp_dir)
        self.mem_sys = AlgorithmMemorySystem(memory_dir=self.mem_dir)

    def tearDown(self):
        if os.path.exists(self.temp_root):
            try:
                shutil.rmtree(self.temp_root)
            except:
                pass

    def test_purge_batch_removes_from_disk_and_state(self):
        # 1. Cria batch dummy
        b4_dir = os.path.join(self.cp_dir, "batch_4", "video_0")
        os.makedirs(b4_dir, exist_ok=True)
        with open(os.path.join(b4_dir, "checkpoint.json"), "w", encoding="utf-8") as f:
            json.dump({
                "batch_name": "batch_4",
                "video_name": "video_0",
                "status": "COMPLETED",
                "topic": {"tema": "Carro Teste Dummy Batch 4"},
                "storyboard": [{"scene_id": 1, "fala": "teste"}]
            }, f)

        # Registra na blacklist
        self.cp_mgr.add_to_blacklist({"tema": "Carro Teste Dummy Batch 4"}, "batch_4", "video_0")
        
        # Atualiza state
        state = self.cp_mgr.load_global_state()
        state["batches"]["batch_4"] = {"status": "COMPLETED", "videos": {"video_0": "COMPLETED"}}
        self.cp_mgr.save_global_state(state)

        # Sincroniza memória
        self.mem_sys.scan_and_sync_checkpoints(checkpoints_dir=self.cp_dir)
        self.assertEqual(len(self.mem_sys.load_history()), 1)

        # 2. Executa Purge
        self.assertTrue(self.cp_mgr.purge_batch("batch_4"))
        self.mem_sys.purge_batch("batch_4")

        # 3. Validações
        self.assertFalse(os.path.exists(os.path.join(self.cp_dir, "batch_4")))
        new_state = self.cp_mgr.load_global_state()
        self.assertNotIn("batch_4", new_state.get("batches", {}))
        self.assertEqual(len(self.mem_sys.load_history()), 0)

        # Blacklist não deve ter nada do batch_4
        bl_items = self.cp_mgr.load_blacklist()
        self.assertEqual(len([it for it in bl_items if it.get("batch") == "batch_4"]), 0)

if __name__ == "__main__":
    unittest.main()
