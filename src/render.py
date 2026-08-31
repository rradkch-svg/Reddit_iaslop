import os
import subprocess
import glob
from typing import List, Tuple

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

def find_ffmpeg_binary() -> str:
    """Busca o executável do FFmpeg em múltiplos locais conhecidos no Windows/PATH."""
    winget_pattern = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe")
    winget_matches = glob.glob(winget_pattern)
    if winget_matches and os.path.exists(winget_matches[0]):
        return winget_matches[0]
    return "ffmpeg"

def assemble_multi_scene_video(
    clip_paths: List[str],
    audio_path: str,
    ass_path: str,
    output_path: str,
    status_callback = None
) -> Tuple[bool, str]:
    """
    Concatena múltiplos clipes 9:16 (1080x1920), funde com a narração de áudio
    e queima as legendas dinâmicas com caixa de destaque (Hormozi style).
    """
    with LogSpan("assemble_multi_scene_video", extra={"clips_count": len(clip_paths), "output": output_path}):
        ffmpeg_bin = find_ffmpeg_binary()
        
        if not clip_paths:
            return False, "Nenhum clipe de vídeo fornecido para montagem."
            
        valid_clips = [cp for cp in clip_paths if os.path.exists(cp) and os.path.getsize(cp) > 0]
        if not valid_clips:
            return False, "Nenhum dos arquivos de clipe existe no disco."

        work_dir = os.path.dirname(output_path)
        concat_txt = os.path.join(work_dir, "scenes_concat.txt")
        combined_scenes_mp4 = os.path.join(work_dir, "combined_scenes.mp4")

        # 1. Gerar arquivo de lista para concatenação segura
        with open(concat_txt, "w", encoding="utf-8") as f:
            for cp in valid_clips:
                safe_cp = os.path.abspath(cp).replace("\\", "/")
                f.write(f"file '{safe_cp}'\n")

        if status_callback:
            status_callback("⚡ Concatenando trilha de cenas (B-rolls e Cards Visuais)...")

        # 2. Concatenação de vídeo 1080x1920 60fps com escala Lanczos e preservação de áudio das cenas
        cmd_concat = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,crop=1080:1920,setsar=1,fps=60",
            "-c:v", "libx264",
            "-crf", "16",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", "60",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            combined_scenes_mp4
        ]

        try:
            subprocess.run(cmd_concat, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            app_logger.info(f"[RenderEngine] Cenas unificadas em 60fps: {combined_scenes_mp4}")
        except subprocess.CalledProcessError as e:
            app_logger.error(f"[RenderEngine] Falha na concatenação de cenas: {e.stderr}")
            return False, f"Falha na união de cenas: {e.stderr}"

        # 3. Composição Final 1080p60fps com Áudio Mixado (Sidechain Ducking no som do motor) e Legendas ASS Queimadas
        safe_ass_path = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        
        if status_callback:
            status_callback("🎨 Queimando legendas dinâmicas com Pill Box e mixando som do motor com narração em 1080p60fps...")

        # Filtro de mixagem: Narração a 100% de volume com sidechain ducking no som do motor (ronco)
        fc_filter = (
            f"[0:v]ass=filename='{safe_ass_path}'[vout];"
            f"[1:a]asplit=2[v_main][v_sc];"
            f"[0:a]volume=0.35[bg_raw];"
            f"[bg_raw][v_sc]sidechaincompress=threshold=0.08:ratio=4:attack=50:release=300[bg_ducked];"
            f"[bg_ducked][v_main]amix=inputs=2:duration=first:dropout_transition=0.5[aout]"
        )

        cmd_final = [
            ffmpeg_bin, "-y",
            "-i", combined_scenes_mp4,
            "-i", audio_path,
            "-filter_complex", fc_filter,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-crf", "16",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", "60",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]

        try:
            subprocess.run(cmd_final, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            app_logger.info(f"[RenderEngine] Vídeo final 1080p60fps renderizado com sucesso: {output_path} ({os.path.getsize(output_path)} bytes)")
            return True, "Vídeo 9:16 final 1080p60fps renderizado com sucesso!"
        except subprocess.CalledProcessError as e:
            app_logger.warning(f"[RenderEngine] Falha no filtro combinado ASS+Ducking: {e.stderr}. Tentando fallback sem legendas queimadas...")
            
            # Fallback de contingência sem filtro ASS mas mantendo mixagem com ducking
            fc_fallback = (
                f"[1:a]asplit=2[v_main][v_sc];"
                f"[0:a]volume=0.35[bg_raw];"
                f"[bg_raw][v_sc]sidechaincompress=threshold=0.08:ratio=4:attack=50:release=300[bg_ducked];"
                f"[bg_ducked][v_main]amix=inputs=2:duration=first:dropout_transition=0.5[aout]"
            )
            cmd_fallback = [
                ffmpeg_bin, "-y",
                "-i", combined_scenes_mp4,
                "-i", audio_path,
                "-filter_complex", fc_fallback,
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", "60",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path
            ]
            try:
                subprocess.run(cmd_fallback, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                app_logger.info(f"[RenderEngine] Vídeo final (modo de contingência com áudio mixado 60fps) renderizado: {output_path}")
                return True, "Vídeo renderizado com sucesso (modo de contingência sem legendas queimadas)!"
            except subprocess.CalledProcessError as e2:
                app_logger.warning(f"[RenderEngine] Falha no fallback com ducking: {e2.stderr}. Tentando fallback estrito de áudio único...")
                # Fallback final com apenas narração
                cmd_single_audio = [
                    ffmpeg_bin, "-y",
                    "-i", combined_scenes_mp4,
                    "-i", audio_path,
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    "-r", "60",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    output_path
                ]
                try:
                    subprocess.run(cmd_single_audio, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    app_logger.info(f"[RenderEngine] Vídeo final (modo estrito áudio único 60fps) renderizado: {output_path}")
                    return True, "Vídeo renderizado com sucesso (áudio de contingência)!"
                except subprocess.CalledProcessError as e3:
                    err_msg = f"Erro crítico no FFmpeg: {e3.stderr}"
                    app_logger.error(err_msg)
                    return False, err_msg

# Alias para retrocompatibilidade
render_final_video = assemble_multi_scene_video
