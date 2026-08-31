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

## 2. Estrutura dos Arquivos Gerados (Padrão Oficial de Batches)

Todos os vídeos e metadados são organizados estritamente na estrutura de lotes contínuos:
`checkpoint/auto_batches/batch_1/video_0/`, `video_1/` ... `video_9/` (e progressão para `batch_2`, `batch_3`...)

Arquivos gerados por slot de vídeo (`video_X`):
- `reddit_story_short_9x16.mp4` — Master vertical (1080x1920 @ 60fps) para YouTube Shorts, Reels e TikTok.
- `reddit_story_master_16x9.mp4` — Master horizontal (1920x1080 @ 60fps) para YouTube Principal.
- `reddit_card_9x16.png` e `reddit_card_16x9.png` — Cards de sobreposição em alta definição ("Reddit Minute").
- `narration_shorts.mp3` — Áudio com entonação dramática e ritmo acelerado (+20%).
- `subtitles_shorts.ass` — Legendas sincronizadas milissegundo a milissegundo.
- `metadata.txt` — Título com alto CTR, descrição estruturada com timestamps e hashtags virais.
- `script_data.json` — Dados estruturados da história, gancho e CTA de comentários.
