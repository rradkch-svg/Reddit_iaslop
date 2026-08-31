# Referência da API: Motor de Coleta e Varredura de B-Rolls (`broll_engine.py`)

Especificação técnica das classes e funções responsáveis pela busca, download, validação de duração via `ffprobe`, varredura multi-trechos (*segment scanning*) e orquestração concorrente com propagação de contexto Streamlit.

---

## 1. Funções Auxiliares

### `find_ffmpeg_binary() -> str`
Localiza dinamicamente o executável do FFmpeg no sistema ou no caminho padrão do WinGet.

### `get_video_duration(file_path: str, ffmpeg_bin: str = "ffmpeg") -> Optional[float]`
Executa o `ffprobe` no arquivo baixado para extrair a duração real exata em segundos (`format=duration`). Previne que valores de seek (`-ss`) ou duração de corte (`-t`) ultrapassem o fim do arquivo, eliminando o erro de saída `3199971767` (`AVERROR_EOF`).

---

## 2. `BRollEngine`

Classe central para download de tomadas, recorte vertical 9:16 (1080x1920) e auditoria visual com IA.

### Construtor

```python
BRollEngine(max_search_results: int = 6)
```

- **`max_search_results` (`int`):** Número de vídeos candidatos inspecionados por query no YouTube via `yt-dlp`.

---

## 3. Métodos Principais

### `search_and_download_clip`

Executa a busca, download do vídeo bruto em alta definição, valida a duração via `ffprobe` e varre múltiplos trechos temporais (timestamps) até encontrar um segmento aprovado pelo `ReviewerAgent`.

```python
search_and_download_clip(
    query: str,
    target_duration: float,
    seen_ids: Set[str],
    output_clip_path: str,
    global_topic: str = "Tópico Global",
    reviewer_agent = None,
    scene_fala: str = "",
    status_callback = None
) -> Tuple[bool, str, str, str, Dict[str, Any]]
```

#### Parâmetros:
- **`query` (`str`):** Termo de busca em inglês gerado pelo `DirectorAgent` (otimizado para pure sound / exhaust acoustics).
- **`target_duration` (`float`):** Duração desejada do corte em segundos.
- **`seen_ids` (`Set[str]`):** Conjunto com os IDs de mídia já utilizados no projeto atual (impede repetição de vídeo).
- **`output_clip_path` (`str`):** Caminho de destino do arquivo `.mp4` 9:16 recortado com áudio estéreo preservado.
- **`global_topic` (`str`):** Título do tema central para ancoragem da auditoria visual e acústica.
- **`reviewer_agent` (`ReviewerAgent`, opcional):** Instância do auditor multimodal para julgamento visual (Zero Faces) e acústico (Zero Voz Humana).
- **`scene_fala` (`str`):** Frase falada na cena correspondente.
- **`status_callback` (`callable`, opcional):** Função para recebimento de atualizações de status.

#### Política de Áudio e Isolamento de Voz:
- **Preservação de Som Puro:** O áudio original do clipe (ronco, escape, turbo, trocas de marcha) é preservado e codificado em AAC 44.1kHz estéreo.
- **Filtro Anti-Voz Humana:** Se o `ReviewerAgent` detectar voz/fala humana no segmento, o áudio desta cena específica é silenciado automaticamente com `anullsrc`, mantendo a filmagem visual aprovada sem vazar conversas.

#### Retorno:
Tupla de 5 elementos contendo `(sucesso: bool, clip_path: str, video_id: str, video_title: str, parecer: Dict)`.

---

### `process_all_scenes_parallel`

Orquestra o download e auditoria de todas as cenas do roteiro de forma concorrente em batches com um pool de threads (`ThreadPoolExecutor`), propagando automaticamente o `ScriptRunContext` do Streamlit para as threads filhas.

```python
process_all_scenes_parallel(
    cenas: List[Dict[str, Any]],
    global_topic: str,
    reviewer_agent,
    project_dir: str,
    total_audio_duration: float,
    max_workers: int = 4,
    status_callback = None,
    progress_callback = None
) -> Tuple[List[str], List[Dict[str, Any]]]
```

#### Parâmetros:
- **`cenas` (`List[Dict]`):** Lista completa de cenas do roteiro gerada pelo `DirectorAgent`.
- **`global_topic` (`str`):** Título do tema principal para avaliação semântica.
- **`reviewer_agent` (`ReviewerAgent`):** Instância do auditor de visão computacional.
- **`project_dir` (`str`):** Diretório do projeto para gravação dos clipes parciais.
- **`total_audio_duration` (`float`):** Duração total da narração para cálculo proporcional.
- **`max_workers` (`int`):** Número de threads simultâneas (padrão: 4).
- **`status_callback` (`callable`, opcional):** Callback para logs textuais de status.
- **`progress_callback` (`callable`, opcional):** Callback invocado com `(concluidas: int, total: int)` a cada cena finalizada.

#### Retorno:
Tupla contendo `(scene_clips: List[str], scene_audits: List[Dict])` ordenados estritamente na sequência cronológica original do roteiro.
