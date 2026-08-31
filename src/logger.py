import os
import sys
import time
import logging
from datetime import datetime
from collections import deque
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.environ.get("LOGS_DIR") or os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# Buffer circular em memória para consumo em tempo real na WebUI
LOG_BUFFER = deque(maxlen=200)

# Buffer circular para rastreamento exclusivo de throttling de API e Download de Vídeo (sem CPU throttling)
THROTTLING_EVENTS = deque(maxlen=100)
_throttling_lock = __import__("threading").Lock()

def record_throttling(
    source: str,
    event_type: str,
    message: str,
    retry_after: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Registra um evento de throttling estritamente de API ou de Download de Vídeo (excluindo throttling de CPU).
    Fontes válidas: 'API_GEMINI' ou 'YOUTUBE_DOWNLOAD'.
    """
    clean_source = source.strip().upper()
    if "CPU" in clean_source:
        return {} # Invariante: sem incluir throttling de CPU

    now = time.time()
    event = {
        "timestamp": now,
        "time_str": datetime.fromtimestamp(now).strftime("%H:%M:%S"),
        "source": clean_source,
        "event_type": event_type,
        "message": message,
        "retry_after": retry_after or 0,
        "details": details or {}
    }
    with _throttling_lock:
        THROTTLING_EVENTS.append(event)

    app_logger.warning(f"🚨 [THROTTLING DETECTADO - {clean_source}] {event_type}: {message} (Retry-After: {retry_after}s)")
    return event

def get_active_throttling_alerts(max_age_seconds: int = 180) -> List[Dict[str, Any]]:
    """Retorna alertas de throttling recentes para exibição prioritária na WebUI."""
    now = time.time()
    with _throttling_lock:
        return [
            ev for ev in THROTTLING_EVENTS
            if (now - ev["timestamp"]) <= max_age_seconds
        ]

def clear_throttling_alerts():
    """Limpa o buffer de alertas de throttling ativos."""
    with _throttling_lock:
        THROTTLING_EVENTS.clear()

def get_throttling_summary() -> Dict[str, Any]:
    """Retorna resumo estatístico de eventos de throttling de API e Download."""
    with _throttling_lock:
        events = list(THROTTLING_EVENTS)
    api_hits = sum(1 for e in events if e["source"] == "API_GEMINI")
    download_hits = sum(1 for e in events if e["source"] == "YOUTUBE_DOWNLOAD")
    latest = events[-1] if events else None
    return {
        "total_throttling_events": len(events),
        "api_throttling_hits": api_hits,
        "download_throttling_hits": download_hits,
        "latest_event": latest
    }

class StreamlitLogHandler(logging.Handler):
    """Handler customizado que alimenta o buffer circular da UI."""
    def emit(self, record):
        try:
            log_entry = self.format(record)
            LOG_BUFFER.append({
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "module": record.module,
                "message": record.getMessage(),
                "raw": log_entry
            })
        except Exception:
            self.handleError(record)

class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                enc = getattr(stream, 'encoding', None) or 'ascii'
                safe_msg = msg.encode(enc, errors='replace').decode(enc)
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger(name: str = "ai_slop") -> logging.Logger:
    """Configura logger persistente em arquivo e console."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s.%(module)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File Handler diário
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOGS_DIR, f"execution_{today_str}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Latest symlink-like file
    latest_file = os.path.join(LOGS_DIR, "latest.log")
    latest_handler = logging.FileHandler(latest_file, mode="a", encoding="utf-8")
    latest_handler.setLevel(logging.DEBUG)
    latest_handler.setFormatter(formatter)
    
    # Console Handler
    console_handler = SafeStreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # UI Handler
    ui_handler = StreamlitLogHandler()
    ui_handler.setLevel(logging.DEBUG)
    ui_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(latest_handler)
    logger.addHandler(console_handler)
    logger.addHandler(ui_handler)
    
    return logger

app_logger = setup_logger()

class LogSpan:
    """Context manager para medir e logar a duração de blocos críticos."""
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None, extra: Optional[Dict[str, Any]] = None):
        self.op = operation_name
        self.logger = logger or app_logger
        self.extra = extra or {}
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"▶️ INICIANDO: {self.op} | Contexto: {self.extra}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = round(time.time() - self.start_time, 2)
        if exc_type:
            self.logger.error(f"❌ FALHA: {self.op} após {duration}s | Erro: {exc_val}", exc_info=True)
        else:
            self.logger.info(f"✅ CONCLUÍDO: {self.op} em {duration}s")
        return False

def get_recent_ui_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Retorna os logs mais recentes para a WebUI."""
    return list(LOG_BUFFER)[-limit:]

def analyze_logs(log_filepath: Optional[str] = None) -> Dict[str, Any]:
    """
    Analisa os logs gravados para identificar gargalos, taxas de erro,
    reprovações de auditoria visual e disparos de cota Gemini.
    """
    target_path = log_filepath or os.path.join(LOGS_DIR, "latest.log")
    if not os.path.exists(target_path):
        return {"status": "empty", "message": "Nenhum arquivo de log encontrado."}

    stats = {
        "total_lines": 0,
        "info_count": 0,
        "warning_count": 0,
        "error_count": 0,
        "brolls_count": 0,
        "quota_hits": 0,
        "timeouts": 0,
        "durations": [],
        "recommendations": []
    }

    with open(target_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stats["total_lines"] += 1
            if "[INFO]" in line:
                stats["info_count"] += 1
            elif "[WARNING]" in line:
                stats["warning_count"] += 1
            elif "[ERROR]" in line:
                stats["error_count"] += 1

            if "BRollEngine" in line or "Trecho aprovado" in line:
                stats["brolls_count"] += 1
            if "ResourceExhausted" in line or "Quota" in line or "429" in line:
                stats["quota_hits"] += 1
            if "Timeout" in line or "DeadlineExceeded" in line:
                stats["timeouts"] += 1

    # Recomendações baseadas na análise
    if stats["quota_hits"] > 0:
        stats["recommendations"].append("Detectada saturação de cota. Recomenda-se manter o Fallback Automático ativo.")
    if stats["timeouts"] > 0:
        stats["recommendations"].append("Ocorrência de timeouts. Modelos Flash-Lite devem ser priorizados.")

    return stats
