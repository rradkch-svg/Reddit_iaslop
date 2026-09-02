import os
import sys
import glob
import json
import re

# Adiciona o diretório raiz ao sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.reddit_thumbnails import RedditThumbnailEngine
from src.reddit_render import get_orbital_backgrounds


def extract_metadata_from_txt(txt_path: str) -> dict:
    """Extrai informações básicas de metadata_youtube.txt se script_data.json não existir."""
    meta = {
        "title": "Insane Reddit Story",
        "subreddit": "r/AITAH",
        "author": "throwaway_op",
        "score": "45.8k"
    }
    if not os.path.exists(txt_path):
        return meta

    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extrai Título
        m_title = re.search(r"TÍTULO DO VÍDEO[^\n]*:\s*\n([^\n]+)", content, re.IGNORECASE)
        if m_title:
            meta["title"] = m_title.group(1).strip()

        # Extrai Subreddit
        m_sub = re.search(r"Subreddit Original:\s*([^\n]+)", content, re.IGNORECASE)
        if m_sub and m_sub.group(1).strip():
            meta["subreddit"] = m_sub.group(1).strip()

        # Extrai Autor
        m_author = re.search(r"Autor Original:\s*([^\n]+)", content, re.IGNORECASE)
        if m_author and m_author.group(1).strip():
            meta["author"] = m_author.group(1).strip()

    except Exception:
        pass
    return meta


def generate_thumbnails_for_all_batches():
    """Varre todos os batches existentes e gera thumbnails 16:9 (1920x1080) em cada vídeo longo."""
    print("🎨 [Thumbnail Batch Engine] Iniciando varredura de vídeos longos nos lotes...")
    batches_dir = os.path.join(BASE_DIR, "checkpoint", "auto_batches")
    if not os.path.exists(batches_dir):
        print(f"❌ Diretório não encontrado: {batches_dir}")
        return

    engine = RedditThumbnailEngine(brand_name="Reddit Minute")
    backgrounds = get_orbital_backgrounds(aspect_ratio="16:9")
    bg_video = backgrounds[0] if backgrounds else None

    # Localiza todas as pastas de vídeo longo
    search_patterns = [
        os.path.join(batches_dir, "batch_*", "video_*", "longform_25min"),
        os.path.join(batches_dir, "batch_*", "video_0"),
        os.path.join(batches_dir, "manual_batches", "*", "longform_25min")
    ]

    target_dirs = set()
    for pat in search_patterns:
        for found in glob.glob(pat):
            if os.path.isdir(found):
                # Se for video_0 e tiver longform_25min dentro, prioriza longform_25min
                lf_sub = os.path.join(found, "longform_25min")
                if os.path.exists(lf_sub):
                    target_dirs.add(lf_sub)
                else:
                    target_dirs.add(found)

    print(f"📁 Pastas de vídeo longo localizadas: {len(target_dirs)}")
    generated_count = 0

    for idx, lf_dir in enumerate(sorted(target_dirs)):
        script_file = os.path.join(lf_dir, "script_data.json")
        meta_txt_file = os.path.join(lf_dir, "metadata_youtube.txt")

        story_data = {}
        if os.path.exists(script_file):
            try:
                with open(script_file, "r", encoding="utf-8") as f:
                    s_json = json.load(f)
                    story_data["title"] = s_json.get("main_title") or s_json.get("title") or "Reddit Story"
                    story_data["subreddit"] = s_json.get("subreddit", "r/AITAH")
                    story_data["author"] = s_json.get("author", "throwaway_op")
                    story_data["score"] = s_json.get("score", "48.2k")
                    story_data["opening_hook"] = s_json.get("opening_hook", "")
            except Exception:
                story_data = extract_metadata_from_txt(meta_txt_file)
        elif os.path.exists(meta_txt_file):
            story_data = extract_metadata_from_txt(meta_txt_file)
        else:
            story_data = {
                "title": "Insane Reddit Story",
                "subreddit": "r/AITAH",
                "author": "throwaway_op",
                "score": "48.5k"
            }

        # Caminho da Thumbnail
        out_png = os.path.join(lf_dir, "thumbnail_youtube.png")
        out_jpg = os.path.join(lf_dir, "thumbnail_youtube.jpg")

        print(f"\n🖼️ [{idx+1}/{len(target_dirs)}] Gerando Thumbnail para: {os.path.relpath(lf_dir, BASE_DIR)}")
        print(f"   Título: '{story_data.get('title')}'")

        try:
            engine.generate_youtube_thumbnail(
                story_data=story_data,
                output_path=out_png,
                background_video_path=bg_video,
                shock_hook=story_data.get("opening_hook")
            )
            generated_count += 1
            print(f"   ✅ Salvo: {os.path.basename(out_png)} & {os.path.basename(out_jpg)} (1920x1080)")

            # Atualiza metadata_youtube.txt se existir
            if os.path.exists(meta_txt_file):
                try:
                    with open(meta_txt_file, "r", encoding="utf-8") as f:
                        meta_txt_content = f.read()

                    if "THUMBNAILS OFICIAIS" not in meta_txt_content:
                        meta_txt_content += f"""
---------------------------------------------------
🖼️ THUMBNAILS OFICIAIS (1920x1080):
PNG: {out_png}
JPG: {out_jpg}
"""
                        with open(meta_txt_file, "w", encoding="utf-8") as f:
                            f.write(meta_txt_content)
                except Exception:
                    pass

        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")

    print(f"\n🎉 [Thumbnail Batch Engine] Concluído! {generated_count} miniaturas de alto CTR geradas.")


if __name__ == "__main__":
    generate_thumbnails_for_all_batches()
