import os
import sys
import unittest
import tempfile
import zipfile
import csv
import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from analytics_parser import (
    YouTubeAnalyticsZipParser,
    normalize_column_name,
    parse_float_safe,
    parse_int_safe,
    clean_youtube_title,
    parse_publish_date
)
from algorithm_memory import AlgorithmMemorySystem

class TestAnalyticsParser(unittest.TestCase):
    def test_column_name_normalization(self):
        """Verifica a normalização de colunas com acentos, maiúsculas e variações em inglês/português."""
        self.assertEqual(normalize_column_name("Visualizações"), "views")
        self.assertEqual(normalize_column_name("Views"), "views")
        self.assertEqual(normalize_column_name("Título do vídeo"), "title")
        self.assertEqual(normalize_column_name("Video title"), "title")
        self.assertEqual(normalize_column_name("Duração"), "duration_sec")
        self.assertEqual(normalize_column_name("Tempo de exibição (horas)"), "watch_time_hours")
        self.assertEqual(normalize_column_name("Taxa de cliques de impressões (%)"), "ctr_pct")
        self.assertEqual(normalize_column_name("Porcentagem média visualizada (%)"), "apv_pct")

    def test_number_parsers(self):
        """Verifica conversão robusta de strings numéricas em formato BR e US."""
        self.assertEqual(parse_int_safe("1.566"), 1566)
        self.assertEqual(parse_int_safe("1,566"), 1566)
        self.assertEqual(parse_int_safe("12.5K"), 12500)
        self.assertEqual(parse_int_safe("1.2M"), 1200000)
        self.assertEqual(parse_float_safe("27,42%"), 27.42)
        self.assertEqual(parse_float_safe("8.2065"), 8.2065)

    def test_date_parsers(self):
        """Verifica parsing de datas em formatos inglês, português e ISO."""
        self.assertEqual(parse_publish_date("Aug 27, 2026"), datetime.date(2026, 8, 27))
        self.assertEqual(parse_publish_date("26 de ago. de 2026"), datetime.date(2026, 8, 26))
        self.assertEqual(parse_publish_date("2026-08-25"), datetime.date(2026, 8, 25))
        self.assertEqual(parse_publish_date("24/08/2026"), datetime.date(2026, 8, 24))

    def test_clean_youtube_title(self):
        """Verifica remoção de hashtags e menções."""
        raw = "🏎️ Porsche 911 GT3 RS (992): O segredo do DRS #minutoautomotivo #Shorts"
        cleaned = clean_youtube_title(raw)
        self.assertEqual(cleaned, "Porsche 911 GT3 RS (992): O segredo do DRS")

    def test_parse_and_match_synthetic_zip(self):
        """Cria um arquivo .zip sintético com Table data e Chart data e testa normalização temporal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analytics_folder = os.path.join(tmpdir, "analytics")
            os.makedirs(analytics_folder, exist_ok=True)
            
            zip_file_path = os.path.join(analytics_folder, "Content 2026-07-30_2026-08-27 Export.zip")
            
            table_csv = """Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,Tempo de exibição (horas),Inscritos,Impressões,Taxa de cliques de impressões (%)
Total,,,,1000,5.0,2,200,5.0
abc12345,Porsche 911 GT3 RS: A Física do Downforce #Shorts,"Aug 27, 2026",85,389,2.5,1,50,4.5
xyz67890,Toyota Supra 2JZ: Segredos do Bloco de Ferro #JDM,"Aug 01, 2026",70,300,1.8,0,40,3.0
"""
            chart_csv = """Data,Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações
