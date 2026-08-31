import os
import tempfile
import unittest
import json
from src.batch_manager import BatchManager

class TestAutoBatchesOrganization(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_video_slot(self, batch_dir: str, video_name: str):
        v_dir = os.path.join(batch_dir, video_name)
        os.makedirs(v_dir, exist_ok=True)
        # Cria arquivo .mp4 simulado valido
        mp4_path = os.path.join(v_dir, "reddit_story_short_9x16.mp4")
        with open(mp4_path, "wb") as f:
            f.write(b"0" * 20000)
        # Cria script_data.json
        script_path = os.path.join(v_dir, "script_data.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump({"title": "Test", "shorts_script": "Narrative test"}, f)
        return v_dir

    def test_initial_slot_allocation(self):
        """Verifica que o primeiro slot alocado e batch_1/video_0."""
        mgr = BatchManager(base_dir=self.test_dir, batch_size=10)
        target_dir, b_num, v_num = mgr.get_next_video_slot()
        self.assertEqual(b_num, 1)
        self.assertEqual(v_num, 0)
        self.assertTrue(target_dir.endswith(os.path.join("batch_1", "video_0")))

    def test_batch_filling_and_progression_to_batch_2(self):
        """Verifica que apos preencher 10 videos (video_0..video_9), o proximo e batch_2/video_0."""
        mgr = BatchManager(base_dir=self.test_dir, batch_size=10)
        b1_dir = os.path.join(self.test_dir, "batch_1")
        
        # Preenche video_0 ate video_9 em batch_1
        for i in range(10):
            self._create_mock_video_slot(b1_dir, f"video_{i}")

        # Proximo deve ser batch_2/video_0
        target_dir, b_num, v_num = mgr.get_next_video_slot()
        self.assertEqual(b_num, 2)
        self.assertEqual(v_num, 0)
        self.assertTrue(target_dir.endswith(os.path.join("batch_2", "video_0")))

    def test_batch_summary(self):
        """Testa o resumo estruturado de lotes e videos."""
        mgr = BatchManager(base_dir=self.test_dir, batch_size=10)
        b1_dir = os.path.join(self.test_dir, "batch_1")
        for i in range(10):
            self._create_mock_video_slot(b1_dir, f"video_{i}")

        b2_dir = os.path.join(self.test_dir, "batch_2")
        self._create_mock_video_slot(b2_dir, "video_0")

        summary = mgr.get_summary()
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]["batch_name"], "batch_1")
        self.assertEqual(summary[0]["video_count"], 10)
        self.assertTrue(summary[0]["is_full"])

        self.assertEqual(summary[1]["batch_name"], "batch_2")
        self.assertEqual(summary[1]["video_count"], 1)
        self.assertFalse(summary[1]["is_full"])

    def test_gap_slot_allocation(self):
        """Verifica que se houver um espaco vago (ex: video_0 e video_2 preenchidos), aloca video_1."""
        mgr = BatchManager(base_dir=self.test_dir, batch_size=10)
        b1_dir = os.path.join(self.test_dir, "batch_1")
        self._create_mock_video_slot(b1_dir, "video_0")
        self._create_mock_video_slot(b1_dir, "video_2")

        target_dir, b_num, v_num = mgr.get_next_video_slot()
        self.assertEqual(b_num, 1)
        self.assertEqual(v_num, 1)
        self.assertTrue(target_dir.endswith(os.path.join("batch_1", "video_1")))

    def test_legacy_directory_migration(self):
        """Verifica a migracao automatica de pastas soltas legadas para batch_1/video_0, video_1..."""
        mgr = BatchManager(base_dir=self.test_dir, batch_size=10)
        legacy_dir = os.path.join(self.test_dir, "shorts")
        os.makedirs(legacy_dir, exist_ok=True)
        
        # Cria duas pastas legadas
        self._create_mock_video_slot(legacy_dir, "maliciouscompliance_123456")
        self._create_mock_video_slot(legacy_dir, "antiwork_654321")

        migrated = mgr.organize_legacy_directories()
        self.assertEqual(migrated, 2)

        # Pastas legadas devem ter sido movidas para batch_1/video_0 e video_1
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "batch_1", "video_0", "reddit_story_short_9x16.mp4")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "batch_1", "video_1", "reddit_story_short_9x16.mp4")))
        self.assertFalse(os.path.exists(legacy_dir))

    def test_multi_batch_progression_up_to_batch_3(self):
        """Verifica a progressao continua: batch_1 (0..9) -> batch_2 (0..9) -> batch_3 (0..9)."""
        mgr = BatchManager(base_dir=self.test_dir, batch_size=10)
        
        # Preenche batch_1 (10 videos)
        b1_dir = os.path.join(self.test_dir, "batch_1")
        for i in range(10):
            self._create_mock_video_slot(b1_dir, f"video_{i}")

        # Preenche batch_2 (10 videos)
        b2_dir = os.path.join(self.test_dir, "batch_2")
        for i in range(10):
            self._create_mock_video_slot(b2_dir, f"video_{i}")

        # O proximo deve ser batch_3/video_0
        target_dir, b_num, v_num = mgr.get_next_video_slot()
        self.assertEqual(b_num, 3)
        self.assertEqual(v_num, 0)
        self.assertTrue(target_dir.endswith(os.path.join("batch_3", "video_0")))

    def test_video_slot_naming_convention(self):
        """Verifica que o padrao de nomeclatura de pastas e estritamente batch_X e video_Y."""
        mgr = BatchManager(base_dir=self.test_dir, batch_size=10)
        for expected_batch in range(1, 4):
            for expected_video in range(10):
                target_dir, b_num, v_num = mgr.get_next_video_slot()
                self.assertEqual(b_num, expected_batch)
                self.assertEqual(v_num, expected_video)
                # Simula conclusao do video
                self._create_mock_video_slot(os.path.join(self.test_dir, f"batch_{expected_batch}"), f"video_{expected_video}")

if __name__ == "__main__":
    unittest.main()
