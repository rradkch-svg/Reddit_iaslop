# Referência da API: Módulo de Agentes (`agents.py`)

Especificação técnica detalhada das classes de agentes, funções de resiliência e controle de taxa de requisições baseadas no pacote oficial `google-genai` (v2.20.0).

---

## 1. `GeminiRateLimiter`

Controla a taxa de emissão de requisições para respeitar o teto de RPM da API do Google Gemini.

### Construtor

```python
GeminiRateLimiter(max_rpm: int = 14)
```

- **`max_rpm` (`int`):** Número máximo de chamadas permitidas por minuto (padrão seguro para a camada gratuita: 14).

### Métodos

- **`acquire() -> None`:** Bloqueia a thread chamadora até que o intervalo temporal seguro tenha transcorrido.

---

## 2. `ProposerAgent`

Gera propostas estruturadas de temas com alto potencial de engajamento e retenção.

### Construtor

```python
ProposerAgent(
    model_name: str = "gemini-flash-lite-latest",
    auto_fallback: bool = True,
    auto_cooldown: bool = True,
    fallback_models: list = None
)
```

### Métodos

- **`generate_topics(count: int = 10, seed: int = None, cooldown_callback = None, status_callback = None) -> List[Dict[str, Any]]`:**
  - Gera uma lista de propostas de temas inéditos com injeção dinâmica de entropia/seed e amostragem de ângulos temáticos variados.
  - Prioriza veículos amplamente consagrados e com alto volume de filmagens em 4K no YouTube para maximizar a convergência de busca de B-Rolls.
  - Retorna uma lista de dicionários com as chaves:
    - `'tema'` (`str`): Título marcante do tema (incluindo marca e modelo exatos).
    - `'hook'` (`str`): Pergunta ou afirmação de abertura para prender a atenção nos primeiros 3 segundos.
    - `'explicacao_tecnica'` (`str`): Síntese explicativa do mecanismo, fenômeno ou princípio abordado.

---

## 3. `EvaluatorAgent`

Avalia criticamente a viabilidade de retenção, clareza e profundidade de um tema proposto.

### Métodos

- **`evaluate_topic(topic_data: Dict[str, Any], cooldown_callback = None, status_callback = None) -> Dict[str, Any]`:**
  - Retorna um dicionário com:
    - `'nota'` (`float`): Avaliação quantitativa de 0.0 a 10.0.
    - `'veredicto'` (`str`): Veredicto formal (ex: "Aprovado", "Necessita Ajustes").
    - `'justificativa'` (`str`): Parecer qualitativo detalhando forças e fraquezas do tema.

---

## 4. `DirectorAgent`

Decompõe o tema aprovado em um roteiro completo de 1 a 2 minutos estruturado em cenas sequenciais com termos de busca visuais.

### Métodos

- **`generate_storyboard(tema: Dict[str, Any], cooldown_callback = None, status_callback = None) -> List[Dict[str, Any]]`:**
  - Retorna a lista de cenas (`'cenas'`), onde cada cena contém:
    - `'scene_id'` (`int`): Identificador sequencial da cena.
    - `'fala'` (`str`): Texto falado pelo narrador durante a cena.
    - `'youtube_query'` (`str`): Termo de busca em inglês (3 a 6 palavras) focado no objeto/ação da cena.
    - `'duracao_estimada'` (`float`): Duração estimada em segundos.

---

## 5. `ReviewerAgent`

Audita visualmente cada trecho de vídeo extraído através de análise multimodal de imagem (Gemini Vision) com timeout de 60s.

### Métodos

- **`pre_filter_title(video_title: str, global_topic: str) -> Tuple[bool, str]`:**
  - Avaliação rápida heurística de metadados em $O(1)$ antes do download.
- **`extract_clip_frame(clip_path: str) -> Optional[PIL.Image.Image]`:**
  - Extrai um frame do clipe a 1.5s e redimensiona para 384x384 pixels para envio leve à API.
- **`inspect_clip(clip_path: str, global_topic: str, scene_fala: str, video_title: str, status_callback = None) -> Dict[str, Any]`:**
  - Retorna um dicionário com:
    - `'aprovado'` (`bool`): `True` se o trecho atender aos critérios de qualidade e ausência de pessoas; `False` caso contrário.
    - `'score'` (`float`): Nota de 0.0 a 10.0.
    - `'motivo'` (`str`): Justificativa do veredicto visual.
    - `'elementos_detectados'` (`str`): Descrição textual dos elementos identificados no quadro.

---

## 6. Funções Utilitárias e Resiliência Multi-Chave

### `resolve_gemini_api_keys(explicit_keys: Optional[Any] = None) -> List[str]`
- Extrai e deduplica todas as chaves de API disponíveis em arquivos (`gemini-api.txt`, `key.txt`, `.env`), variáveis de ambiente (`GEMINI_API_KEY`, `GEMINI_FALLBACK_API_KEY`, `GEMINI_API_KEYS`) e argumentos explícitos, preservando a ordem de prioridade.

### `resolve_gemini_api_key(explicit_key: Optional[str] = None) -> str`
- Retorna a primeira chave válida da lista de resolução para manter retrocompatibilidade com chamadas legado.

### `generate_with_resilience(...) -> str`
- Executa chamadas com streaming em tempo real, timeout configurado (padrão 60s), alternância automática de chaves em caso de erro `429 RESOURCE_EXHAUSTED` e fallback de modelos em cascata.

### `generate_multimodal_with_resilience(...) -> str`
- Executa inspeção multimodal de imagens com isolamento de rate limiter por chave e alternância instantânea para a chave de redundância em caso de throttling.
