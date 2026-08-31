import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock

# Ajusta caminhos
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from audio import AudioEngine
from agents import ProposerAgent, DissertationAgent, DirectorAgent, ReviewerAgent, KNOWN_AUTOMOTIVE_BRANDS
from pronunciation import DEFAULT_PRONUNCIATION_ENGINE, AUTOMOTIVE_PHONETIC_LEXICON
from deduplication import TECHNICAL_DOMAINS, classify_technical_domains, extract_canonical_entity

class TestNicheExpansionAndPacing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_audio_engine_125x_atempo_filter_and_timing(self):
        """Valida que o AudioEngine aplica aceleração 1.25x e ajusta a duração/marcações das palavras."""
        with patch("audio.resolve_gemini_api_keys", return_value=["dummy_key"]), \
             patch("subprocess.run") as mock_subproc, \
             patch("google.genai.Client") as mock_client_cls:
            
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            
            mock_response = MagicMock()
            mock_candidate = MagicMock()
            mock_part = MagicMock()
            mock_inline_data = MagicMock()
            
            # 2 segundos de áudio bruto (24000 amostras/s * 2 bytes * 2s = 96000 bytes)
            fake_pcm = b"\x00\x00" * 48000
            mock_inline_data.data = fake_pcm
            mock_part.inline_data = mock_inline_data
            mock_candidate.content.parts = [mock_part]
            mock_response.candidates = [mock_candidate]
            mock_client.models.generate_content.return_value = mock_response

            engine = AudioEngine(voice="gemini:Charon", rate="+25%")
            out_mp3 = os.path.join(self.temp_dir, "fast_charon.mp3")
            
            text = "O caça SR-71 Blackbird usa turbinas J58 para voar a Mach 3."
            success, words_timing = engine.generate_audio(text, out_mp3)
            
            self.assertTrue(success)
            self.assertIsInstance(words_timing, list)
            
            # Duração bruta = 2.0s. Com 1.25x, duração final = 2.0 / 1.25 = 1.6s
            expected_total_dur = 2.0 / 1.25
            self.assertAlmostEqual(words_timing[-1]["end"], expected_total_dur, delta=0.05)
            
            # Verifica se o comando ffmpeg incluiu o filtro atempo=1.250
            cmd_args = mock_subproc.call_args[0][0]
            self.assertIn("-filter:a", cmd_args)
            self.assertIn("atempo=1.250", cmd_args)

    def test_proposer_agent_covers_broad_engine_niche(self):
        """Valida que o ProposerAgent possui diretrizes para todo o universo de motores."""
        proposer = ProposerAgent()
        instr = proposer.system_instruction.lower()
        self.assertIn("motores", instr)
        self.assertIn("aviões", instr)
        self.assertIn("tanques de guerra", instr)
        self.assertIn("supermotos", instr)
        self.assertIn("wankel", instr)
        self.assertIn("diesel", instr)
        self.assertIn("elétricos", instr)

    def test_dissertation_and_director_cover_broad_engines(self):
        """Valida que DissertationAgent e DirectorAgent cobrem caças, tanques, motos e powertrains."""
        diss = DissertationAgent()
        self.assertIn("turbinas", diss.system_instruction.lower())
        self.assertIn("tanques", diss.system_instruction.lower())
        
        director = DirectorAgent()
        self.assertIn("afterburner", director.system_instruction.lower())

    def test_pronunciation_lexicon_for_new_vehicles_and_engines(self):
        """Valida que o dicionário fonético converte termos aeronáuticos, militares, motos e motores."""
        phon = DEFAULT_PRONUNCIATION_ENGINE
        
        # Aeronáutica
        self.assertIn("Blék-bârd", phon.phoneticize("SR-71 Blackbird"))
        self.assertIn("Éfter-bârner", phon.phoneticize("turbojet com afterburner"))
        self.assertIn("Mák", phon.phoneticize("voa a Mach 3"))
        
        # Tanques
        self.assertIn("Êi-brans", phon.phoneticize("Tanque M1 Abrams"))
        self.assertIn("Léopard", phon.phoneticize("Tanque Leopard 2"))
        
        # Motos
        self.assertIn("Kaua-záki", phon.phoneticize("Kawasaki Ninja H2R"))
        self.assertIn("Raia-búza", phon.phoneticize("Suzuki Hayabusa"))
        
        # Wankel / Diesel / Elétrico
        self.assertIn("Éipex síuls", phon.phoneticize("apex seals do motor wankel"))
        self.assertIn("Rímac Nevêra", phon.phoneticize("Rimac Nevera"))
        self.assertIn("Câ-mins", phon.phoneticize("motor Cummins 6BT"))

    def test_technical_domains_classification(self):
        """Valida classificação de novos domínios mecânicos."""
        self.assertIn("PROPULSAO_AERONAUTICA_JATO", TECHNICAL_DOMAINS)
        self.assertIn("PROPULSAO_MILITAR_BLINDADOS", TECHNICAL_DOMAINS)
        self.assertIn("MOTOCICLETAS_ALTO_GIRO", TECHNICAL_DOMAINS)
        self.assertIn("PROPULSAO_ELETRICA_ALTA_TENSAO", TECHNICAL_DOMAINS)
        self.assertIn("CICLO_DIESEL_ALTA_PRESSAO", TECHNICAL_DOMAINS)
        self.assertIn("CICLO_WANKEL_ROTATIVO", TECHNICAL_DOMAINS)
        
        domains_jet = classify_technical_domains("SR-71 Blackbird com turbina J58 e pós-combustão Mach 3")
        self.assertIn("PROPULSAO_AERONAUTICA_JATO", domains_jet)
        
        domains_tank = classify_technical_domains("Tanque M1 Abrams com turbina a gás Honeywell")
        self.assertIn("PROPULSAO_MILITAR_BLINDADOS", domains_tank)

if __name__ == "__main__":
    unittest.main()
