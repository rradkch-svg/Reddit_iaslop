import os
import json
import shutil
import tempfile
import unittest

from src.checkpoint_manager import CheckpointManager
from src.batch_manager import BatchManager


class TestDualBlacklists(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ckpt_mgr = CheckpointManager(root_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dual_blacklist_initialization(self):
        """Verifica se os 4 arquivos (json e txt para shorts e longform) sao criados corretamente."""
        self.assertTrue(os.path.exists(self.ckpt_mgr.blacklist_shorts_file))
        self.assertTrue(os.path.exists(self.ckpt_mgr.blacklist_shorts_txt))
        self.assertTrue(os.path.exists(self.ckpt_mgr.blacklist_longform_file))
        self.assertTrue(os.path.exists(self.ckpt_mgr.blacklist_longform_txt))

        with open(self.ckpt_mgr.blacklist_shorts_file, "r", encoding="utf-8") as f:
            data_shorts = json.load(f)
            self.assertEqual(data_shorts.get("format"), "shorts")
            self.assertEqual(data_shorts.get("total_items"), 0)

        with open(self.ckpt_mgr.blacklist_longform_file, "r", encoding="utf-8") as f:
            data_long = json.load(f)
            self.assertEqual(data_long.get("format"), "longform")
            self.assertEqual(data_long.get("total_items"), 0)

    def test_format_isolation(self):
        """Verifica se a adicao de um tema no Shorts NAO bloqueia o mesmo tema em Longform e vice-versa."""
        story_shorts = {
            "tema": "Boss demanded I follow the handbook. It cost $42,000 in overtime.",
            "hook": "Here is how following rules cost $42k.",
            "explicacao_tecnica": "Cooling pump tripped and whole factory halted."
        }

        # 1. Registra no Shorts
        added = self.ckpt_mgr.add_to_blacklist(story_shorts, batch_name="batch_1", video_name="video_1", video_type="shorts")
        self.assertTrue(added)

        # 2. Deve constar na blacklist de Shorts
        is_dup_shorts, reason_shorts = self.ckpt_mgr.is_in_blacklist(story_shorts, video_type="shorts")
        self.assertTrue(is_dup_shorts)

        # 3. NAO deve constar na blacklist de Longform (Isolamento Estrito)
        is_dup_long, reason_long = self.ckpt_mgr.is_in_blacklist(story_shorts, video_type="longform")
        self.assertFalse(is_dup_long)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="longform")), 0)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="shorts")), 1)

        # 4. Registra tema diferente em Longform
        story_long = {
            "tema": "Company refused $3 raise. Spent $140,000 hiring consultants.",
            "hook": "They refused $3 raise and lost $140k.",
            "explicacao_tecnica": "Sole database admin quit and legacy SQL crashed."
        }
        self.ckpt_mgr.add_to_blacklist(story_long, batch_name="batch_1", video_name="video_0", video_type="longform")

        # 5. Longform agora tem 1 item, Shorts continua com 1 item
        self.assertTrue(self.ckpt_mgr.is_in_blacklist(story_long, video_type="longform")[0])
        self.assertFalse(self.ckpt_mgr.is_in_blacklist(story_long, video_type="shorts")[0])
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="longform")), 1)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="shorts")), 1)

    def test_contextual_deduplication_within_format(self):
        """Verifica a deteccao de temas muito similares dentro do mesmo formato."""
        story_orig = {
            "tema": "Landlord tried to steal my $4500 deposit with fake contractor bills",
            "hook": "Judge awarded triple damages against shady landlord"
        }
        self.ckpt_mgr.add_to_blacklist(story_orig, batch_name="batch_1", video_name="video_2", video_type="shorts")

        # Tema candidato com redacao similar
        story_cand = {
            "tema": "Landlord tried to steal my $4500 deposit with fake contractor invoices",
            "hook": "Judge awarded triple damages against shady landlord"
        }
        is_dup, reason = self.ckpt_mgr.is_in_blacklist(story_cand, video_type="shorts")
        self.assertTrue(is_dup)

    def test_removal_specific_vs_global(self):
        """Verifica remocao seletiva por formato e remocao global."""
        s1 = {"tema": "Landlord deposit dispute case"}
        s2 = {"tema": "Landlord parking eviction issue"}

        self.ckpt_mgr.add_to_blacklist(s1, batch_name="batch_1", video_name="video_1", video_type="shorts")
        self.ckpt_mgr.add_to_blacklist(s2, batch_name="batch_1", video_name="video_0", video_type="longform")

        # Remove apenas de Shorts
        rem_shorts = self.ckpt_mgr.remove_from_blacklist(keyword="landlord", video_type="shorts")
        self.assertEqual(rem_shorts, 1)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="shorts")), 0)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="longform")), 1)

        # Adiciona de volta em Shorts
        self.ckpt_mgr.add_to_blacklist(s1, batch_name="batch_1", video_name="video_1", video_type="shorts")
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="shorts")), 1)

        # Remove de ambos (video_type=None)
        rem_global = self.ckpt_mgr.remove_from_blacklist(keyword="landlord", video_type=None)
        self.assertEqual(rem_global, 2)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="shorts")), 0)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist(video_type="longform")), 0)

    def test_purge_batch_cleans_both_blacklists(self):
        """Verifica se purge_batch expurga os registros de batch_1 de ambas as blacklists."""
        self.ckpt_mgr.add_to_blacklist("Topic A in Batch 1", batch_name="batch_1", video_name="video_1", video_type="shorts")
        self.ckpt_mgr.add_to_blacklist("Topic B in Batch 1", batch_name="batch_1", video_name="video_0", video_type="longform")
        self.ckpt_mgr.add_to_blacklist("Topic C in Batch 2", batch_name="batch_2", video_name="video_1", video_type="shorts")

        self.assertEqual(len(self.ckpt_mgr.load_blacklist("shorts")), 2)
        self.assertEqual(len(self.ckpt_mgr.load_blacklist("longform")), 1)

        # Purga batch_1
        self.ckpt_mgr.purge_batch("batch_1")

        # Deve restar apenas o Topic C de batch_2 em shorts e 0 em longform
        shorts_left = self.ckpt_mgr.load_blacklist("shorts")
        long_left = self.ckpt_mgr.load_blacklist("longform")
        self.assertEqual(len(shorts_left), 1)
        self.assertEqual(shorts_left[0]["tema"], "Topic C in Batch 2")
        self.assertEqual(len(long_left), 0)

    def test_sync_blacklists_from_batches(self):
        """Verifica a reconstrucao das blacklists a partir de diretorios fisicos existentes de batches."""
        auto_batches_dir = os.path.join(self.test_dir, "auto_batches")
        b1_dir = os.path.join(auto_batches_dir, "batch_1")
        
        # 1. Cria mock de video_0 (Longform)
        v0_dir = os.path.join(b1_dir, "video_0", "longform_25min")
        os.makedirs(v0_dir, exist_ok=True)
        with open(os.path.join(v0_dir, "script_data.json"), "w", encoding="utf-8") as f:
            json.dump({"main_title": "25-Minute Epic Saga of IT Revenge", "opening_hook": "IT team malicious compliance"}, f)

        # 2. Cria mock de video_1 (Short)
        v1_dir = os.path.join(b1_dir, "video_1")
        os.makedirs(v1_dir, exist_ok=True)
        with open(os.path.join(v1_dir, "script_data.json"), "w", encoding="utf-8") as f:
            json.dump({"title": "Short Story of Overtime Fiasco", "hook_text": "Followed protocol strictly"}, f)

        # 3. Executa sync
        res = self.ckpt_mgr.sync_blacklists_from_batches(base_batches_dir=auto_batches_dir)
        self.assertEqual(res["longform_synced"], 1)
        self.assertEqual(res["shorts_synced"], 1)

        # 4. Valida se os itens constam nas blacklists corretas
        long_items = self.ckpt_mgr.load_blacklist("longform")
        shorts_items = self.ckpt_mgr.load_blacklist("shorts")

        self.assertEqual(len(long_items), 1)
        self.assertEqual(long_items[0]["tema"], "25-Minute Epic Saga of IT Revenge")
        self.assertEqual(len(shorts_items), 1)
        self.assertEqual(shorts_items[0]["tema"], "Short Story of Overtime Fiasco")


if __name__ == "__main__":
    unittest.main()
