import os
import sys
import json
import time
import argparse
from typing import Dict, Any, Optional, List

try:
    from .logger import app_logger, LogSpan
    from .reddit_scraper import fetch_top_high_cpm_stories
    from .reddit_agents import RedditStoryDirectorAgent
    from .reddit_audio import RedditAudioEngine, REDDIT_PERSONA_VOICES
    from .reddit_visuals import RedditVisualEngine
    from .reddit_subtitles import generate_reddit_ass_subtitles
    from .reddit_render import render_reddit_story_video, find_ffmpeg_binary
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_scraper import fetch_top_high_cpm_stories
    from reddit_agents import RedditStoryDirectorAgent
    from reddit_audio import RedditAudioEngine, REDDIT_PERSONA_VOICES
    from reddit_visuals import RedditVisualEngine
    from reddit_subtitles import generate_reddit_ass_subtitles
    from reddit_render import render_reddit_story_video, find_ffmpeg_binary

def run_reddit_story_pipeline(
    custom_post: Optional[Dict[str, Any]] = None,
    output_base_dir: str = "checkpoint/reddit_videos",
    model_name: str = "gemini-flash-lite-latest",
    export_dual_format: bool = True,
    status_callback = None
) -> Dict[str, Any]:
    """
    Executa o pipeline completo de produção de vídeo de histórias do Reddit de Alto CPM:
    1. Obtenção do post real (raspagem ao vivo ou post customizado)
    2. Otimização de roteiro, gancho e persona via Gemini IA
    3. Síntese de voz neural por persona e cálculo de timestamps
    4. Renderização do Card oficial do Reddit
    5. Geração de legendas dinâmicas estilo Hormozi
    6. Renderização de vídeo em 9:16 (Shorts) e 16:9 (Long-form)
    7. Exportação de metadados prontos para publicação
    """
    with LogSpan("run_reddit_story_pipeline"):
        if status_callback:
            status_callback("📡 Buscando histórias virais reais de alto CPM no Reddit...")

        # 1. Obter História Real
        if custom_post:
            story_raw = custom_post
        else:
            candidates = fetch_top_high_cpm_stories(max_stories=5)
            story_raw = candidates[0]

        timestamp_id = int(time.time())
        sub_name = story_raw.get("subreddit", "reddit").replace("r/", "").replace("/", "_")
        video_dir = os.path.join(output_base_dir, f"{sub_name}_{timestamp_id}")
        os.makedirs(video_dir, exist_ok=True)

        app_logger.info(f"[Pipeline] Processando história de {story_raw.get('subreddit')}: '{story_raw.get('title')}'")

        # 2. Otimização do Roteiro via Gemini IA
        if status_callback:
            status_callback(f"🧠 IA estruturando gancho magnético e roteiro para {story_raw.get('subreddit')}...")

        director = RedditStoryDirectorAgent(model_name=model_name)
        script_data = director.optimize_story(story_raw)

        # Salva o script estruturado
        script_file = os.path.join(video_dir, "script_data.json")
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)

        # 3. Síntese de Voz Neural por Persona (Edge-TTS)
        persona = script_data.get("persona", "male_dramatic")
        voice_name = script_data.get("recommended_voice", REDDIT_PERSONA_VOICES.get(persona, "en-US-ChristopherNeural"))
        
        if status_callback:
            status_callback(f"🎙️ Sintetizando narração neural com persona **{persona}** ({voice_name})...")

        audio_engine = RedditAudioEngine(voice=voice_name, rate="+20%")
        audio_shorts_path = os.path.join(video_dir, "narration_shorts.mp3")
        shorts_text = script_data.get("shorts_script", story_raw.get("body", "")[:500])
        
        words_timing_shorts = audio_engine.generate_speech(
            text=shorts_text,
            output_mp3=audio_shorts_path,
            voice_name=voice_name
        )

        # 4. Geração dos Cards Oficiais do Reddit
        if status_callback:
            status_callback("🎨 Desenhando Cards Oficiais do Reddit em alta resolução...")

        visual_engine = RedditVisualEngine()
        card_info = script_data.get("ui_card", {
            "subreddit": story_raw.get("subreddit", "r/maliciouscompliance"),
            "author": story_raw.get("author", "u/RedditUser"),
            "score": story_raw.get("score", "24k"),
            "display_title": script_data.get("title", story_raw.get("title", ""))
        })

        card_9x16_png = os.path.join(video_dir, "reddit_card_9x16.png")
        visual_engine.render_reddit_card(card_info, card_9x16_png, aspect_ratio="9:16")

        card_16x9_png = os.path.join(video_dir, "reddit_card_16x9.png")
        visual_engine.render_reddit_card(card_info, card_16x9_png, aspect_ratio="16:9")

        # 5. Geração de Legendas Dinâmicas Hormozi
        if status_callback:
            status_callback("⚡ Gerando legendas dinâmicas animadas estilo Hormozi...")

        ass_shorts_path = os.path.join(video_dir, "subtitles_shorts.ass")
        generate_reddit_ass_subtitles(words_timing_shorts, ass_shorts_path, aspect_ratio="9:16")

        # 6. Renderização do Vídeo Vertical 9:16 (Shorts / Reels / TikTok)
        if status_callback:
            status_callback("🎬 Renderizando Master Video Vertical 9:16 (1080x1920 @ 60fps)...")

        video_shorts_output = os.path.join(video_dir, "reddit_story_short_9x16.mp4")
        ok_9x16, msg_9x16 = render_reddit_story_video(
            audio_path=audio_shorts_path,
            ass_subtitles_path=ass_shorts_path,
            card_png_path=card_9x16_png,
            output_video_path=video_shorts_output,
            aspect_ratio="9:16",
            status_callback=status_callback
        )

        video_16x9_output = None
        if export_dual_format:
            # 7. Renderização do Vídeo Horizontal 16:9 (Long-form YouTube)
            if status_callback:
                status_callback("🎬 Renderizando Master Video Horizontal 16:9 (1920x1080 @ 60fps)...")

            ass_16x9_path = os.path.join(video_dir, "subtitles_16x9.ass")
            generate_reddit_ass_subtitles(words_timing_shorts, ass_16x9_path, aspect_ratio="16:9")

            video_16x9_output = os.path.join(video_dir, "reddit_story_master_16x9.mp4")
            ok_16x9, msg_16x9 = render_reddit_story_video(
                audio_path=audio_shorts_path,
                ass_subtitles_path=ass_16x9_path,
                card_png_path=card_16x9_png,
                output_video_path=video_16x9_output,
                aspect_ratio="16:9",
                status_callback=status_callback
            )

        # 8. Geração do Arquivo de Metadados para Publicação
        metadata_file = os.path.join(video_dir, "metadata.txt")
        tags_str = " ".join(script_data.get("tags", ["#RedditStories", "#MaliciousCompliance", "#Shorts"]))
        meta_content = f"""TÍTULO DO VÍDEO:
{script_data.get('title', story_raw.get('title', ''))}

DESCRIÇÃO COMPLETA:
{script_data.get('youtube_description', '')}

HASHTAGS / TAGS:
{tags_str}

DETALHES DE PRODUÇÃO:
- Subreddit: {story_raw.get('subreddit')}
- Autor Original: {story_raw.get('author')}
- Upvotes: {story_raw.get('score')}
- Persona Vocal: {persona} ({voice_name})
- Gancho Inicial (3s): {script_data.get('hook_text', '')}
- Exportação 9:16 (Shorts): {video_shorts_output}
- Exportação 16:9 (Long-form): {video_16x9_output}
"""
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write(meta_content)

        if status_callback:
            status_callback("🎉 Produção concluída com sucesso! Todos os masters gerados.")

        return {
            "success": True,
            "video_dir": video_dir,
            "title": script_data.get("title"),
            "video_shorts_9x16": video_shorts_output,
            "video_master_16x9": video_16x9_output,
            "metadata_file": metadata_file,
            "audio_file": audio_shorts_path,
            "persona": persona,
            "voice": voice_name
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reddit Story Channel Video Generator (High CPM)")
    parser.add_argument("--sub", type=str, default="maliciouscompliance", help="Target subreddit")
    parser.add_argument("--model", type=str, default="gemini-flash-lite-latest", help="Gemini model")
    args = parser.parse_args()

    print("🚀 Starting Reddit Story Video Studio Pipeline...")
    res = run_reddit_story_pipeline(model_name=args.model)
    print(f"✅ Video generation finished! Check results in: {res.get('video_dir')}")
