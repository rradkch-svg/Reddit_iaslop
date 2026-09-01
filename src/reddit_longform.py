import os
import sys
import json
import time
import glob
import subprocess
from typing import List, Dict, Any, Tuple, Optional

try:
    from .logger import app_logger, LogSpan
    from .reddit_scraper import fetch_top_high_cpm_stories
    from .reddit_agents import RedditStoryDirectorAgent, PERSONA_VOICE_MAP
    from .reddit_audio import RedditAudioEngine
    from .reddit_visuals import RedditVisualEngine
    from .reddit_subtitles import generate_reddit_ass_subtitles
    from .reddit_render import render_reddit_story_video, find_ffmpeg_binary, get_media_duration, get_orbital_backgrounds
    from .batch_manager import BatchManager
    from .checkpoint_manager import DEFAULT_CHECKPOINT_MANAGER
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_scraper import fetch_top_high_cpm_stories
    from reddit_agents import RedditStoryDirectorAgent, PERSONA_VOICE_MAP
    from reddit_audio import RedditAudioEngine
    from reddit_visuals import RedditVisualEngine
    from reddit_subtitles import generate_reddit_ass_subtitles
    from reddit_render import render_reddit_story_video, find_ffmpeg_binary, get_media_duration, get_orbital_backgrounds
    from batch_manager import BatchManager
    from checkpoint_manager import DEFAULT_CHECKPOINT_MANAGER


