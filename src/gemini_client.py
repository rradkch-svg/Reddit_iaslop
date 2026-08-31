import os
import re
import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from google.genai import types

try:
    from .logger import app_logger, LogSpan, record_throttling
except ImportError:
    from logger import app_logger, LogSpan, record_throttling

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_FALLBACK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-pro-latest"
]

def resolve_gemini_api_keys(explicit_keys: Optional[Any] = None) -> List[str]:
    """
    Resolve uma lista ordenada e única de chaves de API do Gemini a partir de múltiplas fontes:
    1. Chaves explícitas passadas (str, list ou separadas por vírgula/ponto-e-vírgula/newline)
    2. Arquivo 'gemini-api.txt' ou outros arquivos txt
    3. Variáveis de ambiente
    4. Arquivo '.env'
    """
    collected: List[str] = []

    def _add_key(k: Optional[str]):
        if not k:
            return
        k = k.strip().strip("'\"")
        if not k or k in ("sua_chave_gemini_aqui", "sua_chave_gemini_redundancia_aqui"):
            return
        if len(k) >= 20 and k not in collected:
            collected.append(k)

    if explicit_keys:
        if isinstance(explicit_keys, (list, tuple, set)):
            for k in explicit_keys:
                _add_key(str(k))
        elif isinstance(explicit_keys, str):
            for token in re.split(r"[,;\n\r\s]+", explicit_keys.strip()):
                _add_key(token)

    txt_candidates = [
        "gemini-api.txt",
        "gemini_api.txt",
        "keys.txt",
        "api_key.txt",
        "key.txt",
        "gemini-key.txt"
    ]
    search_dirs = [os.getcwd(), PROJECT_ROOT]

    for sdir in search_dirs:
        for fn in txt_candidates:
            full_fn = os.path.join(sdir, fn)
            if os.path.exists(full_fn):
                try:
                    with open(full_fn, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    headers = re.findall(r"X-goog-api-key:\s*['\"]?([A-Za-z0-9_\-\.]+)['\"]?", content, re.IGNORECASE)
                    for h in headers:
                        _add_key(h)

                    kvs = re.findall(r"(?:GEMINI_API_KEY|GEMINI_FALLBACK_API_KEY|GEMINI_BACKUP_API_KEY|GEMINI_API_KEYS)\s*=\s*['\"]?([A-Za-z0-9_\-\.,;]+)['\"]?", content, re.IGNORECASE)
                    for kv in kvs:
                        for token in re.split(r"[,;\s]+", kv):
                            _add_key(token)

                    for line in content.splitlines():
                        l = line.strip()
                        if l and not l.startswith("#") and not l.startswith("//") and " " not in l:
                            _add_key(l)
                except Exception as e:
                    app_logger.warning(f"[GeminiClient] Erro ao ler chaves de '{full_fn}': {str(e)}")

    env_vars = [
        "GEMINI_API_KEY",
        "GEMINI_FALLBACK_API_KEY",
        "GEMINI_API_KEY_FALLBACK",
        "GEMINI_BACKUP_API_KEY",
        "GEMINI_REDUNDANCY_KEY"
    ]
    for ev in env_vars:
        _add_key(os.environ.get(ev))

    env_keys_multi = os.environ.get("GEMINI_API_KEYS", "")
    if env_keys_multi:
        for token in re.split(r"[,;\s]+", env_keys_multi):
            _add_key(token)

    for sdir in search_dirs:
        env_file = os.path.join(sdir, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    env_content = f.read()
                matches = re.findall(r"(?:GEMINI_API_KEY|GEMINI_FALLBACK_API_KEY|GEMINI_API_KEY_FALLBACK|GEMINI_BACKUP_API_KEY|GEMINI_API_KEYS)\s*=\s*['\"]?([^\r\n'\"]+)['\"]?", env_content, re.IGNORECASE)
                for m in matches:
                    for token in re.split(r"[,;\s]+", m):
                        _add_key(token)
            except Exception:
                pass

    return collected

def resolve_gemini_api_key(explicit_key: Optional[str] = None) -> str:
    keys = resolve_gemini_api_keys(explicit_key)
    return keys[0] if keys else ""

_CLIENT_CACHE: Dict[str, genai.Client] = {}
_CLIENT_CACHE_LOCK = threading.Lock()

def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    key = resolve_gemini_api_key(api_key) if (api_key is None or not api_key.strip()) else api_key.strip()
    if not key:
        return genai.Client()
    
    with _CLIENT_CACHE_LOCK:
        if key not in _CLIENT_CACHE:
            _CLIENT_CACHE[key] = genai.Client(api_key=key)
        return _CLIENT_CACHE[key]

class GeminiRateLimiter:
    def __init__(self, max_rpm: int = 14):
        self.interval = 60.0 / max_rpm
        self.lock = threading.Lock()
        self.last_call = 0.0

    def acquire(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_call = time.time()

GLOBAL_RATE_LIMITER = GeminiRateLimiter(max_rpm=14)
_KEY_RATE_LIMITERS: Dict[str, GeminiRateLimiter] = {}
_KEY_RATE_LOCK = threading.Lock()
_KEY_COOLDOWNS: Dict[str, float] = {}

def get_rate_limiter_for_key(api_key: str, max_rpm: int = 14) -> GeminiRateLimiter:
    if not api_key:
        return GLOBAL_RATE_LIMITER
    with _KEY_RATE_LOCK:
        if api_key not in _KEY_RATE_LIMITERS:
            _KEY_RATE_LIMITERS[api_key] = GeminiRateLimiter(max_rpm=max_rpm)
        return _KEY_RATE_LIMITERS[api_key]

def get_prioritized_keys(keys: List[str]) -> List[str]:
    now = time.time()
    return sorted(keys, key=lambda k: _KEY_COOLDOWNS.get(k, 0.0) > now)

def extract_retry_seconds(error_str: str) -> int:
    match = re.search(r"retry in (\d+(\.\d+)?)s", str(error_str), re.IGNORECASE)
    if match:
        return int(float(match.group(1))) + 1
    match_sec = re.search(r"seconds:\s*(\d+)", str(error_str), re.IGNORECASE)
    if match_sec:
        return int(match_sec.group(1)) + 1
    match_delay = re.search(r"retryDelay':\s*'(\d+)s'", str(error_str), re.IGNORECASE)
    if match_delay:
        return int(match_delay.group(1)) + 1
    return 20

def generate_with_resilience(
    prompt: str,
    system_instruction: str,
    model_name: str = "gemini-flash-lite-latest",
    fallback_models: list = None,
    auto_fallback: bool = True,
    auto_cooldown: bool = True,
    response_mime_type: str = None,
    cooldown_callback = None,
    status_callback = None,
    timeout_seconds: float = 15.0,
    max_cooldown_retries: int = 1,
    api_keys: Optional[Any] = None
) -> str:
    """
    Executa chamada com streaming em tempo real, timeout, redundância de chaves e fallback de modelos.
    """
    if fallback_models is None:
        fallback_models = list(DEFAULT_FALLBACK_MODELS)
        
    models_to_try = [model_name]
    if auto_fallback:
        for m in fallback_models:
            if m not in models_to_try:
                models_to_try.append(m)

    configured_keys = resolve_gemini_api_keys(api_keys)
    if not configured_keys:
        configured_keys = [""]

    for m_idx, current_model in enumerate(models_to_try):
        retries_left = max_cooldown_retries
        while retries_left > 0:
            active_keys = get_prioritized_keys(configured_keys)
            key_succeeded = False
            last_key_error = None
            min_wait_sec = 20

            for k_idx, current_key in enumerate(active_keys):
                key_limiter = get_rate_limiter_for_key(current_key)
                key_limiter.acquire()
                
                client = get_genai_client(current_key if current_key else None)
                start_time = time.time()
                key_display = f"...{current_key[-6:]}" if len(current_key) >= 10 else "padrão"

                try:
                    if status_callback:
                        status_callback(f"Conectando ao modelo **{current_model}** (chave {key_display})...")

                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type=response_mime_type,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
                    )
                    
                    response_stream = client.models.generate_content_stream(
                        model=current_model,
                        contents=prompt,
                        config=config
                    )
                    
                    full_text = []
                    chunk_count = 0
                    for chunk in response_stream:
                        chunk_text = chunk.text or ""
                        full_text.append(chunk_text)
                        chunk_count += 1
                        elapsed = round(time.time() - start_time, 1)
                        if status_callback and chunk_count % 3 == 1:
                            total_len = sum(len(c) for c in full_text)
                            status_callback(f"Gerando via **{current_model}**... (⏱️ {elapsed}s • {total_len} carac.)")

                    final_text = "".join(full_text).strip()
                    if final_text:
                        elapsed = round(time.time() - start_time, 1)
                        if status_callback:
                            status_callback(f"✅ Concluído via **{current_model}** em {elapsed}s ({len(final_text)} caracteres).")
                        return final_text
                    else:
                        raise Exception("Resposta vazia do modelo.")
                    
                except Exception as e:
                    err_text = str(e)
                    elapsed = round(time.time() - start_time, 1)
                    last_key_error = e
                    is_quota = "ResourceExhausted" in type(e).__name__ or "RESOURCE_EXHAUSTED" in err_text or "Quota exceeded" in err_text or "429" in err_text
                    is_timeout = "DeadlineExceeded" in type(e).__name__ or "DEADLINE_EXCEEDED" in err_text or "timeout" in err_text.lower() or "504" in err_text
                    
                    if is_timeout:
                        app_logger.warning(f"[Gemini API] Timeout (> {timeout_seconds}s) no modelo {current_model} (chave {key_display})")
                        break

                    if is_quota:
                        wait_sec = extract_retry_seconds(err_text)
                        min_wait_sec = min(min_wait_sec, wait_sec)
                        _KEY_COOLDOWNS[current_key] = time.time() + wait_sec
                        record_throttling(
                            source="API_GEMINI",
                            event_type="RESOURCE_EXHAUSTED",
                            message=f"Quota excedida na chave {key_display}",
                            retry_after=wait_sec
                        )
                        app_logger.warning(f"[Gemini API] Quota atingida na chave {key_display} (espera: {wait_sec}s). Tentando próxima chave...")
                        continue

                    app_logger.error(f"[Gemini API] Erro no modelo {current_model}: {str(e)}")
                    break

            if key_succeeded:
                break

            if auto_cooldown and retries_left > 1:
                app_logger.warning(f"[Gemini API] Todas as chaves em cooldown. Aguardando {min_wait_sec}s antes de retentar...")
                for sec in range(min_wait_sec, 0, -1):
                    if cooldown_callback:
                        cooldown_callback(sec, min_wait_sec)
                    time.sleep(1.0)
                retries_left -= 1
            else:
                break

    raise RuntimeError(f"Falha ao gerar conteúdo com Gemini. Último erro: {str(last_key_error)}")
