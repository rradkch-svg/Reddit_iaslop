import os
import re
import json
import time
import shutil
import difflib
from typing import Dict, Any, List, Optional, Tuple, Union

try:
    from .logger import app_logger, LogSpan
    from .deduplication import sanitize_and_cap_title, extract_canonical_entity, DEFAULT_CONTEXTUAL_AUDITOR, ContextualTopicAuditor
except ImportError:
    from logger import app_logger, LogSpan
    from deduplication import sanitize_and_cap_title, extract_canonical_entity, DEFAULT_CONTEXTUAL_AUDITOR, ContextualTopicAuditor

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CHECKPOINT_ROOT = os.environ.get("CHECKPOINT_DIR") or os.path.join(PROJECT_ROOT, "checkpoint")
VIDEOS_PER_BATCH = 10

class CheckpointManager:
    """
    Gerenciador centralizado de Checkpoints, Batches (batch_0 .. batch_N),
    Vídeos Individuais (video_0 .. video_9) e Blacklist de temas não-repetíveis.
    Garante persistência atômica e auto-recuperação resiliente contra quedas de energia.
    """

    def __init__(self, root_dir: Optional[str] = None, videos_per_batch: int = VIDEOS_PER_BATCH):
        self.root_dir = os.path.abspath(root_dir or DEFAULT_CHECKPOINT_ROOT)
        self.videos_per_batch = videos_per_batch
        
        # Dual Blacklist files: Pure Shorts vs Long Videos
        self.blacklist_shorts_file = os.path.join(self.root_dir, "blacklist_shorts.json")
        self.blacklist_shorts_txt = os.path.join(self.root_dir, "blacklist_shorts.txt")
        self.blacklist_longform_file = os.path.join(self.root_dir, "blacklist_longform.json")
        self.blacklist_longform_txt = os.path.join(self.root_dir, "blacklist_longform.txt")
        
        # Legacy compatibility aliases (point to shorts by default)
        self.blacklist_file = self.blacklist_shorts_file
        self.blacklist_txt = self.blacklist_shorts_txt
        self.global_state_file = os.path.join(self.root_dir, "global_state.json")
        
        # Garante a criação da pasta raiz de checkpoints
        os.makedirs(self.root_dir, exist_ok=True)
        self._init_blacklist_if_needed()
        self._init_global_state_if_needed()

    # =========================================================================
    # 1. GESTÃO DE DUAL BLACKLIST (SHORTS vs LONG VIDEOS)
    # =========================================================================

    def _normalize_video_type(self, video_type: Optional[str]) -> str:
        """Normaliza a identificação do formato: 'shorts' ou 'longform'."""
        if not video_type:
            return "shorts"
        v = str(video_type).lower().strip()
        if v in ("long", "longform", "long_video", "long_videos", "25min", "compilation", "saga", "horizontal", "16:9"):
            return "longform"
        return "shorts"

    def _get_blacklist_paths(self, video_type: str = "shorts") -> Tuple[str, str, str]:
        """Retorna (json_file, txt_file, label) correspondente ao formato de vídeo."""
        v_type = self._normalize_video_type(video_type)
        if v_type == "longform":
            return self.blacklist_longform_file, self.blacklist_longform_txt, "Long Videos (16:9 / 25-Min Sagas)"
        return self.blacklist_shorts_file, self.blacklist_shorts_txt, "Pure Shorts (9:16)"

    def _init_blacklist_if_needed(self):
        """Inicializa os arquivos das 2 blacklists caso não existam, migrando dados legados se presentes."""
        legacy_json = os.path.join(self.root_dir, "blacklist.json")
        legacy_txt = os.path.join(self.root_dir, "blacklist.txt")

        for v_type in ["shorts", "longform"]:
            json_file, txt_file, label = self._get_blacklist_paths(v_type)
            if not os.path.exists(json_file):
                if v_type == "shorts" and os.path.exists(legacy_json):
                    try:
                        shutil.copyfile(legacy_json, json_file)
                    except Exception:
                        pass
                if not os.path.exists(json_file):
                    initial_data = {
                        "version": 1,
                        "format": v_type,
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "total_items": 0,
                        "items": []
                    }
                    self._save_json_atomic(json_file, initial_data)

            if not os.path.exists(txt_file):
                if v_type == "shorts" and os.path.exists(legacy_txt):
                    try:
                        shutil.copyfile(legacy_txt, txt_file)
                    except Exception:
                        pass
                if not os.path.exists(txt_file):
                    try:
                        with open(txt_file, "w", encoding="utf-8") as f:
                            f.write(f"# Blacklist de Temas - {label} (Evita Repetição)\n")
                            f.write(f"# Criado em: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    except Exception:
                        pass

    def load_blacklist(self, video_type: str = "shorts") -> List[Dict[str, Any]]:
        """Carrega a lista de itens da blacklist correspondente ao formato ('shorts' ou 'longform')."""
        json_file, _, _ = self._get_blacklist_paths(video_type)
        try:
            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("items", [])
        except Exception as e:
            app_logger.warning(f"[CheckpointManager] Erro ao carregar {os.path.basename(json_file)}: {str(e)}")
        return []

    def get_blacklist_titles(self, video_type: str = "shorts") -> List[str]:
        """Retorna apenas os títulos e entidades principais da blacklist especificada."""
        items = self.load_blacklist(video_type=video_type)
        titles = []
        for it in items:
            t = it.get("tema") or it.get("core_entity")
            if t and t not in titles:
                titles.append(t)
        return titles

    def is_in_blacklist(self, candidate_topic: Union[str, Dict[str, Any]], video_type: str = "shorts", threshold: float = 0.68) -> Tuple[bool, str]:
        """
        Verifica se um tema proposto é idêntico ou semanticamente duplicado
        em relação à blacklist correspondente ao formato de vídeo ('shorts' ou 'longform').
        """
        if not candidate_topic:
            return False, ""

        items = self.load_blacklist(video_type=video_type)
        if not items:
            return False, ""

        is_dup, score, reason = DEFAULT_CONTEXTUAL_AUDITOR.evaluate_candidate(
            candidate_topic=candidate_topic,
            existing_items=items
        )
        return is_dup, reason

    def add_to_blacklist(self, topic_data: Any, batch_name: str, video_name: str, video_type: str = "shorts") -> bool:
        """
        Registra imediatamente um tema na Blacklist do formato especificado ('shorts' ou 'longform').
        Sanitiza o título para nunca ultrapassar 100 caracteres e remove clichês.
        """
        if isinstance(topic_data, str):
            topic_data = {"tema": topic_data}
        raw_title = topic_data.get("tema") or topic_data.get("titulo") or topic_data.get("title") or topic_data.get("main_title") or ""
        tema_title = sanitize_and_cap_title(raw_title)
        if not tema_title:
            return False

        # Extrai entidade canônica
        core_entity = topic_data.get("core_entity") or extract_canonical_entity(tema_title)
        v_norm = self._normalize_video_type(video_type)
        json_file, txt_file, label = self._get_blacklist_paths(v_norm)

        items = self.load_blacklist(video_type=v_norm)
        
        # Evita duplicar no próprio arquivo se já estiver presente
        for it in items:
            if it.get("tema") == tema_title:
                return True

        new_entry = {
            "tema": tema_title,
            "core_entity": core_entity,
            "format": v_norm,
            "hook": topic_data.get("hook") or topic_data.get("hook_text") or "",
            "explicacao_tecnica": topic_data.get("explicacao_tecnica") or topic_data.get("body") or "",
            "batch": batch_name,
            "video": video_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        items.append(new_entry)

        payload = {
            "version": 1,
            "format": v_norm,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_items": len(items),
            "items": items
        }

        self._save_json_atomic(json_file, payload)

        # Atualiza o arquivo txt legível
        try:
            with open(txt_file, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{batch_name}/{video_name}] {tema_title}\n")
        except Exception as e:
            app_logger.warning(f"[CheckpointManager] Erro ao gravar {os.path.basename(txt_file)}: {str(e)}")

        app_logger.info(f"[CheckpointManager] Blacklist ({v_norm}) atualizada com: '{tema_title}' ({batch_name}/{video_name})")
        return True

    def remove_from_blacklist(self, keyword: str, video_type: Optional[str] = None) -> int:
        """
        Remove todas as entradas da(s) Blacklist(s) que contenham a palavra-chave no tema ou na entidade.
        Se video_type for fornecido ('shorts' ou 'longform'), remove apenas daquele formato.
        Se video_type for None, remove de ambas as blacklists.
        Retorna a quantidade total de itens removidos.
        """
        targets = [self._normalize_video_type(video_type)] if video_type else ["shorts", "longform"]
        total_removed = 0
        kw = keyword.lower().strip()

        for v_type in targets:
            json_file, txt_file, label = self._get_blacklist_paths(v_type)
            items = self.load_blacklist(video_type=v_type)
            initial_count = len(items)

            filtered_items = [
                it for it in items
                if kw not in it.get("tema", "").lower() and kw not in it.get("core_entity", "").lower()
            ]

            removed_count = initial_count - len(filtered_items)
            if removed_count > 0:
                total_removed += removed_count
                payload = {
                    "version": 1,
                    "format": v_type,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "total_items": len(filtered_items),
                    "items": filtered_items
                }
                self._save_json_atomic(json_file, payload)

                # Reconstrói o txt limpo
                try:
                    with open(txt_file, "w", encoding="utf-8") as f:
                        f.write(f"# Blacklist de Temas - {label} (Evita Repetição)\n")
                        f.write(f"# Atualizado em: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        for it in filtered_items:
                            b = it.get("batch", "batch_0")
                            v = it.get("video", "video_0")
                            ts = it.get("timestamp", time.strftime('%Y-%m-%d %H:%M:%S')).replace("T", " ")
                            t = it.get("tema", "")
                            f.write(f"[{ts}] [{b}/{v}] {t}\n")
                except Exception as e:
                    app_logger.warning(f"[CheckpointManager] Erro ao regravar {os.path.basename(txt_file)}: {str(e)}")

                app_logger.info(f"[CheckpointManager] {removed_count} item(ns) contendo '{keyword}' removido(s) da blacklist ({v_type}).")

        return total_removed

    def purge_batch(self, batch_name: str) -> bool:
        """
        Descarta e desconsidera um batch por completo:
        1. Remove todas as entradas do batch de AMBAS as Blacklists (shorts e longform).
        2. Remove o batch do global_state.json e recalcula total_videos_completed.
        3. Exclui a pasta do batch no disco.
        """
        # 1. Limpeza em ambas as Blacklists
        for v_type in ["shorts", "longform"]:
            json_file, txt_file, label = self._get_blacklist_paths(v_type)
            items = self.load_blacklist(video_type=v_type)
            filtered_items = [it for it in items if it.get("batch") != batch_name]
            if len(filtered_items) != len(items):
                payload = {
                    "version": 1,
                    "format": v_type,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "total_items": len(filtered_items),
                    "items": filtered_items
                }
                self._save_json_atomic(json_file, payload)
                try:
                    with open(txt_file, "w", encoding="utf-8") as f:
                        f.write(f"# Blacklist de Temas - {label} (Evita Repetição)\n")
                        f.write(f"# Atualizado em: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        for it in filtered_items:
                            b = it.get("batch", "batch_0")
                            v = it.get("video", "video_0")
                            ts = it.get("timestamp", time.strftime('%Y-%m-%d %H:%M:%S')).replace("T", " ")
                            t = it.get("tema", "")
                            f.write(f"[{ts}] [{b}/{v}] {t}\n")
                except Exception as e:
                    app_logger.warning(f"[CheckpointManager] Erro ao regravar {os.path.basename(txt_file)}: {str(e)}")

        # 2. Exclusão física da pasta do batch
        batch_dir = os.path.join(self.root_dir, batch_name)
        if not os.path.exists(batch_dir):
            # Tenta dentro de auto_batches/
            auto_b_dir = os.path.join(self.root_dir, "auto_batches", batch_name)
            if os.path.exists(auto_b_dir):
                batch_dir = auto_b_dir

        if os.path.exists(batch_dir):
            try:
                shutil.rmtree(batch_dir)
                app_logger.info(f"[CheckpointManager] Pasta {batch_dir} excluída do disco.")
            except Exception as e:
                app_logger.error(f"[CheckpointManager] Erro ao excluir pasta {batch_dir}: {str(e)}")

        # 3. Atualização e reconstrução do global_state.json
        state = self.load_global_state()
        if batch_name in state.get("batches", {}):
            del state["batches"][batch_name]

        total_comp = sum(
            len([v for v, st in b_data.get("videos", {}).items() if st == "COMPLETED"])
            for b_data in state.get("batches", {}).values()
        )
        state["total_videos_completed"] = total_comp
        state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        existing_indices = [
            int(b.replace("batch_", "")) for b in state.get("batches", {}).keys() if b.startswith("batch_")
        ]
        next_idx = max(existing_indices) + 1 if existing_indices else 0
        state["current_batch_index"] = next_idx

        self.save_global_state(state)
        app_logger.info(f"[CheckpointManager] Batch '{batch_name}' expurgado com sucesso. Total de vídeos válidos: {total_comp}.")
        return True

    # =========================================================================
    # 2. GESTÃO DE ESTADO GLOBAL E RECUPERAÇÃO DE BATCHES
    # =========================================================================

    def _init_global_state_if_needed(self):
        """Inicializa ou reconstrói o arquivo global_state.json."""
        if not os.path.exists(self.global_state_file):
            self.rebuild_global_state_from_disk()

    def load_global_state(self) -> Dict[str, Any]:
        """Lê o estado global com fallback para reconstrução a partir do disco."""
        try:
            if os.path.exists(self.global_state_file):
                with open(self.global_state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            app_logger.warning(f"[CheckpointManager] Erro ao ler global_state.json: {str(e)}. Reconstruindo...")
        return self.rebuild_global_state_from_disk()

    def save_global_state(self, state: Dict[str, Any]):
        """Salva o estado global de forma atômica."""
        state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_json_atomic(self.global_state_file, state)

    def rebuild_global_state_from_disk(self) -> Dict[str, Any]:
        """
        Escaneia fisicamente a pasta checkpoint/ no disco e reconstrói o estado global exato.
        Mecanismo crucial para recuperação de pane ou falta de luz.
        """
        app_logger.info("[CheckpointManager] Escaneando disco para reconstruir estado global...")
        
        batch_dirs = []
        if os.path.exists(self.root_dir):
            for name in os.listdir(self.root_dir):
                if os.path.isdir(os.path.join(self.root_dir, name)) and name.startswith("batch_"):
                    try:
                        num = int(name.split("_")[1])
                        batch_dirs.append((num, name))
                    except (ValueError, IndexError):
                        pass

        batch_dirs.sort(key=lambda x: x[0])
        
        batches_dict = {}
        total_completed_videos = 0
        current_active_batch_idx = 0

        for num, b_name in batch_dirs:
            b_dir = os.path.join(self.root_dir, b_name)
            
            # Checa vídeos dentro deste batch
            videos_status = {}
            completed_in_batch = 0

            for v_idx in range(self.videos_per_batch):
                v_name = f"video_{v_idx}"
                v_dir = os.path.join(b_dir, v_name)
                v_ckpt_path = os.path.join(v_dir, "checkpoint.json")
                
                v_status = "PENDING"
                if os.path.exists(v_ckpt_path):
                    try:
                        with open(v_ckpt_path, "r", encoding="utf-8") as f:
                            v_data = json.load(f)
                            v_status = v_data.get("status", "PENDING")
                    except:
                        pass
                
                # Validação física de integridade
                final_video_file = os.path.join(v_dir, "final_video.mp4")
                if os.path.exists(final_video_file) and os.path.getsize(final_video_file) > 100_000:
                    v_status = "COMPLETED"

                videos_status[v_name] = v_status
                if v_status == "COMPLETED":
                    completed_in_batch += 1
                    total_completed_videos += 1

            batch_status = "COMPLETED" if completed_in_batch >= self.videos_per_batch else "IN_PROGRESS"
            batches_dict[b_name] = {
                "batch_index": num,
                "status": batch_status,
                "completed_videos_count": completed_in_batch,
                "total_videos": self.videos_per_batch,
                "videos": videos_status
            }

            if batch_status == "IN_PROGRESS" and current_active_batch_idx == 0:
                current_active_batch_idx = num

        # Se todos os batches existentes estiverem completos, o ativo é o próximo
        if batch_dirs:
            last_num = batch_dirs[-1][0]
            if batches_dict[batch_dirs[-1][1]]["status"] == "COMPLETED":
                current_active_batch_idx = last_num + 1

        state = {
            "version": 1,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "current_batch_index": current_active_batch_idx,
            "total_videos_completed": total_completed_videos,
            "batches": batches_dict
        }

        self._save_json_atomic(self.global_state_file, state)
        return state

    # =========================================================================
    # 3. GESTÃO DE CHECKPOINT POR VÍDEO (RESTAURAÇÃO DE ETAPAS)
    # =========================================================================

    def get_batch_dir(self, batch_index: int) -> str:
        """Retorna o caminho da pasta do batch (ex: checkpoint/batch_0)."""
        b_dir = os.path.join(self.root_dir, f"batch_{batch_index}")
        os.makedirs(b_dir, exist_ok=True)
        return b_dir

    def get_video_dir(self, batch_index: int, video_index: int) -> str:
        """Retorna o caminho da pasta do vídeo (ex: checkpoint/batch_0/video_3)."""
        b_dir = self.get_batch_dir(batch_index)
        v_dir = os.path.join(b_dir, f"video_{video_index}")
        os.makedirs(v_dir, exist_ok=True)
        return v_dir

    def get_video_checkpoint_path(self, batch_index: int, video_index: int) -> str:
        """Retorna o caminho do arquivo checkpoint.json do vídeo."""
        v_dir = self.get_video_dir(batch_index, video_index)
        return os.path.join(v_dir, "checkpoint.json")

    def load_video_checkpoint(self, batch_index: int, video_index: int) -> Dict[str, Any]:
        """Carrega os dados de checkpoint de um vídeo específico."""
        ckpt_path = self.get_video_checkpoint_path(batch_index, video_index)
        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                app_logger.warning(f"[CheckpointManager] Erro ao ler checkpoint ({batch_index}/{video_index}): {str(e)}")
        
        # Checkpoint novo padrão
        return {
            "batch_index": batch_index,
            "video_index": video_index,
            "batch_name": f"batch_{batch_index}",
            "video_name": f"video_{video_index}",
            "status": "PENDING", # PENDING, TOPIC_READY, STORYBOARD_READY, AUDIO_READY, SUBTITLES_READY, SCENES_READY, COMPLETED, FAILED
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "topic": {},
            "storyboard": [],
            "audio_file": "audio.mp3",
            "audio_duration": 0.0,
            "words_timing": [],
            "subtitles_file": "subtitles.ass",
            "scene_clips": [],
            "scene_audits": [],
            "final_video_file": "final_video.mp4",
            "final_video_size_bytes": 0,
            "error": None,
            "retry_count": 0
        }

    def save_video_checkpoint(self, batch_index: int, video_index: int, data: Dict[str, Any]):
        """Salva atomicamente o checkpoint do vídeo."""
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        ckpt_path = self.get_video_checkpoint_path(batch_index, video_index)
        self._save_json_atomic(ckpt_path, data)

    def determine_video_resume_stage(self, batch_index: int, video_index: int) -> Tuple[str, Dict[str, Any]]:
        """
        Analisa o checkpoint gravado e os arquivos físicos no disco para determinar
        exatamente de qual etapa retomar a geração deste vídeo.
        
        Retorna (stage_name, checkpoint_data):
        - 'COMPLETED': Vídeo final renderizado e íntegro no disco.
        - 'RENDER_FINAL': Todas as cenas, áudio e legendas prontos, falta apenas o render do FFmpeg.
        - 'PROCESS_SCENES': Áudio e storyboard prontos, faltam baixar/auditar clipes.
        - 'GENERATE_SUBTITLES': Áudio pronto, falta compilar legendas ASS.
        - 'GENERATE_AUDIO': Storyboard pronto, falta gerar narração Edge-TTS.
        - 'GENERATE_STORYBOARD': Tema pronto, falta roteirizar cenas.
        - 'GENERATE_TOPIC': Vídeo em branco, necessita propor novo tema com IA.
        """
        ckpt = self.load_video_checkpoint(batch_index, video_index)
        v_dir = self.get_video_dir(batch_index, video_index)
        
        final_mp4 = os.path.join(v_dir, ckpt.get("final_video_file", "final_video.mp4"))
        audio_mp3 = os.path.join(v_dir, ckpt.get("audio_file", "audio.mp3"))
        subtitles_ass = os.path.join(v_dir, ckpt.get("subtitles_file", "subtitles.ass"))
        storyboard = ckpt.get("storyboard", [])
        topic = ckpt.get("topic", {})

        # 1. Verifica se vídeo final já está 100% concluído e íntegro
        if os.path.exists(final_mp4) and os.path.getsize(final_mp4) > 100_000:
            ckpt["status"] = "COMPLETED"
            ckpt["final_video_size_bytes"] = os.path.getsize(final_mp4)
            self.save_video_checkpoint(batch_index, video_index, ckpt)
            return "COMPLETED", ckpt

        # 2. Verifica se o tema foi definido
        if not topic or not topic.get("tema"):
            return "GENERATE_TOPIC", ckpt

        # 3. Verifica se storyboard foi gerado
        if not storyboard or not isinstance(storyboard, list) or len(storyboard) < 3:
            return "GENERATE_STORYBOARD", ckpt

        # 4. Verifica se áudio foi sintetizado
        if not os.path.exists(audio_mp3) or os.path.getsize(audio_mp3) < 5_000 or not ckpt.get("words_timing"):
            return "GENERATE_AUDIO", ckpt

        # 5. Verifica se legendas ASS existem
        if not os.path.exists(subtitles_ass) or os.path.getsize(subtitles_ass) < 10:
            return "GENERATE_SUBTITLES", ckpt

        # 6. Verifica se todos os clipes de cenas existem no disco
        scene_clips = ckpt.get("scene_clips", [])
        all_scenes_exist = False
        if scene_clips and len(scene_clips) >= min(len(storyboard), 3):
            all_scenes_exist = all(os.path.exists(cp) and os.path.getsize(cp) > 10_000 for cp in scene_clips)

        if not all_scenes_exist:
            return "PROCESS_SCENES", ckpt

        # 7. Todas as partes estão prontas, falta renderizar
        return "RENDER_FINAL", ckpt

    def get_next_work_target(self) -> Tuple[int, int, str, str]:
        """
        Determina o próximo batch e vídeo que precisa de trabalho.
        Garante transição automática de batch_0 para batch_1 .. batch_N.
        """
        state = self.load_global_state()
        current_batch_idx = state.get("current_batch_index", 0)

        # Procura a partir do batch atual
        for b_idx in range(current_batch_idx, current_batch_idx + 1000):
            b_dir = self.get_batch_dir(b_idx)
            completed_in_this_batch = 0

            for v_idx in range(self.videos_per_batch):
                stage, ckpt = self.determine_video_resume_stage(b_idx, v_idx)
                if stage == "COMPLETED":
                    completed_in_this_batch += 1
                else:
                    # Encontrou o primeiro vídeo que precisa de processamento!
                    state["current_batch_index"] = b_idx
                    self.save_global_state(state)
                    return b_idx, v_idx, f"batch_{b_idx}", f"video_{v_idx}"

            # Se todos os 10 vídeos deste batch estiverem completos, continua para o próximo batch
            if completed_in_this_batch >= self.videos_per_batch:
                continue

        # Fallback
        return current_batch_idx, 0, f"batch_{current_batch_idx}", "video_0"

    def mark_video_completed(self, batch_index: int, video_index: int, final_video_path: str):
        """Marca o vídeo como COMPLETED e atualiza estado global e batch."""
        ckpt = self.load_video_checkpoint(batch_index, video_index)
        ckpt["status"] = "COMPLETED"
        ckpt["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if os.path.exists(final_video_path):
            ckpt["final_video_size_bytes"] = os.path.getsize(final_video_path)
            ckpt["final_video_path"] = final_video_path
        self.save_video_checkpoint(batch_index, video_index, ckpt)

        # Atualiza o estado global
        state = self.load_global_state()
        batches = state.setdefault("batches", {})
        b_name = f"batch_{batch_index}"
        b_info = batches.setdefault(b_name, {
            "batch_index": batch_index,
            "status": "IN_PROGRESS",
            "completed_videos_count": 0,
            "total_videos": self.videos_per_batch,
            "videos": {}
        })

        b_info.setdefault("videos", {})[f"video_{video_index}"] = "COMPLETED"
        
        # Conta vídeos concluídos neste batch
        completed_cnt = sum(1 for st in b_info["videos"].values() if st == "COMPLETED")
        b_info["completed_videos_count"] = completed_cnt
        if completed_cnt >= self.videos_per_batch:
            b_info["status"] = "COMPLETED"
            b_info["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            state["current_batch_index"] = max(state.get("current_batch_index", 0), batch_index + 1)

        # Recalcula total de vídeos concluídos
        total_comp = 0
        for b in batches.values():
            for v_st in b.get("videos", {}).values():
                if v_st == "COMPLETED":
                    total_comp += 1
        state["total_videos_completed"] = total_comp
        self.save_global_state(state)

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def _normalize_topic_string(self, text: str) -> str:
        """Normaliza uma string de tema para comparação robusta."""
        t = text.lower()
        t = re.sub(r"[^\w\s]", " ", t)
        words = [w.strip() for w in t.split() if w.strip() and len(w.strip()) > 1]
        # Remove stopwords comuns
        stopwords = {"o", "a", "os", "as", "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas",
                     "por", "que", "com", "como", "funciona", "segredo", "fisica", "engenharia", "tudo", "sobre"}
        filtered = [w for w in words if w not in stopwords]
        return " ".join(filtered)

    def _extract_core_entity(self, text: str) -> str:
        """Extrai o modelo/veículo principal do tema."""
        parts = text.split(":")
        main_part = parts[0] if len(parts) > 1 else text
        cleaned = re.sub(r"^(O Segredo d[oa]|Como funciona o|Por que o|A física d[oa]|A engenharia d[oa]|Tudo sobre o|O Motor d[oa]|A Asa d[oa]|A Suspensão d[oa])\s*", "", main_part, flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
        cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|para|sobre|o|a|os|as)\b", " ", cleaned, flags=re.IGNORECASE)
        words = [w.strip() for w in cleaned.split() if w.strip()]
        return " ".join(words[:6]) if words else text.strip()

    def _save_json_atomic(self, file_path: str, data: Dict[str, Any]):
        """Grava JSON de forma atômica para evitar corrupção em caso de queda de energia."""
        temp_file = f"{file_path}.tmp_{os.getpid()}_{int(time.time()*1000)}"
        parent_dir = os.path.dirname(file_path)
        os.makedirs(parent_dir, exist_ok=True)
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            # Replace atômico
            if os.path.exists(file_path):
                os.replace(temp_file, file_path)
            else:
                os.rename(temp_file, file_path)
        except Exception as e:
            app_logger.error(f"[CheckpointManager] Erro na gravação atômica de '{file_path}': {str(e)}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise e

    @staticmethod
    def extract_story_metadata_from_folder(v_path: str, is_longform: bool) -> Optional[Dict[str, Any]]:
        """
        Extrai de forma resiliente metadados estruturados (tema, hook, body, etc.)
        a partir de arquivos de roteiro (script_data.json) ou metadados (metadata.txt, etc.).
        """
        # 1. Procura script_data.json (prioridade estruturada)
        script_candidates = [
            os.path.join(v_path, "longform_25min", "script_data.json"),
            os.path.join(v_path, "script_data.json"),
            os.path.join(v_path, "teaser_short", "script_data.json"),
        ] if is_longform else [
            os.path.join(v_path, "script_data.json"),
            os.path.join(v_path, "teaser_short", "script_data.json"),
        ]

        for sc_file in script_candidates:
            if os.path.exists(sc_file):
                try:
                    with open(sc_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    title = data.get("tema") or data.get("title") or data.get("main_title") or data.get("titulo")
                    if title:
                        return {
                            "tema": title,
                            "core_entity": data.get("core_entity"),
                            "hook": data.get("hook") or data.get("hook_text") or data.get("opening_hook", ""),
                            "explicacao_tecnica": data.get("explicacao_tecnica") or data.get("body") or data.get("shorts_script") or data.get("longform_script", "")
                        }
                except Exception:
                    pass

        # 2. Procura metadata.txt / metadata_youtube.txt / metadata_teaser.txt
        meta_candidates = [
            os.path.join(v_path, "metadata.txt"),
            os.path.join(v_path, "metadata_youtube.txt"),
            os.path.join(v_path, "longform_25min", "metadata.txt"),
            os.path.join(v_path, "longform_25min", "metadata_youtube.txt"),
            os.path.join(v_path, "teaser_short", "metadata_teaser.txt")
        ]

        for mf in meta_candidates:
            if os.path.exists(mf):
                try:
                    with open(mf, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    lines = [l.strip() for l in content.split("\n")]
                    title = None
                    hook = None
                    body = None
                    for idx, line in enumerate(lines):
                        if not title and re.search(r"\b(T[ÍI]TULO|TITLE)\b", line, re.IGNORECASE):
                            if ":" in line and len(line.split(":", 1)[1].strip()) > 3:
                                title = line.split(":", 1)[1].strip()
                            else:
                                for next_line in lines[idx + 1: idx + 4]:
                                    if next_line and not next_line.startswith("#") and not re.search(r"\b(DESCRI[ÇC][ÃA]O|DESCRIPTION)\b", next_line, re.IGNORECASE):
                                        title = next_line
                                        break
                        if not hook and re.search(r"\b(GANCHO|HOOK)\b", line, re.IGNORECASE):
                            if ":" in line and len(line.split(":", 1)[1].strip()) > 3:
                                hook = line.split(":", 1)[1].strip()
                        if not body and re.search(r"\b(DESCRI[ÇC][ÃA]O|DESCRIPTION)\b", line, re.IGNORECASE):
                            for next_line in lines[idx + 1: idx + 5]:
                                if next_line and not next_line.startswith("#") and not re.search(r"\b(HASHTAGS|TAGS)\b", next_line, re.IGNORECASE):
                                    body = next_line
                                    break

                    if title:
                        return {
                            "tema": title,
                            "hook": hook or "",
                            "explicacao_tecnica": body or ""
                        }
                except Exception:
                    pass

        return None

    def sync_blacklists_from_batches(self, base_batches_dir: Optional[str] = None) -> Dict[str, int]:
        """
        Varre todos os diretórios de batches no disco (ex: checkpoint/auto_batches/batch_1/video_0..)
        e sincroniza os temas nas 2 Blacklists isoladas:
        - video_0 (ou que possua subpasta longform_25min / compilação) -> blacklist_longform
        - video_1..video_9 (ou teaser_short / shorts clássicos) -> blacklist_shorts
        Retorna a quantidade de itens adicionados em cada blacklist: {'shorts': N, 'longform': M}.
        """
        search_dirs = []
        if base_batches_dir and os.path.exists(base_batches_dir):
            search_dirs.append(base_batches_dir)
        auto_dir = os.path.join(self.root_dir, "auto_batches")
        if os.path.exists(auto_dir) and auto_dir not in search_dirs:
            search_dirs.append(auto_dir)
        if self.root_dir not in search_dirs:
            search_dirs.append(self.root_dir)

        shorts_added = 0
        longform_added = 0

        for base_p in search_dirs:
            if not os.path.exists(base_p):
                continue
            for b_name in sorted(os.listdir(base_p)):
                b_path = os.path.join(base_p, b_name)
                if not os.path.isdir(b_path) or not re.match(r"^batch_\d+$", b_name, re.IGNORECASE):
                    continue

                for v_name in sorted(os.listdir(b_path)):
                    v_path = os.path.join(b_path, v_name)
                    if not os.path.isdir(v_path) or not re.match(r"^video_\d+$", v_name, re.IGNORECASE):
                        continue

                    m = re.match(r"^video_(\d+)$", v_name, re.IGNORECASE)
                    v_num = int(m.group(1)) if m else -1
                    is_longform = (v_num == 0) or os.path.exists(os.path.join(v_path, "longform_25min"))

                    story_data = self.extract_story_metadata_from_folder(v_path, is_longform=is_longform)
                    if story_data:
                        v_type = "longform" if is_longform else "shorts"
                        raw_title = story_data.get("tema") or story_data.get("title") or story_data.get("titulo") or story_data.get("main_title") or ""
                        if raw_title:
                            ex_titles = self.get_blacklist_titles(video_type=v_type)
                            sanitized = sanitize_and_cap_title(raw_title)
                            if sanitized and sanitized not in ex_titles:
                                if self.add_to_blacklist(story_data, batch_name=b_name, video_name=v_name, video_type=v_type):
                                    if is_longform:
                                        longform_added += 1
                                    else:
                                        shorts_added += 1

        app_logger.info(f"[CheckpointManager] Sincronização de Batches concluída: +{shorts_added} Shorts, +{longform_added} Longform.")
        return {"shorts_synced": shorts_added, "longform_synced": longform_added}

# Instância singleton padrão
DEFAULT_CHECKPOINT_MANAGER = CheckpointManager()
