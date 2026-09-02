import os
import re
import math
import random
import textwrap
import subprocess
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

try:
    from .logger import app_logger, LogSpan
    from .reddit_render import find_ffmpeg_binary, get_media_duration
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_render import find_ffmpeg_binary, get_media_duration


def get_thumbnail_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Carrega fontes de alta legibilidade para Thumbnails estilo White Card."""
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\tahomabd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf"
    ]
    if not bold:
        candidates = [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf"
        ]

    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


class RedditThumbnailEngine:
    """
    Motor Gráfico Especializado em Thumbnails 16:9 (1920x1080) para YouTube
    seguindo o padrão visual dos canais líderes (@Mini Mystie, @Bountywishes, @QuokkaReads).
    Design: White Card com Borda Laranja #FF4500, Avatar + Selo Azul + Awards + Texto Ultra-Bold Preto.
    """

    def __init__(self, brand_name: str = "Reddit Minute"):
        self.brand_name = brand_name
        self.ffmpeg_bin = find_ffmpeg_binary()

    def _extract_backdrop_frame(self, video_path: Optional[str], output_frame_path: str) -> bool:
        """Extrai um frame estático colorido em HD do vídeo de fundo de gameplay."""
        if not video_path or not os.path.exists(video_path):
            return False

        try:
            dur = get_media_duration(video_path, self.ffmpeg_bin)
            seek_pos = min(45.0, max(5.0, dur * 0.25)) if dur > 10 else 1.0

            cmd = [
                self.ffmpeg_bin, "-y",
                "-ss", str(seek_pos),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                output_frame_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode == 0 and os.path.exists(output_frame_path)
        except Exception as e:
            app_logger.warning(f"[Thumbnail] Falha ao extrair frame de {video_path}: {str(e)}")
            return False

    def _create_procedural_background(self, width: int = 1920, height: int = 1080) -> Image.Image:
        """Cria um fundo degradê vivo e vibrante inspirado em paisagem Minecraft/Cherry Blossom."""
        img = Image.new("RGB", (width, height), (255, 180, 190))
        draw = ImageDraw.Draw(img)
        # Gradiente suave do céu azul claro para verde/rosa cerejeira
        for y in range(height):
            ratio = y / height
            r = int(140 + ratio * 80)
            g = int(185 + (1 - ratio) * 50)
            b = int(240 - ratio * 60)
            draw.line([(0, y), (width, y)], fill=(min(255, r), min(255, g), min(255, b)))
        return img

    def _draw_verified_badge(self, draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 28):
        """Desenha o selo de verificado azul com checkmark branco."""
        draw.ellipse([x, y, x + size, y + size], fill=(29, 155, 240, 255)) # Twitter/YouTube Blue #1D9BF0
        # Checkmark branco
        cx, cy = x + size // 2, y + size // 2
        p1 = (cx - 6, cy)
        p2 = (cx - 2, cy + 5)
        p3 = (cx + 6, cy - 5)
        draw.line([p1, p2, p3], fill=(255, 255, 255, 255), width=3)

    def _draw_reddit_awards_row(self, draw: ImageDraw.ImageDraw, start_x: int, start_y: int):
        """Desenha a faixa de condecorações/awards coloridas do Reddit."""
        awards = [
            {"bg": (255, 110, 160), "symbol": "💖"}, # Wholesome Heart
            {"bg": (255, 195, 0),   "symbol": "🏆"}, # Gold Trophy
            {"bg": (0, 210, 255),   "symbol": "💎"}, # Platinum Diamond
            {"bg": (255, 140, 0),   "symbol": "🎁"}, # Present Award
            {"bg": (255, 90, 95),   "symbol": "🎂"}, # Cake Day
            {"bg": (120, 220, 100), "symbol": "🌟"}, # Star Award
            {"bg": (180, 130, 255), "symbol": "⚡"}  # Energy Spark
        ]

        radius = 14
        spacing = 34
        for idx, aw in enumerate(awards):
            ax = start_x + (idx * spacing)
            ay = start_y
            # Círculo base do award
            draw.ellipse([ax - radius, ay - radius, ax + radius, ay + radius], fill=aw["bg"] + (240,), outline=(255, 255, 255, 220), width=1)
            # Ponto central brilhante
            draw.ellipse([ax - 4, ay - 4, ax + 4, ay + 4], fill=(255, 255, 255, 255))

    def _get_channel_avatar(self, size: int = 80) -> Image.Image:
        """Carrega ou gera o avatar circular do canal Reddit Minute."""
        avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        avatar_draw = ImageDraw.Draw(avatar)

        # Base circular Laranja Reddit (#FF4500)
        avatar_draw.ellipse([0, 0, size, size], fill=(255, 69, 0, 255))

        # Desenho do Snoo / Alien estilizado
        cx, cy = size // 2, size // 2
        # Cabeça branca
        avatar_draw.ellipse([cx - 24, cy - 16, cx + 24, cy + 20], fill=(255, 255, 255, 255))
        # Orelhas
        avatar_draw.ellipse([cx - 30, cy - 10, cx - 20, cy], fill=(255, 255, 255, 255))
        avatar_draw.ellipse([cx + 20, cy - 10, cx + 30, cy], fill=(255, 255, 255, 255))
        # Olhos laranjas
        avatar_draw.ellipse([cx - 14, cy - 6, cx - 6, cy + 4], fill=(255, 69, 0, 255))
        avatar_draw.ellipse([cx + 6, cy - 6, cx + 14, cy + 4], fill=(255, 69, 0, 255))
        # Antena
        avatar_draw.line([(cx, cy - 16), (cx + 8, cy - 28), (cx + 16, cy - 26)], fill=(255, 255, 255, 255), width=3)
        avatar_draw.ellipse([cx + 14, cy - 30, cx + 22, cy - 22], fill=(255, 255, 255, 255))

        return avatar

    def generate_youtube_thumbnail(
        self,
        story_data: Dict[str, Any],
        output_path: str,
        background_video_path: Optional[str] = None,
        shock_hook: Optional[str] = None
    ) -> str:
        """
        Renderiza uma miniatura completa de 1920x1080 (16:9) no formato White Card Premium.
        """
        with LogSpan("generate_youtube_thumbnail", extra={"title": story_data.get("title", "")[:30]}):
            canvas_w, canvas_h = 1920, 1080
            temp_frame = output_path + ".tmp_frame.jpg"

            # 1. Preparação do Background de Minecraft (Saturado e Vivo)
            bg_success = self._extract_backdrop_frame(background_video_path, temp_frame)
            if bg_success and os.path.exists(temp_frame):
                try:
                    bg_img = Image.open(temp_frame).convert("RGBA")
                    bg_img = bg_img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
                    # Desfoque suave de profundidade de campo
                    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=5))
                    # Saturação vívida
                    enhancer_sat = ImageEnhance.Color(bg_img)
                    bg_img = enhancer_sat.enhance(1.25)
                    # Brilho agradável (não escuro, bem iluminado)
                    enhancer_br = ImageEnhance.Brightness(bg_img)
                    bg_img = enhancer_br.enhance(0.95)
                except Exception:
                    bg_img = self._create_procedural_background(canvas_w, canvas_h).convert("RGBA")
                finally:
                    if os.path.exists(temp_frame):
                        try:
                            os.remove(temp_frame)
                        except Exception:
                            pass
            else:
                bg_img = self._create_procedural_background(canvas_w, canvas_h).convert("RGBA")

            # 2. Estrutura e Dimensões do White Card Central
            # O card ocupa a maior parte da tela de forma imponente e centralizada
            card_w = 1680
            card_h = 880
            card_x = (canvas_w - card_w) // 2  # 120px
            card_y = (canvas_h - card_h) // 2  # 100px

            # Camada de sombra 3D suave flutuante
            shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow_layer)
            shadow_box = [card_x - 10, card_y + 16, card_x + card_w + 10, card_y + card_h + 36]
            s_draw.rounded_rectangle(shadow_box, radius=48, fill=(0, 0, 0, 100))
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(32))

            # Combina a sombra sobre o fundo
            composite_img = Image.alpha_composite(bg_img, shadow_layer)

            # Camada de desenho do Card
            card_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(card_layer)

            # Desenho do Card Branco Puro com Borda Laranja Reddit (#FF4500)
            card_rect = [card_x, card_y, card_x + card_w, card_y + card_h]
            # Fundo branco puro
            draw.rounded_rectangle(card_rect, radius=42, fill=(255, 255, 255, 255))
            # Borda Laranja de 10px
            border_width = 10
            draw.rounded_rectangle(card_rect, radius=42, outline=(255, 69, 0, 255), width=border_width)

            # 3. Cabeçalho do Card: Avatar + @Canal + Selo Verificado + Awards
            header_y = card_y + 44

            # Avatar Circular
            avatar_img = self._get_channel_avatar(size=76)
            card_layer.paste(avatar_img, (card_x + 52, header_y), avatar_img)

            # Aro externo de destaque no avatar
            draw.ellipse([card_x + 50, header_y - 2, card_x + 50 + 80, header_y + 78], outline=(255, 69, 0, 255), width=3)

            # Nome do Canal: @Reddit Minute (ou Bountywishes/Mini Mystie)
            channel_label = f"@{self.brand_name.replace(' ', '')}"
            font_channel = get_thumbnail_font(34, bold=True)
            name_x = card_x + 144
            name_y = header_y + 4
            draw.text((name_x, name_y), channel_label, font=font_channel, fill=(15, 20, 25, 255))

            # Selo de Verificado Azul
            # Mede largura do nome
            bbox_name = font_channel.getbbox(channel_label)
            name_w = bbox_name[2] - bbox_name[0]
            badge_x = name_x + name_w + 12
            badge_y = name_y + 5
            self._draw_verified_badge(draw, badge_x, badge_y, size=28)

            # Faixa de Condecorações (Reddit Awards)
            awards_x = name_x
            awards_y = name_y + 42
            self._draw_reddit_awards_row(draw, awards_x + 16, awards_y + 10)

            # 4. Texto Principal da História (Headline Ultra-Bold)
            title_text = (story_data.get("display_title") or story_data.get("title") or "She Demanded My $25K House Savings For Her Wedding, So I Sold Her Car").strip()

            # Normalização de aspas
            title_text = title_text.replace('"', "'").replace('“', "'").replace('”', "'")

            # Quebra de texto com cálculo de tamanho de fonte responsivo
            max_chars_per_line = 44
            if len(title_text) > 130:
                font_size = 52
                max_chars_per_line = 48
            elif len(title_text) > 85:
                font_size = 58
                max_chars_per_line = 44
            else:
                font_size = 64
                max_chars_per_line = 38

            font_title = get_thumbnail_font(font_size, bold=True)
            title_lines = textwrap.wrap(title_text, width=max_chars_per_line)
            if len(title_lines) > 5:
                title_lines = title_lines[:5]
                if not title_lines[-1].endswith("..."):
                    title_lines[-1] = title_lines[-1].rstrip(".!? ") + "..."

            # Cálculo de posicionamento vertical para centralização perfeita no espaço restante
            line_height = int(font_size * 1.32)
            total_text_h = len(title_lines) * line_height

            available_content_top = header_y + 90
            available_content_bottom = card_y + card_h - 40
            available_content_h = available_content_bottom - available_content_top

            text_start_y = available_content_top + max(20, (available_content_h - total_text_h) // 2)
            text_x = card_x + 64

            # Desenha as linhas do texto em Preto Profundo (#0F1419)
            for l_idx, line in enumerate(title_lines):
                cur_y = text_start_y + (l_idx * line_height)
                draw.text((text_x, cur_y), line, font=font_title, fill=(15, 20, 25, 255))

            # Composição final
            final_img = Image.alpha_composite(composite_img, card_layer).convert("RGB")

            # 5. Salva versões em PNG e JPG
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            png_path = output_path if output_path.endswith(".png") else output_path + ".png"
            jpg_path = output_path.replace(".png", ".jpg") if output_path.endswith(".png") else output_path + ".jpg"

            final_img.save(png_path, format="PNG")
            final_img.save(jpg_path, format="JPEG", quality=96, optimize=True)

            app_logger.info(f"[Thumbnail] Miniatura White Card gerada com sucesso: {png_path} & {jpg_path} (1920x1080)")
            return png_path
