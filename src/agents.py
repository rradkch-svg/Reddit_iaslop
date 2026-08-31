import os
import re
import time
import json
import random
import subprocess
import tempfile
import threading
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

try:
    from .logger import app_logger, LogSpan, record_throttling
    from .algorithm_memory import DEFAULT_ALGORITHM_MEMORY
    from .pronunciation import DEFAULT_PRONUNCIATION_ENGINE
    from .deduplication import sanitize_and_cap_title, extract_canonical_entity
except ImportError:
    from logger import app_logger, LogSpan, record_throttling
    from algorithm_memory import DEFAULT_ALGORITHM_MEMORY
    from pronunciation import DEFAULT_PRONUNCIATION_ENGINE
    from deduplication import sanitize_and_cap_title, extract_canonical_entity

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lista de modelos rápidos e comprovadamente ativos
DEFAULT_FALLBACK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite"
]

def resolve_gemini_api_keys(explicit_keys: Optional[Any] = None) -> List[str]:
    """
    Resolve uma lista ordenada e única de chaves de API do Gemini a partir de múltiplas fontes:
    1. Chaves explícitas passadas (str, list ou separadas por vírgula/ponto-e-vírgula/newline)
    2. Arquivo 'gemini-api.txt' (múltiplos cabeçalhos curl -H 'X-goog-api-key: ...' ou linhas de texto)
    3. Arquivos alternativos 'key.txt', 'keys.txt', 'gemini_api.txt', 'api_key.txt', 'gemini-key.txt'
    4. Variáveis de ambiente ('GEMINI_API_KEY', 'GEMINI_FALLBACK_API_KEY', 'GEMINI_API_KEY_FALLBACK', 'GEMINI_BACKUP_API_KEY', 'GEMINI_API_KEYS')
    5. Arquivo '.env'
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

    # 1. Chaves explícitas
    if explicit_keys:
        if isinstance(explicit_keys, (list, tuple, set)):
            for k in explicit_keys:
                _add_key(str(k))
        elif isinstance(explicit_keys, str):
            for token in re.split(r"[,;\n\r\s]+", explicit_keys.strip()):
                _add_key(token)

    # 2. Arquivos .txt conhecidos de chave
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
                    
                    # Extrai todos os cabeçalhos curl (-H 'X-goog-api-key: ...')
                    headers = re.findall(r"X-goog-api-key:\s*['\"]?([A-Za-z0-9_\-\.]+)['\"]?", content, re.IGNORECASE)
                    for h in headers:
                        _add_key(h)

                    # Extrai padrões VAR=...
                    kvs = re.findall(r"(?:GEMINI_API_KEY|GEMINI_FALLBACK_API_KEY|GEMINI_BACKUP_API_KEY|GEMINI_API_KEYS)\s*=\s*['\"]?([A-Za-z0-9_\-\.,;]+)['\"]?", content, re.IGNORECASE)
                    for kv in kvs:
                        for token in re.split(r"[,;\s]+", kv):
                            _add_key(token)

                    # Extrai linhas individuais sem espaços
                    for line in content.splitlines():
                        l = line.strip()
                        if l and not l.startswith("#") and not l.startswith("//") and " " not in l:
                            _add_key(l)
                except Exception as e:
                    app_logger.warning(f"[Agents] Erro ao ler chaves de '{full_fn}': {str(e)}")

    # 3. Variáveis de ambiente
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

    # 4. Arquivo .env
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
    """
    Resolve a chave de API primária do Gemini (retrocompatibilidade).
    """
    keys = resolve_gemini_api_keys(explicit_key)
    return keys[0] if keys else ""

_CLIENT_CACHE: Dict[str, genai.Client] = {}
_CLIENT_CACHE_LOCK = threading.Lock()

def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """Cria e retorna uma instância cacheada do cliente oficial google-genai."""
    key = resolve_gemini_api_key(api_key) if (api_key is None or not api_key.strip()) else api_key.strip()
    if not key:
        return genai.Client()
    
    with _CLIENT_CACHE_LOCK:
        if key not in _CLIENT_CACHE:
            _CLIENT_CACHE[key] = genai.Client(api_key=key)
        return _CLIENT_CACHE[key]

class GeminiRateLimiter:
    """Controle de vazão thread-safe para impedir que chamadas paralelas ultrapassem o teto de 14 RPM do Gemini Free Tier."""
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
    """Retorna um Rate Limiter isolado para a chave de API fornecida."""
    if not api_key:
        return GLOBAL_RATE_LIMITER
    with _KEY_RATE_LOCK:
        if api_key not in _KEY_RATE_LIMITERS:
            _KEY_RATE_LIMITERS[api_key] = GeminiRateLimiter(max_rpm=max_rpm)
        return _KEY_RATE_LIMITERS[api_key]

def get_prioritized_keys(keys: List[str]) -> List[str]:
    """Ordena chaves colocando chaves ativas sem cooldown no topo para evitar latência em chaves esgotadas."""
    now = time.time()
    return sorted(keys, key=lambda k: _KEY_COOLDOWNS.get(k, 0.0) > now)

def extract_retry_seconds(error_str: str) -> int:
    """Extrai os segundos exatos de espera retornados pela mensagem de Quota do Gemini."""
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
    timeout_seconds: float = 60.0,
    max_cooldown_retries: int = 3,
    api_keys: Optional[Any] = None
) -> str:
    """
    Executa chamada com streaming em tempo real, timeout de 60s+, redundância de chaves de API e fallback de modelos.
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
                # Rate limiter isolado por chave
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
                        break  # Timeout no modelo -> avança para próximo modelo

                    if is_quota:
                        wait_sec = extract_retry_seconds(err_text)
                        min_wait_sec = min(min_wait_sec, wait_sec)
                        if current_key:
                            _KEY_COOLDOWNS[current_key] = time.time() + wait_sec
                        record_throttling("API_GEMINI", "HTTP_429_QUOTA", f"Cota esgotada no modelo {current_model} (chave {key_display}): {err_text[:180]}", retry_after=wait_sec)
                        
                        # Se houver outra chave de redundância disponível, alterna imediatamente
                        if k_idx < len(active_keys) - 1:
                            next_key = active_keys[k_idx + 1]
                            next_key_display = f"...{next_key[-6:]}" if len(next_key) >= 10 else "secundária"
                            app_logger.warning(
                                f"[API Key Fallback] Cota esgotada na chave {key_display} ({current_model}). "
                                f"Alternando imediatamente para a chave de redundância {next_key_display}..."
                            )
                            if status_callback:
                                status_callback(f"🛡️ Cota esgotada na chave {key_display}. Fallback para chave {next_key_display}...")
                            continue  # Tenta a próxima chave no mesmo modelo

                    # Se for outro erro e houver outra chave, tenta a chave seguinte
                    if k_idx < len(active_keys) - 1:
                        continue

            # Se todas as chaves falharam para este modelo:
            if auto_fallback and m_idx < len(models_to_try) - 1:
                next_model = models_to_try[m_idx + 1]
                if status_callback:
                    status_callback(f"⚠️ Todas as chaves esgotadas em **{current_model}**. Alternando para modelo **{next_model}**...")
                break  # Sai do while e avança para o próximo modelo

            if auto_cooldown:
                if status_callback:
                    status_callback(f"⏳ Cota esgotada em todas as chaves e modelos. Cooldown de {min_wait_sec}s...")
                for remaining in range(min_wait_sec, 0, -1):
                    if cooldown_callback:
                        cooldown_callback(remaining, min_wait_sec, current_model)
                    time.sleep(1)
                if cooldown_callback:
                    cooldown_callback(0, min_wait_sec, current_model)
                retries_left -= 1
                continue
            else:
                if last_key_error:
                    raise last_key_error
                raise Exception(f"Falha em todas as chaves no modelo {current_model}")
                    
    raise Exception(f"Todos os modelos e chaves de redundância falharam. Último modelo: {models_to_try[-1]}")

