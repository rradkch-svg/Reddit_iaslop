import os
import sys
import math
import struct
import wave
import subprocess
from typing import Optional, List, Tuple

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def generate_procedural_bell_plim(output_wav: str, sample_rate: int = 44100, duration: float = 0.75):
    """
    Gera um som procedural de sino cristalino ('Plim') com harmônicos metálicos e decaimento exponencial suave.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
    num_samples = int(sample_rate * duration)
    
    # Frequências fundamentais do chime de sino (F#6 / D#7 / A#7 shimmer)
    f0 = 1864.66 # A#6
    f1 = 2793.83 # F7 (quinta harmônica)
    f2 = 3729.31 # A#7
    f3 = 5587.65 # F8 (brilho aéreo)

    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        # Envelope de ataque imediato (1ms) e decaimento exponencial
        attack = min(1.0, t / 0.002)
        decay = math.exp(-6.5 * t)
        env = attack * decay
        
        # Síntese aditiva de parciais de sino
        s = (
            0.55 * math.sin(2 * math.pi * f0 * t) +
            0.28 * math.sin(2 * math.pi * f1 * t) +
            0.12 * math.sin(2 * math.pi * f2 * t) +
            0.05 * math.sin(2 * math.pi * f3 * t)
        ) * env
        
        # Soft clipping
        val = max(-0.95, min(0.95, s))
        int_val = int(val * 32767.0)
        # Stereo 16-bit
        samples.append(struct.pack('<hh', int_val, int_val))

    with wave.open(output_wav, 'wb') as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b''.join(samples))

    return output_wav

def generate_procedural_whoosh(output_wav: str, sample_rate: int = 44100, duration: float = 0.55):
    """
    Gera um som procedural de transição de ar ('Whoosh') com modulação de frequência e filtro passa-banda simulado.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
    num_samples = int(sample_rate * duration)

    import random
    rng = random.Random(42) # Determinístico

    raw_noise = [rng.uniform(-1.0, 1.0) for _ in range(num_samples)]
    
    # Filtro suave passa-faixa com varredura de frequência (150Hz -> 1800Hz -> 200Hz)
    samples = []
    prev_out = 0.0
    prev_in = 0.0

    for i in range(num_samples):
        t = i / sample_rate
        norm_t = t / duration # 0.0 a 1.0
        
        # Envelope de curva sino suave
        env = math.sin(math.pi * norm_t) ** 2.2
        
        # Frequência central do whoosh
        cutoff = 200.0 + 1600.0 * math.sin(math.pi * norm_t)
        rc = 1.0 / (2.0 * math.pi * cutoff)
        dt = 1.0 / sample_rate
        alpha = dt / (rc + dt)
        
        # Filtro passa-baixa dinâmico
        curr_in = raw_noise[i]
        curr_out = prev_out + alpha * (curr_in - prev_out)
        prev_out = curr_out
        
        # Sub-graves harmônicos adicionais para peso cinematográfico
        sub_tone = 0.35 * math.sin(2 * math.pi * (120.0 + 80.0 * norm_t) * t)
        
        val = (curr_out * 0.75 + sub_tone) * env * 0.90
        val = max(-0.95, min(0.95, val))
        int_val = int(val * 32767.0)
        
        # Stereo com leve efeito de varredura estéreo (esquerda para direita)
        pan_left = 1.0 - 0.5 * norm_t
        pan_right = 0.5 + 0.5 * norm_t
        int_left = int(int_val * pan_left)
        int_right = int(int_val * pan_right)
        samples.append(struct.pack('<hh', int_left, int_right))

    with wave.open(output_wav, 'wb') as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b''.join(samples))

    return output_wav

