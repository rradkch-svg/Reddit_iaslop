import os
import re
from typing import List, Dict, Any

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

def format_ass_time(seconds: float) -> str:
    """Converte segundos para formato ASS (H:MM:SS.cs)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def format_srt_time(seconds: float) -> str:
    """Converte segundos para formato SRT padrão SubRip (HH:MM:SS,mmm)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def hex_to_ass(hex_code: str) -> str:
    """Converte RRGGBB para BBGGRR (formato de cor do ASS)"""
    h = hex_code.lstrip("#").upper()
    if len(h) == 6:
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"{b}{g}{r}"
    return "00E5FF" # Amarelo neon padrão (FFE500 -> 00E5FF)

def generate_reddit_ass_subtitles(
    words_timing: List[Dict[str, Any]],
    output_ass: str,
    aspect_ratio: str = "9:16",
    primary_color: str = "FFFFFF",
    highlight_color: str = "FFE500", # Amarelo vibrante
    chunk_size: int = 3,
    tail_overhead: float = 0.35
) -> bool:
    """
    Gera legendas dinâmicas no estilo Hormozi / MrBeast com destaque palavra por palavra (Karaoke Pill).
    Adapta automaticamente resolução, tamanho de fonte e margens para 9:16 (1080x1920) e 16:9 (1920x1080).
    """
    with LogSpan("generate_reddit_ass_subtitles", extra={"words_count": len(words_timing), "output": output_ass}):
        is_vertical = (aspect_ratio == "9:16")
        res_x = 1080 if is_vertical else 1920
        res_y = 1920 if is_vertical else 1080
        font_size = 76 if is_vertical else 54
        margin_v = 640 if is_vertical else 140

        ass_primary = hex_to_ass(primary_color)
        ass_highlight = hex_to_ass(highlight_color)
        ass_outline = "000000"

        header = f"""[Script Info]
Title: Reddit Dynamic Hormozi Subtitles
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HormoziDefault,Arial,{font_size},&H00{ass_primary},&H000000FF,&H00{ass_outline},&H80000000,-1,0,0,0,100,100,1,0,1,6,2,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_ass)), exist_ok=True)
            with open(output_ass, "w", encoding="utf-8") as f:
                f.write(header)

                if not words_timing:
                    f.write("Dialogue: 0,0:00:00.00,0:00:05.00,HormoziDefault,,0,0,0,,REDDIT STORY\n")
                    return True

                total_w_count = len(words_timing)
                for i in range(0, total_w_count, chunk_size):
                    chunk = words_timing[i:i+chunk_size]
                    if not chunk:
                        continue

                    for j, active_word_info in enumerate(chunk):
                        global_idx = i + j
                        is_last_word = (global_idx == total_w_count - 1)

                        start_sec = active_word_info.get("start", 0.0)
                        end_sec = active_word_info.get("end", start_sec + 0.3)
                        if is_last_word and tail_overhead > 0:
                            end_sec += tail_overhead

                        start_t = format_ass_time(start_sec)
                        end_t = format_ass_time(end_sec)

                        text_parts = []
                        for k, w_info in enumerate(chunk):
                            w = str(w_info.get("word", "")).upper().strip()
                            if not w:
                                continue
                            if k == j:
                                # Palavra ativa destacada com pill box neon e zoom de impacto 112%
                                text_parts.append(f"{{\\c&H00000000&\\3c&H00{ass_highlight}&\\bord14\\shad0\\fscx112\\fscy112}}{w}{{\\r}}")
                            else:
                                text_parts.append(f"{{\\c&H00{ass_primary}&\\3c&H00{ass_outline}&\\bord6\\shad2}}{w}")

                        line_dialogue = " ".join(text_parts)
                        f.write(f"Dialogue: 0,{start_t},{end_t},HormoziDefault,,0,0,0,,{line_dialogue}\n")

            return True
        except Exception as e:
            app_logger.error(f"[Subtitles] Erro ao gravar arquivo ASS: {str(e)}")
            return False

def generate_reddit_srt_subtitles(
    words_timing: List[Dict[str, Any]],
    output_srt: str,
    time_offset_sec: float = 0.0,
    chunk_size: int = 6,
    append: bool = False,
    start_index: int = 1
) -> int:
    """
    Gera arquivo de legendas no formato SubRip (.srt) agrupadas em frases curtas e legíveis,
    ideais para upload direto no YouTube Studio e indexação imediata de SEO/palavras-chave.
    Retorna o próximo índice numérico para encadeamento de múltiplos capítulos.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_srt)), exist_ok=True)
        mode = "a" if append else "w"
        current_idx = start_index

        with open(output_srt, mode, encoding="utf-8") as f:
            if not words_timing:
                if not append:
                    f.write(f"1\n00:00:00,000 --> 00:00:05,000\nReddit Story\n\n")
                return current_idx + 1

            for i in range(0, len(words_timing), chunk_size):
                chunk = words_timing[i:i + chunk_size]
                if not chunk:
                    continue

                words_text = [str(w.get("word", "")).strip() for w in chunk if str(w.get("word", "")).strip()]
                if not words_text:
                    continue

                start_sec = time_offset_sec + chunk[0].get("start", 0.0)
                end_sec = time_offset_sec + chunk[-1].get("end", start_sec + 0.5)

                start_str = format_srt_time(start_sec)
                end_str = format_srt_time(end_sec)
                phrase = " ".join(words_text)

                f.write(f"{current_idx}\n{start_str} --> {end_str}\n{phrase}\n\n")
                current_idx += 1

        return current_idx
    except Exception as e:
        app_logger.error(f"[Subtitles] Erro ao gravar arquivo SRT: {str(e)}")
        return start_index