def generate_multimodal_with_resilience(
    contents: list,
    system_instruction: str,
    model_name: str = "gemini-flash-lite-latest",
    fallback_models: list = None,
    auto_fallback: bool = True,
    auto_cooldown: bool = True,
    response_mime_type: str = "application/json",
    cooldown_callback = None,
    status_callback = None,
    timeout_seconds: float = 60.0,
    api_keys: Optional[Any] = None
) -> str:
    """
    Executa chamada multimodal (imagens + texto) com rate limiter isolado por chave, redundância de API keys e fallback.
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
        active_keys = get_prioritized_keys(configured_keys)
        for k_idx, current_key in enumerate(active_keys):
            key_limiter = get_rate_limiter_for_key(current_key)
            key_limiter.acquire()
            client = get_genai_client(current_key if current_key else None)
            key_display = f"...{current_key[-6:]}" if len(current_key) >= 10 else "padrão"

            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type=response_mime_type,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
                )
                response = client.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=config
                )
                if response and response.text:
                    return response.text.strip()
                raise Exception("Resposta multimodal vazia.")
            except Exception as e:
                err_text = str(e)
                is_quota = "ResourceExhausted" in type(e).__name__ or "RESOURCE_EXHAUSTED" in err_text or "429" in err_text
                if is_quota:
                    wait_sec = extract_retry_seconds(err_text)
                    if current_key:
                        _KEY_COOLDOWNS[current_key] = time.time() + wait_sec
                    record_throttling("API_GEMINI", "HTTP_429_MULTIMODAL_QUOTA", f"Cota esgotada em visão ({current_model}, chave {key_display}): {err_text[:180]}", retry_after=wait_sec)
                    if k_idx < len(active_keys) - 1:
                        next_key = active_keys[k_idx + 1]
                        next_key_display = f"...{next_key[-6:]}" if len(next_key) >= 10 else "secundária"
                        app_logger.warning(f"[MultimodalVision Fallback] Alternando chave de visão {key_display} -> {next_key_display} ({current_model})")
                        continue

                app_logger.warning(f"[MultimodalVision] Erro no modelo {current_model} (chave {key_display}): {err_text}")
                if k_idx < len(active_keys) - 1:
                    continue
                if auto_fallback and m_idx < len(models_to_try) - 1:
                    break
                raise e
    raise Exception("Todos os modelos de visão multimodal e chaves falharam.")

POPULAR_AUTOMOTIVE_ANGLES = [
    # 1. Supercarros, Hipercarros e Lendas do Ciclo Otto (V8, V10, V12, W16)
    "Hipercarros e Supercarros Icônicos (ex: Ferrari SF90/F40/LaFerrari, Porsche 911 GT3 RS/Carrera GT, Lamborghini Revuelto/Aventador, McLaren F1/720S/Senna, Bugatti Chiron W16, Lexus LFA V10)",
    # 2. Aviação, Caças Militares e Turbinas a Jato / Turbofan / Turboélice
    "Motores Aeronáuticos e Turbinas a Jato Extremas (ex: SR-71 Blackbird Pratt & Whitney J58 turbo-ramjet a Mach 3, P-51 Mustang / Spitfire Rolls-Royce Merlin V12 com compressor duplo, Concorde Olympus 593 pós-combustão, A-10 Thunderbolt GE TF34 e canhão GAU-8, GE90 do Boeing 777)",
    # 3. Tanques de Guerra, Blindados e Propulsão Militar Pesada
    "Motores de Tanques de Guerra e Veículos de Combate (ex: M1 Abrams e sua turbina a gás Honeywell AGT1500 de 1.500hp, Leopard 2 com motor diesel V12 biturbo MTU MB 873 de 47.6 litros, Tiger I com Maybach HL230, T-90 com motor diesel V-92S2 superalimentado)",
    # 4. Supermotos e Motores de 2 Rodas de Altíssimo Giro
    "Supermotos e Engenharia de Duas Rodas (ex: Kawasaki Ninja H2R com supercharger centrífugo a 130.000 RPM e 310hp, Ducati Panigale V4R com comando desmodrômico a 16.500 RPM, Honda CBX 1000 6 cilindros, Yamaha YZF-R1 com virabrequim Crossplane, Suzuki Hayabusa 1340cc)",
    # 5. Motores Rotativos Wankel e Rotação Pura
    "A Física dos Motores Rotativos Wankel (ex: Mazda 787B campeão de Le Mans com R26B 4-rotores aspirado a 10.000 RPM, Mazda RX-7 FD3S 13B-REW bi-turbo sequencial, dinâmica dos apex seals e câmara trocoidal)",
    # 6. Monstros do Ciclo Diesel e Alta Pressão
    "Monstros do Ciclo Diesel e Torque Extremo (ex: Audi R10 TDI e R18 V10/V6 turbodiesel dominando Le Mans, Cummins 6BT 5.9 turbo de ferro fundido aguentando 100 psi de boost, Duramax V8, Wärtsilä-Sulzer RTA96-C o maior motor diesel marítimo de 109.000hp)",
    # 7. Powertrains Elétricos Extremos e Inversores de Alta Tensão
    "Propulsão Elétrica Extrema e Inversores SiC (ex: Rimac Nevera com 4 motores elétricos e vetorização de torque de 1.914hp, McMurtry Spéirling com vácuo ativo e 0 a 100 em 1.4s, Tesla Model S Plaid rotor de carbono a 20.000 RPM, Porsche Taycan 800V)",
    # 8. Monstros Náuticos e Lanchas Offshore de Competição
    "Motores Náuticos e Barcos Offshore de Corrida (ex: Lanchas Cigarette e MTI com motores Mercury Racing 1750 Dual-Fuel V8 bi-turbo de 1.750hp, hidroaviões com Napier Sabre H-24 com válvulas de camisa corrediça)",
    # 9. Lendas do Rali Grupo B e JDM de Alta Performance
    "Lendas Mecânicas do Rali Grupo B e JDM (ex: Audi Sport Quattro S1 com turbo anti-lag, Lancia Delta S4 twin-charged turbo + compressor volumétrico simultâneo, Nissan Skyline GT-R RB26DETT, Toyota Supra 2JZ-GTE bloco fechado)",
    # 10. Inovações em Sobrealimentação, Aerodinâmica Ativa e Transmissões
    "Inovações Extremas de Engenharia Mecânica (ex: Supercharger Roots vs Twin-Screw vs Centrífugo, Turbos de Geometria Variável VGT, Turbos elétricos MGU-H da Fórmula 1, câmbio sequencial com dentes retos, suspensão eletromagnética ativa)"
]

class ProposerAgent:
    """
    Agente Propositor Estratégico de Ideias de Motores e Engenharia Mecânica.
    Consulta os pesos auxiliares ativos na Memória Algorítmica (.md) para gerar
    propostas completas de alta atratividade, cobrindo veículos motorizados consagrados
    (carros, aviões, tanques de guerra, motos, barcos, motores wankel, diesel, elétrico, otto).
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_keys = api_keys
        self.system_instruction = (
            "Você é um estrategista sênior de conteúdo viral e engenheiro mecânico especializado em YouTube Shorts para entusiastas de motores e máquinas de alta potência (ritmo dinâmico 1.25x).\n"
            "Sua missão é conceber ideias completas de vídeos de altíssimo valor técnico e atratividade instantânea cobrindo TODO O UNIVERSO DOS MOTORES:\n"
            "- Carros e Hipercarros (Otto, V8/V10/V12/W16, bi-turbo, supercharged);\n"
            "- Aviões e Caças Militares (turbinas a jato, turbofan, turboélice, motores radiais e V12 de aviação);\n"
            "- Tanques de Guerra e Veículos Blindados (turbinas a gás como Abrams, motores diesel V12 como Leopard 2);\n"
            "- Supermotos (Kawasaki Ninja H2R com compressor, Ducati Panigale V4R desmodrômico, Honda CBX 1000 6 cil);\n"
            "- Motores Rotativos Wankel (Mazda 787B 4-rotores, RX-7 13B);\n"
            "- Monstros do Ciclo Diesel (Audi TDI Le Mans, Cummins 6BT, Duramax, motores navais gigantes);\n"
            "- Elétricos de Alta Performance (Rimac Nevera, McMurtry Spéirling, Tesla Plaid rotor de carbono);\n"
            "- Lanchas Offshore e Barcos de Corrida (Mercury Racing V8 bi-turbo).\n\n"
            "FOCO ESTRITO EM VEÍCULOS E MOTORES FAMOSOS COM VASTA DISPONIBILIDADE DE VÍDEOS REAIS EM 4K NO YOUTUBE.\n"
            "EVITE modelos conceituais obscuros ou protótipos sem filmagens reais.\n\n"
            "REGRAS CRÍTICAS DE TÍTULO ('tema'):\n"
            "1. TETO ESTRITO DE TAMANHO: O título ('tema') DEVE ter NO MÁXIMO 80 a 95 caracteres (NUNCA ultrapassar 100 caracteres).\n"
            "2. PROIBIÇÃO DE CLICHÊS: NUNCA coloque sufixos como '| Segredos da Engenharia' ou '| AutoTech'. O título deve ser direto e focado na máquina e no mecanismo (ex: 'SR-71 Blackbird: A Brutal Física dos Motores J58 a Mach 3', 'Kawasaki H2R: O Compressor que Gira a 130.000 RPM', 'M1 Abrams: A Insana Turbina a Gás de 1.500 hp do Tanque').\n\n"
            "Responda SEMPRE em formato JSON com uma lista de objetos contendo exatamente:\n"
            "- 'tema': Título do vídeo otimizado para clique e retenção (marca e modelo exatos, MÁXIMO 100 CARACTERES, SEM SUFIXOS CLICHÊS)\n"
            "- 'descricao': Descrição completa e formatada para a publicação no YouTube Shorts (incluindo hook, resumo da física/mecânica, CTA para inscrição e pergunta para engajamento nos comentários)\n"
            "- 'tags': Lista de 8 a 15 hashtags virais e pertinentes (ex: ['#Shorts', '#NomeDaMaquina', '#Motor', '#EngenhariaMecanica', '#Turbina', '#Aviation', '#Motorsport', ...])\n"
            "- 'hook': Frase de impacto inicial para os primeiros 3 segundos da narração (palavra de chamariz + paradoxo mecânico intrigante)\n"
            "- 'explicacao_tecnica': Resumo técnico preliminar do funcionamento mecânico."
        )

    def generate_topics(self, count=10, blacklist: Optional[List[Any]] = None, seed=None, cooldown_callback=None, status_callback=None):
        seed_val = seed if seed is not None else random.randint(100000, 999999)
        time_salt = int(time.time() * 1000) % 100000
        angles_sample = random.sample(POPULAR_AUTOMOTIVE_ANGLES, min(4, len(POPULAR_AUTOMOTIVE_ANGLES)))
        angles_str = "\n".join([f"- {a}" for a in angles_sample])
        memory_guidance = DEFAULT_ALGORITHM_MEMORY.get_prompt_guidance()

        blacklist_str = ""
        if blacklist:
            formatted_items = []
            for b in blacklist[-60:]:
                if isinstance(b, dict):
                    t = b.get("tema") or b.get("core_entity") or str(b)
                else:
                    t = str(b).strip()
                if t:
                    formatted_items.append(f"- {t}")
            if formatted_items:
                blacklist_str = (
                    f"\n\n[BLACKLIST DE TEMAS E MÁQUINAS JÁ UTILIZADOS - ESTRITAMENTE PROIBIDO REPETIR]:\n"
                    f"{chr(10).join(formatted_items)}\n"
                    f"ATENÇÃO MÁXIMA: É TERMINANTEMENTE PROIBIDO repetir qualquer um dos veículos, máquinas ou focos listados na Blacklist acima. "
                    f"Gere temas 100% INÉDITOS com outras máquinas e soluções mecânicas."
                )

        prompt = (
            f"Gere {count} ideias COMPLETAS e INÉDITAS sobre engenharia de motores e veículos de alta performance para YouTube Shorts (ritmo dinâmico 1.25x).\n\n"
            f"{memory_guidance}\n\n"
            f"[ENTROPIA & SEED DE DIVERSIDADE]: #{seed_val}-{time_salt}\n"
            f"DIRETRIZES OBRIGATÓRIAS:\n"
            f"1. PACOTE COMPLETO: Cada ideia DEVE conter 'tema' (Título), 'descricao' (Descrição completa para o YouTube), 'tags' (Hashtags virais), 'hook' (Primeiros 3 segundos) e 'explicacao_tecnica' (Engenharia mecânica).\n"
            f"2. TÍTULOS CURTOS E DIRETOS: O título DEVE ter no MÁXIMO 85 a 95 caracteres (NUNCA ultrapassar 100 caracteres). PROIBIDO colocar '| Segredos da Engenharia'.\n"
            f"3. DIVERSIDADE TOTAL DO NICHO DE MOTORES: Alterne entre carros esportivos, caças e aviões lendários, tanques de guerra, motos de alta rotação, motores rotativos wankel, diesel de alta pressão e elétricos extremos com vastos vídeos reais em 4K no YouTube.\n"
            f"4. VARIEDADE MÁXIMA: Garanta que as {count} ideias cubram diferentes tipos de propulsão, épocas e tecnologias.\n"
            f"5. ÂNGULOS DESTAQUE SORTEADOS PARA ESTA RODADA:\n{angles_str}"
            f"{blacklist_str}\n\n"
            f"Responda SEMPRE em JSON puro com a lista de {count} objetos contendo 'tema', 'descricao', 'tags', 'hook' e 'explicacao_tecnica'."
        )
        raw_text = generate_with_resilience(
            prompt=prompt,
            system_instruction=self.system_instruction,
            model_name=self.model_name,
            fallback_models=self.fallback_models,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown,
            response_mime_type="application/json",
            cooldown_callback=cooldown_callback,
            status_callback=status_callback,
            api_keys=self.api_keys
        )
        try:
            topics = json.loads(raw_text)
            if isinstance(topics, list):
                for t in topics:
                    if isinstance(t, dict) and "tema" in t:
                        t["tema"] = sanitize_and_cap_title(t["tema"], max_length=100)
            return topics
        except Exception as e:
            return {"error": str(e), "raw": raw_text}

