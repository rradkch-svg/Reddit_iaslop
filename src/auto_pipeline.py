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
    from .checkpoint_manager import DEFAULT_CHECKPOINT_MANAGER, CheckpointManager
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_scraper import HIGH_CPM_SUBREDDITS, EXPANDED_HIGH_CPM_STORIES, fetch_top_high_cpm_stories
    from reddit_pipeline import run_reddit_story_pipeline, generate_teaser_short_video
    from reddit_longform import generate_25min_single_story_video
    from gemini_client import DEFAULT_FALLBACK_MODELS, resolve_gemini_api_keys
    from batch_manager import BatchManager
    from checkpoint_manager import DEFAULT_CHECKPOINT_MANAGER, CheckpointManager

import random

class RedditAutoPipelineRunner:
    """
    Executor mestre autônomo para o Reddit Story Studio.
    Produz lotes contínuos no formato oficial batch_1, batch_2... (10 slots por lote: video_0 a video_9).
    
    REGRA OFICIAL DOS LOTES:
    - video_0: Formato DUAL OBRIGATÓRIO (subpastas 'longform_25min/' e 'teaser_short/')
    - video_1 a video_9: Shorts normais individuais em alta retenção (9:16 até 2.5 min com CTA)
    - DUAL BLACKLISTS:
      * video_0 consulta e grava em 'blacklist_longform'
      * video_1..video_9 consultam e gravam em 'blacklist_shorts'
    """
    def __init__(
        self,
        target_subreddits: Optional[List[str]] = None,
        model_name: str = "gemini-flash-lite-latest",
        output_dir: str = "checkpoint/auto_batches",
        batch_size: int = 10,
        checkpoint_manager: Optional[CheckpointManager] = None
    ):
        self.target_subreddits = target_subreddits or HIGH_CPM_SUBREDDITS
        self.model_name = model_name
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.batch_manager = BatchManager(base_dir=output_dir, batch_size=batch_size)
        self.batch_manager.organize_legacy_directories()
        self.checkpoint_manager = checkpoint_manager or DEFAULT_CHECKPOINT_MANAGER

    def run_continuous_batch(self, count: int = 10):
        print(f"\n=======================================================")
        print(f"🔥 REDDIT STORY STUDIO - MODO AUTÔNOMO POR BATCHES")
        print(f"   Estrutura: batch_1, batch_2... (10 vídeos por lote)")
        print(f"   Regra: video_0 = Dual (25min Long + Teaser) | video_1..9 = Shorts Normais")
        print(f"   Dual Blacklists: blacklist_shorts.json & blacklist_longform.json")
        print(f"   Subreddits: {', '.join(self.target_subreddits)}")
        print(f"   Total a produzir nesta sessão: {count} slots de vídeo")
        print(f"=======================================================\n")

        # Sincroniza previamente batches existentes com as 2 blacklists
        self.checkpoint_manager.sync_blacklists_from_batches()

        stories = fetch_top_high_cpm_stories(subreddits=self.target_subreddits, max_stories=max(count * 3, 20))
        if not stories:
            stories = list(EXPANDED_HIGH_CPM_STORIES)

        story_idx = 0
        completed = 0
        while RUNNING and completed < count:
            target_slot, batch_num, video_num = self.batch_manager.get_next_video_slot()
            batch_name = f"batch_{batch_num}"
            video_name = f"video_{video_num}"
            is_video_0 = (video_num == 0)
            target_video_type = "longform" if is_video_0 else "shorts"

            # Encontra próxima história válida não-blacklisted para este formato
            selected_story = None
            while story_idx < len(stories):
                candidate = stories[story_idx]
                story_idx += 1
                is_dup, reason = self.checkpoint_manager.is_in_blacklist(candidate, video_type=target_video_type)
                if is_dup:
                    print(f"   ⚠️ [Blacklist ({target_video_type})] Tema ignorado: '{candidate.get('title', '')[:45]}...' ({reason})")
                    continue
                selected_story = candidate
                break

            # Se esgotou a lista de histórias, busca mais
            if not selected_story:
                print(f"📡 Buscando lote adicional de histórias no Reddit...")
                more_stories = fetch_top_high_cpm_stories(subreddits=self.target_subreddits, max_stories=20)
                new_stories = [s for s in more_stories if s not in stories]
                if new_stories:
                    stories.extend(new_stories)
                    continue
                else:
                    # Fallback para histórias expandidas
                    for fallback in EXPANDED_HIGH_CPM_STORIES:
                        is_dup, _ = self.checkpoint_manager.is_in_blacklist(fallback, video_type=target_video_type)
                        if not is_dup:
                            selected_story = fallback
                            break
                    if not selected_story:
                        selected_story = random.choice(EXPANDED_HIGH_CPM_STORIES)

            sub = selected_story.get("subreddit", "reddit")
            title = selected_story.get("title", "")[:45]

            if is_video_0:
                print(f"\n🌟 [{completed+1}/{count}] Slot Especial: {batch_name}/{video_name} ({sub}) ➔ PRODUZINDO FORMATO DUAL (Longform 25min + Teaser Short)...")
                try:
                    # 1. Gera vídeo longo de 25min (16:9) na subpasta longform_25min/
                    res_long = generate_25min_single_story_video(
                        custom_post=selected_story,
                        target_duration_minutes=25.0,
                        custom_output_dir=target_slot
                    )
                    # 2. Gera teaser short vertical (9:16) na subpasta teaser_short/
                    res_teaser = generate_teaser_short_video(
                        story_raw=selected_story,
                        custom_output_dir=target_slot,
                        teaser_data=res_long.get("teaser_short_data")
                    )
                    # Registra na Blacklist de Longform
                    self.checkpoint_manager.add_to_blacklist(
                        selected_story,
                        batch_name=batch_name,
                        video_name=video_name,
                        video_type="longform"
                    )
                    print(f"✅ [{batch_name} | {video_name}] DUAL CONCLUÍDO (Registrado em blacklist_longform):")
                    print(f"   🎬 Longform 25min: {target_slot}/longform_25min/")
                    print(f"   ⚡ Teaser Short 9:16: {target_slot}/teaser_short/")
                    completed += 1
                except Exception as e:
                    print(f"❌ Erro ao produzir slot dual {video_name}: {e}")
                    time.sleep(2)
            else:
                print(f"\n🚀 [{completed+1}/{count}] Slot Standard: {batch_name}/{video_name} ({sub}) ➔ PRODUZINDO SHORT INDIVIDUAL...")
                try:
                    # Gera Short individual clássico diretamente na pasta video_Y/
                    res_short = run_reddit_story_pipeline(
                        custom_post=selected_story,
                        custom_output_dir=target_slot,
                        model_name=self.model_name
                    )
                    # Registra na Blacklist de Shorts
                    self.checkpoint_manager.add_to_blacklist(
                        selected_story,
                        batch_name=batch_name,
                        video_name=video_name,
                        video_type="shorts"
                    )
                    print(f"✅ [{batch_name} | {video_name}] Short Individual 9:16 gerado (Registrado em blacklist_shorts): {target_slot}/")
                    completed += 1
                except Exception as e:
                    print(f"❌ Erro ao produzir short {video_name}: {e}")
                    time.sleep(2)

        print(f"\n🎉 Sessão concluída! Total produzidos: {completed}/{count}")
        self.print_status()
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

