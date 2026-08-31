import unittest
import os
import sys
import json
from unittest.mock import MagicMock, patch

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from agents import DissertationAgent, DirectorAgent, extract_core_entity, save_video_metadata_file
from algorithm_memory import DEFAULT_ALGORITHM_MEMORY

class TestDissertationAndDistillation(unittest.TestCase):
    def setUp(self):
        self.sample_topic = {
            "tema": "Porsche 911 GT3 RS: A Física do Downforce de 860 kg",
            "hook": "Por que a Porsche instalou uma asa maior que o próprio teto?",
            "explicacao_tecnica": "O sistema DRS e os atuadores hidráulicos geram 860 kg de downforce a 285 km/h sem arrasto excessivo.",
            "descricao": "Entenda a física do Porsche 911 GT3 RS.",
            "tags": ["#Shorts", "#Porsche", "#GT3RS", "#Downforce", "#Engenharia"]
        }

    def test_extract_core_entity(self):
        core = extract_core_entity("Por que o Porsche 911 GT3 RS destrói nas pistas?")
        self.assertTrue("Porsche" in core or "911" in core or "GT3" in core)

        core_ferrari = extract_core_entity("A física do motor V12 da Ferrari 812 Competizione")
        self.assertTrue("Ferrari" in core_ferrari or "812" in core_ferrari)

    @patch("agents.generate_with_resilience")
    def test_dissertation_agent_structure(self, mock_gen):
        mock_response = json.dumps({
            "entidade_principal": "Porsche 911 GT3 RS",
            "especificacoes_tecnicas": {
                "motor": "4.0L Boxer 6 cilindros aspirado",
                "cv": "525 cv",
                "rpm": "9000 rpm",
                "downforce": "860 kg a 285 km/h"
            },
            "desafio_de_engenharia": "Eliminar o arrasto induzido em linha reta mantendo downforce em curvas.",
            "solucao_mecanica": "Asa com sistema DRS ativo operado por pistões hidráulicos e flaps dianteiros.",
            "impacto_historico_telemetria": "Volta em Nürburgring Nordschleife em 6:49.328.",
            "dissertacao_completa": (
                "O Porsche 911 GT3 RS geração 992 representa o ápice da aerodinâmica ativa em carros de produção. "
                "Utilizando um radiador central único herdado do 911 RSR, os engenheiros liberaram espaço nas laterais dianteiras "
                "para canais aerodinâmicos contínuos. A asa traseira com perfil biplano é equipada com atuadores que variam o ângulo "
                "de ataque em milissegundos, gerando 409 kg a 200 km/h e 860 kg na velocidade máxima de 285 km/h."
            )
        })
        mock_gen.return_value = mock_response

        agent = DissertationAgent(model_name="gemini-flash-lite-latest")
        result = agent.generate_dissertation(self.sample_topic)

        self.assertIn("especificacoes_tecnicas", result)
        self.assertIn("dissertacao_completa", result)
        self.assertEqual(result["entidade_principal"], "Porsche 911 GT3 RS")
        self.assertTrue(len(result["dissertacao_completa"]) > 100)

    @patch("agents.generate_with_resilience")
    def test_director_agent_distillation(self, mock_gen):
        dissertation_mock = {
            "entidade_principal": "Porsche 911 GT3 RS",
            "desafio_de_engenharia": "Arrasto vs Downforce",
            "solucao_mecanica": "DRS Ativo e Radiador Central",
            "dissertacao_completa": "Texto denso de engenharia mecânica."
        }

        mock_storyboard = json.dumps({
            "cenas": [
                {
                    "scene_id": 1,
                    "tipo": "broll",
                    "fala": "Esta asa traseira gera 860 quilos de força invisível empurrando este monstro para o chão.",
                    "youtube_query": "Porsche 911 GT3 RS active aero wing 4k",
                    "duracao_estimada": 3.5
                },
                {
                    "scene_id": 2,
                    "tipo": "broll",
                    "fala": "A 285 por hora, os pistões hidráulicos mudam o ângulo das aletas em milissegundos.",
                    "youtube_query": "Porsche 911 GT3 RS cornering track test 4k",
                    "duracao_estimada": 4.0
                }
            ]
        })
        mock_gen.return_value = mock_storyboard

        director = DirectorAgent(model_name="gemini-flash-lite-latest")
        storyboard = director.generate_storyboard(self.sample_topic, dissertacao_data=dissertation_mock)

        self.assertEqual(len(storyboard), 2)
        self.assertIn("youtube_query", storyboard[0])
        # Garante ancoragem estrita do modelo na query de busca
        self.assertTrue("porsche" in storyboard[0]["youtube_query"].lower())

    def test_metadata_generation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = save_video_metadata_file(tmpdir, self.sample_topic)
            self.assertTrue(os.path.exists(file_path))
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("TÍTULO:", content)
            self.assertIn("DESCRIÇÃO:", content)
            self.assertIn("HASHTAGS:", content)
            self.assertIn("#Shorts", content)

if __name__ == "__main__":
    unittest.main()
