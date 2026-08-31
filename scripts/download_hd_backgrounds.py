import os
import sys
import glob
import subprocess
import yt_dlp
import imageio_ffmpeg

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding="utf-8")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "scripts" else CURRENT_DIR

ff_exe = imageio_ffmpeg.get_ffmpeg_exe()
ff_dir = os.path.dirname(ff_exe)
if ff_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")

bg_dir = os.path.join(PROJECT_ROOT, "assets", "backgrounds")
os.makedirs(bg_dir, exist_ok=True)

# Lista de vídeos de gameplay 1080p60 do @OrbitalNCG (Sem copyright)
# 3 Verticais (1080x1920 60fps) e 3 Horizontais (1920x1080 60fps)
BACKGROUND_VIDEOS = [
    {
        "id": "P9Xlr1BOByw",
        "type": "vertical",
        "name": "orbital_vertical_1080p_P9Xlr1BOByw.mp4",
        "url": "https://www.youtube.com/watch?v=P9Xlr1BOByw"
    },
    {
        "id": "LKx3805bIa8",
        "type": "vertical",
        "name": "orbital_vertical_1080p_LKx3805bIa8.mp4",
        "url": "https://www.youtube.com/watch?v=LKx3805bIa8"
    },
    {
        "id": "XLzE_oO4WQs",
        "type": "vertical",
        "name": "orbital_vertical_1080p_XLzE_oO4WQs.mp4",
        "url": "https://www.youtube.com/watch?v=XLzE_oO4WQs"
    },
    {
        "id": "u7ieZtmf_qg",
        "type": "horizontal",
        "name": "orbital_horizontal_1080p_u7ieZtmf_qg.mp4",
        "url": "https://www.youtube.com/watch?v=u7ieZtmf_qg"
    },
    {
        "id": "ErIlPUQ5yms",
        "type": "horizontal",
        "name": "orbital_horizontal_1080p_ErIlPUQ5yms.mp4",
        "url": "https://www.youtube.com/watch?v=ErIlPUQ5yms"
    },
    {
        "id": "64Dw7XvHl4w",
        "type": "horizontal",
        "name": "orbital_horizontal_1080p_64Dw7XvHl4w.mp4",
        "url": "https://www.youtube.com/watch?v=64Dw7XvHl4w"
    }
]

def purge_old_backgrounds():
    """Remove vídeos antigos de baixa qualidade."""
    print("[CleanUp] Removendo todos os vídeos antigos de assets/backgrounds/...")
    for f in glob.glob(os.path.join(bg_dir, "*.mp4")):
        try:
            os.remove(f)
            print(f"   - Removido: {os.path.basename(f)}")
        except Exception as e:
            print(f"   - Erro ao remover {f}: {e}")

def download_hd_videos():
    """Baixa vídeos de gameplay em alta resolução 1080p 60fps usando cookies e ffmpeg."""
    purge_old_backgrounds()

    # Formato prioritário: 1080p60 + melhor áudio mesclado para MP4
    ydl_opts_base = {
        "format": "bestvideo[height>=1080][fps>=50]+bestaudio/bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/best",
        "merge_output_format": "mp4",
        "ffmpeg_location": ff_exe,
        "cookiesfrombrowser": ("firefox", None, None, None),
        "noplaylist": True,
        "quiet": False,
        "socket_timeout": 30
    }

    print("\n[DownloadHD] Iniciando download de backgrounds de gameplay em 1080p60 HD...")
    for item in BACKGROUND_VIDEOS:
        out_path = os.path.join(bg_dir, item["name"])
        print(f"\n[Download] Baixando {item['type'].upper()} ({item['id']}) em 1080p60 HD...")
        opts = dict(ydl_opts_base)
        opts["outtmpl"] = out_path

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([item["url"]])
            if os.path.exists(out_path):
                sz = os.path.getsize(out_path) / (1024 * 1024)
                print(f"[OK] {item['name']} baixado com sucesso! ({sz:.1f} MB)")
            else:
                print(f"[AVISO] Arquivo não gerado no caminho esperado: {out_path}")
        except Exception as e:
            print(f"[ERRO] Falha ao baixar {item['id']}: {e}")

if __name__ == "__main__":
    download_hd_videos()