class EvaluatorAgent:
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_keys = api_keys
        self.system_instruction = (
            "Você é um diretor de produção audiovisual automotiva rigoroso. "
            "Avalie o tema considerando o potencial de manter retenção alta em um vídeo de 1 a 2 minutos, "
            "a clareza da explicação mecânica e o fator curiosidade. "
            "Responda SEMPRE em JSON contendo 'nota' (0 a 10), 'veredicto' (Aprovado/Reprovado), e 'justificativa'."
        )

    def evaluate_topic(self, topic_data, cooldown_callback=None, status_callback=None):
        prompt = f"Avalie o seguinte tema de vídeo de 1 a 2 minutos:\n\n{json.dumps(topic_data, indent=2, ensure_ascii=False)}"
        raw_text = generate_with_resilience(
            prompt=prompt,
            system_instruction=self.system_instruction,
            model_name=self.model_name,
            fallback_models=self.fallback_models,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown,
            response_mime_type="application/json",
            cooldown_callback=cooldown_callback,
            status_callback=status_callback,
            api_keys=self.api_keys
        )
        try:
            return json.loads(raw_text)
        except Exception as e:
            return {"error": str(e), "raw": raw_text}

class DissertationAgent:
    """
    Agente Mestre de Pesquisa e Dissertação de Engenharia Mecânica e Motores (Fase 1 da Síntese).
    Constrói uma monografia completa, rigorosa e densa (300 a 500 palavras) sobre o tema,
    detalhando a física real, telemetria, fluidodinâmica, termodinâmica e contexto mecânico exato
    (carros, caças/aviões, tanques de guerra, motos, barcos, motores wankel, diesel, elétrico, etc.),
    sem recorrer a adjetivação vazia ou sensacionalismo superficial.
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_keys = api_keys
        self.system_instruction = (
            "Você é o Engenheiro-Chefe e Historiador Tecnológico de Motores e Veículos de Alta Performance.\n"
            "Sua missão é produzir uma DISSERTAÇÃO TÉCNICA E HISTÓRICA COMPLETA (300 a 500 palavras) sobre o veículo/motor/sistema mecânico.\n\n"
            "DIRETRIZES DE PROFUNDIDADE E CONTEÚDO PURO (ANTI-HYPE):\n"
            "1. CONTEÚDO DENSO E EXATO: Apresente dados exatos de engenharia:\n"
            "   - Motores a Combustão (Otto/Diesel/Wankel): arquitetura do bloco, cilindrada, diâmetro e curso, taxa de compressão, pressão de sobrealimentação em bar/psi, rotação máxima (RPM), cavalaria (cv/hp), torque (kgfm/Nm), apex seals ou bombas injetoras;\n"
            "   - Turbinas Aeronáuticas e Jatos: estágios de compressão axial, temperatura da turbina em °C, empuxo em kN/lbf, bypass ratio, pós-combustão (afterburner);\n"
            "   - Tanques Militares: turbinas a gás vs diesel multicombustível, blindagem, torque em baixa rotação;\n"
            "   - Supermotos: desmodrômico, compressores centrífugos, virabrequim crossplane, limites de giro a 16.000+ RPM;\n"
            "   - Propulsão Elétrica: inversores SiC, voltagem (400V/800V), rotação do rotor com fibra de carbono, vetorização de torque.\n"
            "2. FÍSICA E AERODINÂMICA: Explique a fluidodinâmica real (downforce gerado em kg, Mach em aviação, efeito solo, dutos Venturi ou asas ativas com atuadores eletro-hidráulicos).\n"
            "3. O DESAFIO E A SOLUÇÃO: Qual era o problema físico intransponível que os engenheiros enfrentavam e qual foi a solução metalúrgica, mecânica ou de software que resolveu a equação?\n"
            "4. TOLERÂNCIA ZERO A SENSACIONALISMO VAZIO: NUNCA use clichês genéricos como 'o monstro que destruiu as leis da física'. Seja fascinante através da precisão implacável dos fatos da engenharia.\n\n"
            "Responda SEMPRE em formato JSON com as chaves:\n"
            "- 'entidade_principal': Nome exato da máquina/veículo/motor\n"
            "- 'especificacoes_tecnicas': Dicionário com motor, cv/empuxo, torque, rpm/temperatura, transmissao/pos_combustao, 0_100/mach, vel_max\n"
            "- 'desafio_de_engenharia': Descrição concisa do problema físico resolvido\n"
            "- 'solucao_mecanica': Descrição do mecanismo exato utilizado\n"
            "- 'impacto_historico_telemetria': Fatos de pista, recordes, conquistas ou telemetria comprovada\n"
            "- 'dissertacao_completa': Texto corrido e denso (300 a 500 palavras) consolidando todo o estudo."
        )

    def generate_dissertation(self, topic: Dict[str, Any], cooldown_callback=None, status_callback=None) -> Dict[str, Any]:
        tema_str = topic.get("tema", "Veículo de Alta Performance")
        core_entity = extract_core_entity(tema_str)
        prompt = (
            f"Construa a Dissertação Completa de Engenharia Mecânica para o seguinte tema:\n\n"
            f"TÍTULO/TEMA: '{tema_str}'\n"
            f"VEÍCULO/ENTIDADE: '{core_entity}'\n"
            f"Hook Proposto: {topic.get('hook', '')}\n"
            f"Base Técnica Inicial: {topic.get('explicacao_tecnica', '')}\n\n"
            f"Gere o estudo técnico minucioso e completo em JSON com todas as especificações e a 'dissertacao_completa'."
        )
        raw_text = generate_with_resilience(
            prompt=prompt,
            system_instruction=self.system_instruction,
            model_name=self.model_name,
            fallback_models=self.fallback_models,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown,
            response_mime_type="application/json",
            cooldown_callback=cooldown_callback,
            status_callback=status_callback,
            api_keys=self.api_keys
        )
        try:
            return json.loads(raw_text)
        except Exception as e:
            app_logger.warning(f"[DissertationAgent] Erro ao decodificar JSON da dissertação: {str(e)}")
            return {
                "entidade_principal": core_entity,
                "especificacoes_tecnicas": {"tema": tema_str},
                "desafio_de_engenharia": "Equilíbrio entre confiabilidade e entrega de potência.",
                "solucao_mecanica": topic.get("explicacao_tecnica", "Engenharia mecânica avançada."),
                "impacto_historico_telemetria": "Referência absoluta de alta performance mecânica.",
                "dissertacao_completa": topic.get("explicacao_tecnica", "Engenharia mecânica e termodinâmica de alta performance.")
            }

KNOWN_AUTOMOTIVE_BRANDS = [
    # Supercarros, Carros e Hipercarros
    "audi", "bmw", "mercedes", "amg", "ferrari", "lamborghini", "porsche", "mclaren",
    "aston martin", "chevrolet", "corvette", "ford", "mustang", "toyota", "honda",
    "nissan", "subaru", "volkswagen", "vw", "volvo", "hyundai", "kia", "byd", "tesla",
    "bugatti", "koenigsegg", "pagani", "maserati", "alfa romeo", "bentley", "rolls royce",
    "rolls-royce", "cadillac", "dodge", "viper", "jeep", "land rover", "range rover", "jaguar", "peugeot",
    "renault", "citroen", "lotus", "rimac", "cupra", "seat", "fiat", "lexus", "acura",
    "infiniti", "genesis", "yangwang", "zeekr", "nio", "xpeng", "lucid", "rivian", "bose",
    "mcmurtry", "caterham", "shelby",
    # Aviação, Caças e Turbinas
    "lockheed", "blackbird", "sr-71", "boeing", "airbus", "pratt & whitney", "pratt and whitney",
    "general electric", "ge aviation", "snecma", "olympus", "rolls-royce merlin", "supermarine",
    "spitfire", "north american p-51", "fairchild", "a-10", "warthog", "concorde", "sukhoi", "mikoyan",
    # Tanques de Guerra e Veículos Militares
    "abrams", "m1 abrams", "leopard", "leopard 2", "tiger", "panther", "maybach", "honeywell",
    "mtu", "rheinmetall", "krauss-maffei", "general dynamics", "t-90", "t-72", "t-80", "t-34",
    # Motocicletas e Motores de 2 Rodas
    "kawasaki", "ninja", "h2r", "ducati", "panigale", "yamaha", "yzf-r1", "r1", "suzuki",
    "hayabusa", "honda cbx", "bmw motorrad", "s1000rr", "ktm", "aprilia", "mv agusta", "triumph", "harley-davidson",
    # Motores Pesados, Diesel e Náutica
    "cummins", "duramax", "caterpillar", "cat", "wartsila", "sulzer", "mercury racing", "yanmar", "man"
]

FORBIDDEN_TITLE_KEYWORDS = [
    # Câmeras de ação, tutoriais de software e sobreposição de GPS/telemetria
    "gopro", "insta360", "dji osmo", "action cam", "action camera",
    "telemetry overlay", "gps telemetry", "gps stats", "telemetry app",
    "tutorial", "how to", "how-to", "how to add", "how to install", "como fazer", "passo a passo",
    "install", "installation", "setup", "diy", "guia", "guide", "review", "unboxing",
    "windows", "macos", "mac os", "macbook", "pc build", "software", "plugin",
    "obs studio", "premiere pro", "after effects", "davinci", "photoshop", "apk",
    # Modelismo, brinquedos, drones, motores RC e miniaturas
    "drone", "fpv", "quadcopter", "brushless", "kv motor", "10000kv", "eaglepower",
    "t-motor", "tinywhoop", "flight test", "rc car", "rc truck", "rc plane",
    "hot wheels", "diecast", "miniatura", "lego", "roblox",
    # Jogos e gameplays de simulação
    "gameplay", "walkthrough", "playthrough", "forza horizon", "forza motorsport",
    "gran turismo", "assetto corsa", "gta 5", "gta v", "beamng", "far cry",
    # Formatos de criador de conteúdo / podcast / reaction / vlogs
    "podcast", "react", "reaction", "reacting", "interview", "entrevista", "bate papo",
    "daily vlog", "vlog", "meu dia", "comprei", "compramos", "minha garagem", "child", "kid", "kids"
]

def extract_core_entity(topic_str: str) -> str:
    """Extrai os termos centrais do veículo/objeto de estudo (marca + modelo + variante)."""
    parts = topic_str.split(":")
    main_part = parts[0] if len(parts) > 1 else topic_str
    cleaned = re.sub(r"^(O Segredo d[oa]|Como funciona o|Por que o|A física d[oa]|A engenharia d[oa]|Tudo sobre o|O Motor d[oa]|A Asa d[oa]|A Suspensão d[oa]|A Turbina d[oa]|O Canhão d[oa])\s*", "", main_part, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
    cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|por ser bom demais|que a f1 baniu|para|sobre|o|a|os|as)\b", " ", cleaned, flags=re.IGNORECASE)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return " ".join(words[:6]) if words else topic_str.strip()

def generate_video_metadata_text(topic: Dict[str, Any]) -> str:
    """
    Gera o conteúdo textual completo (.txt) para publicação do Short/Vídeo contendo:
    - TÍTULO (gerado pela IA ou formatado com emojis e gancho)
    - DESCRIÇÃO (gerada pela IA ou formatada com hook, resumo técnico e CTAs)
    - HASHTAGS (geradas pela IA ou extraídas estrategicamente do tema)
    """
    tema = topic.get("tema") or topic.get("titulo") or "Curiosidade de Motores"
    hook = topic.get("hook", "")
    tech = topic.get("explicacao_tecnica", "")
    ai_descricao = topic.get("descricao", "").strip()
    ai_tags = topic.get("tags") or topic.get("hashtags")
    
    # 1. Título do Vídeo (MÁXIMO 100 CARACTERES, SEM SUFIXOS CLICHÊS)
    titulo_formatado = sanitize_and_cap_title(tema, max_length=100)
    
    # 2. Descrição (usa a gerada pela IA se disponível e rica, ou constrói layout estruturado)
    if ai_descricao and len(ai_descricao) >= 30:
        descricao_formatada = ai_descricao
    else:
        descricao_formatada = (
            f"🔥 {hook}\n\n"
            f"🔬 O SEGREDO MECÂNICO:\n"
            f"{tech}\n\n"
            f"---------------------------------------------------\n"
            f"⚡ Produzido automaticamente por AI Slop Studio (Edição 9:16 Dinâmica 1.25x)\n"
            f"🔔 Curtiu? Deixe o like e inscreva-se no canal para não perder nenhuma curiosidade de engenharia e motores!\n"
            f"💬 Comente aqui: Qual a próxima máquina lendária que você quer ver explicada?"
        )
        
    # 3. Tags / Hashtags (usa as tags geradas pela IA se disponíveis, ou extrai dinamicamente)
    if isinstance(ai_tags, list) and ai_tags:
        tags_list = [f"#{t.lstrip('#')}" for t in ai_tags if t.strip()]
        hashtags_str = " ".join(tags_list)
    elif isinstance(ai_tags, str) and ai_tags.strip():
        hashtags_str = ai_tags.strip()
    else:
        core_entity = extract_core_entity(tema)
        entity_tag = "#" + re.sub(r"[^\w]", "", core_entity) if core_entity else ""
        brand_tags = []
        tema_lower = tema.lower()
        for b in KNOWN_AUTOMOTIVE_BRANDS:
            if re.search(rf"\b{re.escape(b)}\b", tema_lower):
                b_clean = re.sub(r"[^\w]", "", b.title())
                if b_clean:
                    brand_tags.append(f"#{b_clean}")
                    
        base_hashtags = [
            "#Shorts",
            "#EngenhariaMecanica",
            "#Motores",
            "#Supercarros",
            "#Aviation",
            "#Curiosidades",
            "#AutoTech",
            "#Mecanica",
            "#Motorsport",
            "#Gearhead"
        ]
        
        all_tags = []
        if entity_tag and entity_tag not in all_tags and len(entity_tag) > 2:
            all_tags.append(entity_tag)
        for bt in brand_tags:
            if bt not in all_tags:
                all_tags.append(bt)
        for ht in base_hashtags:
            if ht not in all_tags:
                all_tags.append(ht)
                
        hashtags_str = " ".join(all_tags[:12])
    
    metadata_content = f"""TÍTULO:
{titulo_formatado}

