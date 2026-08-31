import os
import re
import json
import glob
import shutil
from typing import Dict, Any, List, Optional, Tuple

class BatchManager:
    """
    Gerenciador de organização em lotes:
    - Organiza vídeos em: checkpoint/auto_batches/batch_1, batch_2...
    - Cada lote contém exatamente 10 vídeos numerados: video_0, video_1 ... video_9
    - Progressão e transição automática para o próximo batch quando 10 vídeos forem concluídos.
    """
    def __init__(self, base_dir: str = "checkpoint/auto_batches", batch_size: int = 10):
        self.base_dir = os.path.abspath(base_dir)
        self.batch_size = batch_size
        os.makedirs(self.base_dir, exist_ok=True)

    def is_slot_completed(self, video_dir: str) -> bool:
        """Verifica se o diretório do vídeo (ou suas subpastas longform/teaser_short) possui uma renderização concluída ou dados válidos."""
        if not os.path.exists(video_dir) or not os.path.isdir(video_dir):
            return False
        mp4_files = glob.glob(os.path.join(video_dir, "*.mp4")) + glob.glob(os.path.join(video_dir, "**", "*.mp4"), recursive=True)
        if mp4_files and any(os.path.getsize(f) > 10000 for f in mp4_files):
            return True
        script_files = glob.glob(os.path.join(video_dir, "script_data.json")) + glob.glob(os.path.join(video_dir, "**", "script_data.json"), recursive=True)
        for script_path in script_files:
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data and ("shorts_script" in data or "chapters" in data):
                    return True
            except Exception:
                pass
        return False

    def list_batches(self) -> List[int]:
        """Retorna a lista ordenada dos números de batches existentes (ex: [1, 2])."""
        if not os.path.exists(self.base_dir):
            return []
        batches = []
        for name in os.listdir(self.base_dir):
            full_p = os.path.join(self.base_dir, name)
            if os.path.isdir(full_p):
                m = re.match(r"^batch_(\d+)$", name, re.IGNORECASE)
                if m:
                    batches.append(int(m.group(1)))
        return sorted(batches)

    def get_batch_videos(self, batch_num: int) -> List[int]:
        """Retorna os índices numéricos de vídeos existentes dentro de batch_N (ex: [0, 1, 2])."""
        batch_dir = os.path.join(self.base_dir, f"batch_{batch_num}")
        if not os.path.exists(batch_dir):
            return []
        videos = []
        for name in os.listdir(batch_dir):
            full_p = os.path.join(batch_dir, name)
            if os.path.isdir(full_p):
                m = re.match(r"^video_(\d+)$", name, re.IGNORECASE)
                if m:
                    v_num = int(m.group(1))
                    if self.is_slot_completed(full_p):
                        videos.append(v_num)
        return sorted(videos)

    def get_next_video_slot(self) -> Tuple[str, int, int]:
        """
        Determina o próximo slot de vídeo (batch_X/video_Y).
        Garante exatamente 10 vídeos (video_0 a video_9) por batch antes de avançar.
        Retorna (target_dir_path, batch_number, video_number).
        """
        batches = self.list_batches()
        if not batches:
            target_batch = 1
            target_video = 0
        else:
            latest_batch = batches[-1]
            existing_videos = self.get_batch_videos(latest_batch)
            
            # Encontra o próximo índice livre entre 0 e (batch_size - 1)
            next_idx = None
            for idx in range(self.batch_size):
                if idx not in existing_videos:
                    next_idx = idx
                    break

            if next_idx is not None:
                target_batch = latest_batch
                target_video = next_idx
            else:
                # O batch atual atingiu a cota de 10 vídeos (video_0..video_9)
                target_batch = latest_batch + 1
                target_video = 0

        target_dir = os.path.join(self.base_dir, f"batch_{target_batch}", f"video_{target_video}")
        os.makedirs(target_dir, exist_ok=True)
        return target_dir, target_batch, target_video

    def get_summary(self) -> List[Dict[str, Any]]:
        """Gera um resumo estruturado de todos os batches cadastrados."""
        batches = self.list_batches()
        summary = []
        for b in batches:
            videos = self.get_batch_videos(b)
            summary.append({
                "batch_num": b,
                "batch_name": f"batch_{b}",
                "video_count": len(videos),
                "max_videos": self.batch_size,
                "videos": [f"video_{v}" for v in videos],
                "is_full": len(videos) >= self.batch_size,
                "path": os.path.join(self.base_dir, f"batch_{b}")
            })
        return summary

    def organize_legacy_directories(self) -> int:
        """
        Varre diretórios soltos ou legados (ex: checkpoint/auto_batches/shorts/*, checkpoint/reddit_videos/*)
        e os migra de forma limpa para a estrutura oficial batch_1/video_0, video_1, etc.
        """
        migrated = 0
        if not os.path.exists(self.base_dir):
            return 0

        legacy_folders: List[str] = []
        
        # 1. Procura subpastas não conformes na raiz de auto_batches
        for item in os.listdir(self.base_dir):
            full_path = os.path.join(self.base_dir, item)
            if not os.path.isdir(full_path):
                continue
            if re.match(r"^batch_\d+$", item, re.IGNORECASE):
                continue
            if item.lower() in ("shorts", "longform_25min", "reddit_videos"):
                # Pastas intermediárias antigas
                for sub_item in os.listdir(full_path):
                    sub_full = os.path.join(full_path, sub_item)
                    if os.path.isdir(sub_full):
                        legacy_folders.append(sub_full)
            else:
                legacy_folders.append(full_path)

        # 2. Também verifica pastas legadas soltas no diretório raiz checkpoint/
        parent_dir = os.path.dirname(self.base_dir)
        if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
            for legacy_parent_name in ["reddit_videos", "reddit_longform_25min"]:
                legacy_parent = os.path.join(parent_dir, legacy_parent_name)
                if os.path.exists(legacy_parent) and os.path.isdir(legacy_parent):
                    for sub_item in os.listdir(legacy_parent):
                        sub_full = os.path.join(legacy_parent, sub_item)
                        if os.path.isdir(sub_full) and not re.match(r"^batch_\d+$", sub_item, re.IGNORECASE):
                            legacy_folders.append(sub_full)

        # 3. Ordena pastas legadas por tempo de criação
        legacy_folders.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)

        for folder in legacy_folders:
            if not os.path.exists(folder) or not os.path.isdir(folder):
                continue
            folder_name = os.path.basename(folder)
            if re.match(r"^(batch|video)_\d+$", folder_name, re.IGNORECASE):
                continue

            if self.is_slot_completed(folder):
                try:
                    target_dir, b_num, v_num = self.get_next_video_slot()
                    for f_item in os.listdir(folder):
                        src_f = os.path.join(folder, f_item)
                        dst_f = os.path.join(target_dir, f_item)
                        if os.path.exists(dst_f):
                            if os.path.isdir(dst_f):
                                shutil.rmtree(dst_f, ignore_errors=True)
                            else:
                                try:
                                    os.remove(dst_f)
                                except Exception:
                                    pass
                        try:
                            shutil.move(src_f, dst_f)
                        except Exception:
                            try:
                                if os.path.isdir(src_f):
                                    shutil.copytree(src_f, dst_f, dirs_exist_ok=True)
                                else:
                                    shutil.copy2(src_f, dst_f)
                            except Exception:
                                pass
                    try:
                        shutil.rmtree(folder, ignore_errors=True)
                    except Exception:
                        pass
                    migrated += 1
                except Exception:
                    pass
            else:
                # Diretório incompleto/vazio, remove com segurança
                try:
                    shutil.rmtree(folder, ignore_errors=True)
                except Exception:
                    pass

        # 4. Remove pastas vazias de shorts/longform_25min/reddit_videos
        for extra in ["shorts", "longform_25min"]:
            extra_p = os.path.join(self.base_dir, extra)
            if os.path.exists(extra_p) and os.path.isdir(extra_p):
                try:
                    if not os.listdir(extra_p):
                        os.rmdir(extra_p)
                    else:
                        shutil.rmtree(extra_p, ignore_errors=True)
                except Exception:
                    pass

        if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
            for legacy_parent_name in ["reddit_videos", "reddit_longform_25min"]:
                legacy_parent = os.path.join(parent_dir, legacy_parent_name)
                if os.path.exists(legacy_parent) and os.path.isdir(legacy_parent):
                    try:
                        if not os.listdir(legacy_parent):
                            os.rmdir(legacy_parent)
                    except Exception:
                        pass

        return migrated
