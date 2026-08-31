import os
import sys
import time
import json
import signal
import argparse
from typing import Dict, Any, List, Optional, Tuple

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "src" else CURRENT_DIR
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

import atexit
try:
    from .logger import app_logger, LogSpan
    from .reddit_scraper import HIGH_CPM_SUBREDDITS, EXPANDED_HIGH_CPM_STORIES, fetch_top_high_cpm_stories
    from .reddit_pipeline import run_reddit_story_pipeline
    from .reddit_longform import generate_25min_single_story_video
    from .gemini_client import DEFAULT_FALLBACK_MODELS, resolve_gemini_api_keys
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_scraper import HIGH_CPM_SUBREDDITS, EXPANDED_HIGH_CPM_STORIES, fetch_top_high_cpm_stories
    from reddit_pipeline import run_reddit_story_pipeline
    from reddit_longform import generate_25min_single_story_video
    from gemini_client import DEFAULT_FALLBACK_MODELS, resolve_gemini_api_keys

RUNNING = True

def signal_handler(sig, frame):
    global RUNNING
    print("\n\n⚠️ [AutoPipeline] Interrupção solicitada. Finalizando etapa atual com segurança...")
    RUNNING = False

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGTERM, signal_handler)
except:
    pass

class RedditAutoPipelineRunner:
    """
    Executor mestre autônomo para o Reddit Story Studio.
    Produz lotes contínuos de Shorts virais (até 2.5 min com CTA) e Sagas Longas de 25 Minutos.
    """
    def __init__(
        self,
        target_subreddits: Optional[List[str]] = None,
        model_name: str = "gemini-flash-lite-latest",
        output_dir: str = "checkpoint/auto_batches",
        generate_longform: bool = False
    ):
        self.target_subreddits = target_subreddits or HIGH_CPM_SUBREDDITS
        self.model_name = model_name
        self.output_dir = output_dir
        self.generate_longform = generate_longform
        os.makedirs(self.output_dir, exist_ok=True)

    def run_continuous_batch(self, count: int = 5):
        print(f"\n=======================================================")
        print(f"🔥 REDDIT STORY STUDIO - MODO AUTÔNOMO CONTÍNUO")
        print(f"   Subreddits: {', '.join(self.target_subreddits)}")
        print(f"   Total planejado: {count} vídeos")
        print(f"   Modo Longform 25min: {'SIM' if self.generate_longform else 'NÃO (Shorts 9:16 até 2.5min)'}")
        print(f"=======================================================\n")

        stories = fetch_top_high_cpm_stories(subreddits=self.target_subreddits, max_stories=count * 2)
        if not stories:
            stories = list(EXPANDED_HIGH_CPM_STORIES)

        completed = 0
        for idx, story in enumerate(stories):
            if not RUNNING or completed >= count:
                break

            sub = story.get("subreddit", "reddit")
            title = story.get("title", "")[:45]
            print(f"\n🚀 [{completed+1}/{count}] Produzindo vídeo de {sub}: '{title}...'")

            try:
                if self.generate_longform:
                    res = generate_25min_single_story_video(
                        custom_post=story,
                        target_duration_minutes=25.0,
                        output_base_dir=os.path.join(self.output_dir, "longform_25min")
                    )
                    print(f"✅ Vídeo de 25min gerado: {res.get('output_video')}")
                else:
                    res = run_reddit_story_pipeline(
                        custom_post=story,
                        output_base_dir=os.path.join(self.output_dir, "shorts"),
                        model_name=self.model_name
                    )
                    print(f"✅ Short 9:16 gerado: {res.get('video_shorts_9x16')}")

                completed += 1
            except Exception as e:
                print(f"❌ Erro ao produzir história {idx+1}: {e}")
                time.sleep(2)

        print(f"\n🎉 Lote concluído com sucesso! Total produzidos: {completed}/{count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reddit Story Studio Auto Pipeline")
    parser.add_argument("--count", type=int, default=5, help="Quantidade de vídeos a produzir")
    parser.add_argument("--sub", type=str, default=None, help="Subreddit alvo específico")
    parser.add_argument("--longform", action="store_true", help="Produzir vídeos longos de 25 minutos de histórias únicas")
    args = parser.parse_args()

    subs = [args.sub] if args.sub else None
    runner = RedditAutoPipelineRunner(
        target_subreddits=subs,
        generate_longform=args.longform
    )
    runner.run_continuous_batch(count=args.count)
