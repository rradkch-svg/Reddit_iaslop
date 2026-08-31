import os
import re
import asyncio
from typing import List, Dict, Any, Tuple, Optional
import edge_tts

try:
    from .logger import app_logger, LogSpan
    from .pronunciation import AutomotivePronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE
    from .agents import resolve_gemini_api_keys
except ImportError:
    from logger import app_logger, LogSpan
    from pronunciation import AutomotivePronunciationEngine, DEFAULT_PRONUNCIATION_ENGINE
    from agents import resolve_gemini_api_keys

FALLBACK_VOICES = [
    "gemini:Charon",
    "gemini:Puck",
    "gemini:Fenrir",
    "gemini:Kore",
    "gemini:Aoede",
    "pt-BR-AntonioNeural"
]

# Estilos e perfis de dinamismo vocal para narração automotiva
VOICE_PROSODY_PRESETS = {
    "DINAMICO_ENERGICO": {
        "rate": "+25%",
        "pitch": "+3Hz",
        "volume": "+0%",
        "description": "Ritmo acelerado 1.25x com entonação enérgica para retenção máxima em Shorts."
    },
    "DOCUMENTARIO_TECNICO": {
        "rate": "+18%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "description": "Cadência firme e analítica para explicações de alta complexidade mecânica."
    },
    "ADRENALINA_VELOZ": {
        "rate": "+30%",
        "pitch": "+5Hz",
        "volume": "+5%",
        "description": "Velocidade máxima e tom vibrante para vídeos de superesportivos e arrancadas."
    }
}

