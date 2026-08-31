# Reddit Story Studio — Viral High-CPM Video Generator

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Plataforma profissional e autônoma para produção automatizada de vídeos do Reddit em alta qualidade (High CPM), especializada em:
1. **Vídeos Curtos (Shorts / Reels / TikTok 9:16):** Duração estendida de até 2.5 minutos com Card Oficial do Reddit, ritmo acelerado e pergunta de engajamento no final (CTA).
2. **Vídeos Longos (YouTube 16:9):** Narrativa profunda de **25 minutos** de uma **HISTÓRIA ÚNICA** (não um compilado), estruturada em 8 capítulos cronológicos da mesma história com cards e timestamps.
3. **Gameplay HD 1080p60:** Fundos de gameplay em alta resolução 1080x1920 e 1920x1080/2560x1440 a 60 fps (Minecraft Parkour sem copyright).
4. **Legendas Dinâmicas Hormozi:** Efeito palavra por palavra com destaque de alto contraste.
5. **Vozes Neurais:** Personas vocais automáticas adaptadas ao tom de cada relato.

---

## 🏗️ Estrutura do Projeto

```text
automotive-slop/
├── .env.example                 # Modelo de variáveis de ambiente
├── .gitignore                   # Arquivos ignorados no controle de versão
├── AGENTS.md                    # Regras operacionais do projeto
├── GEMINI.md                    # Protocolo operacional global
├── requirements.txt             # Dependências de bibliotecas
├── README.md                    # Visão geral do repositório
│
├── src/                         # Código-fonte principal da aplicação
│   ├── __init__.py
│   ├── gemini_client.py         # Cliente Gemini com redundância e rate limiter
│   ├── app.py                   # Painel Web Streamlit interativo
│   ├── auto_pipeline.py         # Pipeline de geração automática em lote
│   ├── reddit_agents.py         # Otimizador de roteiros e diretor de 25 minutos
│   ├── reddit_audio.py          # Síntese neural de voz por persona (Edge-TTS)
│   ├── reddit_longform.py       # Gerador de vídeo de 25 min de história única
│   ├── reddit_pipeline.py       # Pipeline de produção de Shorts (9:16)
│   ├── reddit_render.py         # Renderização FFmpeg com overlay de Cards e Legendas
│   ├── reddit_scraper.py        # Raspador ao vivo de subreddits de alto CPM
│   ├── reddit_subtitles.py      # Gerador de legendas dinâmicas ASS Hormozi
│   ├── reddit_visuals.py        # Motor de Cards Oficiais do Reddit (Dark Theme)
│   └── logger.py                # Logging estruturado e controle de execução
│
├── scripts/                     # Scripts de automação e atalhos
│   ├── download_hd_backgrounds.py # Downloader de backgrounds em 1080p60 HD
│   ├── gerar_video_reddit.bat     # Atalho para geração de Shorts 9:16
│   ├── gerar_longform_25min.bat   # Atalho para geração de História Única de 25min
│   ├── iniciar.bat                # Atalho para inicializar o painel WebUI
│   └── iniciar_backend.bat        # Inicializador do painel WebUI Streamlit
│
├── tests/                       # Suíte de testes automatizados
│   ├── test_background_resolutions.py # Validação de resolução 1080p60
│   ├── test_reddit_card_overlay.py    # Validação do overlay do Card do Reddit
│   ├── test_shorts_script_cta.py      # Validação de duração e CTA nos Shorts
│   └── test_longform_single_story.py  # Validação da história única de 25min
│
├── assets/                      # Recursos visuais e vídeos de fundo
│   └── backgrounds/             # Vídeos de gameplay 1080p60 HD
│
├── checkpoint/                  # Checkpoints e vídeos masters gerados
│   └── auto_batches/            # Estrutura oficial: batch_1, batch_2... (10 slots por lote)
│       └── batch_1/
│           ├── video_0/                     # 🌟 SLOT ESPECIAL DUAL
│           │   ├── longform_25min/          # 🎬 Master Longform 25min (16:9) + 8 chunks + narration
│           │   └── teaser_short/            # ⚡ Teaser Short (9:16) com Gancho Final de tela
│           ├── video_1/                     # 🚀 SHORTS INDIVIDUAIS NORMAIS
│           │   ├── reddit_story_short_9x16.mp4
│           │   └── script_data.json
│           └── ... video_9/
```

---

## 🚀 Como Iniciar

### 1. Pré-requisitos
- Python 3.10+ (recomendado Python 3.11)
- FFmpeg instalado
- Chave de API do Google Gemini (opcional, fallback algorítmico ativo)

### 2. Executando o Estúdio

- **Painel Interativo (WebUI):**
  Execute `iniciar.bat` ou `scripts\iniciar_backend.bat` e acesse `http://localhost:8501`.

- **Geração Automática Contínua de Lotes (video_0 Dual + video_1..9 Shorts):**
  Execute `scripts\iniciar_auto_geracao.bat` ou:
  ```bash
  python src/auto_pipeline.py --count 10
  ```

- **Gerar Short 9:16 Individual no próximo slot:**
  ```bash
  python -m src.reddit_pipeline --sub maliciouscompliance
  ```

- **Gerar Vídeo Longo de 25 Minutos (História Única em 8 Capítulos):**
  ```bash
  python -m src.reddit_longform
  ```

- **Verificar Status dos Batches:**
  ```bash
  python src/auto_pipeline.py --status
  ```

- **Executar Suíte de Testes:**
  ```bash
  python -m unittest discover -s tests
  ```