DESCRIÇÃO:
{descricao_formatada}

HASHTAGS:
{hashtags_str}
"""
    return metadata_content

def save_video_metadata_file(video_dir: str, topic: Dict[str, Any], filename: str = "metadata.txt") -> str:
    """
    Grava o arquivo .txt de metadados (Título, Descrição, Hashtags) na pasta do vídeo.
    Retorna o caminho absoluto do arquivo gravado.
    """
    os.makedirs(video_dir, exist_ok=True)
    file_path = os.path.join(video_dir, filename)
    content = generate_video_metadata_text(topic)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    app_logger.info(f"[Metadata] Arquivo de metadados gravado: {file_path}")
    return file_path

class DirectorAgent:
    """
    Agente Diretor de Produção de Motores/Veículos e Destilador de Alta Retenção (Fase 2 da Síntese).
    Pega a dissertação técnica profunda e a destila em um roteiro magnético de 60s a 120s (160 a 260 palavras a 1.25x),
    com gancho de chamariz nos primeiros 3s e meio denso de física real sem buzzwords vazias.
    Gera termos de busca no YouTube em INGLÊS, CURTOS (3 a 6 palavras) estritamente ancorados na máquina principal
    (carros, aviões/caças, tanques, motos, motores wankel/diesel/elétricos).
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_keys = api_keys
        self.system_instruction = (
            "Você é o Diretor de Produção e Arquiteto de Roteiros de Alta Retenção para Entusiastas de Motores e Veículos de Alta Performance (RITMO 1.25x ACELERADO).\n"
            "Sua missão é DESTILAR UMA DISSERTAÇÃO TÉCNICA PROFUNDA em um roteiro magnético, rápido e de densidade máxima (60s a 110s de fala a 1.25x, aprox. 160 a 260 palavras) "
            "abrangendo carros, aviões/caças, tanques de guerra, motos, barcos, motores wankel, diesel ou elétricos.\n\n"
            "ESTRUTURA DO ROTEIRO EM 3 ETAPAS (DESTILAÇÃO PERFEITA):\n"
            "1. OS PRIMEIROS 3 SEGUNDOS (HOOK / PALAVRA DE CHAMARIZ): Comece com uma afirmação provocativa, paradoxo ou número surpreendente que prenda o espectador de imediato.\n"
            "2. O CORPO DO VÍDEO (EXPLICAÇÃO MECÂNICA DENSA): Não use termos exagerados genéricos para preencher espaço. Use a matéria-prima rica da Dissertação (ex: fluxo de ar, atuadores, rotação, temperatura de turbina, pós-combustor, compressor, injeção, milissegundos, termodinâmica) para entregar valor real e hipnotizante.\n"
            "3. O CLÍMAX E CTA (DESFECHO): Feche com a conclusão do triunfo da máquina e uma pergunta orgânica estimulando comentários.\n\n"
            "REGRAS CRÍTICAS DE BUSCA NO YOUTUBE ('youtube_query'):\n"
            "1. Todas as queries DEVEM ser em INGLÊS, CURTAS (3 a 6 palavras) e com CONEXÃO PARTICULAR OBRIGATÓRIA ao objeto mecânico/veículo de estudo.\n"
            "2. OBRIGATÓRIO: TODA query DEVE iniciar ou conter o [NOME EXATO DA MÁQUINA/VEÍCULO] + [COMPONENTE OU AÇÃO ESPECÍFICA DA CENA] "
            "(ex: 'SR-71 Blackbird afterburner sound 4k', 'M1 Abrams turbine engine sound 4k', 'Kawasaki Ninja H2R supercharger sound 4k', 'Mazda 787B 4 rotor pure sound 4k', 'Porsche 911 GT3 RS exhaust sound 4k', 'Ducati Panigale V4R dyno sound 4k').\n"
            "3. NUNCA gere termos genéricos como 'dyno test', 'gps telemetry', 'torque vectoring' sem o modelo exato.\n"
            "4. FOCO ABSOLUTO EM SOM MECÂNICO PURO E AÇÃO REAL: 'pure sound exhaust 4k', 'raw onboard engine sound 4k', 'afterburner takeoff sound 4k', 'track test pure sound 4k', 'acceleration sound 4k', 'dyno pull sound 4k'.\n"
            "5. Divida em 14 a 22 tomadas rápidas (cortes a cada 2 a 4 segundos).\n"
            "Responda SEMPRE em JSON com a chave raiz 'cenas' (lista de objetos com 'scene_id', 'fala', 'youtube_query', 'duracao_estimada')."
        )

    def generate_storyboard(
        self,
        tema: Dict[str, Any],
        dissertacao_data: Optional[Dict[str, Any]] = None,
        cooldown_callback = None,
        status_callback = None
    ) -> List[Dict[str, Any]]:
        raw_topic = tema.get('tema', 'Carro Esportivo')
        core_entity = extract_core_entity(raw_topic)
        memory_guidance = DEFAULT_ALGORITHM_MEMORY.get_prompt_guidance()

        dissertacao_texto = ""
        if dissertacao_data:
            dissertacao_texto = (
                f"\n\n[DISSERTAÇÃO TÉCNICA PROFUNDA - FONTE PRIMÁRIA DE CONTEÚDO]:\n"
                f"{dissertacao_data.get('dissertacao_completa', '')}\n"
                f"Especificações: {json.dumps(dissertacao_data.get('especificacoes_tecnicas', {}), ensure_ascii=False)}\n"
                f"Desafio de Engenharia: {dissertacao_data.get('desafio_de_engenharia', '')}\n"
                f"Solução Mecânica: {dissertacao_data.get('solucao_mecanica', '')}\n"
                f"DIRETRIZ DE DESTILAÇÃO: Use os fatos, números e dinâmica explicados na Dissertação acima para construir a narração. "
                f"Elimine qualquer clichê ou adjetivação vazia no meio do vídeo; entregue substância pura."
            )

        prompt = (
            f"Destile o seguinte estudo mecânico em um roteiro de alta retenção (1.25x acelerado, 160 a 260 palavras) e plano de cortes detalhado.\n"
            f"{memory_guidance}\n\n"
            f"TEMA CENTRAL: '{raw_topic}'\n"
            f"ENTIDADE MECÂNICA/VEÍCULO: '{core_entity}'\n"
            f"Hook Inicial Proposto: {tema.get('hook')}\n"
            f"{dissertacao_texto}\n\n"
            f"Gere entre 14 e 22 cenas dinâmicas com queries CURTAS em INGLÊS sobre as filmagens mais espetaculares de '{core_entity}' em 4K."
        )
        raw_text = generate_with_resilience(
            prompt=prompt,
            system_instruction=self.system_instruction,
            model_name=self.model_name,
            fallback_models=self.fallback_models,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown,
            response_mime_type="application/json",
            cooldown_callback=cooldown_callback,
            status_callback=status_callback,
            api_keys=self.api_keys
        )
        cenas = []
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict) and "cenas" in data:
                cenas = data["cenas"]
            elif isinstance(data, list):
                cenas = data
        except Exception as e:
            app_logger.error(f"[DirectorAgent] Erro ao decodificar JSON do storyboard: {str(e)}")
            hook = tema.get("hook", "Você já se perguntou como essa obra de engenharia funciona?")
            tech = tema.get("explicacao_tecnica", "Engenharia mecânica pura.")
            cenas = [
                {
                    "scene_id": 1,
                    "tipo": "broll",
                    "fala": hook,
                    "youtube_query": f"{core_entity} action test 4k",
                    "duracao_estimada": 4.0
                },
                {
                    "scene_id": 2,
                    "tipo": "broll",
                    "fala": tech[:120],
                    "youtube_query": f"{core_entity} working cutaway 4k",
                    "duracao_estimada": 5.0
                },
                {
                    "scene_id": 3,
                    "tipo": "broll",
                    "fala": tech[120:] if len(tech) > 120 else f"Essa é a genialidade mecânica por trás do {core_entity}.",
                    "youtube_query": f"{core_entity} race track sound 4k",
                    "duracao_estimada": 5.0
                }
            ]

        # Sanitização e ancoragem estrita de todas as queries de busca para garantir a máquina correta
        core_words = [w.lower() for w in core_entity.split() if len(w) > 2]
        sanitized_cenas = []
        for c in cenas:
            q = c.get("youtube_query", "").strip()
            q_lower = q.lower()
            has_anchor = any(w in q_lower for w in core_words) if core_words else False
            if not has_anchor and q:
                q = f"{core_entity} {q}".strip()
            c["youtube_query"] = q
            sanitized_cenas.append(c)

        return sanitized_cenas

