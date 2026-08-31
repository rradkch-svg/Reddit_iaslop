import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from deduplication import (
    sanitize_and_cap_title,
    extract_canonical_entity,
    classify_technical_domains,
    extract_semantic_stems,
    ContextualTopicAuditor,
    DEFAULT_CONTEXTUAL_AUDITOR
)
from agents import generate_video_metadata_text
from checkpoint_manager import CheckpointManager

class TestDeduplicationAndTitleConstraints(unittest.TestCase):
    def test_title_max_100_characters(self):
        """Verifica se títulos longos são estritamente truncados em <= 100 caracteres sem quebrar palavras."""
        long_title = "Porsche 911 GT3 RS: A Insana Aerodinâmica de Efeito Solo com Asa Traseira de 860 kg que Gruda o Carro no Asfalto em Nürburgring"
        self.assertGreater(len(long_title), 100)
        
        capped = sanitize_and_cap_title(long_title, max_length=100)
        self.assertLessEqual(len(capped), 100)
        self.assertFalse(capped.endswith(" "))
        self.assertTrue(capped.startswith("Porsche 911 GT3 RS"))

    def test_removal_of_segredos_da_engenharia_suffix(self):
        """Verifica se o sufixo '| Segredos da Engenharia' é removido em todas as suas variações."""
        cases = [
            ("Ferrari F40: A Bruta Engenharia dos Turbos Duplos | Segredos da Engenharia", "Ferrari F40: A Bruta Engenharia dos Turbos Duplos"),
            ("Toyota Supra 2JZ: O Bloco Indestrutível - Segredos da Engenharia", "Toyota Supra 2JZ: O Bloco Indestrutível"),
            ("🏎️ BMW M3 CSL E46: O Teto de Fibra de Carbono | Segredo da Engenharia", "BMW M3 CSL E46: O Teto de Fibra de Carbono"),
            ("🔥 Audi RS6 Avant: A Insana Tração Quattro | AutoTech", "Audi RS6 Avant: A Insana Tração Quattro")
        ]
        for original, expected in cases:
            cleaned = sanitize_and_cap_title(original)
            self.assertEqual(cleaned, expected)
            self.assertNotIn("Segredos da Engenharia", cleaned)
            self.assertNotIn("🏎️", cleaned)
            self.assertNotIn("🔥", cleaned)

    def test_metadata_generator_title_cap_and_no_suffix(self):
        """Verifica se generate_video_metadata_text gera título com <= 100 chars e sem Segredos da Engenharia."""
        topic = {
            "tema": "McLaren Senna: A Insana Física Aerodinâmica Ativa com Flaps Ocultos e Difusores Traseiros Duplos | Segredos da Engenharia",
            "hook": "Como a McLaren colocou 800 kg de downforce sem quebrar o carro?",
            "explicacao_tecnica": "Flaps ativos na dianteira equilibram o centro de pressão aerodinâmica."
        }
        metadata_txt = generate_video_metadata_text(topic)
        self.assertNotIn("Segredos da Engenharia", metadata_txt)
        
        # Extrai a linha do título
        title_line = [l.strip() for l in metadata_txt.splitlines() if l.strip() and not l.startswith("TÍTULO:") and not l.startswith("DESCRIÇÃO:")][0]
        self.assertLessEqual(len(title_line), 100)

    def test_contextual_heuristic_deduplication_same_vehicle_different_title(self):
        """
        Verifica a detecção heurística de duplicata contextual:
        Mesmo carro com palavras completamente diferentes abordando o mesmo subsistema de engenharia.
        """
        existing_database = [
            {
                "tema": "Porsche 911 GT3 RS: A Física do Downforce de 860 kg",
                "core_entity": "Porsche 911 GT3 RS",
                "hook": "Como este Porsche gera quase uma tonelada de pressão aerodinâmica?",
                "explicacao_tecnica": "A asa traseira ativa com sistema DRS e os dutos no capô criam downforce brutal sem arrasto excessivo."
            }
        ]

        # Candidato 1: Título refraseado falando sobre a mesma aerodinâmica do 911 GT3 RS
        candidate_paraphrased = {
            "tema": "Como a asa ativa com DRS do Porsche 911 GT3 RS gruda o carro na pista em curvas rápidas",
            "hook": "Entenda a aerodinâmica e o arrasto reduzido deste monstro de Nürburgring",
            "explicacao_tecnica": "Os flaps do aerofólio traseiro e o efeito solo geram sustentação negativa."
        }

        auditor = ContextualTopicAuditor()
        is_dup, conf, reason = auditor.evaluate_candidate(candidate_paraphrased, existing_database)
        
        self.assertTrue(is_dup, f"Deveria ter identificado repetição de tema. Razão: {reason}")
        self.assertGreater(conf, 0.70)
        self.assertIn("Porsche 911 GT3 RS", reason)

    def test_contextual_heuristic_deduplication_different_vehicle_same_concept(self):
        """
        Verifica que carros DIFERENTES abordando o mesmo conceito (ex: Efeito Solo) NÃO são bloqueados.
        """
        existing_database = [
            {
                "tema": "Aston Martin Valkyrie: A Insana Física do Efeito Solo Venturi",
                "core_entity": "Aston Martin Valkyrie",
                "hook": "Como este hipercarro gera 1.8 toneladas de downforce sem asas gigantes?",
                "explicacao_tecnica": "Túneis venturi gigantes sob o assoalho criam sucção extrema."
            }
        ]

        candidate_different_car = {
            "tema": "Porsche 911 GT3 RS: A Asa Ativa e o Downforce de 860 kg",
            "core_entity": "Porsche 911 GT3 RS",
            "hook": "Como a asa traseira deste Porsche gruda nas curvas de alta?",
            "explicacao_tecnica": "Aerodinâmica ativa com DRS."
        }

        auditor = ContextualTopicAuditor()
        is_dup, conf, reason = auditor.evaluate_candidate(candidate_different_car, existing_database)
        self.assertFalse(is_dup, f"Carros diferentes com asas distintas não devem ser bloqueados. Razão: {reason}")

    def test_checkpoint_manager_is_in_blacklist_integration(self):
        """Testa o método is_in_blacklist do CheckpointManager com a nova auditoria contextual."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CheckpointManager(root_dir=tmpdir)
            mgr.add_to_blacklist({
                "tema": "BMW M3 CSL E46: A Insana Inovação do Teto de Fibra de Carbono",
                "hook": "Como a BMW reduziu o centro de gravidade usando carbono no teto?",
                "explicacao_tecnica": "O teto de fibra de carbono alivia peso no ponto mais alto do chassi."
            }, "batch_0", "video_0")

            # Teste 1: Tema idêntico ou muito similar
            is_blk1, r1 = mgr.is_in_blacklist("BMW M3 CSL E46: O Segredo do Teto de Carbono")
            self.assertTrue(is_blk1, f"Deveria ter bloqueado duplicata: {r1}")

            # Teste 2: Tema 100% inédito
            is_blk2, r2 = mgr.is_in_blacklist("Mazda 787B: O Lendário Motor Wankel 4-Rotor de Le Mans")
            self.assertFalse(is_blk2, f"Tema inédito não deveria ser bloqueado: {r2}")

if __name__ == "__main__":
    unittest.main()
