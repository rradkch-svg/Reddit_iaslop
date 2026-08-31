import os
import re
import glob
import subprocess
import tempfile
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Set, Optional, List, Dict, Any
import yt_dlp

try:
    from .logger import app_logger, LogSpan, record_throttling
except ImportError:
    from logger import app_logger, LogSpan, record_throttling

def ensure_js_runtime_in_path():
    """Garante que executáveis de JS runtimes (Deno, Node) estejam no PATH do processo."""
    winget_patterns = [
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\DenoLand.Deno_*\*\deno.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\DenoLand.Deno_*\deno.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS_*\*\node.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS_*\node.exe"),
    ]
    for pat in winget_patterns:
        for match in glob.glob(pat):
            d = os.path.dirname(os.path.abspath(match))
            if d and d not in os.environ.get("PATH", ""):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")

ensure_js_runtime_in_path()

def find_ffmpeg_binary() -> str:
    """Busca o executável do FFmpeg no Windows/PATH."""
    winget_pattern = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe")
    winget_matches = glob.glob(winget_pattern)
    if winget_matches and os.path.exists(winget_matches[0]):
        return winget_matches[0]
    return "ffmpeg"

def find_cookie_file() -> Optional[str]:
    """Localiza arquivo de cookies (cookies.txt ou cookies2.txt) na raiz do projeto, diretório de trabalho ou caminho configurado."""
    candidates = [
        os.environ.get("YOUTUBE_COOKIES_PATH", ""),
        os.environ.get("COOKIES_PATH", ""),
        os.path.join(os.getcwd(), "cookies.txt"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies.txt"),
        os.path.join(os.getcwd(), "cookies2.txt"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies2.txt"),
        os.path.expanduser(r"~\cookies.txt"),
        os.path.expanduser(r"~\cookies2.txt"),
        os.path.expanduser(r"~/.config/yt-dlp/cookies.txt"),
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                    if first_line.startswith("#") or "\t" in first_line:
                        return os.path.abspath(path)
            except Exception:
                continue
    return None



def get_video_duration(file_path: str, ffmpeg_bin: str = "ffmpeg") -> Optional[float]:
    """
    Valida a duração exata do arquivo baixado via ffprobe antes de qualquer corte (Item 3).
    Impede que -ss exceda a duração real do arquivo, prevenindo exit code 3199971767.
    """
    ffprobe_bin = ffmpeg_bin.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in ffmpeg_bin else "ffprobe"
    cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        dur_val = float(res.stdout.strip())
        return dur_val if dur_val > 0 else None
    except Exception as e:
        app_logger.warning(f"[BRollEngine] ffprobe falhou ao ler duração de '{file_path}': {str(e)}")
        return None

def get_video_resolution(file_path: str, ffmpeg_bin: str = "ffmpeg") -> Optional[Tuple[int, int]]:
    """
    Obtém a resolução nativa (largura, altura) do arquivo de vídeo via ffprobe.
    Permite descartar vídeos com resolução vertical/menor dimensão inferior a 720p.
    """
    ffprobe_bin = ffmpeg_bin.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in ffmpeg_bin else "ffprobe"
    cmd = [
        ffprobe_bin, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        output = res.stdout.strip()
        if "x" in output:
            parts = output.split("x")
            return int(parts[0]), int(parts[1])
    except Exception as e:
        app_logger.warning(f"[BRollEngine] ffprobe falhou ao ler resolução de '{file_path}': {str(e)}")
    return None

def extract_vehicle_keywords(text: str) -> str:
    """Extrai os termos essenciais do veículo/máquina de estudo de um título longo."""
    parts = text.split(":")
    main_part = parts[0] if len(parts) > 1 else text
    cleaned = re.sub(r"^(O Segredo d[oa]|Como funciona o|Por que o|A física d[oa]|A engenharia d[oa]|Tudo sobre o|O Motor d[oa]|A Asa d[oa]|A Suspensão d[oa])\s*", "", main_part, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
    cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|para|sobre|que|por|ser|bom|demais|segredo|fisica|engenharia|o|a|os|as)\b", " ", cleaned, flags=re.IGNORECASE)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return " ".join(words[:6]) if words else text.strip()

def build_topic_queries(global_topic: str, base_query: str) -> List[str]:
    """Gera queries de busca focadas, com conexão particular obrigatória ao veículo e objeto de estudo."""
    vehicle_kw = extract_vehicle_keywords(global_topic)
    queries = []
    
    # Verifica se base_query já contém palavras-chave do veículo
    v_tokens = [w.lower() for w in vehicle_kw.split() if len(w) > 1]
    base_clean = base_query.strip() if base_query else ""
    base_lower = base_clean.lower()
    has_anchor = any(t in base_lower for t in v_tokens) if v_tokens else False
    
    if base_clean:
        if has_anchor:
            queries.append(base_clean)
            if not base_lower.endswith("4k") and not base_lower.endswith("hd"):
                queries.append(f"{base_clean} 4k")
        else:
            # Ancora obrigatoriamente a query com o veículo
            anchored = f"{vehicle_kw} {base_clean}".strip()
            queries.append(anchored)
            queries.append(f"{anchored} 4k")
            
    if vehicle_kw:
        queries.extend([
            f"{vehicle_kw} 60fps",
            f"{vehicle_kw} pure sound exhaust 60fps 4k",
            f"{vehicle_kw} onboard raw engine sound 60fps 4k",
            f"{vehicle_kw} launch acceleration sound 60fps 4k",
            f"{vehicle_kw} track test pure sound 60fps 4k",
            f"{vehicle_kw} dyno pull exhaust flame sound 60fps 4k",
            f"{vehicle_kw} flyby sound 60fps 4k",
            f"{vehicle_kw} engine technical cutaway 60fps 4k",
            f"{vehicle_kw} pure sound exhaust 4k",
            f"{vehicle_kw} onboard raw engine sound 4k",
            f"{vehicle_kw} launch acceleration sound 4k",
            f"{vehicle_kw} track test pure sound 4k",
            f"{vehicle_kw} dyno pull exhaust flame sound 4k",
            f"{vehicle_kw} flyby sound 4k",
            f"{vehicle_kw} engine technical cutaway 4k"
        ])
        
    unique_queries = []
    for q in queries:
        q_clean = " ".join(q.split())
        if q_clean and q_clean not in unique_queries:
            unique_queries.append(q_clean)
    return unique_queries

def safe_status(cb, msg: str):
    if cb:
        try:
            cb(msg)
        except:
            pass

def safe_progress(cb, d: int, t: int):
    if cb:
        try:
            cb(d, t)
        except:
            pass

def calculate_scene_durations(
    cenas: List[Dict[str, Any]],
    total_audio_duration: float,
    words_timing: Optional[List[Dict[str, Any]]] = None,
    tail_overhead: float = 0.5
) -> List[float]:
    """
    Calcula com precisão milimétrica a duração de cada corte de cena para que:
    1. Cada tomada acompanhe exatamente o tempo em que a respectiva frase/fala é dita no áudio.
    2. A soma total de todos os clipes cubra 100% da narração + um overhead/buffer de segurança
       compacto no final (tail_overhead) para evitar cortes secos sem criar pausas mortas.
    """
    n_scenes = len(cenas)
    if n_scenes == 0:
        return []
    
    # Caso 1: Mapeamento preciso por words_timing do Edge-TTS
    if words_timing and len(words_timing) > 0:
        scene_durations = []
        word_idx = 0
        total_words = len(words_timing)
        curr_time = 0.0
        
        for sc_idx, cena in enumerate(cenas):
            fala = cena.get("fala", "").strip()
            sc_words = fala.split()
            sc_word_count = len(sc_words) if sc_words else 1
            
            start_t = curr_time
            end_idx = min(word_idx + sc_word_count - 1, total_words - 1)
            speech_end_t = words_timing[end_idx].get("end", total_audio_duration)
            
            word_idx = end_idx + 1
            
            if sc_idx == n_scenes - 1:
                dur = max(total_audio_duration - start_t, speech_end_t - start_t) + tail_overhead
            else:
                dur = max(1.8, speech_end_t - start_t)
                
            dur = round(dur, 2)
            scene_durations.append(dur)
            curr_time += dur
        
        # Garantia final de overhead total
        if sum(scene_durations) < total_audio_duration + tail_overhead:
            diff = (total_audio_duration + tail_overhead) - sum(scene_durations)
            scene_durations[-1] = round(scene_durations[-1] + diff, 2)
            
        return scene_durations
    
    # Caso 2: Cálculo proporcional pelos pesos das palavras / texto de cada cena
    weights = []
    for c in cenas:
        fala = c.get("fala", "").strip()
        w = len(fala.split()) if fala else 1
        weights.append(max(w, 1))
    
    total_w = sum(weights)
    durations = []
    for sc_idx, w in enumerate(weights):
        base_dur = (w / total_w) * total_audio_duration
        if sc_idx == n_scenes - 1:
            base_dur += tail_overhead
        durations.append(round(max(1.8, base_dur), 2))
    
    if sum(durations) < total_audio_duration + tail_overhead:
        diff = (total_audio_duration + tail_overhead) - sum(durations)
        durations[-1] = round(durations[-1] + diff, 2)
        
    return durations

class BRollEngine:
    """
    Motor de busca, download, varredura multi-trecho e auditoria concorrente de B-Rolls.
    Garante que 100% dos trechos utilizados sejam limpos (Zero Rostos) e renderizados em 1080x1920 HD
    com política estrita de Early-Discard para não desperdiçar tempo nem tokens em vídeos fora do tema.
    """
    def __init__(self, max_search_results: int = 6):
        self.max_search_results = max_search_results
        self.ffmpeg_bin = find_ffmpeg_binary()
        self.lock = threading.Lock()

    def search_and_download_clip(
        self,
        query: str,
        target_duration: float,
        seen_ids: Set[str],
        output_clip_path: str,
        global_topic: str = "Supercarro",
        reviewer_agent = None,
        scene_fala: str = "",
        status_callback = None
    ) -> Tuple[bool, str, str, str, Dict[str, Any]]:
        """
        Pesquisa no YouTube e executa pipeline de download em 2 Etapas:
        1. Etapa de Avaliação: Baixa prévia na menor qualidade aceitável (<=360p) para auditoria multimodal rápida
           e de baixo consumo, com suporte a Early-Discard e varredura multi-trechos.
        2. Etapa de Alta Definição: APÓS VALIDAR A RELEVÂNCIA, baixa a versão na maior resolução disponível até 1080p,
           descartando automaticamente fontes com resolução inferior a 720p. Recorta em 1080x1920 HD.
        """
        with LogSpan("BRollEngine.search_and_download_clip", extra={"query": query, "topic": global_topic, "duration": target_duration}):
            queries_to_try = build_topic_queries(global_topic, query)

            cookie_file = find_cookie_file()
            for current_q in queries_to_try:
                safe_status(status_callback, f"🔍 Buscando tomada no YouTube: *'{current_q}'*...")

                ydl_opts_search = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": "in_playlist",
                    "default_search": f"ytsearch{self.max_search_results}",
                    "noplaylist": True,
                    "remote_components": ["ejs:github", "ejs:npm"],
                }
                if cookie_file:
                    ydl_opts_search["cookiefile"] = cookie_file

                entries = []
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
                        search_results = ydl.extract_info(f"ytsearch{self.max_search_results}:{current_q}", download=False)
                        entries = search_results.get("entries", [])
                except Exception as e:
                    err_str = str(e)
                    is_dl_throttled = "429" in err_str or "Too Many Requests" in err_str or "rate-limit" in err_str.lower() or "bot" in err_str.lower()
                    if is_dl_throttled:
                        record_throttling("YOUTUBE_DOWNLOAD", "HTTP_429_SEARCH_THROTTLE", f"Busca no YouTube sob rate limit: {err_str[:150]}", retry_after=10)
                    app_logger.warning(f"[BRollEngine] Erro ao buscar '{current_q}': {err_str}")
                    continue

                candidates = []
                with self.lock:
                    for entry in entries:
                        if not entry:
                            continue
                        v_id = entry.get("id")
                        v_dur = entry.get("duration") or 60
                        if v_id and v_id not in seen_ids and 8 <= v_dur <= 2400:
                            candidates.append(entry)

                if not candidates:
                    continue

                for cand in candidates:
                    vid_id = cand.get("id")
                    vid_title = cand.get("title", current_q)
                    vid_dur = cand.get("duration") or 60
                    vid_url = f"https://www.youtube.com/watch?v={vid_id}"

                    # 1. Pré-filtragem instantânea de metadados / título antes do download
                    if reviewer_agent:
                        ok_title, pre_reason = reviewer_agent.pre_filter_title(vid_title, global_topic)
                        if not ok_title:
                            app_logger.info(f"[BRollEngine] Candidato '{vid_title}' descartado pelo pré-filtro: {pre_reason}")
                            continue

                    # =========================================================================
                    # ETAPA 1: Download de Prévia em Baixa Resolução para Avaliação da IA
                    # =========================================================================
                    safe_status(status_callback, f"📥 Baixando prévia leve para avaliação: **{vid_title[:45]}...**")

                    temp_preview_file = os.path.join(tempfile.gettempdir(), f"broll_prev_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")
                    temp_preview_cut = os.path.join(tempfile.gettempdir(), f"broll_prevcut_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")

                    ydl_opts_preview = {
                        "format": "bestvideo[height<=360]+bestaudio/best[height<=360]/bestvideo[height<=480]+bestaudio/best[height<=480]/worst",
                        "outtmpl": temp_preview_file,
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "socket_timeout": 20,
                        "remote_components": ["ejs:github", "ejs:npm"],
                    }
                    if cookie_file:
                        ydl_opts_preview["cookiefile"] = cookie_file

                    try:
                        with yt_dlp.YoutubeDL(ydl_opts_preview) as ydl:
                            ydl.download([vid_url])

                        if not os.path.exists(temp_preview_file):
                            matches = glob.glob(temp_preview_file.replace(".mp4", ".*"))
                            if matches:
                                temp_preview_file = matches[0]
                            else:
                                continue

                        actual_dur = get_video_duration(temp_preview_file, self.ffmpeg_bin)
                        if not actual_dur or actual_dur < 1.0:
                            app_logger.warning(f"[BRollEngine] Arquivo de prévia corrompido ou sem duração detectável: {temp_preview_file}")
                            if os.path.exists(temp_preview_file):
                                try:
                                    os.remove(temp_preview_file)
                                except:
                                    pass
                            continue

                        # Varredura Multi-Trechos Inteligente na Prévia
                        if actual_dur <= target_duration:
                            seek_offsets = [0.0]
                            effective_cut_dur = max(1.0, actual_dur)
                        else:
                            max_seek = max(0.0, actual_dur - target_duration - 0.5)
                            offsets_pct = [0.25, 0.60]
                            seek_offsets = [min(max_seek, max(0.0, actual_dur * p)) for p in offsets_pct]
                            seek_offsets = list(dict.fromkeys([round(s, 1) for s in seek_offsets if s <= max_seek]))
                            if not seek_offsets:
                                seek_offsets = [0.0]
                            effective_cut_dur = target_duration

                        approved = False
                        approved_seek_t = 0.0
                        approved_cut_dur = effective_cut_dur
                        best_inspection = {}

                        for seek_t in seek_offsets:
                            if os.path.exists(temp_preview_cut):
                                try:
                                    os.remove(temp_preview_cut)
                                except:
                                    pass

                            cut_dur = min(effective_cut_dur, max(1.0, actual_dur - seek_t))

                            # Recorte rápido da prévia
                            cmd_prev = [
                                self.ffmpeg_bin, "-y",
                                "-ss", str(seek_t),
                                "-i", temp_preview_file,
                                "-t", str(cut_dur),
                                "-c:v", "libx264",
                                "-preset", "ultrafast",
                                "-pix_fmt", "yuv420p",
                                "-c:a", "aac",
                                "-b:a", "96k",
                                "-ar", "44100",
                                "-ac", "2",
                                "-r", "30",
                                "-t", str(cut_dur),
                                temp_preview_cut
                            ]
                            try:
                                subprocess.run(cmd_prev, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                            except Exception:
                                cmd_prev_silent = [
                                    self.ffmpeg_bin, "-y",
                                    "-ss", str(seek_t),
                                    "-i", temp_preview_file,
                                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                                    "-t", str(cut_dur),
                                    "-map", "0:v:0",
                                    "-map", "1:a:0",
                                    "-c:v", "libx264",
                                    "-preset", "ultrafast",
                                    "-pix_fmt", "yuv420p",
                                    "-c:a", "aac",
                                    "-b:a", "96k",
                                    "-r", "30",
                                    "-t", str(cut_dur),
                                    temp_preview_cut
                                ]
                                try:
                                    subprocess.run(cmd_prev_silent, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                                except Exception:
                                    pass

                            if not os.path.exists(temp_preview_cut) or os.path.getsize(temp_preview_cut) == 0:
                                continue

                            # Auditoria visual e acústica da prévia
                            if reviewer_agent:
                                safe_status(status_callback, f"🧐 Inspecionando prévia aos {seek_t:.0f}s de *'{vid_title[:35]}'*...")
                                inspection = reviewer_agent.inspect_clip(
                                    clip_path=temp_preview_cut,
                                    global_topic=global_topic,
                                    scene_fala=scene_fala,
                                    video_title=vid_title,
                                    status_callback=status_callback
                                )
                                best_inspection = inspection
                                if inspection.get("aprovado", False):
                                    approved = True
                                    approved_seek_t = seek_t
                                    approved_cut_dur = cut_dur
                                    safe_status(status_callback, f"✅ **Relevância Validada aos {seek_t:.0f}s!** ({inspection.get('motivo')})")
                                    break
                                else:
                                    motivo_low = str(inspection.get("motivo", "")).lower()
                                    is_irrelevant = (
                                        inspection.get("descartar_video_inteiro", False) or
                                        float(inspection.get("score", 10.0)) <= 3.0 or
                                        any(kw in motivo_low for kw in [
                                            "desalinhado", "irrelevante", "outra marca", "outro modelo",
                                            "desconectad", "drone", "gopro", "tutorial", "estático", "gráfico",
                                            "incompatível", "diferente", "software", "gameplay", "sem relação"
                                        ])
                                    )
                                    if is_irrelevant:
                                        safe_status(status_callback, f"🚫 Vídeo descartado por irrelevância total ({inspection.get('motivo')}) -> Pulando candidato...")
                                        app_logger.info(f"[BRollEngine] Early-Discard acionado para '{vid_title}': {inspection.get('motivo')}")
                                        break
                                    else:
                                        safe_status(status_callback, f"⚠️ Prévia aos {seek_t:.0f}s reprovada ({inspection.get('motivo')}) -> Testando próximo trecho...")
                            else:
                                approved = True
                                approved_seek_t = seek_t
                                approved_cut_dur = cut_dur
                                best_inspection = {"aprovado": True, "score": 8.0, "motivo": "Aprovado automaticamente"}
                                break

                        # Limpeza dos arquivos de prévia
                        if os.path.exists(temp_preview_file):
                            try:
                                os.remove(temp_preview_file)
                            except:
                                pass
                        if os.path.exists(temp_preview_cut):
                            try:
                                os.remove(temp_preview_cut)
                            except:
                                pass

                        if not approved:
                            continue

                        # =========================================================================
                        # ETAPA 2: Download em Alta Definição (720p até 1080p) APÓS VALIDAÇÃO
                        # Descarte estrito de conteúdos com resolução inferior a 720p.
                        # =========================================================================
                        safe_status(status_callback, f"📥 Baixando versão HD (1080p/720p 60fps): **{vid_title[:45]}...**")

                        temp_hd_file = os.path.join(tempfile.gettempdir(), f"broll_hd_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")
                        temp_cut_clip = os.path.join(tempfile.gettempdir(), f"broll_cut_{vid_id}_{int(time.time()*1000)}_{threading.get_ident()}.mp4")

                        ydl_opts_hd = {
                            "format": "bestvideo[height<=1080][height>=720][fps>=50]+bestaudio/bestvideo[height<=1080][height>=720]+bestaudio/best[height<=1080][height>=720]",
                            "format_sort": ["fps:60", "res:1080", "codec:h264"],
                            "outtmpl": temp_hd_file,
                            "quiet": True,
                            "no_warnings": True,
                            "noplaylist": True,
                            "socket_timeout": 25,
                            "remote_components": ["ejs:github", "ejs:npm"],
                        }
                        if cookie_file:
                            ydl_opts_hd["cookiefile"] = cookie_file

                        try:
                            with yt_dlp.YoutubeDL(ydl_opts_hd) as ydl:
                                ydl.download([vid_url])
                        except Exception as err_hd_dl:
                            err_msg = str(err_hd_dl)
                            if "Requested format is not available" in err_msg or "format" in err_msg.lower():
                                safe_status(status_callback, f"⚠️ Vídeo descartado: resolução máxima inferior a 720p -> Pulando candidato...")
                                app_logger.warning(f"[BRollEngine] Candidato '{vid_title}' ({vid_id}) descartado: não possui resolução entre 720p e 1080p.")
                            else:
                                app_logger.warning(f"[BRollEngine] Erro ao baixar versão HD de '{vid_title}': {err_msg}")
                            continue

                        if not os.path.exists(temp_hd_file):
                            matches = glob.glob(temp_hd_file.replace(".mp4", ".*"))
                            if matches:
                                temp_hd_file = matches[0]
                            else:
                                app_logger.warning(f"[BRollEngine] Arquivo HD não encontrado após download: {temp_hd_file}")
                                continue

                        # Validação estrita de resolução mínima (720p)
                        res_info = get_video_resolution(temp_hd_file, self.ffmpeg_bin)
                        if res_info:
                            effective_res = min(res_info[0], res_info[1])
                            if effective_res < 720:
                                safe_status(status_callback, f"⚠️ Vídeo descartado: resolução ({effective_res}p) inferior a 720p -> Pulando candidato...")
                                app_logger.warning(f"[BRollEngine] Candidato '{vid_title}' descartado por resolução baixa ({res_info[0]}x{res_info[1]}).")
                                if os.path.exists(temp_hd_file):
                                    try:
                                        os.remove(temp_hd_file)
                                    except:
                                        pass
                                continue

                        hd_actual_dur = get_video_duration(temp_hd_file, self.ffmpeg_bin) or actual_dur
                        hd_cut_dur = min(approved_cut_dur, max(1.0, hd_actual_dur - approved_seek_t))

                        safe_status(status_callback, f"✂️ Recortando tomada final em 1080x1920 60fps HD...")

                        # Recorte 9:16 Ultra HD 60fps (Lanczos + Unsharp Sharpening + CRF 16) com preservação de áudio estéreo
                        cmd_cut = [
                            self.ffmpeg_bin, "-y",
                            "-ss", str(approved_seek_t),
                            "-i", temp_hd_file,
                            "-t", str(hd_cut_dur),
                            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2,setsar=1,fps=60,unsharp=lx=5:ly=5:la=0.8:cx=3:cy=3:ca=0.4,tpad=stop_mode=clone:stop_duration=5.0",
                            "-c:v", "libx264",
                            "-crf", "16",
                            "-preset", "fast",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-ar", "44100",
                            "-ac", "2",
                            "-r", "60",
                            "-t", str(hd_cut_dur),
                            temp_cut_clip
                        ]
                        try:
                            subprocess.run(cmd_cut, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                        except Exception:
                            # Fallback com gerador de silêncio (anullsrc) caso o arquivo de origem não possua stream de áudio
                            cmd_silent = [
                                self.ffmpeg_bin, "-y",
                                "-ss", str(approved_seek_t),
                                "-i", temp_hd_file,
                                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                                "-t", str(hd_cut_dur),
                                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2,setsar=1,fps=60,unsharp=lx=5:ly=5:la=0.8:cx=3:cy=3:ca=0.4,tpad=stop_mode=clone:stop_duration=5.0",
                                "-map", "0:v:0",
                                "-map", "1:a:0",
                                "-c:v", "libx264",
                                "-crf", "16",
                                "-preset", "fast",
                                "-pix_fmt", "yuv420p",
                                "-c:a", "aac",
                                "-b:a", "192k",
                                "-r", "60",
                                "-t", str(hd_cut_dur),
                                temp_cut_clip
                            ]
                            subprocess.run(cmd_silent, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")

                        # Limpeza do arquivo bruto HD
                        if os.path.exists(temp_hd_file):
                            try:
                                os.remove(temp_hd_file)
                            except:
                                pass

                        if not os.path.exists(temp_cut_clip) or os.path.getsize(temp_cut_clip) == 0:
                            continue

                        # Se fala humana foi detectada na prévia, silenciar o áudio desta cena mantendo o vídeo
                        if best_inspection.get("tem_voz_humana", False):
                            safe_status(status_callback, f"🔇 Voz humana detectada no áudio original -> Silenciando áudio desta cena...")
                            temp_muted = temp_cut_clip.replace(".mp4", "_muted.mp4")
                            cmd_mute = [
                                self.ffmpeg_bin, "-y",
                                "-i", temp_cut_clip,
                                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                                "-map", "0:v:0",
                                "-map", "1:a:0",
                                "-c:v", "copy",
                                "-c:a", "aac",
                                "-b:a", "192k",
                                "-shortest",
                                temp_muted
                            ]
                            try:
                                subprocess.run(cmd_mute, check=True, capture_output=True)
                                if os.path.exists(temp_muted) and os.path.getsize(temp_muted) > 0:
                                    os.replace(temp_muted, temp_cut_clip)
                            except Exception as e_m:
                                app_logger.warning(f"[BRollEngine] Erro ao silenciar cena com voz: {str(e_m)}")
                        else:
                            safe_status(status_callback, f"🔊 Som mecânico do carro preservado com sucesso!")

                        with self.lock:
                            seen_ids.add(vid_id)
                        if os.path.exists(output_clip_path):
                            try:
                                os.remove(output_clip_path)
                            except:
                                pass
                        os.rename(temp_cut_clip, output_clip_path)
                        app_logger.info(f"[BRollEngine] Trecho HD aprovado e gravado: {output_clip_path} (ID: {vid_id} - '{vid_title}')")
                        return True, output_clip_path, vid_id, vid_title, best_inspection

                    except Exception as err_dl:
                        err_str = str(err_dl)
                        is_dl_throttled = "429" in err_str or "Too Many Requests" in err_str or "rate-limit" in err_str.lower() or "bot" in err_str.lower() or "throttl" in err_str.lower()
                        if is_dl_throttled:
                            record_throttling("YOUTUBE_DOWNLOAD", "HTTP_429_DOWNLOAD_THROTTLE", f"Download no YouTube sob rate limit ({vid_id}): {err_str[:150]}", retry_after=15)
                            time.sleep(1.5)
                        app_logger.warning(f"[BRollEngine] Erro no candidato {vid_id}: {err_str}")
                        for f_clean in [temp_preview_file, temp_preview_cut, temp_hd_file if 'temp_hd_file' in locals() else '', temp_cut_clip if 'temp_cut_clip' in locals() else '']:
                            if f_clean and os.path.exists(f_clean):
                                try:
                                    os.remove(f_clean)
                                except:
                                    pass
                        continue

            app_logger.error(f"[BRollEngine] Nenhum trecho aprovado encontrado para '{query}' após varredura.")
            return False, "", "", "", {"aprovado": False, "motivo": "Nenhum trecho aprovado"}

    def process_all_scenes_parallel(
        self,
        cenas: List[Dict[str, Any]],
        global_topic: str,
        reviewer_agent,
        project_dir: str,
        total_audio_duration: float,
        words_timing: Optional[List[Dict[str, Any]]] = None,
        tail_overhead: float = 0.5,
        max_workers: int = 4,
        status_callback = None,
        progress_callback = None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Processa e audita todas as cenas do roteiro DE FORMA CONCORRENTE EM BATCHES (default max_workers=4),
        anexando o ScriptRunContext do Streamlit a todas as threads para eliminar warnings (Item 4).
        Garante que a duração de cada corte acompanhe a fala da cena e a soma total cubra o áudio + tail_overhead.
        """
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
            parent_ctx = get_script_run_ctx()
        except Exception:
            parent_ctx = None

        seen_ids = set()
        results = [None] * len(cenas)
        completed_count = 0
        total_scenes = len(cenas)

        # Cálculo preciso das durações reais por cena (Word-Timing / Proporcional + Overhead)
        target_durations = calculate_scene_durations(
            cenas=cenas,
            total_audio_duration=total_audio_duration,
            words_timing=words_timing,
            tail_overhead=tail_overhead
        )
        app_logger.info(f"[BRollEngine] Durações de cena calculadas: {target_durations} (Soma: {sum(target_durations):.2f}s para áudio de {total_audio_duration:.2f}s + overhead {tail_overhead}s)")

        def worker_task(c_idx: int, cena: Dict[str, Any]):
            if parent_ctx is not None:
                try:
                    from streamlit.runtime.scriptrunner import add_script_run_ctx
                    add_script_run_ctx(threading.current_thread(), parent_ctx)
                except Exception:
                    pass

            c_dur = target_durations[c_idx] if c_idx < len(target_durations) else float(cena.get("duracao_estimada", total_audio_duration / total_scenes))
            c_dur = max(1.8, c_dur)
            clip_out = os.path.join(project_dir, f"scene_{c_idx:02d}.mp4")
            
            def on_item_status(msg):
                safe_status(status_callback, f"🎬 **Cena #{c_idx+1}/{total_scenes}:** {msg}")
            
            query = cena.get("youtube_query") or f"{global_topic} 4k acceleration"
            success_clip, clip_path, vid_id, vid_title, inspection = self.search_and_download_clip(
                query=query,
                target_duration=c_dur,
                seen_ids=seen_ids,
                output_clip_path=clip_out,
                global_topic=global_topic,
                reviewer_agent=reviewer_agent,
                scene_fala=cena.get("fala", ""),
                status_callback=on_item_status
            )
            
            return c_idx, success_clip, clip_out, vid_id, vid_title, inspection, cena.get("fala", "")

        app_logger.info(f"[BRollEngine] Iniciando processamento paralelo de {total_scenes} cenas com {max_workers} workers...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker_task, idx, c) for idx, c in enumerate(cenas)]
            
            for future in as_completed(futures):
                try:
                    c_idx, success_clip, clip_out, vid_id, vid_title, inspection, fala = future.result()
                    completed_count += 1
                    safe_progress(progress_callback, completed_count, total_scenes)
                        
                    if success_clip and os.path.exists(clip_out):
                        results[c_idx] = {
                            "clip_path": clip_out,
                            "cena": c_idx + 1,
                            "fala": fala,
                            "titulo": vid_title,
                            "id": vid_id,
                            "score": inspection.get("score", 8.0),
                            "motivo": inspection.get("motivo", "Aprovado"),
                            "elementos": inspection.get("elementos_detectados", "")
                        }
                    else:
                        app_logger.warning(f"[BRollEngine] Cena #{c_idx+1} não obteve clipe aprovado.")
                except Exception as e:
                    app_logger.error(f"[BRollEngine] Erro no worker da cena: {str(e)}")

        scene_clips = []
        scene_audits = []
        for r in results:
            if r and os.path.exists(r["clip_path"]):
                scene_clips.append(r["clip_path"])
                scene_audits.append(r)

        return scene_clips, scene_audits