def ensure_sfx_assets() -> Tuple[str, str]:
    """Garante a existência dos arquivos de SFX em assets/sfx/."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sfx_dir = os.path.join(base_dir, "assets", "sfx")
    os.makedirs(sfx_dir, exist_ok=True)
    
    plim_path = os.path.join(sfx_dir, "bell_plim.wav")
    whoosh_path = os.path.join(sfx_dir, "whoosh.wav")

    if not os.path.exists(plim_path) or os.path.getsize(plim_path) < 1000:
        generate_procedural_bell_plim(plim_path)

    if not os.path.exists(whoosh_path) or os.path.getsize(whoosh_path) < 1000:
        generate_procedural_whoosh(whoosh_path)

    return plim_path, whoosh_path

def mix_sfx_to_audio(
    main_audio_path: str,
    output_audio_path: str,
    video_type: str = "shorts", # "shorts", "teaser", "longform", "chunk"
    total_duration_sec: float = 60.0,
    card_duration_sec: float = 4.8,
    final_hook_duration_sec: float = 5.0,
    ffmpeg_bin: Optional[str] = None
) -> str:
    """
    Mixa os efeitos sonoros (SFX) na trilha de áudio com sincronização exata:
    - shorts: Plim no início (0.0s) + Whoosh na saída do card (~4.4s)
    - teaser: Plim no início (0.0s) + Whoosh na saída (~4.4s) + Plim na entrada do hook final
    - longform: Whoosh na entrada do card (0.0s) + Whoosh na saída do card (~4.4s)
    - chunk: Sem SFX de card (áudio limpo)
    """
    if video_type == "chunk" or card_duration_sec <= 0:
        return main_audio_path

    if ffmpeg_bin is None:
        try:
            from .reddit_render import find_ffmpeg_binary
            ffmpeg_bin = find_ffmpeg_binary()
        except Exception:
            try:
                from reddit_render import find_ffmpeg_binary
                ffmpeg_bin = find_ffmpeg_binary()
            except Exception:
                ffmpeg_bin = "ffmpeg"

    plim_wav, whoosh_wav = ensure_sfx_assets()
    card_out_delay_ms = int(max(0.0, card_duration_sec - 0.4) * 1000)
    os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)

    if output_audio_path.endswith(".mp3"):
        codec_args = ["-c:a", "libmp3lame", "-b:a", "192k"]
    elif output_audio_path.endswith(".wav"):
        codec_args = ["-c:a", "pcm_s16le"]
    else:
        codec_args = ["-c:a", "aac", "-b:a", "192k"]

    if video_type == "teaser":
        hook_delay_ms = int(max(0.0, max(card_duration_sec, total_duration_sec - final_hook_duration_sec)) * 1000)
        filter_complex = (
            f"[1:a]volume=0.35,adelay=0|0[sfx_in];"
            f"[2:a]volume=0.32,adelay={card_out_delay_ms}|{card_out_delay_ms}[sfx_out];"
            f"[3:a]volume=0.38,adelay={hook_delay_ms}|{hook_delay_ms}[sfx_hook];"
            f"[0:a][sfx_in][sfx_out][sfx_hook]amix=inputs=4:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        cmd = [
            ffmpeg_bin, "-y",
            "-i", main_audio_path,
            "-i", plim_wav,
            "-i", whoosh_wav,
            "-i", plim_wav,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            *codec_args,
            "-ar", "44100",
            output_audio_path
        ]
    elif video_type == "longform":
        filter_complex = (
            f"[1:a]volume=0.30,adelay=0|0[sfx_in];"
            f"[2:a]volume=0.32,adelay={card_out_delay_ms}|{card_out_delay_ms}[sfx_out];"
            f"[0:a][sfx_in][sfx_out]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        cmd = [
            ffmpeg_bin, "-y",
            "-i", main_audio_path,
            "-i", whoosh_wav,
            "-i", whoosh_wav,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            *codec_args,
            "-ar", "44100",
            output_audio_path
        ]
    else: # shorts
        filter_complex = (
            f"[1:a]volume=0.35,adelay=0|0[sfx_in];"
            f"[2:a]volume=0.32,adelay={card_out_delay_ms}|{card_out_delay_ms}[sfx_out];"
            f"[0:a][sfx_in][sfx_out]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        cmd = [
            ffmpeg_bin, "-y",
            "-i", main_audio_path,
            "-i", plim_wav,
            "-i", whoosh_wav,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            *codec_args,
            "-ar", "44100",
            output_audio_path
        ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_audio_path
    except Exception:
        return main_audio_path

if __name__ == "__main__":
    p, w = ensure_sfx_assets()
    print(f"✅ SFX assets prontos: Plim={p} ({os.path.getsize(p)}b), Whoosh={w} ({os.path.getsize(w)}b)")
