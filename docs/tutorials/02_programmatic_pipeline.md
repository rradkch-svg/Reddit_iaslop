# Tutorial: Execução Programática do Pipeline em Python

Este tutorial ensina como invocar os agentes, os motores de áudio, busca e renderização diretamente via script Python 3.11+, sem a necessidade da interface gráfica Streamlit, para qualquer tema ou nicho.

---

## 1. Estrutura Básica do Script

Crie um arquivo chamado `run_custom_pipeline.py` na raiz do projeto:

```python
import os
import json
from dotenv import load_dotenv
from google import genai

from agents import DirectorAgent, ReviewerAgent
from audio import AudioEngine
from broll_engine import BRollEngine
from subtitles import convert_words_to_ass
from render import assemble_multi_scene_video

# 1. Carregar variáveis de ambiente e autenticar
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

output_dir = os.path.join(os.getcwd(), "custom_project_output")
os.makedirs(output_dir, exist_ok=True)
```

---

## 2. Definindo o Tema e Gerando o Storyboard

Você pode definir qualquer tema de interesse técnico, científico ou educacional:

```python
tema_input = {
    "tema": "A Física dos Reatores de Fusão Nuclear Tokamak e Campos Magnéticos",
    "hook": "Como uma estrela artificial é mantida suspensa no vácuo a 150 milhões de graus?",
    "explicacao_tecnica": "Bobinas magnéticas supercondutoras criam uma gaiola de plasma toroidal impedindo o contato térmico com as paredes metálicas."
}

director = DirectorAgent()
cenas = director.generate_storyboard(tema_input)
print(f"Storyboard gerado com {len(cenas)} cenas.")
```

---

## 3. Síntese de Voz e Legendas Sincronizadas

```python
audio_engine = AudioEngine(voice_name="pt-BR-AntonioNeural")
full_script = " ".join([c.get("fala", "") for c in cenas])
mp3_path = os.path.join(output_dir, "narration.mp3")

success_audio, words_timing = audio_engine.generate_audio(full_script, mp3_path)
total_audio_duration = words_timing[-1].get("end", 60.0) if words_timing else 60.0

ass_path = os.path.join(output_dir, "subtitles.ass")
convert_words_to_ass(words_timing, ass_path, primary_color="FFFFFF", highlight_color="FFE500")
print("Áudio e legendas sincronizadas gerados com sucesso.")
```

---

## 4. Coleta Paralela de Clipes e Auditoria Multimodal

```python
broll_engine = BRollEngine(max_search_results=6)
reviewer = ReviewerAgent()

scene_clips, scene_audits = broll_engine.process_all_scenes_parallel(
    cenas=cenas,
    global_topic=tema_input["tema"],
    reviewer_agent=reviewer,
    project_dir=output_dir,
    total_audio_duration=total_audio_duration,
    max_workers=4
)
print(f"Total de {len(scene_clips)} cenas coletadas, validadas com ffprobe e aprovadas por visão computacional.")
```

---

## 5. Renderização Final 9:16

```python
final_video = os.path.join(output_dir, "final_video_tokamak.mp4")
success_render, msg = assemble_multi_scene_video(scene_clips, mp3_path, ass_path, final_video)

if success_render:
    print(f"Vídeo 9:16 renderizado com sucesso em: {final_video}")
else:
    print(f"Falha na renderização: {msg}")
```

Execute o script no terminal com Python 3.11+:

```powershell
py -3.11 run_custom_pipeline.py
```