2026-08-27,abc12345,Porsche 911 GT3 RS: A Física do Downforce #Shorts,"Aug 27, 2026",85,389
2026-08-01,xyz67890,Toyota Supra 2JZ: Segredos do Bloco de Ferro #JDM,"Aug 01, 2026",70,10
"""
            with zipfile.ZipFile(zip_file_path, "w") as z:
                z.writestr("Table data.csv", table_csv.encode("cp1252"))
                z.writestr("Chart data.csv", chart_csv.encode("cp1252"))

            parser = YouTubeAnalyticsZipParser(analytics_dir=analytics_folder)
            latest = parser.find_latest_zip()
            self.assertEqual(latest, zip_file_path)

            items = parser.parse_zip_content(latest)
            self.assertEqual(len(items), 2)
            
            # abc12345 publicado em 27/08 (1 dia de exposição)
            self.assertEqual(items[0]["views"], 389)
            self.assertEqual(items[0]["exposure_days"], 1.0)
            self.assertEqual(items[0]["views_per_day"], 389.0)
            self.assertEqual(items[0]["growth_trajectory"], "VIRAL_BURST")
            self.assertGreater(items[0]["projected_28d_views"], 1000)

            # xyz67890 publicado em 01/08 (27 dias de exposição)
            self.assertEqual(items[1]["views"], 300)
            self.assertEqual(items[1]["exposure_days"], 27.0)
            self.assertEqual(items[1]["views_per_day"], 11.11)

            # Casamento com base local
            local_records = [
                {
                    "video_id": "vid_01",
                    "tema": "Porsche 911 GT3 RS: A Física do Downforce de 860 kg",
                    "core_entity": "Porsche 911 GT3 RS",
                    "duracao_segundos": 86.0
                },
                {
                    "video_id": "vid_02",
                    "tema": "Toyota Supra 2JZ: Segredos do Bloco de Ferro",
                    "core_entity": "Toyota Supra 2JZ",
                    "duracao_segundos": 70.0
                }
            ]

            matched, unmatched = parser.match_youtube_to_local_records(items, local_records)
            self.assertEqual(len(matched), 2)
            self.assertEqual(len(unmatched), 0)
            self.assertEqual(matched[0]["local_record"]["video_id"], "vid_01")
            self.assertEqual(matched[1]["local_record"]["video_id"], "vid_02")

    def test_algorithm_memory_ingest_from_zip(self):
        """Testa o fluxo ponta-a-ponta de ingestão do ZIP com normalização de idade e recalibração de pesos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_dir = os.path.join(tmpdir, "algorithm_memory")
            analytics_folder = os.path.join(tmpdir, "analytics")
            os.makedirs(analytics_folder, exist_ok=True)
            
            memory_sys = AlgorithmMemorySystem(memory_dir=mem_dir)
            
            # Registra vídeo local recente
            memory_sys.record_video_generation({
                "video_id": "batch_0_video_0",
                "batch": "batch_0",
                "video_index": 0,
                "tema": "Ferrari F40: A Bruta Engenharia dos Turbos Duplos",
                "core_entity": "Ferrari F40",
                "duracao_segundos": 60.0
            })

            # Gera ZIP do YouTube com publicação recente
            zip_path = os.path.join(analytics_folder, "Content 2026-07-30_2026-08-27 Test.zip")
            csv_content = """Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,Tempo de exibição (horas),Inscritos,Impressões,Taxa de cliques de impressões (%)
Total,,,,850,4.0,2,100,5.0
f40vid123,Ferrari F40: A Bruta Engenharia dos Turbos Duplos #Shorts,"Aug 27, 2026",60,850,4.0,2,100,5.0
"""
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("Table data.csv", csv_content.encode("utf-8"))

            upd, ign, msgs = memory_sys.ingest_from_analytics_zip(zip_path)
            self.assertEqual(upd, 1)
            
            history = memory_sys.load_history()
            f40_record = next(r for r in history if r["video_id"] == "batch_0_video_0")
            self.assertEqual(f40_record["analytics"]["views"], 850)
            self.assertEqual(f40_record["analytics"]["views_per_day"], 850.0)
            self.assertEqual(f40_record["analytics"]["performance_tier"], "S")

    def test_exposure_aware_tier_algorithm(self):
        """Verifica a classificação de tiers imune ao viés de tempo de publicação."""
        # 1. Vídeo de 1 dia com 389 views -> Tier S (Alta velocidade)
        tier_recent_viral = AlgorithmMemorySystem._calculate_exposure_aware_tier(
            views=389,
            exposure_days=1.0,
            views_per_day=389.0,
            projected_28d_views=1944,
            apv_pct=27.4,
            ctr_pct=3.5,
            retention_3s_pct=35.0
        )
        self.assertEqual(tier_recent_viral, "S")

        # 2. Vídeo de 28 dias com 100 views -> Tier B (Baixa velocidade diária ~3.5 v/d)
        tier_old_slow = AlgorithmMemorySystem._calculate_exposure_aware_tier(
            views=100,
            exposure_days=28.0,
            views_per_day=3.57,
            projected_28d_views=100,
            apv_pct=42.0,
            ctr_pct=2.0,
            retention_3s_pct=40.0
        )
        self.assertEqual(tier_old_slow, "B")

        # 3. Vídeo postado hoje com 3 views -> INCUBATING (Sandbox)
        tier_incubating = AlgorithmMemorySystem._calculate_exposure_aware_tier(
            views=3,
            exposure_days=1.0,
            views_per_day=3.0,
            projected_28d_views=15,
            apv_pct=10.0,
            ctr_pct=0.0,
            retention_3s_pct=20.0
        )
        self.assertEqual(tier_incubating, "INCUBATING")

    def test_check_and_auto_ingest_analytics_on_filename_change(self):
        """Verifica se check_and_auto_ingest_analytics detecta mudancas de nome de arquivo e novos zips."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analytics_folder = os.path.join(tmpdir, "analytics")
            memory_folder = os.path.join(tmpdir, "algorithm_memory")
            os.makedirs(analytics_folder, exist_ok=True)
            os.makedirs(memory_folder, exist_ok=True)

            memory_sys = AlgorithmMemorySystem(memory_dir=memory_folder)
            memory_sys.record_video_generation({
                "video_id": "batch_0_video_0",
                "batch": "batch_0",
                "video_index": 0,
                "tema": "McLaren F1: O V12 com Cofre Banhado a Ouro",
                "hook": "Ouro no motor?",
                "explicacao_tecnica": "Isolamento termico de ouro 24k"
            })

            # 1. Primeiro arquivo ZIP
            zip_1 = os.path.join(analytics_folder, "Content 2026-07-01_2026-07-28 Export.zip")
            csv_content_1 = """Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,Tempo de exibição (horas),Inscritos,Impressões,Taxa de cliques de impressões (%)