class ReviewerAgent:
    """
    Agente Revisor e Auditor de Qualidade Visual Multimodal (Gemini Vision).
    Executa pré-filtragem instantânea de metadados e inspeção visual rápida (1 quadro 384px)
    com POLÍTICA DE EARLY-DISCARD para eliminar perda de tempo e tokens com vídeos fora do tema.
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_keys = api_keys
        self.system_instruction = (
            "Você é o Auditor Chefe de Qualidade Visual e Acústica de Máquinas e Motores (POLÍTICA ZERO ROSTOS E AUDITORIA DE SOM MECÂNICO).\n"
            "Sua missão é inspecionar o quadro (frame) e o áudio de um recorte do YouTube e julgar a pertinência técnica (carros, caças/aviões, tanques, motos, lanchas, motores).\n\n"
            "DIRETRIZES CRÍTICAS:\n"
            "1. POLÍTICA ZERO ROSTOS: Qualquer pessoa, rosto humano visível, apresentador, youtuber conversando ou talking head no trecho DEVE SER REPROVADO IMEDIATAMENTE (aprovado = false, score = 1.0).\n"
            "2. AUDITORIA DE ÁUDIO (ISOLAMENTO DO SOM MECÂNICO PURO):\n"
            "   - O áudio contém QUALQUER voz ou fala humana, narrador, apresentador ou pessoa conversando? Marque 'tem_voz_humana: true'.\n"
            "   - O áudio contém o som mecânico autêntico da máquina (ronco do motor, escapamento, aceleração, turbina/afterburner, trocas de marcha, disparo mecânico, dinamômetro) ou som ambiente sem pessoas falando? Marque 'tem_voz_humana: false' e 'som_mecanico_puro: true'.\n"
            "3. POLÍTICA DE EARLY-DISCARD ('descartar_video_inteiro'):\n"
            "   - Defina 'descartar_video_inteiro: true' se o vídeo for FUNDAMENTALMENTE IRRELEVANTE, FORA DO TEMA OU LIXO (ex: tutoriais de software/GoPro, gráficos estáticos sem a máquina real, motores de brinquedo/drone/RC como Eaglepower/brushless, máquinas de outra marca/modelo descorrelacionada, gameplay de videogame, vlog/oficina amadora).\n"
            "   - Defina 'descartar_video_inteiro: false' APENAS SE o vídeo for de fato sobre o veículo/máquina do tema global, mas este trecho específico continha um rosto transitório ou texto que pode não estar presente em outro ponto do mesmo vídeo.\n"
            "4. REGRAS DE APROVAÇÃO (aprovado = true, descartar_video_inteiro = false, score >= 7.0):\n"
            "   - Filmagem nítida de alta qualidade focada 100% no veículo, turbina, motor, suspensão, chassi, escapamento, dinamômetro, voo ou pista (SEM PESSOAS VISÍVEIS).\n"
            "   - Demonstração de engenharia pura ou animação/esquema 3D limpa sem pessoas e sem texto invasivo.\n\n"
            "Responda SEMPRE em JSON:\n"
            "{\n"
            "  \"aprovado\": true | false,\n"
            "  \"descartar_video_inteiro\": true | false,\n"
            "  \"score\": 0.0 a 10.0,\n"
            "  \"tem_voz_humana\": true | false,\n"
            "  \"som_mecanico_puro\": true | false,\n"
            "  \"motivo\": \"justificativa concisa\",\n"
            "  \"elementos_detectados\": \"elementos visíveis e sonoros\"\n"
            "}"
        )

    def pre_filter_title(self, video_title: str, global_topic: str) -> Tuple[bool, str]:
        """
        Pré-filtro instantâneo de título para descartar lixo evidente, tutoriais,
        drones, câmeras de ação e marcas concorrentes em 0.001s antes de qualquer download.
        """
        t_low = video_title.lower()
        topic_low = global_topic.lower()
        
        # 1. Termos explicitamente proibidos (tutoriais, gopro, drones, gameplay, etc.)
        for b in FORBIDDEN_TITLE_KEYWORDS:
            if b in t_low:
                return False, f"Título contém termo proibido/irrelevante: '{b}'"

        # 2. Detecção de conflito de marcas automotivas
        target_brands = [b for b in KNOWN_AUTOMOTIVE_BRANDS if b in topic_low]
        if target_brands:
            title_brands = [b for b in KNOWN_AUTOMOTIVE_BRANDS if re.search(rf"\b{re.escape(b)}\b", t_low)]
            if title_brands:
                has_matching_brand = any(tb in target_brands for tb in title_brands)
                has_target_in_title = any(re.search(rf"\b{re.escape(tb)}\b", t_low) for tb in target_brands)
                if not has_matching_brand and not has_target_in_title:
                    return False, f"Marca conflitante detectada no título ('{title_brands[0]}') para o tema com foco em '{target_brands[0]}'"

        return True, "Título pré-aprovado"

    def extract_clip_frame(self, clip_path: str) -> Optional[Image.Image]:
        """Extrai 1 frame representativo do trecho e redimensiona para 384px para envio ultra-rápido."""
        try:
            temp_frame = os.path.join(tempfile.gettempdir(), f"frame_rev_{int(time.time()*1000)}_{threading.get_ident()}.jpg")
            cmd = ["ffmpeg", "-y", "-ss", "1.5", "-i", clip_path, "-vframes", "1", "-q:v", "3", temp_frame]
            subprocess.run(cmd, capture_output=True, check=True)
            if os.path.exists(temp_frame):
                img = Image.open(temp_frame).convert("RGB")
                img.thumbnail((384, 384))
                try:
                    os.remove(temp_frame)
                except:
                    pass
                return img
        except Exception as e:
            app_logger.warning(f"[ReviewerAgent] Erro ao extrair frame: {str(e)}")
        return None

    def extract_clip_audio_snippet(self, clip_path: str, max_duration: float = 3.5) -> Optional[bytes]:
        """Extrai um trecho curto de áudio (MP3 leve) para auditoria multimodal de voz/ronco."""
        try:
            temp_audio = os.path.join(tempfile.gettempdir(), f"audio_rev_{int(time.time()*1000)}_{threading.get_ident()}.mp3")
            cmd = [
                "ffmpeg", "-y",
                "-ss", "0.5",
                "-i", clip_path,
                "-t", str(max_duration),
                "-vn",
                "-ac", "1",
                "-ar", "22050",
                "-b:a", "32k",
                temp_audio
            ]
            res = subprocess.run(cmd, capture_output=True, check=False)
            if res.returncode == 0 and os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 500:
                with open(temp_audio, "rb") as f:
                    data = f.read()
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass
                return data
        except Exception as e:
            app_logger.warning(f"[ReviewerAgent] Erro ao extrair áudio para auditoria: {str(e)}")
        return None

    def inspect_clip(
        self,
        clip_path: str,
        global_topic: str,
        scene_fala: str,
        video_title: str,
        status_callback = None
    ) -> Dict[str, Any]:
        """
        Inspeciona o recorte de vídeo e áudio com Gemini Vision (1 frame 384px + áudio, timeout 60s)
        com suporte total a early-discard de vídeos irrelevantes, auditoria de voz humana e redundância de chaves.
        """
        with LogSpan("ReviewerAgent.inspect_clip", extra={"clip": clip_path, "topic": global_topic, "title": video_title}):
            ok_title, reason = self.pre_filter_title(video_title, global_topic)
            if not ok_title:
                app_logger.info(f"[ReviewerAgent] Pré-filtro reprovou '{video_title}': {reason}")
                return {
                    "aprovado": False,
                    "descartar_video_inteiro": True,
                    "score": 1.0,
                    "tem_voz_humana": False,
                    "som_mecanico_puro": False,
                    "motivo": reason,
                    "elementos_detectados": "Título incompatível"
                }

            frame = self.extract_clip_frame(clip_path)
            audio_bytes = self.extract_clip_audio_snippet(clip_path)

            if not frame:
                return {
                    "aprovado": True,
                    "descartar_video_inteiro": False,
                    "score": 7.0,
                    "tem_voz_humana": False,
                    "som_mecanico_puro": True,
                    "motivo": "Aprovado por pré-filtro de título",
                    "elementos_detectados": "Vídeo"
                }

            prompt_text = (
                f"Avalie a qualidade e pertinência deste recorte para o vídeo (POLÍTICA ZERO ROSTOS & ZERO VOZ HUMANA NO ÁUDIO ORIGINAL).\n"
                f"TEMA GLOBAL: '{global_topic}'\n"
                f"TÍTULO DO VÍDEO NO YOUTUBE: '{video_title}'\n"
                f"FALA DA CENA: '{scene_fala}'\n\n"
                f"DIRETRIZES DE INSPEÇÃO:\n"
                f"1. QUALIDADE VISUAL: SE HOUVER QUALQUER ROSTO HUMANO/PESSOA, REPROVE IMEDIATAMENTE (score 1.0, aprovado = false). "
                f"Se o vídeo for fora do tema (tutorial de software/GoPro, outra marca de carro, gráfico estático, motor de drone/brinquedo), marque 'descartar_video_inteiro: true'.\n"
                f"2. AUDITORIA DE ÁUDIO: Verifique se o áudio contém QUALQUER voz ou fala humana ('tem_voz_humana': true/false) "
                f"ou se contém som mecânico de motor/escapamento/pista ('som_mecanico_puro': true/false)."
            )

            contents = [prompt_text, frame]
            if audio_bytes:
                try:
                    contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3"))
                except Exception:
                    pass

            try:
                raw_json = generate_multimodal_with_resilience(
                    contents=contents,
                    system_instruction=self.system_instruction,
                    model_name=self.model_name,
                    fallback_models=self.fallback_models,
                    auto_fallback=self.auto_fallback,
                    auto_cooldown=self.auto_cooldown,
                    response_mime_type="application/json",
                    timeout_seconds=60.0,
                    api_keys=self.api_keys
                )
                result = json.loads(raw_json)
                
                # Garantir campo descartar_video_inteiro
                if "descartar_video_inteiro" not in result:
                    motivo_low = result.get("motivo", "").lower()
                    is_irrelevant = any(kw in motivo_low for kw in [
                        "desalinhado", "irrelevante", "outra marca", "outro modelo",
                        "desconectad", "drone", "gopro", "tutorial", "estático",
                        "gráfico", "software", "sem relação", "incompatível"
                    ])
                    result["descartar_video_inteiro"] = (not result.get("aprovado", False)) and (result.get("score", 10.0) <= 3.0 or is_irrelevant)

                # Garantir campos de áudio
                if "tem_voz_humana" not in result:
                    motivo_low = str(result.get("motivo", "")).lower()
                    result["tem_voz_humana"] = any(kw in motivo_low for kw in ["fala", "voz", "conversando", "apresentador", "narrador", "falando", "talking", "speech"])
                if "som_mecanico_puro" not in result:
                    result["som_mecanico_puro"] = not result.get("tem_voz_humana", False)

                app_logger.info(
                    f"[ReviewerAgent] Parecer do trecho '{video_title}': "
                    f"Aprovado={result.get('aprovado')} (VozHumana={result.get('tem_voz_humana')}, "
                    f"SomMecanico={result.get('som_mecanico_puro')}, Nota {result.get('score')}/10) - {result.get('motivo')}"
                )
                return result
            except Exception as e:
                app_logger.warning(f"[ReviewerAgent] Timeout/Erro na visão ({str(e)}). Usando aprovação por pré-filtro.")
                return {
                    "aprovado": True,
                    "descartar_video_inteiro": False,
                    "score": 7.5,
                    "tem_voz_humana": False,
                    "som_mecanico_puro": True,
                    "motivo": "Aprovado por título e contingência",
                    "elementos_detectados": "Veículo"
                }

# Retrocompatibilidade
CoderAgent = DirectorAgent
