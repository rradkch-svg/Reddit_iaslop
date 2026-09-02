import os
import glob
import random
import subprocess
from typing import List, Tuple, Optional, Dict, Any

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

def find_ffmpeg_binary() -> str:
    """Localiza o binário FFmpeg com prioridade máxima para o executável do imageio-ffmpeg."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    winget_pattern = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe")
    winget_matches = glob.glob(winget_pattern)
    if winget_matches and os.path.exists(winget_matches[0]):
        return winget_matches[0]

    return "ffmpeg"

def get_media_duration(file_path: str, ffmpeg_bin: Optional[str] = None) -> float:
    """Retorna a duração exata do arquivo em segundos via FFmpeg stderr."""
    ff = ffmpeg_bin or find_ffmpeg_binary()
    try:
        cmd = [ff, "-i", file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            hours, mins, secs = float(m.group(1)), float(m.group(2)), float(m.group(3))
            return hours * 3600 + mins * 60 + secs
    except Exception:
        pass
    return 45.0

def is_valid_video_file(file_path: str, min_size_mb: float = 1.0) -> bool:
    """Verifica se o arquivo de vídeo existe e possui tamanho mínimo válido."""
    try:
        return os.path.exists(file_path) and os.path.getsize(file_path) >= (min_size_mb * 1024 * 1024)
    except Exception:
        return False

def get_best_orbital_background(aspect_ratio: str = "9:16") -> Optional[str]:
    """Localiza o melhor vídeo de gameplay saudável (priorizando Minecraft) em assets/backgrounds."""
    bgs = get_orbital_backgrounds(aspect_ratio=aspect_ratio)
    return bgs[0] if bgs else None

def get_orbital_backgrounds(aspect_ratio: str = "16:9") -> List[str]:
    """Retorna lista de vídeos de gameplay válidos em assets/backgrounds com Minecraft priorizado."""
    is_vertical = (aspect_ratio == "9:16")
    bg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "backgrounds")
    
    candidates = []
    for f in glob.glob(os.path.join(bg_dir, "*.mp4")):
        if not is_valid_video_file(f, min_size_mb=2.0):
            continue
        fn = os.path.basename(f).lower()
        if is_vertical:
            if "vertical" in fn or "p9xlr1bobyw" in fn or "lkx3805bia8" in fn or "xlze_oo4wqs" in fn:
                score = 3 if "minecraft" in fn else 2
                candidates.append((score, f))
            else:
                # Vídeos horizontais de Minecraft também funcionam perfeitamente para Shorts via scale+crop
                score = 2 if "minecraft" in fn else 1
                candidates.append((score, f))
        else:
            if "horizontal" in fn or "u7ieztmf" in fn or "erilpuq5yms" in fn or "64dw7xvh" in fn:
                score = 3 if "minecraft" in fn else 2
                candidates.append((score, f))
            else:
                score = 2 if "minecraft" in fn else 1
                candidates.append((score, f))

    if not candidates:
        for f in glob.glob(os.path.join(bg_dir, "*.mp4")):
            if is_valid_video_file(f, min_size_mb=2.0):
                fn = os.path.basename(f).lower()
                score = 2 if "minecraft" in fn else 1
                candidates.append((score, f))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in candidates]

def render_reddit_story_video(
    audio_path: str,
    ass_subtitles_path: str,
    card_png_path: Optional[str],
    output_video_path: str,
    background_video_path: Optional[str] = None,
    final_hook_png_path: Optional[str] = None,
    video_type: str = "shorts", # "shorts", "teaser", "longform", "chunk"
    aspect_ratio: str = "9:16",
    card_duration_sec: float = 4.8,
    final_hook_duration_sec: float = 5.0,
    status_callback = None
) -> Tuple[bool, str]:
    """
    Renderiza o vídeo final com fundo de gameplay real em 1080p60fps,
    Card oficial do Reddit em destaque por card_duration_sec (opcional),
    Gancho Final de tela (See More Here / Full 25-Min Story) nos últimos segundos,
    Sistema de SFX de transição (Plim / Whoosh) e legendas dinâmicas palavra por palavra.
    """
    with LogSpan("render_reddit_story_video", extra={"output": output_video_path, "ratio": aspect_ratio, "type": video_type}):
        ffmpeg_bin = find_ffmpeg_binary()
        is_vertical = (aspect_ratio == "9:16")
        target_w = 1080 if is_vertical else 1920
        target_h = 1920 if is_vertical else 1080

        if not os.path.exists(audio_path):
            return False, f"Arquivo de áudio não encontrado: {audio_path}"

        total_duration = get_media_duration(audio_path, ffmpeg_bin) + 0.4
        work_dir = os.path.dirname(output_video_path)
        os.makedirs(work_dir, exist_ok=True)

        has_card = bool(card_png_path and os.path.exists(card_png_path) and card_duration_sec > 0)
        has_final_hook = bool(final_hook_png_path and os.path.exists(final_hook_png_path))

        # 1. Aplica mixagem de SFX (Plim / Whoosh) na trilha de áudio
        audio_to_encode = audio_path
        if has_card or (has_final_hook and video_type == "teaser"):
            try:
                from .reddit_sfx import mix_sfx_to_audio
            except ImportError:
                from reddit_sfx import mix_sfx_to_audio

            sfx_mixed_audio = os.path.join(work_dir, f"_mixed_sfx_{os.path.basename(audio_path)}")
            audio_to_encode = mix_sfx_to_audio(
                main_audio_path=audio_path,
                output_audio_path=sfx_mixed_audio,
                video_type=video_type,
                total_duration_sec=total_duration,
                card_duration_sec=card_duration_sec if has_card else 0.0,
                final_hook_duration_sec=final_hook_duration_sec,
                ffmpeg_bin=ffmpeg_bin
            )

        bg_to_use = background_video_path or get_best_orbital_background(aspect_ratio=aspect_ratio)
        safe_ass = os.path.abspath(ass_subtitles_path).replace("\\", "/").replace(":", "\\:")
        fade_out_st = max(1.0, card_duration_sec - 0.4)
        fade_in_hook = max(card_duration_sec, total_duration - final_hook_duration_sec)

        if status_callback:
            status_callback(f"🎬 Compondo vídeo {aspect_ratio} 60fps com gameplay HD, Card, SFX e Legendas...")

        inputs = []
        if bg_to_use and os.path.exists(bg_to_use):
            bg_dur = get_media_duration(bg_to_use, ffmpeg_bin)
            if bg_dur >= (total_duration + 2.0):
                # Se o vídeo de fundo é maior que a duração total, escolhe um ponto aleatório
                # garantindo que nunca atinja o final do arquivo (reprodução 100% contínua sem repetições)
                max_start = max(0.0, bg_dur - total_duration - 1.0)
                random_start = random.uniform(0.0, max_start)
                inputs.extend(["-err_detect", "ignore_err", "-fflags", "+genpts+discardcorrupt", "-ss", f"{random_start:.2f}", "-i", bg_to_use])
            else:
                # Se o vídeo de fundo for mais curto que o áudio, inicia em 00:00 e faz loop completo
                # evitando loops de fragmentos curtos no final
                inputs.extend(["-err_detect", "ignore_err", "-fflags", "+genpts+discardcorrupt", "-stream_loop", "-1", "-i", bg_to_use])
            bg_filter = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},setsar=1,fps=60[bg];"
        else:
            src_w = 1080 if is_vertical else 1920
            src_h = 1920 if is_vertical else 1080
            inputs.extend(["-f", "lavfi", "-i", f"testsrc2=size={src_w}x{src_h}:rate=60"])
            bg_filter = f"[0:v]scale={target_w}:{target_h}:flags=bicubic,eq=brightness=-0.30:contrast=1.30:saturation=1.35[bg];"

        # Montagem dinâmica do filter complex conforme os overlays presentes
        filter_parts = [bg_filter]
        current_v = "[bg]"

        if has_card and has_final_hook:
            inputs.extend(["-loop", "1", "-i", card_png_path])
            inputs.extend(["-loop", "1", "-i", final_hook_png_path])
            inputs.extend(["-i", audio_to_encode])
            audio_map_idx = 3

            filter_parts.append(f"[1:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={fade_out_st:.2f}:d=0.4:alpha=1[card_faded];")
            filter_parts.append(f"[2:v]format=rgba,fade=t=in:st={fade_in_hook:.2f}:d=0.4:alpha=1[hook_faded];")
            filter_parts.append(f"{current_v}[card_faded]overlay=0:0:enable='between(t,0,{card_duration_sec:.2f})'[v_card];")
            filter_parts.append(f"[v_card][hook_faded]overlay=0:0:enable='gte(t,{fade_in_hook:.2f})'[v_hook];")
            current_v = "[v_hook]"
        elif has_card:
            inputs.extend(["-loop", "1", "-i", card_png_path])
            inputs.extend(["-i", audio_to_encode])
            audio_map_idx = 2

            filter_parts.append(f"[1:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={fade_out_st:.2f}:d=0.4:alpha=1[card_faded];")
            filter_parts.append(f"{current_v}[card_faded]overlay=0:0:enable='between(t,0,{card_duration_sec:.2f})'[v_card];")
            current_v = "[v_card]"
        elif has_final_hook:
            inputs.extend(["-loop", "1", "-i", final_hook_png_path])
            inputs.extend(["-i", audio_to_encode])
            audio_map_idx = 2

            filter_parts.append(f"[1:v]format=rgba,fade=t=in:st={fade_in_hook:.2f}:d=0.4:alpha=1[hook_faded];")
            filter_parts.append(f"{current_v}[hook_faded]overlay=0:0:enable='gte(t,{fade_in_hook:.2f})'[v_hook];")
            current_v = "[v_hook]"
        else: # Sem cards (chunks de capítulos de vídeo longo)
            inputs.extend(["-i", audio_to_encode])
            audio_map_idx = 1

        filter_parts.append(f"{current_v}ass=filename='{safe_ass}'[vout]")
        filter_complex = "".join(filter_parts)

        cmd = [
            ffmpeg_bin, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", f"{audio_map_idx}:a",
            "-t", f"{total_duration:.2f}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", "60",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-shortest",
            output_video_path
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            app_logger.info(f"[RenderEngine] Vídeo master renderizado com sucesso: {output_video_path} ({os.path.getsize(output_video_path)} bytes)")
            return True, output_video_path
        except subprocess.CalledProcessError as e:
            app_logger.warning(f"[RenderEngine] Falha inicial ao renderizar ({str(e)}). Tentando fallback sem seek aleatório...")
            if "-ss" in inputs:
                try:
                    fallback_inputs = []
                    skip_next = False
                    for item in inputs:
                        if skip_next:
                            skip_next = False
                            continue
                        if item == "-ss":
                            skip_next = True
                            continue
                        fallback_inputs.append(item)
                    fallback_cmd = [
                        ffmpeg_bin, "-y",
                        *fallback_inputs,
                        "-filter_complex", filter_complex,
                        "-map", "[vout]",
                        "-map", f"{audio_map_idx}:a",
                        "-t", f"{total_duration:.2f}",
                        "-c:v", "libx264",
                        "-preset", "ultrafast",
                        "-crf", "18",
                        "-pix_fmt", "yuv420p",
                        "-r", "60",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-ar", "44100",
                        "-shortest",
                        output_video_path
                    ]
                    subprocess.run(fallback_cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    app_logger.info(f"[RenderEngine] Vídeo renderizado com sucesso via fallback seguro: {output_video_path}")
                    return True, output_video_path
                except Exception as fb_err:
                    app_logger.error(f"[RenderEngine] Fallback seguro também falhou: {fb_err}")

            app_logger.error(f"[RenderEngine] Erro no render FFmpeg: {e.stderr}")
            return False, f"Falha na renderização: {e.stderr}"
