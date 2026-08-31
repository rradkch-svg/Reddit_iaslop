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
    """Retorna a duração exata do arquivo em segundos."""
    ff = ffmpeg_bin or find_ffmpeg_binary()
    ffprobe = ff.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in ff else "ffprobe"
    
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        return float(res.stdout.strip())
    except Exception:
        return 45.0

def render_reddit_story_video(
    audio_path: str,
    ass_subtitles_path: str,
    card_png_path: str,
    output_video_path: str,
    background_video_path: Optional[str] = None,
    aspect_ratio: str = "9:16",
    card_duration_sec: float = 3.8,
    status_callback = None
) -> Tuple[bool, str]:
    """
    Renderiza o vídeo final completo em passo único de altíssima performance:
    - Fundo dinâmico 60fps (gameplay customizado ou lavfi sintético de alto dinamismo);
    - Sobreposição do Card oficial do Reddit nos primeiros 3.8s com transição fade suave;
    - Queima de legendas animadas palavra por palavra (Pill Box Hormozi);
    - Áudio neural integrado.
    """
    with LogSpan("render_reddit_story_video", extra={"output": output_video_path, "ratio": aspect_ratio}):
        ffmpeg_bin = find_ffmpeg_binary()
        is_vertical = (aspect_ratio == "9:16")
        target_w = 1080 if is_vertical else 1920
        target_h = 1920 if is_vertical else 1080
        src_w = 540 if is_vertical else 960
        src_h = 960 if is_vertical else 540

        if not os.path.exists(audio_path):
            return False, f"Arquivo de áudio não encontrado: {audio_path}"

        work_dir = os.path.dirname(output_video_path)
        os.makedirs(work_dir, exist_ok=True)

        safe_ass = os.path.abspath(ass_subtitles_path).replace("\\", "/").replace(":", "\\:")
        fade_out_st = max(1.0, card_duration_sec - 0.4)

        if status_callback:
            status_callback(f"🎬 Renderizando Master Video {aspect_ratio} 60fps com Card do Reddit e Legendas Hormozi...")

        # Monta pipeline single-pass
        if background_video_path and os.path.exists(background_video_path):
            bg_input_args = ["-stream_loop", "-1", "-i", background_video_path]
            filter_complex = (
                f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},setsar=1,fps=60[bg];"
                f"[1:v]format=rgba,fade=t=in:st=0:d=0.25:alpha=1,fade=t=out:st={fade_out_st:.2f}:d=0.35:alpha=1[card_faded];"
                f"[bg][card_faded]overlay=0:0:enable='between(t,0,{card_duration_sec:.2f})'[v_card];"
                f"[v_card]ass=filename='{safe_ass}'[vout]"
            )
        else:
            bg_input_args = ["-f", "lavfi", "-i", f"testsrc2=size={src_w}x{src_h}:rate=60"]
            filter_complex = (
                f"[0:v]scale={target_w}:{target_h}:flags=bicubic,eq=brightness=-0.32:contrast=1.25:saturation=1.4[bg];"
                f"[1:v]format=rgba,fade=t=in:st=0:d=0.25:alpha=1,fade=t=out:st={fade_out_st:.2f}:d=0.35:alpha=1[card_faded];"
                f"[bg][card_faded]overlay=0:0:enable='between(t,0,{card_duration_sec:.2f})'[v_card];"
                f"[v_card]ass=filename='{safe_ass}'[vout]"
            )

        cmd = [
            ffmpeg_bin, "-y",
            *bg_input_args,
            "-i", card_png_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "2:a",
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
