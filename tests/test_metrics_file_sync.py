import unittest
import os
import sys
import json
import tempfile
import csv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from algorithm_memory import AlgorithmMemorySystem

class TestMetricsFileSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_sys = AlgorithmMemorySystem(data_dir=self.temp_dir.name)
        self.mock_cp_dir = os.path.join(self.temp_dir.name, "checkpoints")
        os.makedirs(self.mock_cp_dir, exist_ok=True)

        # 1. Cria Checkpoint Válido 1 (Porsche GT3 RS)
        cp1_dir = os.path.join(self.mock_cp_dir, "batch_1", "video_0")
        os.makedirs(cp1_dir, exist_ok=True)
        with open(os.path.join(cp1_dir, "checkpoint.json"), "w", encoding="utf-8") as f:
            json.dump({
                "batch_name": "batch_1",
                "video_name": "video_0",
                "batch_index": 1,
                "video_index": 0,
                "status": "COMPLETED",
                "topic": {
                    "tema": "Porsche 911 GT3 RS: A Física do Downforce de 860 kg",
                    "core_entity": "Porsche 911 GT3 RS",
                    "hook": "Por que esta asa traseira é maior que o teto?"
                },
                "storyboard": [
                    {"scene_id": 1, "fala": "Fala 1", "youtube_query": "query 1"},
                    {"scene_id": 2, "fala": "Fala 2", "youtube_query": "query 2"}
                ],
                "audio_duration": 65.4,
                "words_timing": [{"word": "w"} for _ in range(180)],
                "generation_weights": {
                    "hook_curiosity_gap_weight": 0.96,
                    "technical_depth_weight": 0.94,
                    "anti_hype_precision_weight": 0.92,
                    "pacing_cadence_wpm": 190.0,
                    "broll_cut_frequency_sec": 2.5
                }
            }, f, indent=2)

        # 2. Cria Checkpoint Válido 2 (Lexus LFA)
        cp2_dir = os.path.join(self.mock_cp_dir, "batch_1", "video_1")
        os.makedirs(cp2_dir, exist_ok=True)
        with open(os.path.join(cp2_dir, "checkpoint.json"), "w", encoding="utf-8") as f:
            json.dump({
                "batch_name": "batch_1",
                "video_name": "video_1",
                "batch_index": 1,
                "video_index": 1,
                "status": "COMPLETED",
                "topic": {
                    "tema": "Lexus LFA: O V10 com Painel Digital",
                    "core_entity": "Lexus LFA V10",
                    "hook": "Por que o conta-giros analógico não conseguia acompanhar este motor?"
                },
                "storyboard": [
                    {"scene_id": 1, "fala": "Fala 1", "youtube_query": "query 1"},
                    {"scene_id": 2, "fala": "Fala 2", "youtube_query": "query 2"}
                ],
                "audio_duration": 58.2,
                "words_timing": [{"word": "w"} for _ in range(160)],
                "generation_weights": {
                    "hook_curiosity_gap_weight": 0.95,
                    "technical_depth_weight": 0.91,
                    "anti_hype_precision_weight": 0.89,
                    "pacing_cadence_wpm": 182.0,
                    "broll_cut_frequency_sec": 2.9
                }
            }, f, indent=2)

        # 3. Cria Checkpoint Corrompido / Perdido (Sem tema e sem storyboard)
        cp3_dir = os.path.join(self.mock_cp_dir, "batch_1", "video_2")
        os.makedirs(cp3_dir, exist_ok=True)
        with open(os.path.join(cp3_dir, "checkpoint.json"), "w", encoding="utf-8") as f:
            json.dump({
                "batch_name": "batch_1",
                "video_name": "video_2",
                "status": "ERROR",
                "topic": None,
                "storyboard": []
            }, f, indent=2)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scan_and_filter_lost_metadata(self):
        valid_cnt, ignored_cnt = self.memory_sys.scan_and_sync_checkpoints(checkpoints_dir=self.mock_cp_dir)
        self.assertEqual(valid_cnt, 2)
        self.assertEqual(ignored_cnt, 1)

        history = self.memory_sys.load_history()
        self.assertEqual(len(history), 2)
        
        # Verifica se os pesos de geração individuais foram preservados
        porsche_rec = next(r for r in history if "Porsche" in r["tema"])
        self.assertEqual(porsche_rec["generation_weights"]["hook_curiosity_gap_weight"], 0.96)
        self.assertEqual(porsche_rec["status_metadata"], "VALIDO")

    def test_export_and_import_metrics_csv(self):
        self.memory_sys.scan_and_sync_checkpoints(checkpoints_dir=self.mock_cp_dir)
        
        csv_file = os.path.join(self.temp_dir.name, "METRICAS_TEST.csv")
        md_file = os.path.join(self.temp_dir.name, "METRICAS_TEST.md")

        # 1. Exporta CSV
        self.memory_sys.export_metrics_csv(csv_path=csv_file)
        self.assertTrue(os.path.exists(csv_file))

        # Lê conteúdo e simula entrada do usuário
        rows = []
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if "Porsche" in r["titulo"]:
                    r["views"] = "185000"
                    r["retencao_3s_pct"] = "89.5"
                    r["apv_pct"] = "94.0"
                    r["curtidas"] = "12000"
                    r["observacoes_sucesso"] = "Super viral! Explicar a asa gerou muita curiosidade."
                rows.append(r)

        # Regrava CSV com as views inseridas pelo usuário
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        # 2. Importa CSV e verifica processamento
        updated, ignored, msgs = self.memory_sys.import_metrics_csv(csv_path=csv_file)
        self.assertEqual(updated, 1)

        # 3. Verifica se o vídeo do Porsche foi classificado como Tier S
        history = self.memory_sys.load_history()
        porsche_rec = next(r for r in history if "Porsche" in r["tema"])
        self.assertEqual(porsche_rec["analytics"]["views"], 185000)
        self.assertEqual(porsche_rec["analytics"]["performance_tier"], "S")

        # 4. Verifica exportação do Markdown
        self.memory_sys.export_metrics_markdown(md_path=md_file)
        self.assertTrue(os.path.exists(md_file))
        with open(md_file, "r", encoding="utf-8") as mf:
            md_text = mf.read()
        self.assertIn("185,000", md_text)
        self.assertIn("Tier S", md_text)
        self.assertIn("Porsche 911 GT3 RS", md_text)

    def test_non_destructive_csv_reexport(self):
        self.memory_sys.scan_and_sync_checkpoints(checkpoints_dir=self.mock_cp_dir)
        csv_file = os.path.join(self.temp_dir.name, "METRICAS_TEST.csv")

        self.memory_sys.export_metrics_csv(csv_path=csv_file)

        # Usuário digita views
        rows = []
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if "Lexus" in r["titulo"]:
                    r["views"] = "55000"
                rows.append(r)

        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        # Re-executa export_metrics_csv (não deve apagar as views do Lexus)
        self.memory_sys.export_metrics_csv(csv_path=csv_file)

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if "Lexus" in r["titulo"]:
                    self.assertEqual(r["views"], "55000")

if __name__ == "__main__":
    unittest.main()
