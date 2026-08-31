# Como Gerar Vídeos Virais de Histórias do Reddit de Alto CPM (Dual Format 9:16 & 16:9)

Este guia prático ensina como operar o **Reddit Story Studio** integrado ao ecossistema para gerar vídeos monetizáveis de alto CPM em nichos como *Workplace Revenge*, *Malicious Compliance*, *Legal Advice* e *Finance*.

---

## 1. Modos de Execução

### A. Execução Rápida via Script Batch
Basta dar dois cliques no arquivo:
```cmd
scripts\gerar_video_reddit.bat
```
O sistema irá automaticamente:
1. Conectar aos subreddits de alto CPM (`r/maliciouscompliance`, `r/antiwork`, `r/legaladvice`, `r/AITAH`, `r/pettyrevenge`).
2. Estruturar o gancho viral dos primeiros 3 segundos.
3. Sintetizar a voz neural da persona adequada (`en-US-ChristopherNeural`, `en-US-JennyNeural`, `en-US-GuyNeural`).
4. Desenhar o Card Oficial do Reddit em Dark Mode (1080x1920 e 1920x1080).
5. Aplicar legendas dinâmicas animadas estilo Hormozi (Pill Box).
6. Exportar os vídeos finais e gerar o arquivo `metadata.txt` com Título, Descrição e Tags.

### B. Execução via Linha de Comando (CLI)
Você pode especificar subreddits e modelos customizados:
```bash
# Gerar vídeo a partir do r/antiwork
python -m src.reddit_pipeline --sub antiwork

# Gerar com modelo específico do Gemini
python -m src.reddit_pipeline --sub legaladvice --model gemini-flash-lite-latest
```

---

## 2. Estrutura dos Arquivos Gerados (Padrão Oficial de Batches Dual)

Todos os vídeos e metadados são organizados estritamente na estrutura de lotes contínuos com subpastas dedicadas:
`checkpoint/auto_batches/batch_1/video_0/`, `video_1/` ... `video_9/` (e progressão para `batch_2`, `batch_3`...)

Dentro de cada slot de vídeo (`video_X`):
```text
checkpoint/auto_batches/batch_1/video_0/
├── longform_25min/
│   ├── longform_master_25min_16x9.mp4  # Master 25min (1080p60) montado via stream copy
│   ├── narration_longform.mp3         # Áudio neural contínuo de 25 minutos
│   ├── script_data.json               # Roteiro da saga expandido em 8 capítulos
│   ├── metadata_youtube.txt           # Título, descrição e timestamps clicáveis
│   ├── cards/                         # Cards oficiais dos 8 capítulos ("Reddit Minute")
│   └── chunks/                        # Clipes individuais renderizados de cada capítulo
│
└── teaser_short/
    ├── teaser_short_9x16.mp4          # Short vertical (9:16) com gancho final de tela
    ├── narration_teaser.mp3           # Áudio da Parte 1 + gancho + CTA
    ├── script_teaser.json             # Roteiro do teaser focado em retenção
    ├── subtitles_teaser.ass           # Legendas Pill Box animadas
    ├── final_hook_badge.png           # Banner visual de tela "👉 FULL 25-MIN SAGA ON CHANNEL"
    └── metadata_teaser.txt            # Metadados e links para o vídeo longo
```
