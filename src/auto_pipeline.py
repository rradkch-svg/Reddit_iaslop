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

CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "checkpoint")
LOCK_FILE = os.path.join(CHECKPOINT_DIR, ".pipeline.lock")

# Garante que o arquivo .env existe a partir de .env.example
env_path = os.path.join(PROJECT_ROOT, ".env")
if not os.path.exists(env_path):
    example_path = os.path.join(PROJECT_ROOT, ".env.example")
    if os.path.exists(example_path):
        try:
            import shutil
            shutil.copyfile(example_path, env_path)
        except Exception:
            pass

try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
except ImportError:
    pass

import atexit

class PipelineLockManager:
    """Gerencia o bloqueio de execução única do gerador de forma resiliente."""
    def __init__(self, lock_file: str):
        self.lock_file = lock_file
        self.handle = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_file)), exist_ok=True)
        try:
            self.handle = open(self.lock_file, "a+", encoding="utf-8")
            if sys.platform == "win32":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write(f"{os.getpid()}\n")
            self.handle.flush()
            return True
        except (IOError, OSError, PermissionError):
            if self.handle:
                try:
                    self.handle.close()
                except Exception:
                    pass
                self.handle = None
            return False

    def release(self):
        if self.handle:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                self.handle.close()
            except Exception:
                pass
            self.handle = None
            try:
                if os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
            except Exception:
                pass

LOCK_MANAGER = PipelineLockManager(LOCK_FILE)
RUNNING = True

def signal_handler(sig, frame):
    global RUNNING
    print("\n\n⚠️ [AutoPipeline] Interrupção solicitada. Finalizando etapa atual com segurança...")
    RUNNING = False
    LOCK_MANAGER.release()

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGTERM, signal_handler)
except Exception:
    pass

try:
    from .logger import app_logger, LogSpan
    from .reddit_scraper import HIGH_CPM_SUBREDDITS, EXPANDED_HIGH_CPM_STORIES, fetch_top_high_cpm_stories
    from .reddit_pipeline import run_reddit_story_pipeline, generate_teaser_short_video
    from .reddit_longform import generate_25min_single_story_video
    from .gemini_client import DEFAULT_FALLBACK_MODELS, resolve_gemini_api_keys
    from .batch_manager import BatchManager
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_scraper import HIGH_CPM_SUBREDDITS, EXPANDED_HIGH_CPM_STORIES, fetch_top_high_cpm_stories
    from reddit_pipeline import run_reddit_story_pipeline, generate_teaser_short_video
    from reddit_longform import generate_25min_single_story_video
    from gemini_client import DEFAULT_FALLBACK_MODELS, resolve_gemini_api_keys
    from batch_manager import BatchManager