class AudioEngine:
    """
    Motor de Síntese Vocal Neural e Dinâmica com Dicionário Fonético Automotivo.
    Garante pronúncia correta de termos em inglês e marcas estrangeiras via pt-BR Neural TTS,
    enquanto preserva o texto original para as legendas ASS.
    """
    def __init__(
        self,
        voice: str = "gemini:Charon",
        rate: str = "+25%",
        pitch: str = "+3Hz",
        volume: str = "+0%",
        pronunciation_engine: Optional[AutomotivePronunciationEngine] = None
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.fallback_voices = [v for v in FALLBACK_VOICES if v != voice]
        self.pronunciation_engine = pronunciation_engine or DEFAULT_PRONUNCIATION_ENGINE

    def _sanitize_text_for_pacing(self, text: str) -> str:
        """
        Limpa marcações markdown e remove pontuações excessivas (ex: reticências longas,
        travessões e quebras duplas) para eliminar pausas mortas e garantir dinâmica ágil.
        Adiciona micro-pausas rítmicas com vírgulas antes de conjunções explicativas.
        """
        clean = text.replace("**", "").replace("*", "").replace("#", "")
        # Remove reticências longas que provocam pausas artificiais de 1.5s
        clean = re.sub(r"\.{2,}", ".", clean)
        # Substitui travessões por vírgula para manter fluidez
        clean = re.sub(r"\s*—\s*|\s*--\s*", ", ", clean)
        # Normaliza espaços
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def _generate_async_for_voice(
        self,
        text: str,
        output_mp3: str,
        voice_name: str,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # 1. Texto de exibição limpo
        clean_display_text = self._sanitize_text_for_pacing(text)
        
        # 2. Conversão fonética especializada para o TTS pronunciar termos em inglês perfeitamente
        phonetic_tts_text = self.pronunciation_engine.phoneticize(clean_display_text)
        
        rate_to_use = rate if rate is not None else self.rate
        pitch_to_use = pitch if pitch is not None else self.pitch
        volume_to_use = volume if volume is not None else self.volume

        app_logger.info(
            f"[AudioEngine] Síntese: Voz={voice_name} | Rate={rate_to_use} | Pitch={pitch_to_use} | "
            f"Display='{clean_display_text[:60]}...' | Fonético='{phonetic_tts_text[:60]}...'"
        )

        # Suporte a Motor Generativo Google Gemini TTS (Voz Padrão: Charon)
        if voice_name.startswith("gemini:"):
            from google import genai
            from google.genai import types
            import wave, subprocess

            g_voice = voice_name.split(":")[1]
            instruction = (
                f"Você é um narrador profissional de documentários automotivos de prestígio internacional (estilo BBC Top Gear). "
                f"Leia o seguinte texto em português com voz imponente, autoridade técnica, pausas dramáticas de respiração e dicção perfeita, sem alterar as palavras:\n\n{clean_display_text}"
            )

            keys = resolve_gemini_api_keys()
            raw_pcm = None
            last_err = None

            for attempt in range(4):
                for k_idx, key in enumerate(keys):
                    try:
                        client = genai.Client(api_key=key)
                        response = client.models.generate_content(
                            model="gemini-2.5-flash-preview-tts",
                            contents=instruction,
                            config=types.GenerateContentConfig(
                                response_modalities=["AUDIO"],
                                speech_config=types.SpeechConfig(
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=g_voice)
                                    )
                                )
                            )
                        )
                        raw_pcm = response.candidates[0].content.parts[0].inline_data.data
                        break
                    except Exception as e:
                        err_str = str(e)
                        last_err = e
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            app_logger.warning(f"[AudioEngine] Cota na chave #{k_idx+1}. Tentando próxima chave...")
                            continue
                        else:
                            raise e
                if raw_pcm:
                    break
                app_logger.info("[AudioEngine] Todas as chaves em cooldown. Aguardando 20s para liberação de cota do Gemini TTS...")
                await asyncio.sleep(20)

            if not raw_pcm:
                raise last_err or Exception("Falha em todas as chaves e tentativas de síntese do Gemini TTS.")

            temp_wav = output_mp3.replace(".mp3", "_temp.wav")
            with wave.open(temp_wav, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(raw_pcm)

            # Converte taxa percentual para fator de aceleração atempo (ex: "+25%" -> 1.25)
            tempo_factor = 1.25
            if rate_to_use:
                try:
                    num_pct = float(rate_to_use.replace("%", "").replace("+", ""))
                    tempo_factor = max(0.5, min(2.0, 1.0 + (num_pct / 100.0)))
                except:
                    tempo_factor = 1.25

            cmd = ["ffmpeg", "-y", "-i", temp_wav]
            if abs(tempo_factor - 1.0) > 0.01:
                cmd.extend(["-filter:a", f"atempo={tempo_factor:.3f}"])
            cmd.extend(["-codec:a", "libmp3lame", "-b:a", "192k", output_mp3])

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except:
                    pass

            raw_words = clean_display_text.split()
            raw_duration = len(raw_pcm) / (24000 * 2)
            total_duration = raw_duration / tempo_factor
            total_chars = max(1, sum(len(w) for w in raw_words))
            words_timing = []
            curr = 0.0
            for w in raw_words:
                dur = (len(w) / total_chars) * total_duration
                words_timing.append({"word": w, "start": round(curr, 3), "end": round(curr + dur, 3)})
                curr += dur
            return words_timing

        # Suporte a Motor Neural Local Piper VITS ONNX
        if voice_name.startswith("piper:"):
            import piper, wave, subprocess

            m_name = voice_name.split(":")[1]
            m_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tts_models", "piper", f"{m_name}.onnx")
            if not os.path.exists(m_path):
                raise FileNotFoundError(f"Modelo Piper não encontrado em: {m_path}")
            p_voice = piper.PiperVoice.load(m_path)
            temp_wav = output_mp3.replace(".mp3", "_temp.wav")
            with wave.open(temp_wav, "wb") as wf:
                p_voice.synthesize_wav(clean_display_text, wf)

            cmd = ["ffmpeg", "-y", "-i", temp_wav, "-codec:a", "libmp3lame", "-b:a", "192k", output_mp3]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except:
                    pass

            raw_words = clean_display_text.split()
            words_timing = []
            curr = 0.0
            for w in raw_words:
                dur = max(len(w) * 0.045, 0.20)
                words_timing.append({"word": w, "start": round(curr, 3), "end": round(curr + dur, 3)})
                curr += dur
            return words_timing

        communicate = edge_tts.Communicate(
            phonetic_tts_text,
            voice_name,
            rate=rate_to_use,
            pitch=pitch_to_use,
            volume=volume_to_use
        )
        
        sentence_boundaries = []
        word_boundaries = []
        raw_audio = bytearray()
        
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                raw_audio.extend(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                start_sec = chunk["offset"] / 10_000_000.0
                duration_sec = chunk["duration"] / 10_000_000.0
                sentence_boundaries.append({
                    "text": chunk["text"],
                    "start": start_sec,
                    "end": start_sec + duration_sec,
                    "duration": duration_sec
                })
            elif chunk["type"] == "WordBoundary":
                start_sec = chunk["offset"] / 10_000_000.0
                duration_sec = chunk["duration"] / 10_000_000.0
                word_boundaries.append({
                    "word": chunk["text"],
                    "start": start_sec,
                    "end": start_sec + duration_sec
                })

        if not raw_audio:
            raise Exception(f"Nenhum byte de áudio retornado pelo serviço Edge-TTS para a voz {voice_name}")

        with open(output_mp3, "wb") as f:
            f.write(raw_audio)

        # 3. Alinhar os timestamps de volta para o texto de exibição original
        # Isso garante que a legenda na tela use a ortografia limpa original ("TWIN TURBO", "PORSCHE GT3 RS")
        if word_boundaries:
            aligned_words = self.pronunciation_engine.align_phonetic_timing_to_original(
                clean_display_text,
                word_boundaries
            )
            return aligned_words
        
        if sentence_boundaries:
            words_timing = []
            for sent in sentence_boundaries:
                s_text = sent["text"]
                s_start = sent["start"]
                s_duration = sent["duration"]
                raw_words = s_text.split()
                if not raw_words:
                    continue

                weights = []
                for w in raw_words:
                    w_len = len(w)
                    if w.endswith((".", "!", "?", ",", ";", ":")):
                        w_len += 2
                    weights.append(max(w_len, 1))

                total_weight = sum(weights)
                current_time = s_start

                for w, weight in zip(raw_words, weights):
                    w_dur = (weight / total_weight) * s_duration
                    w_start = current_time
                    w_end = min(current_time + w_dur, sent["end"])
                    words_timing.append({
                        "word": w.strip(),
                        "start": round(w_start, 3),
                        "end": round(w_end, 3)
                    })
                    current_time = w_end
            
            return self.pronunciation_engine.align_phonetic_timing_to_original(
                clean_display_text,
                words_timing
            )

        # Fallback de contagem de palavras original
        raw_words = clean_display_text.split()
        words_timing = []
        curr = 0.0
        for w in raw_words:
            dur = max(len(w) * 0.045, 0.20)
            words_timing.append({
                "word": w.strip(),
                "start": round(curr, 3),
                "end": round(curr + dur, 3)
            })
            curr += dur
        return words_timing

    def generate_audio(
        self,
        text: str,
        output_mp3: str,
        output_vtt: str = "",
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        volume: Optional[str] = None
    ) -> Tuple[bool, Any]:
        """
        Gera áudio MP3 com redundância e failover de vozes em caso de queda do servidor,
        aplicando a taxa de aceleração configurada (padrão +25% / 1.25x) e pronúncia fonética.
        """
        voices_to_try = [self.voice] + self.fallback_voices
        rate_to_use = rate if rate is not None else self.rate
        pitch_to_use = pitch if pitch is not None else self.pitch
        volume_to_use = volume if volume is not None else self.volume
        
        with LogSpan("AudioEngine.generate_audio", extra={"text_len": len(text), "output": output_mp3, "rate": rate_to_use}):
            for v_name in voices_to_try:
                try:
                    app_logger.info(f"[AudioEngine] Tentando síntese com a voz: {v_name} (taxa: {rate_to_use}, pitch: {pitch_to_use})")
                    words_timing = asyncio.run(
                        self._generate_async_for_voice(
                            text,
                            output_mp3,
                            v_name,
                            rate=rate_to_use,
                            pitch=pitch_to_use,
                            volume=volume_to_use
                        )
                    )
                    app_logger.info(
                        f"[AudioEngine] Síntese concluída com sucesso usando {v_name} "
                        f"({len(words_timing)} palavras alinhadas, taxa {rate_to_use})."
                    )
                    return True, words_timing
                except Exception as e:
                    app_logger.warning(f"[AudioEngine] Falha na voz {v_name}: {str(e)}. Tentando próxima voz de fallback...")
            
            err_msg = f"Todas as vozes de TTS ({voices_to_try}) falharam."
            app_logger.error(err_msg)
            return False, err_msg