Total,,,,500,2.5,1,80,4.0
mclaren1,McLaren F1: O V12 com Cofre Banhado a Ouro #Shorts,"Jul 28, 2026",60,500,2.5,1,80,4.0
"""
            with zipfile.ZipFile(zip_1, "w") as z:
                z.writestr("Table data.csv", csv_content_1.encode("utf-8"))

            has_new, msg = memory_sys.check_and_auto_ingest_analytics(analytics_dir=analytics_folder)
            self.assertTrue(has_new)
            self.assertIn("Content 2026-07-01_2026-07-28 Export.zip", msg)

            # 2. Execucao subsequente sem mudancas no arquivo deve ser ignorada (idempotente)
            has_new_repeat, msg_repeat = memory_sys.check_and_auto_ingest_analytics(analytics_dir=analytics_folder)
            self.assertFalse(has_new_repeat)
            self.assertIn("já está ingerido", msg_repeat)

            # 3. Novo arquivo com NOME DIFERENTE (ex: novo relatorio semanal do YouTube)
            zip_2 = os.path.join(analytics_folder, "Content 2026-08-01_2026-08-28 Export.zip")
            csv_content_2 = """Conteúdo,Título do vídeo,Horário de publicação do vídeo,Duração,Visualizações,Tempo de exibição (horas),Inscritos,Impressões,Taxa de cliques de impressões (%)
Total,,,,2000,10.0,5,300,6.0
mclaren1,McLaren F1: O V12 com Cofre Banhado a Ouro #Shorts,"Aug 28, 2026",60,2000,10.0,5,300,6.0
"""
            with zipfile.ZipFile(zip_2, "w") as z:
                z.writestr("Table data.csv", csv_content_2.encode("utf-8"))

            # Como o nome do arquivo mudou, o sistema deve detectar e re-ingerir imediatamente
            has_new_changed, msg_changed = memory_sys.check_and_auto_ingest_analytics(analytics_dir=analytics_folder)
            self.assertTrue(has_new_changed)
            self.assertIn("Content 2026-08-01_2026-08-28 Export.zip", msg_changed)

            # Verifica se o historico refletiu a nova metrica (2000 views)
            history = memory_sys.load_history()
            rec = next(r for r in history if r["video_id"] == "batch_0_video_0")
            self.assertEqual(rec["analytics"]["views"], 2000)

if __name__ == "__main__":
    unittest.main()
