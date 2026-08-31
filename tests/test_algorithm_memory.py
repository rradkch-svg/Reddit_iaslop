import unittest
import os
import sys
import json
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from algorithm_memory import AlgorithmMemorySystem

class TestAlgorithmMemorySystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_sys = AlgorithmMemorySystem(data_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_generation_and_initial_weights(self):
        vid_id = self.memory_sys.record_video_generation({
            "video_id": "test_batch_0_video_0",
            "batch": "batch_0",
            "video_index": 0,
            "tema": "Lexus LFA: O Motor V10 que Gira Mais Rápido que a Física Permite",
            "core_entity": "Lexus LFA V10",
            "hook": "Por que a Lexus teve que inventar um painel digital para este carro?",
            "duracao_segundos": 68.5,
            "palavras_totais": 195,
            "total_cenas": 16,
            "estilo_voz": "pt-BR-AntonioNeural"
        })

        self.assertIsNotNone(vid_id)
        self.assertEqual(vid_id, "test_batch_0_video_0")

        # Verifica persistência
        history = self.memory_sys.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["tema"], "Lexus LFA: O Motor V10 que Gira Mais Rápido que a Física Permite")

        weights = self.memory_sys.load_weights()
        self.assertIn("hook_curiosity_gap_weight", weights)
        self.assertIn("technical_depth_weight", weights)

    def test_ingest_analytics_and_tier_classification(self):
        # 1. Registra 2 vídeos
        self.memory_sys.record_video_generation({
            "video_id": "batch_1/video_0",
            "batch": "batch_1",
            "video_index": 0,
            "tema": "Ferrari F40: A Última Criação de Enzo Ferrari",
            "core_entity": "Ferrari F40",
            "hook": "Por que esta Ferrari não tem maçanetas internas?",
            "duracao_segundos": 62.0,
            "palavras_totais": 180,
            "total_cenas": 15,
            "estilo_voz": "pt-BR-AntonioNeural"
        })

        self.memory_sys.record_video_generation({
            "video_id": "batch_1/video_1",
            "batch": "batch_1",
            "video_index": 1,
            "tema": "Toyota Supra 2JZ: Segredos do Bloco de Ferro",
            "core_entity": "Toyota Supra 2JZ",
            "hook": "O que faz este bloco de ferro aguentar 1000 cavalos?",
            "duracao_segundos": 75.0,
            "palavras_totais": 210,
            "total_cenas": 18,
            "estilo_voz": "pt-BR-AntonioNeural"
        })

        # 2. Ingestão de Feedback Viral (Tier S)
        ok_s, msg_s, rec_s = self.memory_sys.ingest_analytics_feedback(
            identifier="batch_1/video_0",
            views=125000,
            retention_3s_pct=88.5,
            apv_pct=92.0,
            ctr_pct=14.2,
            likes=9500,
            comments=420,
            feedback_notes="Explosão de retenção pelo gancho sem enrolação."
        )

        self.assertTrue(ok_s)
        self.assertEqual(rec_s["analytics"]["performance_tier"], "S")

        # 3. Ingestão de Feedback com queda rápida (Tier D)
        ok_d, msg_d, rec_d = self.memory_sys.ingest_analytics_feedback(
            identifier="batch_1/video_1",
            views=1200,
            retention_3s_pct=22.0,
            apv_pct=28.0,
            ctr_pct=3.5,
            likes=15,
            comments=1,
            feedback_notes="Gancho muito lento, público pulou nos primeiros 3s."
        )

        self.assertTrue(ok_d)
        self.assertEqual(rec_d["analytics"]["performance_tier"], "D")

        # 4. Verifica recalibração de pesos
        weights = self.memory_sys.load_weights()
        self.assertGreaterEqual(weights["hook_curiosity_gap_weight"], 0.90)

        # 5. Verifica geração de ALGORITHM_MEMORY.md
        md_file = self.memory_sys.memory_md_file
        self.assertTrue(os.path.exists(md_file))
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()

        self.assertIn("Tier S (Super Viral", md_text)
        self.assertIn("Ferrari F40", md_text)
        self.assertIn("Toyota Supra 2JZ", md_text)

    def test_prompt_guidance_generation(self):
        guidance = self.memory_sys.get_prompt_guidance()
        self.assertIn("MEMÓRIA DE INTELIGÊNCIA DO ALGORITMO", guidance)
        self.assertIn("Intensidade do Gancho Inicial", guidance)
        self.assertIn("Profundidade Técnica", guidance)

if __name__ == "__main__":
    unittest.main()
