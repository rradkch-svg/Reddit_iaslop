import os
import sys
import time
import json
import signal
import argparse
from typing import Dict, Any, List, Optional, Tuple

# Forçar UTF-8 no stdout do Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

# Configurar sys.path dinamicamente para suportar src/ e raiz
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "src" else CURRENT_DIR
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Carregar variáveis de ambiente (.env)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

import atexit
try:
    from .logger import app_logger, LogSpan, record_throttling
    from .checkpoint_manager import CheckpointManager, VIDEOS_PER_BATCH
    from .agents import (
        ProposerAgent,
        EvaluatorAgent,
        DissertationAgent,
        DirectorAgent,
        ReviewerAgent,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key,
        resolve_gemini_api_keys,
        save_video_metadata_file
    )
    from .audio import AudioEngine, FALLBACK_VOICES
    from .broll_engine import BRollEngine, find_ffmpeg_binary
    from .subtitles import convert_words_to_ass
    from .render import assemble_multi_scene_video
    from .algorithm_memory import DEFAULT_ALGORITHM_MEMORY
    from .deduplication import sanitize_and_cap_title
except ImportError:
    from logger import app_logger, LogSpan, record_throttling
    from checkpoint_manager import CheckpointManager, VIDEOS_PER_BATCH
    from agents import (
        ProposerAgent,
        EvaluatorAgent,
        DissertationAgent,
        DirectorAgent,
        ReviewerAgent,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key,
        resolve_gemini_api_keys,
        save_video_metadata_file
    )
    from audio import AudioEngine, FALLBACK_VOICES
    from broll_engine import BRollEngine, find_ffmpeg_binary
    from subtitles import convert_words_to_ass
    from render import assemble_multi_scene_video
    from algorithm_memory import DEFAULT_ALGORITHM_MEMORY
    from deduplication import sanitize_and_cap_title

# Flag de encerramento gracioso (Ctrl+C / SIGINT)
RUNNING = True

def signal_handler(sig, frame):
    global RUNNING
    print("\n\n⚠️ [AutoPipeline] Sinal de interrupção recebido (SIGINT/SIGTERM). Finalizando etapa atual com segurança...")
    app_logger.info("[AutoPipeline] Interrupção solicitada pelo usuário/sistema. Salvando estado...")
    RUNNING = False

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGTERM, signal_handler)
except:
    pass

class SingleInstanceLock:
    """
    Garante que apenas uma instância do auto_pipeline execute por vez,
    evitando concorrência ou duplicação de processos acessando os mesmos checkpoints.
    """
    def __init__(self, lock_file_path: str):
        self.lock_file_path = lock_file_path
        self.handle = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_file_path)), exist_ok=True)
        try:
            if sys.platform == "win32":
                import msvcrt
                self.handle = open(self.lock_file_path, "a+")
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                self.handle.truncate(0)
                self.handle.write(str(os.getpid()))
                self.handle.flush()
            else:
                import fcntl
                self.handle = open(self.lock_file_path, "w+")
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.handle.write(str(os.getpid()))
                self.handle.flush()
            atexit.register(self.release)
            return True
        except (IOError, OSError, PermissionError, BlockingIOError):
            return False

    def release(self):
        if self.handle:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                self.handle.close()
                if os.path.exists(self.lock_file_path):
                    os.remove(self.lock_file_path)
            except Exception:
                pass
            self.handle = None

