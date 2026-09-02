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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    seguindo o padrão visual exato dos canais líderes (@Mini Mystie, @Bountywishes, @QuokkaReads).
    Design: White Card Adaptativo com Borda Laranja #FF4500, Ícone 3D do Canal, Selo Azul, Awards e Tipografia Ultra-Bold.
    """

    def __init__(self, brand_name: str = "Reddit Minute", icon_path: Optional[str] = None):
        self.brand_name = brand_name
        self.ffmpeg_bin = find_ffmpeg_binary()
        if icon_path and os.path.exists(icon_path):
            self.icon_path = icon_path
        else:
            default_icon = os.path.join(BASE_DIR, "assets", "icon.jpg")
            self.icon_path = default_icon if os.path.exists(default_icon) else None

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
        for y in range(height):
            ratio = y / height
            r = int(140 + ratio * 80)
            g = int(185 + (1 - ratio) * 50)
            b = int(240 - ratio * 60)
            draw.line([(0, y), (width, y)], fill=(min(255, r), min(255, g), min(255, b)))
        return img

    def _draw_verified_badge(self, draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 30):
        """Desenha o selo de verificado azul com checkmark branco."""
        draw.ellipse([x, y, x + size, y + size], fill=(29, 155, 240, 255))
        cx, cy = x + size // 2, y + size // 2
        p1 = (cx - 7, cy)
        p2 = (cx - 2, cy + 6)
        p3 = (cx + 7, cy - 6)
        draw.line([p1, p2, p3], fill=(255, 255, 255, 255), width=4)

    def _draw_reddit_awards_row(self, draw: ImageDraw.ImageDraw, start_x: int, start_y: int):
        """Desenha a faixa de condecorações/awards coloridas do Reddit."""
        awards = [
            {"bg": (255, 90, 140), "symbol": "💖"}, # Wholesome
            {"bg": (255, 185, 0),  "symbol": "🏆"}, # Gold
            {"bg": (0, 210, 255),  "symbol": "💎"}, # Platinum
            {"bg": (255, 130, 0),  "symbol": "🎁"}, # Present
            {"bg": (255, 80, 80),  "symbol": "🎂"}, # Cake
            {"bg": (110, 215, 90), "symbol": "🌟"}, # Star
            {"bg": (170, 120, 255),"symbol": "⚡"}  # Spark
        ]

        radius = 16
        spacing = 38
        for idx, aw in enumerate(awards):
            ax = start_x + (idx * spacing)
            ay = start_y
            draw.ellipse([ax - radius, ay - radius, ax + radius, ay + radius], fill=aw["bg"] + (255,), outline=(255, 255, 255, 230), width=2)
            draw.ellipse([ax - 5, ay - 5, ax + 5, ay + 5], fill=(255, 255, 255, 255))

    def _draw_comment_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 24):
        """Desenha um ícone vetorial nítido de balão de comentários do Reddit."""
        w, h = size + 4, size - 4
        draw.rounded_rectangle([x, y, x + w, y + h], radius=6, outline=(110, 115, 120, 255), width=2)
        draw.polygon([(x + 4, y + h - 1), (x + 9, y + h - 1), (x + 2, y + h + 6)], fill=(110, 115, 120, 255))

    def _get_channel_avatar(self, size: int = 94) -> Image.Image:
        """Carrega o ícone oficial 3D do canal (assets/icon.jpg) com recorte circular anti-aliased."""
        avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))

        if self.icon_path and os.path.exists(self.icon_path):
            try:
                raw_icon = Image.open(self.icon_path).convert("RGBA")
                raw_icon = raw_icon.resize((size, size), Image.Resampling.LANCZOS)

                mask_size = size * 4
                mask = Image.new("L", (mask_size, mask_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse([0, 0, mask_size, mask_size], fill=255)
                mask = mask.resize((size, size), Image.Resampling.LANCZOS)

                avatar.paste(raw_icon, (0, 0), mask=mask)
                return avatar
            except Exception as e:
                app_logger.warning(f"[Thumbnail] Erro ao carregar icon.jpg: {str(e)}")

        avatar_draw = ImageDraw.Draw(avatar)
        avatar_draw.ellipse([0, 0, size, size], fill=(255, 69, 0, 255))
        cx, cy = size // 2, size // 2
        avatar_draw.ellipse([cx - 24, cy - 16, cx + 24, cy + 20], fill=(255, 255, 255, 255))
        avatar_draw.ellipse([cx - 14, cy - 6, cx - 6, cy + 4], fill=(255, 69, 0, 255))
        avatar_draw.ellipse([cx + 6, cy - 6, cx + 14, cy + 4], fill=(255, 69, 0, 255))
        return avatar

    def generate_youtube_thumbnail(
        self,
        story_data: Dict[str, Any],
        output_path: str,
        background_video_path: Optional[str] = None,
        shock_hook: Optional[str] = None
    ) -> str:
        """
        Renderiza uma miniatura completa de 1920x1080 (16:9) no formato White Card Proporcional.
        """
        with LogSpan("generate_youtube_thumbnail", extra={"title": story_data.get("title", "")[:30]}):
            canvas_w, canvas_h = 1920, 1080
            temp_frame = output_path + ".tmp_frame.jpg"

            # 1. Preparação do Background de Minecraft
            bg_success = self._extract_backdrop_frame(background_video_path, temp_frame)
            if bg_success and os.path.exists(temp_frame):
                try:
                    bg_img = Image.open(temp_frame).convert("RGBA")
                    bg_img = bg_img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
                    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=5))
                    enhancer_sat = ImageEnhance.Color(bg_img)
                    bg_img = enhancer_sat.enhance(1.30)
                    enhancer_br = ImageEnhance.Brightness(bg_img)
                    bg_img = enhancer_br.enhance(0.96)
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

            # 2. Processamento e Tipografia da História (Ultra-Bold e Preenchimento Otimizado)
            title_text = (story_data.get("display_title") or story_data.get("title") or "She Demanded My $25K House Savings For Her Wedding, So I Sold Her Car").strip()
            # Remove tags de minutagem redundantes no título da thumbnail (ex: [25 MIN FULL STORY])
            title_text = re.sub(r'\[\s*\d+\s*MIN[^\n\]]*\]', '', title_text, flags=re.IGNORECASE)
            title_text = re.sub(r'\[\s*FULL\s+STORY\s*\]', '', title_text, flags=re.IGNORECASE)
            title_text = title_text.strip().replace('"', "'").replace('“', "'").replace('”', "'")

            title_len = len(title_text)
            if title_len <= 85:
                font_size = 84
                max_chars_per_line = 30
            elif title_len <= 135:
                font_size = 70
                max_chars_per_line = 36
            elif title_len <= 190:
                font_size = 58
                max_chars_per_line = 42
            else:
                font_size = 50
                max_chars_per_line = 46

            font_title = get_thumbnail_font(font_size, bold=True)
            title_lines = textwrap.wrap(title_text, width=max_chars_per_line)
            if len(title_lines) > 5:
                title_lines = title_lines[:5]
                if not title_lines[-1].endswith("..."):
                    title_lines[-1] = title_lines[-1].rstrip(".!? ") + "..."

            line_height = int(font_size * 1.32)
            total_text_h = len(title_lines) * line_height

            # 3. Cálculo Dinâmico das Dimensões do White Card (Ajuste Perfeito sem Vazio)
            card_w = 1720
            card_x = (canvas_w - card_w) // 2  # 100px

            avatar_size = 88
            # Altura adaptativa proporcional ao conteúdo
            needed_h = 42 + avatar_size + 34 + total_text_h + 110
            card_h = min(940, max(520, needed_h))
            card_y = (canvas_h - card_h) // 2

            # Camada de sombra 3D suave flutuante
            shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow_layer)
            shadow_box = [card_x - 12, card_y + 16, card_x + card_w + 12, card_y + card_h + 36]
            s_draw.rounded_rectangle(shadow_box, radius=48, fill=(0, 0, 0, 115))
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(34))

            composite_img = Image.alpha_composite(bg_img, shadow_layer)

            # Camada de desenho do Card
            card_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(card_layer)

            # Desenho do Card Branco com Borda Laranja Reddit (#FF4500)
            card_rect = [card_x, card_y, card_x + card_w, card_y + card_h]
            draw.rounded_rectangle(card_rect, radius=44, fill=(255, 255, 255, 255))
            border_width = 10
            draw.rounded_rectangle(card_rect, radius=44, outline=(255, 69, 0, 255), width=border_width)

            # 4. Cabeçalho do Card: Ícone Oficial + @Canal + Selo Verificado + Awards
            header_y = card_y + 40
            avatar_x = card_x + 56

            # Avatar Circular do Canal (Ícone Oficial 3D)
            avatar_img = self._get_channel_avatar(size=avatar_size)
            card_layer.paste(avatar_img, (avatar_x, header_y), avatar_img)

            # Anel de contorno laranja no avatar
            draw.ellipse([avatar_x - 2, header_y - 2, avatar_x + avatar_size + 2, header_y + avatar_size + 2], outline=(255, 69, 0, 255), width=3)

            # Nome do Canal: @Reddit Minute
            channel_label = f"@{self.brand_name.replace(' ', '')}"
            font_channel = get_thumbnail_font(38, bold=True)
            name_x = avatar_x + avatar_size + 22
            name_y = header_y + 4
            draw.text((name_x, name_y), channel_label, font=font_channel, fill=(15, 20, 25, 255))

            # Selo de Verificado Azul
            bbox_name = font_channel.getbbox(channel_label)
            name_w = bbox_name[2] - bbox_name[0]
            badge_x = name_x + name_w + 14
            badge_y = name_y + 6
            self._draw_verified_badge(draw, badge_x, badge_y, size=30)

            # Faixa de Condecorações (Reddit Awards)
            awards_x = name_x
            awards_y = name_y + 48
            self._draw_reddit_awards_row(draw, awards_x + 18, awards_y + 10)

            # 5. Texto Principal da História (Alinhado Rigorosamente à Esquerda)
            text_x = card_x + 56
            text_start_y = header_y + avatar_size + 34

            for l_idx, line in enumerate(title_lines):
                cur_y = text_start_y + (l_idx * line_height)
                draw.text((text_x, cur_y), line, font=font_title, fill=(15, 20, 25, 255))

            # 6. Barra de Interação do Reddit no Rodapé do Card
            score = story_data.get("score", "48.5k")
            if isinstance(score, (int, float)):
                score = f"{score/1000:.1f}k" if score >= 1000 else str(score)

            footer_y = card_y + card_h - 68
            font_footer = get_thumbnail_font(28, bold=True)
            font_footer_regular = get_thumbnail_font(26, bold=False)

            # Upvotes Pill
            upvote_pill_x = text_x
            upvote_pill_w = 175
            upvote_pill_h = 46
            draw.rounded_rectangle(
                [upvote_pill_x, footer_y, upvote_pill_x + upvote_pill_w, footer_y + upvote_pill_h],
                radius=16,
                fill=(246, 247, 248, 255),
                outline=(220, 222, 224, 255),
                width=1
            )
            draw.text((upvote_pill_x + 20, footer_y + 6), f"▲  {score}  ▼", font=font_footer, fill=(255, 69, 0, 255))

            # Comments Pill
            comment_pill_x = upvote_pill_x + upvote_pill_w + 16
            comment_pill_w = 230
            draw.rounded_rectangle(
                [comment_pill_x, footer_y, comment_pill_x + comment_pill_w, footer_y + upvote_pill_h],
                radius=16,
                fill=(246, 247, 248, 255),
                outline=(220, 222, 224, 255),
                width=1
            )
            self._draw_comment_icon(draw, comment_pill_x + 18, footer_y + 12, size=22)
            draw.text((comment_pill_x + 50, footer_y + 7), "2.8k Comments", font=font_footer_regular, fill=(100, 105, 110, 255))

            # Composição final
            final_img = Image.alpha_composite(composite_img, card_layer).convert("RGB")

            # 7. Salva versões em PNG e JPG
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            png_path = output_path if output_path.endswith(".png") else output_path + ".png"
            jpg_path = output_path.replace(".png", ".jpg") if output_path.endswith(".png") else output_path + ".jpg"

            final_img.save(png_path, format="PNG")
            final_img.save(jpg_path, format="JPEG", quality=96, optimize=True)

            app_logger.info(f"[Thumbnail] Miniatura White Card Polida gerada: {png_path} & {jpg_path} (1920x1080)")
            return png_path
