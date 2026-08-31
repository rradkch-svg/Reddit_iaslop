import os
import re
import asyncio
from typing import List, Dict, Any, Tuple, Optional
import edge_tts

try:
    from .logger import app_logger, LogSpan
except ImportError:
    from logger import app_logger, LogSpan

REDDIT_PERSONA_VOICES = {
    "male_dramatic": "en-US-ChristopherNeural",
    "male_casual": "en-US-GuyNeural",
    "female_expressive": "en-US-JennyNeural",
    "female_calm": "en-US-AvaNeural",
    "young_fast": "en-US-EricNeural"
}

class RedditAudioEngine:
    """
    Motor de Síntese Vocal de Alta Retenção para Histórias do Reddit (Edge-TTS Neural).
    Suporta seleção dinâmica de personas por gênero/tom e cálculo milimétrico de timestamps para legendas.
    """
    def __init__(
        self,
        voice: str = "en-US-ChristopherNeural",
        rate: str = "+20%",
        pitch: str = "+0Hz",
        volume: str = "+0%"
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume

    def sanitize_narration_text(self, text: str) -> str:
        """Limpa símbolos desnecessários para uma locução contínua e dinâmica."""
        clean = text.replace("**", "").replace("*", "").replace("#", "").replace('"', "")
        clean = re.sub(r"\.{2,}", ".", clean)
        clean = re.sub(r"\s*—\s*|\s*--\s*", ", ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def generate_speech_async(
        self,
        text: str,
        output_mp3: str,
        voice_name: Optional[str] = None,
        rate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        voice_to_use = voice_name or self.voice
        rate_to_use = rate or self.rate
        clean_text = self.sanitize_narration_text(text)

        app_logger.info(f"[RedditAudioEngine] Sintetizando áudio | Voz={voice_to_use} | Rate={rate_to_use} | Texto='{clean_text[:60]}...'")

        communicate = edge_tts.Communicate(
            clean_text,
            voice_to_use,
            rate=rate_to_use,
            pitch=self.pitch,
            volume=self.volume
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
            raise Exception(f"Nenhum áudio retornado pelo Edge-TTS para {voice_to_use}")

        os.makedirs(os.path.dirname(os.path.abspath(output_mp3)), exist_ok=True)
        with open(output_mp3, "wb") as f:
            f.write(raw_audio)

        if word_boundaries:
            return word_boundaries

        # Converte sentence boundaries em word timings proporcionais
        words_timing = []
        if sentence_boundaries:
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
                    current_time += w_dur
        else:
            raw_words = clean_text.split()
            current_time = 0.0
            for w in raw_words:
                dur = max(0.22, len(w) * 0.045)
                words_timing.append({
                    "word": w,
                    "start": round(current_time, 3),
                    "end": round(current_time + dur, 3)
                })
                current_time += dur

        return words_timing

    def generate_speech(
        self,
        text: str,
        output_mp3: str,
        voice_name: Optional[str] = None,
        rate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return asyncio.run(self.generate_speech_async(text, output_mp3, voice_name, rate))