class AutoPipelineRunner:
    """
    Executor mestre do pipeline em modo autônomo.
    Processa batches de 10 vídeos (batch_0 .. batch_N) com recuperação
    automática de checkpoints em caso de queda de energia ou reinicialização.
    """

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        videos_per_batch: int = VIDEOS_PER_BATCH,
        model_name: str = "gemini-flash-lite-latest",
        voice: str = "gemini:Charon",
        rate: str = "+25%",
        max_workers: int = 4,
        auto_fallback: bool = True,
        auto_cooldown: bool = True,
        primary_subtitle_color: str = "FFFFFF",
        highlight_subtitle_color: str = "FFE500"
    ):
        self.checkpoint_mgr = CheckpointManager(root_dir=checkpoint_dir, videos_per_batch=videos_per_batch)
        self.videos_per_batch = videos_per_batch
        self.model_name = model_name
        self.voice = voice
        self.rate = rate
        self.max_workers = max_workers
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.primary_subtitle_color = primary_subtitle_color.lstrip("#")
        self.highlight_subtitle_color = highlight_subtitle_color.lstrip("#")

        # Garante as chaves do Gemini (Primária e Redundância)
        api_keys = resolve_gemini_api_keys()
        if api_keys:
            os.environ["GEMINI_API_KEY"] = api_keys[0]
            if len(api_keys) > 1:
                os.environ["GEMINI_FALLBACK_API_KEY"] = api_keys[1]

        # Instanciação dos motores reutilizáveis com ritmo acelerado 1.25x
        self.audio_engine = AudioEngine(voice=self.voice, rate=self.rate)
        self.broll_engine = BRollEngine(max_search_results=6)
        self.reviewer_agent = ReviewerAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )
        self.proposer_agent = ProposerAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )
        self.dissertation_agent = DissertationAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )
        self.director_agent = DirectorAgent(
            model_name=self.model_name,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown
        )

    def print_banner(self):
        print("=" * 75)
        print("🏎️  AI SLOP STUDIO - MODO GERAÇÃO E RECUPERAÇÃO AUTOMÁTICA (BATCHES 9:16)")
        print("=" * 75)
        print(f"📁 Pasta de Checkpoints : {self.checkpoint_mgr.root_dir}")
        print(f"📦 Vídeos por Batch    : {self.videos_per_batch}")
        print(f"🤖 Modelo de IA        : {self.model_name}")
        print(f"🎙️ Voz Neural (TTS)    : {self.voice}")
        print(f"⚡ Dinâmica / Ritmo    : {self.rate} (1.25x Acelerado)")
        print(f"⚡ Threads Paralelas   : {self.max_workers}")
        print("=" * 75)
        print()

    def show_status(self):
        """Exibe um resumo detalhado do progresso atual de todos os batches."""
        state = self.checkpoint_mgr.load_global_state()
        blacklist = self.checkpoint_mgr.load_blacklist()
        
        print("\n📊 RESUMO DO STATUS ATUAL:")
        print(f"• Total de Vídeos 100% Concluídos : {state.get('total_videos_completed', 0)}")
        print(f"• Batch Ativo Atual               : batch_{state.get('current_batch_index', 0)}")
        print(f"• Total de Temas na Blacklist     : {len(blacklist)}")
        print("\n📦 BATCHES REGISTRADOS NO DISCO:")
        
        batches = state.get("batches", {})
        if not batches:
            print("  (Nenhum batch iniciado ainda)")
        else:
            for b_name, b_data in sorted(batches.items(), key=lambda x: x[1].get("batch_index", 0)):
                status_icon = "✅" if b_data.get("status") == "COMPLETED" else "⏳"
                comp_cnt = b_data.get("completed_videos_count", 0)
                tot_cnt = b_data.get("total_videos", self.videos_per_batch)
                print(f"  {status_icon} [{b_name}] Status: {b_data.get('status')} | Concluídos: {comp_cnt}/{tot_cnt}")
                
                # Lista status dos vídeos
                v_dict = b_data.get("videos", {})
                v_summary = " ".join([f"v{i}:{'✅' if v_dict.get(f'video_{i}')=='COMPLETED' else '⏳'}" for i in range(tot_cnt)])
                print(f"     └─ {v_summary}")
        print()

    def process_single_video(self, batch_idx: int, video_idx: int) -> bool:
        """
        Processa um único vídeo respeitando todos os checkpoints já salvos.
        Se faltou luz na etapa 4, retoma exatamente a partir da etapa 4 sem repetir as anteriores.
        """
        b_name = f"batch_{batch_idx}"
        v_name = f"video_{video_idx}"
        v_dir = self.checkpoint_mgr.get_video_dir(batch_idx, video_idx)
        
        app_logger.info(f"[AutoPipeline] Iniciando/Retomando {b_name}/{v_name}...")
        print(f"\n🎬 >>> PROCESSANDO: {b_name.upper()} / {v_name.upper()} <<<")

        with LogSpan(f"AutoPipeline_{b_name}_{v_name}"):
            # 1. Determina a etapa exata de retomada
            stage, ckpt = self.checkpoint_mgr.determine_video_resume_stage(batch_idx, video_idx)
            
            if stage == "COMPLETED":
                print(f"  ✅ Vídeo {b_name}/{v_name} já está 100% finalizado e íntegro no disco.")
                return True

            # Auto-Sync de Analytics: Checa se há um novo .zip na pasta /analytics caso o nome do arquivo tenha mudado
            try:
                has_new_analytics, analytics_msg = DEFAULT_ALGORITHM_MEMORY.check_and_auto_ingest_analytics()
                if has_new_analytics:
                    print(f"  📊 [Analytics Auto-Sync] {analytics_msg}")
            except Exception as e_an:
                app_logger.warning(f"[AutoPipeline] Erro na auto-ingestão de analytics: {str(e_an)}")

            # ETAPA 1: GERAÇÃO DE NOVO TEMA INÉDITO & DISSERTAÇÃO TÉCNICA PROFUNDA (FASE 1)
            if stage == "GENERATE_TOPIC":
                print("  💡 [1/6] Propondo tema inédito com ProposerAgent (consultando Blacklist e Memória .md)...")
                blacklist_titles = self.checkpoint_mgr.get_blacklist_titles()
                
                max_topic_attempts = 4
                selected_topic = None

                for attempt in range(max_topic_attempts):
                    try:
                        proposed_topics = self.proposer_agent.generate_topics(
                            count=5,
                            blacklist=blacklist_titles,
                            status_callback=lambda m: print(f"    📡 {m}")
                        )
                        
                        if isinstance(proposed_topics, list) and proposed_topics:
                            for candidate in proposed_topics:
                                candidate["tema"] = sanitize_and_cap_title(candidate.get("tema", ""), max_length=100)
                                is_blk, blk_reason = self.checkpoint_mgr.is_in_blacklist(candidate)
                                if not is_blk:
                                    selected_topic = candidate
                                    break
                                else:
                                    print(f"    ⚠️ Tema descartado pela Blacklist Heurística: '{candidate.get('tema')}' ({blk_reason})")
                            
                            if selected_topic:
                                break
                    except Exception as e:
                        app_logger.warning(f"[AutoPipeline] Erro ao propor tema (tentativa {attempt+1}): {str(e)}")
                        time.sleep(2)

                if not selected_topic:
                    # Fallback de emergência com tema dinâmico garantido
                    time_id = int(time.time()) % 10000
                    selected_topic = {
                        "tema": sanitize_and_cap_title(f"Engenharia Extrema: O Segredo Mecânico #{time_id}", max_length=100),
                        "hook": "Você conhece o segredo dessa obra-prima da engenharia?",
                        "explicacao_tecnica": "A combinação de aerodinâmica avançada e materiais leves gera estabilidade máxima."
                    }

                selected_topic["tema"] = sanitize_and_cap_title(selected_topic.get("tema", ""), max_length=100)
                print(f"  🎯 TEMA APROVADO: \"{selected_topic.get('tema')}\"")
                
                # FASE 1 DA SÍNTESE: CONSTRUÇÃO DA DISSERTAÇÃO COMPLETA DE ENGENHARIA
                print("  🔬 [1.5/6] Construindo dissertação técnica profunda e detalhada (DissertationAgent)...")
                try:
                    dissertacao_data = self.dissertation_agent.generate_dissertation(
                        selected_topic,
                        status_callback=lambda m: print(f"    🔬 {m}")
                    )
                    ckpt["dissertation"] = dissertacao_data
                    
                    # Salva dissertação em arquivo texto para auditoria e documentação
                    dissertacao_file = os.path.join(v_dir, "dissertacao.txt")
                    with open(dissertacao_file, "w", encoding="utf-8") as df:
                        df.write(f"TEMA: {selected_topic.get('tema')}\n\n")
                        df.write(f"DESAFIO: {dissertacao_data.get('desafio_de_engenharia')}\n\n")
                        df.write(f"SOLUÇÃO MECÂNICA: {dissertacao_data.get('solucao_mecanica')}\n\n")
                        df.write(f"DISSERTAÇÃO COMPLETA:\n{dissertacao_data.get('dissertacao_completa')}\n")
                    print(f"  📄 Dissertação gravada em: {dissertacao_file}")
                except Exception as e_dis:
                    app_logger.warning(f"[AutoPipeline] Erro ao gerar dissertação: {str(e_dis)}")
                    ckpt["dissertation"] = {"dissertacao_completa": selected_topic.get("explicacao_tecnica", "")}

                ckpt["topic"] = selected_topic
                ckpt["status"] = "TOPIC_READY"
                save_video_metadata_file(v_dir, selected_topic)
                ckpt["metadata_file"] = "metadata.txt"
                self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                
                # Registra IMEDIATAMENTE na Blacklist para reservar este tema
                self.checkpoint_mgr.add_to_blacklist(selected_topic, b_name, v_name)
                stage = "GENERATE_STORYBOARD"

            if not RUNNING:
                return False

            # ETAPA 2: ROTEIRIZAÇÃO E DESTILAÇÃO DE ALTA RETENÇÃO (DIRECTOR AGENT - FASE 2)
            if stage == "GENERATE_STORYBOARD":
                print("  ✍️ [2/6] Destilando dissertação em roteiro dinâmico e plano de cortes (DirectorAgent)...")
                topic = ckpt["topic"]
                dissertacao_info = ckpt.get("dissertation")
                try:
                    cenas = self.director_agent.generate_storyboard(
                        topic,
                        dissertacao_data=dissertacao_info,
                        status_callback=lambda m: print(f"    ✍️ {m}")
                    )
                    if not cenas or len(cenas) < 3:
                        raise Exception("Storyboard retornado com menos de 3 cenas.")
                    
                    ckpt["storyboard"] = cenas
                    ckpt["status"] = "STORYBOARD_READY"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    print(f"  ✅ Storyboard concluído com {len(cenas)} cenas planejadas!")
                    stage = "GENERATE_AUDIO"
                except Exception as e:
                    app_logger.error(f"[AutoPipeline] Falha no Storyboard: {str(e)}")
                    ckpt["error"] = f"Falha no Storyboard: {str(e)}"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

            if not RUNNING:
                return False

            # ETAPA 3: SÍNTESE DE VOZ NEURAL (EDGE-TTS)
            if stage == "GENERATE_AUDIO":
                print(f"  🎙️ [3/6] Sintetizando narração neural ({self.voice})...")
                cenas = ckpt.get("storyboard", [])
                full_script = " ".join([c.get("fala", "").strip() for c in cenas if c.get("fala")])
                if not full_script:
                    topic = ckpt.get("topic", {})
                    full_script = f"{topic.get('hook', '')} {topic.get('explicacao_tecnica', '')}"

                audio_path = os.path.join(v_dir, "audio.mp3")
                success_audio, words_timing = self.audio_engine.generate_audio(full_script, audio_path)
                
                if not success_audio:
                    err_msg = f"Falha no áudio: {words_timing}"
                    app_logger.error(f"[AutoPipeline] {err_msg}")
                    ckpt["error"] = err_msg
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

                total_audio_dur = words_timing[-1].get("end", 60.0) if words_timing else 60.0
                ckpt["audio_file"] = "audio.mp3"
                ckpt["audio_duration"] = total_audio_dur
                ckpt["words_timing"] = words_timing
                ckpt["status"] = "AUDIO_READY"
                self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                print(f"  ✅ Narração concluída: {total_audio_dur:.1f}s ({len(words_timing)} palavras)")
                stage = "GENERATE_SUBTITLES"

            if not RUNNING:
                return False

            # ETAPA 4: FORMATO DE LEGENDAS HORMOZI (PILL BOX AMARELA)
            if stage == "GENERATE_SUBTITLES":
                print("  🎨 [4/6] Compilando legendas ASS dinâmicas com destaque Pill Box...")
                words_timing = ckpt.get("words_timing", [])
                ass_path = os.path.join(v_dir, "subtitles.ass")
                
                convert_words_to_ass(
                    words_timing=words_timing,
                    output_ass=ass_path,
                    primary_color=self.primary_subtitle_color,
                    highlight_color=self.highlight_subtitle_color,
                    tail_overhead=0.4
                )
                ckpt["subtitles_file"] = "subtitles.ass"
                ckpt["status"] = "SUBTITLES_READY"
                self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                print(f"  ✅ Legendas ASS geradas com sucesso!")
                stage = "PROCESS_SCENES"

            if not RUNNING:
                return False

            # ETAPA 5: DOWNLOAD E AUDITORIA CONCORRENTE DE CENAS DO YOUTUBE
            if stage == "PROCESS_SCENES":
                print(f"  🎬 [5/6] Coletando e auditando B-rolls em paralelo ({self.max_workers} threads)...")
                cenas = ckpt.get("storyboard", [])
                global_topic = ckpt.get("topic", {}).get("tema", "Supercarro")
                total_audio_dur = ckpt.get("audio_duration", 60.0)

                def on_parallel_status(msg):
                    print(f"    📡 {msg}")

                def on_parallel_prog(done, total):
                    print(f"    📊 Progresso das Cenas: {done}/{total} auditadas")

                try:
                    scene_clips, scene_audits = self.broll_engine.process_all_scenes_parallel(
                        cenas=cenas,
                        global_topic=global_topic,
                        reviewer_agent=self.reviewer_agent,
                        project_dir=v_dir,
                        total_audio_duration=total_audio_dur,
                        words_timing=ckpt.get("words_timing"),
                        tail_overhead=0.5,
                        max_workers=self.max_workers,
                        status_callback=on_parallel_status,
                        progress_callback=on_parallel_prog
                    )

                    if not scene_clips:
                        raise Exception("Nenhum clipe de B-roll foi aprovado pelo ReviewerAgent.")

                    ckpt["scene_clips"] = scene_clips
                    ckpt["scene_audits"] = scene_audits
                    ckpt["status"] = "SCENES_READY"
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    print(f"  ✅ {len(scene_clips)} cenas 100% auditadas e salvas em disco!")
                    stage = "RENDER_FINAL"
                except Exception as e:
                    err_msg = f"Falha na obtenção de cenas: {str(e)}"
                    app_logger.error(f"[AutoPipeline] {err_msg}")
                    ckpt["error"] = err_msg
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

            if not RUNNING:
                return False

            # ETAPA 6: RENDERIZAÇÃO FINAL NO FFMPEG
            if stage == "RENDER_FINAL":
                print("  ⚡ [6/6] Renderizando Composição Final 9:16 no FFmpeg...")
                scene_clips = ckpt.get("scene_clips", [])
                audio_path = os.path.join(v_dir, ckpt.get("audio_file", "audio.mp3"))
                ass_path = os.path.join(v_dir, ckpt.get("subtitles_file", "subtitles.ass"))
                final_output = os.path.join(v_dir, "final_video.mp4")

                success_render, msg = assemble_multi_scene_video(
                    clip_paths=scene_clips,
                    audio_path=audio_path,
                    ass_path=ass_path,
                    output_path=final_output,
                    status_callback=lambda m: print(f"    ⚡ {m}")
                )

                if not success_render or not os.path.exists(final_output) or os.path.getsize(final_output) < 50_000:
                    err_msg = f"Falha na renderização FFmpeg: {msg}"
                    app_logger.error(f"[AutoPipeline] {err_msg}")
                    ckpt["error"] = err_msg
                    self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                    return False

                # Marca como concluído no CheckpointManager
                meta_file = save_video_metadata_file(v_dir, ckpt.get("topic", {}))
                ckpt["metadata_file"] = "metadata.txt"
                self.checkpoint_mgr.save_video_checkpoint(batch_idx, video_idx, ckpt)
                self.checkpoint_mgr.mark_video_completed(batch_idx, video_idx, final_output)
                
                # Registra na Memória Algorítmica (.md) para aprendizado contínuo de retenção
                try:
                    topic_info = ckpt.get("topic", {})
                    DEFAULT_ALGORITHM_MEMORY.record_video_generation({
                        "video_id": f"{b_name}_{v_name}",
                        "batch": b_name,
                        "video_index": video_idx,
                        "tema": topic_info.get("tema", ""),
                        "core_entity": topic_info.get("core_entity", ""),
                        "hook": topic_info.get("hook", ""),
                        "dissertacao_resumo": ckpt.get("dissertation", {}).get("dissertacao_completa", "")[:200],
                        "duracao_segundos": ckpt.get("audio_duration", 0.0),
                        "palavras_totais": len(ckpt.get("words_timing", [])),
                        "total_cenas": len(ckpt.get("storyboard", [])),
                        "estilo_voz": self.voice
                    })
                    DEFAULT_ALGORITHM_MEMORY.export_metrics_csv()
                    DEFAULT_ALGORITHM_MEMORY.export_metrics_markdown()
                except Exception as e_mem:
                    app_logger.warning(f"[AutoPipeline] Erro ao registrar na memória algorítmica: {str(e_mem)}")

                file_size_mb = os.path.getsize(final_output) / (1024 * 1024)
                print(f"  📄 Metadados salvos: {meta_file}")
                print(f"  🧠 Registrado na Memória Algorítmica (.md) e METRICAS_VIDEOS.csv atualizado na raiz")
                print(f"  🎉 VÍDEO CONCLUÍDO COM SUCESSO! -> {final_output} ({file_size_mb:.2f} MB)")
                return True

        return True

    def run_loop(self, max_batches: Optional[int] = None):
        """
        Loop infinito ou limitado por max_batches.
        Processa continuamente batches de 10 vídeos com auto-recuperação.
        """
        self.print_banner()
        self.show_status()

        print("\n🚀 Iniciando motor de processamento autônomo contínuo...")
        
        while RUNNING:
            batch_idx, video_idx, b_name, v_name = self.checkpoint_mgr.get_next_work_target()
            
            if max_batches is not None and batch_idx >= max_batches:
                print(f"\n🏁 Limite de {max_batches} batches atingido com sucesso. Finalizando execução!")
                break

            print("-" * 75)
            print(f"📦 [LOTE ATIVO: {b_name.upper()}] • Item #{video_idx + 1} de {self.videos_per_batch}")
            print("-" * 75)

            try:
                success = self.process_single_video(batch_idx, video_idx)
                if not success:
                    print(f"⚠️ Houve uma falha no processamento de {b_name}/{v_name}. Aguardando 10s antes da próxima tentativa...")
                    for _ in range(10):
                        if not RUNNING:
                            break
                        time.sleep(1)
                else:
                    time.sleep(2)
            except Exception as e:
                app_logger.error(f"[AutoPipeline] Exceção no loop principal ({b_name}/{v_name}): {str(e)}")
                print(f"❌ Exceção inesperada: {str(e)}")
                time.sleep(5)

        print("\n🛑 Processamento encerrado.")
        self.show_status()

