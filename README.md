# AI Slop Studio - Plataforma Autônoma de Vídeo (9:16)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Diátaxis Documentation](https://img.shields.io/badge/docs-Diátaxis-green.svg)](docs/README.md)

AI Slop Studio é uma plataforma autônoma e resiliente para produção automatizada em lote de vídeos verticais (Shorts, Reels, TikTok) no formato 9:16, alimentada por um ecossistema multi-agentes (Gemini 2.5/Flash-Lite), síntese neural de voz (Edge-TTS), coleta e auditoria concorrente de clipes B-Roll (YouTube/yt-dlp) e legendas dinâmicas animadas estilo Hormozi.

---

## 🏗️ Estrutura do Projeto

O projeto segue rigorosamente os protocolos da **Systematic Project Architecture** e **Clean-Root Invariant**:

```text
automotive-slop/
├── .env.example                 # Modelo de variáveis de ambiente
├── .gitignore                   # Arquivos e pastas ignorados no controle de versão
├── AGENTS.md                    # Regras operacionais do projeto
├── GEMINI.md                    # Protocolo operacional global
├── pyproject.toml               # Configuração do pacote Python
├── requirements.txt             # Dependências de bibliotecas
├── README.md                    # Visão geral do repositório
│
├── src/                         # Código-fonte principal da aplicação
│   ├── __init__.py
│   ├── agents.py                # Agentes IA (Proposer, Evaluator, Director, Reviewer)
│   ├── app.py                   # Interface Web Streamlit interativa
│   ├── audio.py                 # Síntese neural de voz com Edge-TTS
│   ├── auto_pipeline.py         # Motor de processamento autônomo em lote
│   ├── broll_engine.py          # Busca, download e auditoria multimodal de B-Rolls
│   ├── checkpoint_manager.py    # Persistência atômica de checkpoints e blacklist
│   ├── logger.py                # Logging estruturado e detecção de throttling
│   ├── render.py                # Montagem e renderização final com FFmpeg
│   ├── subtitles.py             # Legendas ASS dinâmicas estilo Hormozi (Pill Box)
│   ├── visual_engine.py         # Motor de cartões e infográficos visuais 1080x1920
│   └── watchdog.py              # Supervisor de auto-restart e resiliência
│
├── scripts/                     # Scripts utilitários, automação e inicializadores
│   ├── auto_recovery.bat        # Recuperação acionada pelo Agendador do Windows
│   ├── iniciar.bat              # Atalho de inicialização
│   ├── iniciar_auto.bat         # Inicialização do pipeline autônomo
│   ├── iniciar_auto_geracao.bat # Inicializador completo da geração em batches
│   ├── iniciar_backend.bat      # Inicializador do painel WebUI Streamlit
│   ├── iniciar_watchdog.bat     # Inicializador do Watchdog supervisor
│   ├── setup_task.ps1           # Script PowerShell do Agendador de Tarefas
│   ├── registrar_agendador_tarefas.bat # Registra o Watchdog no Task Scheduler
│   ├── verificar_agendador_tarefas.bat # Exibe status em tempo real do agendador
│   ├── remover_agendador_tarefas.bat   # Remove a tarefa do Task Scheduler
│   ├── ativar_autologon.bat     # Ativa login automático no Windows
│   ├── desativar_autologon.bat  # Desativa login automático no Windows
│   └── benchmark_concurrency.py # Teste de concorrência e throughput
│
├── tests/                       # Suíte de testes automatizados
│   ├── __init__.py
│   ├── test_backend.py          # Testes de integração dos motores
│   └── test_pipeline_comprehensive.py # Testes de ponta a ponta do pipeline
│
├── docs/                        # Documentação Técnica Canônica (Diátaxis Framework)
│   ├── README.md                # Índice geral da documentação
│   ├── tutorials/               # Lições práticas guiadas
│   ├── how-to/                  # Guias de solução de problemas e receitas
│   ├── reference/               # Especificações técnicas e contratos de API
│   └── explanation/             # Fundamentação teórica e decisões de arquitetura
│
├── assets/                      # Recursos visuais, estáticos e referências
│   └── referencias/
│
├── checkpoint/                  # Checkpoints atômicos e vídeos gerados (ignorado no git)
└── logs/                        # Logs de execução diários (ignorado no git)
```

---

## 🚀 Como Iniciar

### 1. Pré-requisitos
- Python 3.10+ (recomendado Python 3.11)
- FFmpeg instalado e no PATH
- Chave de API do Google Gemini (configurada em `.env` ou `gemini-api.txt`)

Instalação das dependências:
```bash
pip install -r requirements.txt
```

### 2. Executando o Pipeline

- **Painel Interativo (WebUI):**
  Execute `scripts\iniciar_backend.bat` e acesse `http://localhost:8501`.

- **Geração Autônoma Contínua com Watchdog:**
  Execute `scripts\iniciar_watchdog.bat`.

- **Registrar Recuperação Automática no Windows:**
  Execute `scripts\registrar_agendador_tarefas.bat`.

---

## 📖 Documentação Completa

Consulte a [Documentação Técnica em `docs/`](docs/README.md) organizada conforme o Diátaxis Framework:
- [Tutorial de Início Rápido](docs/tutorials/01_quickstart.md)
- [Guia do Watchdog e Recuperação](docs/how-to/05_auto_recovery_and_watchdog.md)
- [Arquitetura do Sistema](docs/reference/01_system_architecture.md)
- [Filosofia Multi-Agentes](docs/explanation/01_multi_agent_philosophy.md)
