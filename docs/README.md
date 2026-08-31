# Documentação Técnica da Plataforma Autônoma de Vídeo (Diátaxis Framework)

Bem-vindo à documentação completa do pipeline autônomo e modular de geração de vídeos curtos em formato vertical 9:16 (Shorts, Reels, TikTok) para qualquer nicho de conhecimento, ciência, tecnologia e educação.

Esta documentação é organizada rigorosamente de acordo com os quatro quadrantes canônicos do [Diátaxis Framework](https://diataxis.fr/):

```text
               PRÁTICA (Foco no Trabalho)
                      ▲
        Tutoriais      │      Guias Como-Fazer
     (Orientado ao     │     (Orientado a Metas)
      Aprendizado)     │
──────────────────────┼──────────────────────► CONHECIMENTO
        Explicação     │         Referência
     (Orientado ao     │       (Orientado à
      Entendimento)    │        Informação)
                      ▼
               TEORIA (Foco no Estudo)
```

---

## 1. 🎓 Tutoriais (Learning-Oriented)
Lições práticas passo a passo para novos usuários e desenvolvedores:
- [01. Criação do Primeiro Vídeo 9:16 com a WebUI](tutorials/01_quickstart.md)
- [02. Execução Programática do Pipeline em Python](tutorials/02_programmatic_pipeline.md)

---

## 2. 🛠️ Guias Práticos / How-To (Goal-Oriented)
Receitas e soluções diretas para tarefas de configuração, operação e ajuste:
- [01. Configuração do Ambiente e Dependências (Python 3.11+)](how-to/01_environment_setup.md)
- [02. Gestão de Cotas, Rate Limiting e Alertas de Throttling](how-to/02_rate_limits_and_quotas.md)
- [03. Customização de Políticas Visuais e Varredura de Trechos](how-to/03_zero_faces_customization.md)
- [04. Personalização de Vozes Neurais e Estilização de Legendas](how-to/04_subtitles_and_audio_styling.md)
- [05. Watchdog e Recuperação Automática Contínua](how-to/05_auto_recovery_and_watchdog.md)

---

## 3. 📖 Referência (Information-Oriented)
Especificações técnicas completas, contratos de API, classes e parâmetros:
- [01. Arquitetura Geral do Sistema e Fluxo de Dados](reference/01_system_architecture.md)
- [02. API do Módulo de Agentes e Rate Limiter (`agents.py`)](reference/02_agents_api.md)
- [03. API do Motor de Coleta e Varredura de B-Rolls (`broll_engine.py`)](reference/03_broll_engine_api.md)
- [04. API de Áudio, Legendas e Renderização (`audio.py`, `subtitles.py`, `render.py`)](reference/04_rendering_and_subtitles_api.md)
- [05. API de Deduplicação Heurística de Contexto e Títulos (`deduplication.py`)](reference/05_deduplication_and_title_api.md)

---

## 4. 🧠 Explicação (Understanding-Oriented)
Discussões conceituais, fundamentação teórica e decisões de arquitetura:
- [01. Filosofia do Sistema Multi-Agentes com Auditoria Multimodal](explanation/01_multi_agent_philosophy.md)
- [02. Varredura Temporal de Trechos e Enquadramento Dinâmico 9:16](explanation/02_smart_segment_scanning.md)
- [03. Psicologia da Retenção Visual e Legendas Sincronizadas (Pill Box)](explanation/03_visual_retention_and_pillbox.md)
- [04. Estudo de Escalabilidade Concorrente e Gestão de Recursos](explanation/04_concurrency_benchmarks.md)