def main():
    parser = argparse.ArgumentParser(description="AI Slop Studio - Pipeline de Geração e Recuperação Automática")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Diretório raiz de checkpoints")
    parser.add_argument("--batch-size", type=int, default=10, help="Quantidade de vídeos por batch (padrão: 10)")
    parser.add_argument("--max-batches", type=int, default=None, help="Quantidade máxima de batches a processar")
    parser.add_argument("--model", type=str, default="gemini-flash-lite-latest", help="Modelo principal do Gemini")
    parser.add_argument("--voice", type=str, default="gemini:Charon", help="Voz do narrador (Google Gemini ou Neural TTS)")
    parser.add_argument("--rate", type=str, default="+25%", help="Taxa de velocidade do TTS (padrão: +25%% para 1.25x)")
    parser.add_argument("--workers", type=int, default=4, help="Quantidade de threads para download e visão")
    parser.add_argument("--status", action="store_true", help="Exibe apenas o status dos batches e encerra")
    parser.add_argument("--rebuild", action="store_true", help="Reconstrói o arquivo global_state.json a partir do disco")
    
    args = parser.parse_args()

    runner = AutoPipelineRunner(
        checkpoint_dir=args.checkpoint_dir,
        videos_per_batch=args.batch_size,
        model_name=args.model,
        voice=args.voice,
        rate=args.rate,
        max_workers=args.workers
    )

    if args.rebuild:
        print("[*] Reconstruindo estado global a partir da pasta checkpoint no disco...")
        runner.checkpoint_mgr.rebuild_global_state_from_disk()
        runner.show_status()
        return

    if args.status:
        runner.show_status()
        return

    # Trava de instância única para impedir execuções duplicadas / concorrentes
    lock_path = os.path.join(runner.checkpoint_mgr.root_dir, ".pipeline.lock")
    instance_lock = SingleInstanceLock(lock_path)
    if not instance_lock.acquire():
        print("\n" + "=" * 75)
        print("⚠️  [AutoPipeline] AVISO: Uma instância do pipeline já está em execução!")
        print("    Para evitar concorrência e corrupção de checkpoints, esta instância foi encerrada.")
        print("=" * 75 + "\n")
        app_logger.warning("[AutoPipeline] Tentativa de execução duplicada bloqueada com sucesso pelo lock.")
        return

    try:
        runner.run_loop(max_batches=args.max_batches)
    finally:
        instance_lock.release()

if __name__ == "__main__":
    main()