class RedditAutoPipelineRunner:
    """
    Executor mestre autônomo para o Reddit Story Studio.
    Produz lotes contínuos no formato oficial batch_1, batch_2... (10 slots por lote: video_0 a video_9).
    
    REGRA OFICIAL DOS LOTES:
    - video_0: Formato DUAL OBRIGATÓRIO (subpastas 'longform_25min/' e 'teaser_short/')
    - video_1 a video_9: Shorts normais individuais em alta retenção (9:16 até 2.5 min com CTA)
    """
    def __init__(
        self,
        target_subreddits: Optional[List[str]] = None,
        model_name: str = "gemini-flash-lite-latest",
        output_dir: str = "checkpoint/auto_batches",
        batch_size: int = 10
    ):
        self.target_subreddits = target_subreddits or HIGH_CPM_SUBREDDITS
        self.model_name = model_name
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.batch_manager = BatchManager(base_dir=output_dir, batch_size=batch_size)
        self.batch_manager.organize_legacy_directories()

    def run_continuous_batch(self, count: int = 10):
        print(f"\n=======================================================")
        print(f"🔥 REDDIT STORY STUDIO - MODO AUTÔNOMO POR BATCHES")
        print(f"   Estrutura: batch_1, batch_2... (10 vídeos por lote)")
        print(f"   Regra: video_0 = Dual (25min Long + Teaser) | video_1..9 = Shorts Normais")
        print(f"   Subreddits: {', '.join(self.target_subreddits)}")
        print(f"   Total a produzir nesta sessão: {count} slots de vídeo")
        print(f"=======================================================\n")

        stories = fetch_top_high_cpm_stories(subreddits=self.target_subreddits, max_stories=count * 2)
        if not stories:
            stories = list(EXPANDED_HIGH_CPM_STORIES)

        completed = 0
        for idx, story in enumerate(stories):
            if not RUNNING or completed >= count:
                break

            target_slot, batch_num, video_num = self.batch_manager.get_next_video_slot()
            sub = story.get("subreddit", "reddit")
            title = story.get("title", "")[:45]
            
            is_video_0 = (video_num == 0)

            if is_video_0:
                print(f"\n🌟 [{completed+1}/{count}] Slot Especial: batch_{batch_num}/video_0 ({sub}) ➔ PRODUZINDO FORMATO DUAL (Longform 25min + Teaser Short)...")
                try:
                    # 1. Gera vídeo longo de 25min (16:9) na subpasta longform_25min/
                    res_long = generate_25min_single_story_video(
                        custom_post=story,
                        target_duration_minutes=25.0,
                        custom_output_dir=target_slot
                    )
                    # 2. Gera teaser short vertical (9:16) na subpasta teaser_short/
                    res_teaser = generate_teaser_short_video(
                        story_raw=story,
                        custom_output_dir=target_slot,
                        teaser_data=res_long.get("teaser_short_data")
                    )
                    print(f"✅ [batch_{batch_num} | video_0] DUAL CONCLUÍDO:")
                    print(f"   🎬 Longform 25min: {target_slot}/longform_25min/")
                    print(f"   ⚡ Teaser Short 9:16: {target_slot}/teaser_short/")
                    completed += 1
                except Exception as e:
                    print(f"❌ Erro ao produzir slot dual video_0: {e}")
                    time.sleep(2)
            else:
                print(f"\n🚀 [{completed+1}/{count}] Slot Standard: batch_{batch_num}/video_{video_num} ({sub}) ➔ PRODUZINDO SHORT INDIVIDUAL...")
                try:
                    # Gera Short individual clássico diretamente na pasta video_Y/
                    res_short = run_reddit_story_pipeline(
                        custom_post=story,
                        custom_output_dir=target_slot,
                        model_name=self.model_name
                    )
                    print(f"✅ [batch_{batch_num} | video_{video_num}] Short Individual 9:16 gerado em: {target_slot}/")
                    completed += 1
                except Exception as e:
                    print(f"❌ Erro ao produzir short {video_num}: {e}")
                    time.sleep(2)

        print(f"\n🎉 Sessão concluída! Total produzidos: {completed}/{count}")
        self.print_status()

    def print_status(self):
        summary = self.batch_manager.get_summary()
        print("\n📊 Resumo dos Batches Organizados:")
        if not summary:
            print("   Nenhum batch gerado ainda.")
        for b in summary:
            status_tag = " [COMPLETO - 10/10]" if b["is_full"] else f" [{b['video_count']}/10 vídeos]"
            print(f"   📁 {b['batch_name']}{status_tag}: {', '.join(b['videos']) if b['videos'] else 'vazio'}")
        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reddit Story Studio Auto Pipeline")
    parser.add_argument("--count", type=int, default=10, help="Quantidade de vídeos a produzir (padrão: 10)")
    parser.add_argument("--sub", type=str, default=None, help="Subreddit alvo específico")
    parser.add_argument("--organize", action="store_true", help="Organizar diretórios legados em batch_1/video_0...")
    parser.add_argument("--status", action="store_true", help="Exibir status dos batches organizados")
    args = parser.parse_args()

    mgr = BatchManager()
    if args.organize:
        migrated = mgr.organize_legacy_directories()
        print(f"✅ Organização concluída! {migrated} vídeos legados foram movidos para a estrutura de batches.")
        runner = RedditAutoPipelineRunner()
        runner.print_status()
        sys.exit(0)

    if args.status:
        runner = RedditAutoPipelineRunner()
        runner.print_status()
        sys.exit(0)

    if not LOCK_MANAGER.acquire():
        print("⚠️ [AutoPipeline] Outra instância do gerador já está em execução. Encerrando para evitar duplicações.")
        sys.exit(0)
    atexit.register(LOCK_MANAGER.release)

    subs = [args.sub] if args.sub else None
    runner = RedditAutoPipelineRunner(target_subreddits=subs)
    runner.run_continuous_batch(count=args.count)