def generate_25min_single_story_video(
    target_subreddit: Optional[str] = None,
    custom_post: Optional[Dict[str, Any]] = None,
    target_duration_minutes: float = 25.0,
    output_base_dir: str = "checkpoint/auto_batches",
    custom_output_dir: Optional[str] = None,
    aspect_ratio: str = "16:9",
    status_callback = None
) -> Dict[str, Any]:
    """
    Gera um vídeo longo de 25 MINUTOS (1500+ segundos) de UMA HISTÓRIA ÚNICA (não um compilado de histórias diferentes).
    
    Estrutura:
    1. Expande uma história real de alto impacto em uma narrativa profunda de 8 capítulos da MESMA história;
    2. Locução neural consistente com a persona da história;
    3. Cards Oficiais do Reddit com numeração de Partes/Capítulos no início de cada capítulo (4.8s);
    4. Gameplay 1080p 60fps HD sem copyright do canal @OrbitalNCG;
    5. Legendas dinâmicas estilo Hormozi palavra por palavra;
    6. Concatenação perfeita dos capítulos em master 25min sem limite de memória;
    7. Metadados e Timestamps oficiais salvos no padrão oficial batch_1/video_0...
    """
    with LogSpan("generate_25min_single_story_video", extra={"target_min": target_duration_minutes}):
        ffmpeg_bin = find_ffmpeg_binary()
        
        # 1. Obter a história única a ser desenvolvida
        if custom_post:
            story_raw = custom_post
        else:
            subs = [target_subreddit] if target_subreddit else None
            candidates = fetch_top_high_cpm_stories(subreddits=subs, max_stories=1)
            story_raw = candidates[0]


        if custom_output_dir:
            work_dir = os.path.abspath(custom_output_dir)
        else:
            # Organização oficial em batches (batch_1, batch_2...) com 10 vídeos por lote (video_0..video_9)
            mgr = BatchManager(base_dir=output_base_dir)
            work_dir, b_num, v_num = mgr.get_next_video_slot()

        # Garante pasta dedicada longform_25min dentro do slot
        if os.path.basename(work_dir).lower() == "longform_25min":
            longform_dir = work_dir
        else:
            longform_dir = os.path.join(work_dir, "longform_25min")
            
        cards_dir = os.path.join(longform_dir, "cards")
        chunks_dir = os.path.join(longform_dir, "chunks")
        os.makedirs(longform_dir, exist_ok=True)
        os.makedirs(cards_dir, exist_ok=True)
        os.makedirs(chunks_dir, exist_ok=True)

        app_logger.info(f"[Longform25Min] Iniciando produção de história única de 25 min para: '{story_raw.get('title')}' em {longform_dir}")
        if status_callback:
            status_callback(f"📖 Desenvolvendo narrativa profunda de 25 minutos: '{story_raw.get('title')[:40]}...'")

        # 2. Expansão da História Única em 8 Capítulos Épicos
        director = RedditStoryDirectorAgent()
        longform_data = director.expand_25min_single_story(
            story_raw,
            target_minutes=target_duration_minutes,
            status_callback=status_callback
        )

        chapters = longform_data.get("chapters", [])
        if not chapters:
            raise ValueError("Nenhum capítulo retornado para a história de 25 minutos.")

        # Salva o roteiro completo estruturado
        script_file = os.path.join(longform_dir, "script_data.json")
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(longform_data, f, indent=2, ensure_ascii=False)

        # 3. Localizar clipes de fundo 1080p60 HD
        orbital_clips = get_orbital_backgrounds(aspect_ratio=aspect_ratio)
        if not orbital_clips:
            app_logger.warning("[Longform25Min] Nenhum clipe em assets/backgrounds. Usando gerador procedural...")

        visual_engine = RedditVisualEngine()
        persona = longform_data.get("persona", "male_dramatic")
        voice_name = longform_data.get("recommended_voice", PERSONA_VOICE_MAP.get(persona, "en-US-ChristopherNeural"))
        audio_engine = RedditAudioEngine(voice=voice_name, rate="+15%")

        chapter_data = []
        chapter_video_files = []
        chapter_audio_files = []
        accumulated_time = 0.0

        # 4. Renderizar cada capítulo da história única (Modular Chunking)
        for idx, ch in enumerate(chapters):
            ch_num = ch.get("chapter_num", idx + 1)
            ch_title = ch.get("chapter_title", f"Part {ch_num}")
            ch_narration = ch.get("narration_text", "")

            if status_callback:
                status_callback(f"🎙️ Gravando Áudio e Card da Parte {ch_num}/8: {ch_title}...")

            # Áudio do capítulo
            seg_audio_path = os.path.join(chunks_dir, f"audio_part_{ch_num:02d}.mp3")
            words_timing = audio_engine.generate_speech(
                text=ch_narration,
                output_mp3=seg_audio_path,
                voice_name=voice_name
            )
            seg_dur = get_media_duration(seg_audio_path, ffmpeg_bin)
            chapter_audio_files.append(seg_audio_path)

            # Card Oficial do Reddit: Apenas na Parte 1 (Abertura do Vídeo)
            is_opening_part = (idx == 0)
            card_png = None
            if is_opening_part:
                card_png = os.path.join(cards_dir, "card_opening.png")
                card_info = {
                    "channel_name": "Reddit Minute",
                    "score": story_raw.get("score", "38.2k"),
                    "display_title": story_raw.get('title', 'Insane Reddit Story')
                }
                visual_engine.render_reddit_card(card_info, card_png, aspect_ratio=aspect_ratio)

            # Legendas dinâmicas ASS
            ass_path = os.path.join(chunks_dir, f"subtitles_part_{ch_num:02d}.ass")
            generate_reddit_ass_subtitles(words_timing, ass_path, aspect_ratio=aspect_ratio)

            # Seleciona clipe de fundo alternado
            bg_clip = orbital_clips[idx % len(orbital_clips)] if orbital_clips else None
            ch_video_output = os.path.join(chunks_dir, f"part_{ch_num:02d}.mp4")

            if status_callback:
                status_callback(f"🎬 Renderizando chunk da Parte {ch_num}/8 ({seg_dur:.0f}s)...")

            ok, out_path = render_reddit_story_video(
                audio_path=seg_audio_path,
                ass_subtitles_path=ass_path,
                card_png_path=card_png if is_opening_part else None,
                output_video_path=ch_video_output,
                background_video_path=bg_clip,
                video_type="longform" if is_opening_part else "chunk",
                aspect_ratio=aspect_ratio,
                card_duration_sec=4.8 if is_opening_part else 0.0,
                status_callback=status_callback
            )

            if not ok or not os.path.exists(ch_video_output):
                raise RuntimeError(f"Falha ao renderizar parte {ch_num}: {out_path}")

            chapter_video_files.append(ch_video_output)
            chapter_data.append({
                "part": ch_num,
                "title": ch_title,
                "start_time_sec": accumulated_time,
                "duration_sec": seg_dur,
                "video_file": ch_video_output
            })
            accumulated_time += seg_dur

        total_story_duration = accumulated_time
        app_logger.info(f"[Longform25Min] Todas as {len(chapter_video_files)} partes renderizadas! Duração total: {total_story_duration/60:.2f} min")

        # 5. Concatenação ultrarrápida no Master 25 Minutos Final (FFmpeg Demuxer - Stream Copy)
        if status_callback:
            status_callback(f"⚡ Consolidando Master Final de {total_story_duration/60:.1f} minutos...")

        concat_txt = os.path.join(longform_dir, "story_parts_concat.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for cv in chapter_video_files:
                safe_cv = os.path.abspath(cv).replace("\\", "/")
                f.write(f"file '{safe_cv}'\n")

        output_master_mp4 = os.path.join(longform_dir, "longform_master_25min_16x9.mp4")
        cmd_concat = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c", "copy",
            output_master_mp4
        ]
        subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        app_logger.info(f"[Longform25Min] Master final gerado com sucesso: {output_master_mp4} ({os.path.getsize(output_master_mp4)} bytes)")

        # 6. Concatena os áudios individuais no arquivo narration_longform.mp3
        master_audio_mp3 = os.path.join(longform_dir, "narration_longform.mp3")
        concat_audio_txt = os.path.join(longform_dir, "audio_parts_concat.txt")
        with open(concat_audio_txt, "w", encoding="utf-8") as f:
            for ca in chapter_audio_files:
                safe_ca = os.path.abspath(ca).replace("\\", "/")
                f.write(f"file '{safe_ca}'\n")
        cmd_concat_audio = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_audio_txt,
            "-c", "copy",
            master_audio_mp3
        ]
        try:
            subprocess.run(cmd_concat_audio, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        # 7. Metadados e Timestamps do YouTube para a História Única
        timestamps_lines = []
        for ch in chapter_data:
            sec = int(ch["start_time_sec"])
            m, s = divmod(sec, 60)
            h, m = divmod(m, 60)
            ts_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            timestamps_lines.append(f"{ts_str} - Part {ch['part']}: {ch['title']}")

        timestamps_block = "\n".join(timestamps_lines)
        metadata_path = os.path.join(longform_dir, "metadata_youtube.txt")
        meta_content = f"""TÍTULO DO VÍDEO (ALTO CPM):
{longform_data.get('main_title', story_raw.get('title', ''))}

DESCRIÇÃO COMPLETA:
{longform_data.get('youtube_description', '')}

⏱️ TIMESTAMPS & CAPÍTULOS DA HISTÓRIA:
{timestamps_block}

---------------------------------------------------
🎮 Background Gameplay: Minecraft Parkour 1080p 60fps by @OrbitalNCG (No Copyright Gameplay)
🎙️ Narração Neural: Persona {persona} ({voice_name}) via Reddit Story Studio
Subreddit Original: {story_raw.get('subreddit')}
Autor Original: {story_raw.get('author')}

HASHTAGS:
{" ".join(longform_data.get('tags', ['#RedditStories', '#MaliciousCompliance', '#25MinStory']))}
"""
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(meta_content)

        if status_callback:
            status_callback(f"🎉 Vídeo de História Única de {total_story_duration/60:.1f} minutos gerado com sucesso!")

        # Registra o tema na Blacklist de Long Videos
        try:
            b_name = os.path.basename(os.path.dirname(work_dir)) if "batch_" in work_dir else "manual_batch"
            v_name = os.path.basename(work_dir) if "video_" in work_dir else "video_0"
            DEFAULT_CHECKPOINT_MANAGER.add_to_blacklist(
                topic_data={
                    "tema": longform_data.get("main_title", story_raw.get("title", "")),
                    "hook": longform_data.get("opening_hook", ""),
                    "explicacao_tecnica": story_raw.get("body", "")
                },
                batch_name=b_name,
                video_name=v_name,
                video_type="longform"
            )
        except Exception as e:
            app_logger.warning(f"[Longform25Min] Erro ao registrar em blacklist_longform: {str(e)}")

        return {
            "success": True,
            "work_dir": work_dir,
            "longform_dir": longform_dir,
            "output_video": output_master_mp4,
            "metadata_file": metadata_path,
            "total_duration_minutes": round(total_story_duration / 60.0, 2),
            "total_chapters": len(chapter_data),
            "title": longform_data.get("main_title"),
            "teaser_short_data": longform_data.get("teaser_short", {})
        }

if __name__ == "__main__":
    print("🚀 Starting 25-Minute Single Story Generator...")
    res = generate_25min_single_story_video(target_duration_minutes=25.0)
    print(f"✅ 25-Minute Single Story Video finished successfully in: {res.get('work_dir')}")
