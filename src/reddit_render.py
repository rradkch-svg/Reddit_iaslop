import os
import glob
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

def get_best_orbital_background(aspect_ratio: str = "9:16") -> Optional[str]:
    """Localiza o melhor vídeo de gameplay em assets/backgrounds."""
    is_vertical = (aspect_ratio == "9:16")
    bg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "backgrounds")
    
    candidates = []
    for f in glob.glob(os.path.join(bg_dir, "*.mp4")):
        fn = os.path.basename(f).lower()
        if is_vertical:
            if "vertical" in fn or "p9xlr1bobyw" in fn or "lkx3805bia8" in fn or "xlze_oo4wqs" in fn:
                candidates.append(f)
        else:
            if "horizontal" in fn or "u7ieztmf" in fn or "erilpuq5yms" in fn or "64dw7xvh" in fn:
                candidates.append(f)

    if not candidates:
        candidates = glob.glob(os.path.join(bg_dir, "*.mp4"))

    return candidates[0] if candidates else None

def get_orbital_backgrounds(aspect_ratio: str = "16:9") -> List[str]:
    """Retorna lista de vídeos de gameplay disponíveis em assets/backgrounds."""
    is_vertical = (aspect_ratio == "9:16")
    bg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "backgrounds")
    
    candidates = []
    for f in glob.glob(os.path.join(bg_dir, "*.mp4")):
        fn = os.path.basename(f).lower()
        if is_vertical:
            if "vertical" in fn or "p9xlr1bobyw" in fn or "lkx3805bia8" in fn or "xlze_oo4wqs" in fn:
                candidates.append(f)
        else:
            if "horizontal" in fn or "u7ieztmf" in fn or "erilpuq5yms" in fn or "64dw7xvh" in fn:
                candidates.append(f)

    if not candidates:
        candidates = glob.glob(os.path.join(bg_dir, "*.mp4"))

    return candidates

def render_reddit_story_video(
    audio_path: str,
    ass_subtitles_path: str,
    card_png_path: str,
    output_video_path: str,
    background_video_path: Optional[str] = None,
    aspect_ratio: str = "9:16",
    card_duration_sec: float = 4.8,
    status_callback = None
) -> Tuple[bool, str]:
    """
    Renderiza o vídeo final com fundo de gameplay real em 1080p60fps,
    Card oficial do Reddit em destaque por card_duration_sec e legendas dinâmicas palavra por palavra.
    """
    with LogSpan("render_reddit_story_video", extra={"output": output_video_path, "ratio": aspect_ratio}):
        ffmpeg_bin = find_ffmpeg_binary()
        is_vertical = (aspect_ratio == "9:16")
        target_w = 1080 if is_vertical else 1920
        target_h = 1920 if is_vertical else 1080

        if not os.path.exists(audio_path):
            return False, f"Arquivo de áudio não encontrado: {audio_path}"

        total_duration = get_media_duration(audio_path, ffmpeg_bin) + 0.4
        work_dir = os.path.dirname(output_video_path)
        os.makedirs(work_dir, exist_ok=True)

        bg_to_use = background_video_path or get_best_orbital_background(aspect_ratio=aspect_ratio)
        
        safe_ass = os.path.abspath(ass_subtitles_path).replace("\\", "/").replace(":", "\\:")
        fade_out_st = max(1.0, card_duration_sec - 0.4)

        if status_callback:
            status_callback(f"🎬 Compondo vídeo {aspect_ratio} 60fps com gameplay HD, Card do Reddit e Legendas...")

        if bg_to_use and os.path.exists(bg_to_use):
            bg_input_args = ["-stream_loop", "-1", "-i", bg_to_use]
            filter_complex = (
                f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},setsar=1,fps=60[bg];"
                f"[1:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={fade_out_st:.2f}:d=0.4:alpha=1[card_faded];"
                f"[bg][card_faded]overlay=0:0:enable='between(t,0,{card_duration_sec:.2f})'[v_card];"
                f"[v_card]ass=filename='{safe_ass}'[vout]"
            )
        else:
            src_w = 540 if is_vertical else 960
            src_h = 960 if is_vertical else 540
            bg_input_args = ["-f", "lavfi", "-i", f"testsrc2=size={src_w}x{src_h}:rate=60"]
            filter_complex = (
                f"[0:v]scale={target_w}:{target_h}:flags=bicubic,eq=brightness=-0.32:contrast=1.25:saturation=1.4[bg];"
                f"[1:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={fade_out_st:.2f}:d=0.4:alpha=1[card_faded];"
                f"[bg][card_faded]overlay=0:0:enable='between(t,0,{card_duration_sec:.2f})'[v_card];"
                f"[v_card]ass=filename='{safe_ass}'[vout]"
            )

        cmd = [
            ffmpeg_bin, "-y",
            *bg_input_args,
            "-loop", "1", "-i", card_png_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "2:a",
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
            app_logger.error(f"[RenderEngine] Erro no render FFmpeg: {e.stderr}")
            return False, f"Falha na renderização: {e.stderr}"
