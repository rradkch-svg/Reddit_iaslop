import re
import os
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

def hex_to_ass(hex_code: str) -> str:
    """Converte RRGGBB para BBGGRR (formato de cor do ASS)"""
    h = hex_code.lstrip("#").upper()
    if len(h) == 6:
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"{b}{g}{r}"
    return "00E5FF" # Amarelo neon padrão (FFE500 -> 00E5FF)

def convert_words_to_ass(
    words_timing: List[Dict[str, Any]],
    output_ass: str,
    primary_color: str = "FFFFFF",
    highlight_color: str = "FFE500",
    outline_color: str = "000000",
    chunk_size: int = 3,
    tail_overhead: float = 0.4
) -> bool:
    """
    Gera um arquivo ASS (Advanced SubStation Alpha) com efeito de destaque dinâmico
    palavra por palavra com CAIXA DE DESTAQUE COLORIDA (Pill / Badge Estilo Hormozi)
    para vídeo vertical 9:16 (1080x1920).
    Estende a última legenda pelo tempo de tail_overhead para respiro e leitura confortável.
    """
    with LogSpan("convert_words_to_ass", extra={"words_count": len(words_timing), "output": output_ass}):
        ass_primary = hex_to_ass(primary_color)
        ass_highlight = hex_to_ass(highlight_color)
        ass_outline = hex_to_ass(outline_color)

        # 1080x1920 layout vertical: Posição no terço inferior (Alignment=2, MarginV=620)
        header = f"""[Script Info]
Title: Dynamic Karaoke Hormozi Pill Box
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HormoziDefault,Arial,78,&H00{ass_primary},&H000000FF,&H00{ass_outline},&H80000000,-1,0,0,0,100,100,1,0,1,6,2,2,40,40,620,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        try:
            with open(output_ass, "w", encoding="utf-8") as f:
                f.write(header)
                
                if not words_timing:
                    app_logger.warning("[Subtitles] words_timing vazio! Gerando legenda padrão de fallback...")
                    f.write("Dialogue: 0,0:00:00.00,0:00:10.00,HormoziDefault,,0,0,0,,CURIOSIDADE AUTOMOTIVA\n")
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
                        end_sec = active_word_info.get("end", 1.0)
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
                                # Palavra ativa com Caixa Colorida (Pill):
                                # \c&H00000000& (texto preto) + \3c&H00{ass_highlight}& (borda neon grossa formando caixa) + \bord14 + zoom 112%
                                text_parts.append(f"{{\\c&H00000000&\\3c&H00{ass_highlight}&\\bord14\\shad0\\fscx112\\fscy112}}{w}{{\\r}}")
                            else:
                                # Palavra inativa: texto branco com contorno preto
                                text_parts.append(f"{{\\c&H00{ass_primary}&\\3c&H00{ass_outline}&\\bord6}}{w}{{\\r}}")

                        dialogue_text = " ".join(text_parts)
                        f.write(f"Dialogue: 0,{start_t},{end_t},HormoziDefault,,0,0,0,,{dialogue_text}\n")
            
            app_logger.info(f"[Subtitles] Legenda com Pill Box gravada com sucesso: {output_ass}")
            return True
        except Exception as e:
            app_logger.error(f"[Subtitles] Erro ao gravar legenda ASS: {str(e)}")
            return False

convert_vtt_to_ass = convert_words_to_ass
