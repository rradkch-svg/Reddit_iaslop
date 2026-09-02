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


def get_thumbnail_font(size: int, bold: bool = False, impact: bool = False) -> ImageFont.FreeTypeFont:
    """Carrega fontes de alta legibilidade para Thumbnails com fallbacks do sistema."""
    if impact:
        candidates = [
            r"C:\Windows\Fonts\impact.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf"
        ]
    elif bold:
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\tahomabd.ttf",
            r"C:\Windows\Fonts\calibrib.ttf"
        ]
    else:
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


def extract_shock_phrase(title: str, custom_hook: Optional[str] = None) -> str:
    """
    Extrai ou sintetiza uma frase de choque de 1 a 4 palavras para a Thumbnail
    baseada no conflito central da história (ex: 'SOLD HER CAR!', '$25K WEDDING DEMAND').
    """
    if custom_hook and len(custom_hook.strip()) > 0:
        return custom_hook.upper().strip()

    title_clean = title.strip()

    # Padrões comuns de alta retenção no Reddit
    if re.search(r"sold\s+(?:her|his|their|the)\s+car", title_clean, re.IGNORECASE):
        return "SOLD HER CAR!"
    if re.search(r"\$25[kK]|\$25,000", title_clean):
        return "$25K WEDDING DEMAND!"
    if re.search(r"\$18[kK]|\$18,000", title_clean):
        return "$18,000 DEMAND!"
    if re.search(r"\$280[kK]|\$280,000", title_clean):
        return "$280K OUTAGE!"
    if re.search(r"\$38[kK]|\$38,000", title_clean):
        return "$38,000 OVERTIME!"
    if re.search(r"\$34[kK]|\$34,000", title_clean):
        return "$34,000 DISASTER!"
    if re.search(r"\$42[kK]|\$42,000", title_clean):
        return "$42,000 REVENGE!"
    if re.search(r"\$140[kK]|\$140,000", title_clean):
        return "$140,000 COST!"
    if re.search(r"sourdough|starter", title_clean, re.IGNORECASE):
        return "130-YR HEIRLOOM RUINED!"
    if re.search(r"overtime", title_clean, re.IGNORECASE):
        return "MASSIVE OVERTIME REVENGE!"
    if re.search(r"fired|termination|dismissed", title_clean, re.IGNORECASE):
        return "FIRED ON THE SPOT!"
    if re.search(r"wedding", title_clean, re.IGNORECASE):
        return "WEDDING DRAMA EXPLODES!"
    if re.search(r"landlord|deposit", title_clean, re.IGNORECASE):
        return "LANDLORD GOT REVENGE!"
    if re.search(r"malicious\s+compliance", title_clean, re.IGNORECASE):
        return "MALICIOUS COMPLIANCE!"
    if re.search(r"aitah|aita", title_clean, re.IGNORECASE):
        return "WHO IS IN THE WRONG?"

    # Fallback genérico: primeiras 3-4 palavras de impacto
    words = title_clean.split()
    if len(words) >= 3:
        candidate = " ".join(words[:4]).upper()
        return candidate.rstrip(".,!?:;") + "!"
    return "INSANE REDDIT STORY!"


class RedditThumbnailEngine:
    """
    Motor Gráfico Especializado em Thumbnails 16:9 (1920x1080) para YouTube
    seguindo as diretrizes de alto CTR e branding do canal 'Reddit Minute'.
    """

    def __init__(self, brand_name: str = "Reddit Minute"):
        self.brand_name = brand_name
        self.ffmpeg_bin = find_ffmpeg_binary()

    def _extract_backdrop_frame(self, video_path: Optional[str], output_frame_path: str) -> bool:
        """Extrai um frame estático em HD do vídeo de fundo de gameplay."""
        if not video_path or not os.path.exists(video_path):
            return False

        try:
            dur = get_media_duration(video_path, self.ffmpeg_bin)
            seek_pos = min(30.0, max(5.0, dur * 0.2)) if dur > 10 else 1.0

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
        """Cria um fundo degradê cinematográfico escuro em caso de ausência de vídeo."""
        img = Image.new("RGB", (width, height), (15, 18, 26))
        draw = ImageDraw.Draw(img)
        # Gradiente radial sutil escurecendo para as bordas
        for y in range(height):
            ratio = y / height
            r = int(22 - ratio * 12)
            g = int(26 - ratio * 14)
            b = int(38 - ratio * 20)
            draw.line([(0, y), (width, y)], fill=(max(5, r), max(8, g), max(12, b)))
        return img

    def generate_youtube_thumbnail(
        self,
        story_data: Dict[str, Any],
        output_path: str,
        background_video_path: Optional[str] = None,
        shock_hook: Optional[str] = None
    ) -> str:
        """
        Renderiza uma miniatura completa de 1920x1080 (16:9) em formato PNG e JPG.
        """
        with LogSpan("generate_youtube_thumbnail", extra={"title": story_data.get("title", "")[:30]}):
            canvas_w, canvas_h = 1920, 1080
            temp_frame = output_path + ".tmp_frame.jpg"

            # 1. Preparação do Background
            bg_success = self._extract_backdrop_frame(background_video_path, temp_frame)
            if bg_success and os.path.exists(temp_frame):
                try:
                    bg_img = Image.open(temp_frame).convert("RGBA")
                    bg_img = bg_img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
                    # Desfoque cinematográfico suave para realçar o primeiro plano
                    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=6))
                    # Ajuste de contraste e brilho escurecido (-25% brilho para legibilidade)
                    enhancer = ImageEnhance.Brightness(bg_img)
                    bg_img = enhancer.enhance(0.72)
                    enhancer_sat = ImageEnhance.Color(bg_img)
                    bg_img = enhancer_sat.enhance(1.15)
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

            # Aplicação de Vinheta Escura nas Bordas
            vignette = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            v_draw = ImageDraw.Draw(vignette)
            v_draw.rectangle([0, 0, canvas_w, canvas_h], fill=(0, 0, 0, 100))
            # Gradiente escuro no rodapé e topo
            for y in range(220):
                alpha = int(180 * (1 - y / 220))
                v_draw.line([(0, y), (canvas_w, y)], fill=(0, 0, 0, alpha))
            for y in range(canvas_h - 260, canvas_h):
                alpha = int(210 * ((y - (canvas_h - 260)) / 260))
                v_draw.line([(0, y), (canvas_w, y)], fill=(0, 0, 0, alpha))

            bg_img = Image.alpha_composite(bg_img, vignette)

            # Criação da Camada de Desenho Principal
            overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # Dados do Post
            subreddit = story_data.get("subreddit", "r/AITAH")
            if not subreddit.startswith("r/"):
                subreddit = f"r/{subreddit}"
            author = story_data.get("author", "throwaway_reddit")
            if not author.startswith("u/"):
                author = f"u/{author}"
            score = story_data.get("score", "48.2k")
            if isinstance(score, (int, float)):
                score = f"{score/1000:.1f}k" if score >= 1000 else str(score)

            title_text = (story_data.get("display_title") or story_data.get("title") or "She Demanded My House Savings, So I Sold Her Car").strip()

            # 2. TOPO: Branding do Canal "Reddit Minute" & Badges
            # Badge Esquerdo: Reddit Minute
            brand_pill_x, brand_pill_y = 60, 50
            brand_pill_w, brand_pill_h = 320, 64
            draw.rounded_rectangle(
                [brand_pill_x, brand_pill_y, brand_pill_x + brand_pill_w, brand_pill_y + brand_pill_h],
                radius=18,
                fill=(255, 69, 0, 240), # Reddit Orange #FF4500
                outline=(255, 255, 255, 200),
                width=2
            )
            # Ícone Reddit (círculo branco simples com olhos laranjas)
            ico_cx, ico_cy = brand_pill_x + 32, brand_pill_y + 32
            draw.ellipse([ico_cx - 16, ico_cy - 16, ico_cx + 16, ico_cy + 16], fill=(255, 255, 255, 255))
            draw.ellipse([ico_cx - 8, ico_cy - 5, ico_cx - 3, ico_cy], fill=(255, 69, 0, 255))
            draw.ellipse([ico_cx + 3, ico_cy - 5, ico_cx + 8, ico_cy], fill=(255, 69, 0, 255))

            font_brand = get_thumbnail_font(28, bold=True)
            draw.text((brand_pill_x + 60, brand_pill_y + 14), self.brand_name.upper(), font=font_brand, fill=(255, 255, 255, 255))

            # Badge Central: Subreddit
            sub_pill_x = brand_pill_x + brand_pill_w + 20
            sub_pill_w = 260
            draw.rounded_rectangle(
                [sub_pill_x, brand_pill_y, sub_pill_x + sub_pill_w, brand_pill_y + brand_pill_h],
                radius=18,
                fill=(0, 121, 211, 230), # Reddit Blue #0079D3
                outline=(255, 255, 255, 180),
                width=2
            )
            draw.text((sub_pill_x + 24, brand_pill_y + 14), subreddit, font=font_brand, fill=(255, 255, 255, 255))

            # Badge Direito: "30+ MIN FULL STORY"
            tag_pill_x = canvas_w - 380
            tag_pill_w = 320
            draw.rounded_rectangle(
                [tag_pill_x, brand_pill_y, tag_pill_x + tag_pill_w, brand_pill_y + brand_pill_h],
                radius=18,
                fill=(18, 20, 28, 240),
                outline=(255, 230, 0, 255), # Amarelo Destaque
                width=3
            )
            font_tag = get_thumbnail_font(26, bold=True)
            draw.text((tag_pill_x + 22, brand_pill_y + 16), "⏱️ 30+ MIN FULL STORY", font=font_tag, fill=(255, 230, 0, 255))

            # 3. CARD CENTRAL OFICIAL DO REDDIT (Dark Mode #1A1A1B)
            card_x = 60
            card_y = 150
            card_w = 1800
            card_h = 420

            # Sombra 3D profunda atrás do Card
            shadow_box = [card_x - 12, card_y + 12, card_x + card_w + 12, card_y + card_h + 24]
            shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow_layer)
            s_draw.rounded_rectangle(shadow_box, radius=36, fill=(0, 0, 0, 235))
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(24))
            overlay = Image.alpha_composite(shadow_layer, overlay)
            draw = ImageDraw.Draw(overlay)

            # Corpo do Card
            draw.rounded_rectangle(
                [card_x, card_y, card_x + card_w, card_y + card_h],
                radius=28,
                fill=(26, 26, 27, 245), # Dark Mode Reddit #1A1A1B
                outline=(52, 53, 54, 255), # Borda sutil
                width=3
            )

            # Cabeçalho do Card
            header_y = card_y + 36
            # Ícone Subreddit
            draw.ellipse([card_x + 40, header_y, card_x + 40 + 48, header_y + 48], fill=(255, 69, 0, 255))
            draw.text((card_x + 40 + 16, header_y + 10), "r/", font=get_thumbnail_font(24, bold=True), fill=(255, 255, 255, 255))

            font_meta_bold = get_thumbnail_font(28, bold=True)
            font_meta_gray = get_thumbnail_font(26, bold=False)

            draw.text((card_x + 104, header_y + 8), subreddit, font=font_meta_bold, fill=(255, 255, 255, 255))
            draw.text((card_x + 104 + len(subreddit) * 16 + 15, header_y + 10), f"• Posted by {author} • 4h ago", font=font_meta_gray, fill=(129, 131, 132, 255))

            # Upvotes Pill (Direita do Header do Card)
            upvote_x = card_x + card_w - 240
            draw.rounded_rectangle(
                [upvote_x, header_y - 4, upvote_x + 200, header_y + 52],
                radius=20,
                fill=(39, 39, 41, 255),
                outline=(52, 53, 54, 255),
                width=2
            )
            font_upvote = get_thumbnail_font(26, bold=True)
            draw.text((upvote_x + 20, header_y + 8), f"▲  {score}", font=font_upvote, fill=(255, 69, 0, 255))

            # Título do Post no Card (Quebra inteligente de até 3 linhas)
            font_title = get_thumbnail_font(44, bold=True)
            title_lines = textwrap.wrap(title_text, width=64)
            if len(title_lines) > 3:
                title_lines = title_lines[:3]
                if not title_lines[-1].endswith("..."):
                    title_lines[-1] = title_lines[-1].rstrip(".!? ") + "..."

            title_y_start = header_y + 74
            for l_idx, line in enumerate(title_lines):
                draw.text((card_x + 44, title_y_start + (l_idx * 58)), line, font=font_title, fill=(255, 255, 255, 255))

            # 4. 🔥 TEXTO DE CHOQUE / ALTO CTR (Impact Banner)
            shock_text = extract_shock_phrase(title_text, shock_hook)
            font_shock = get_thumbnail_font(78, bold=True, impact=True)

            shock_y = card_y + card_h + 60
            shock_x = 60

            # Renderiza Tarja / Destaque de Fundo para o Texto de Choque
            # Medição aproximada do texto
            bbox = font_shock.getbbox(shock_text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            # Fundo preto translúcido atrás do texto de choque para máximo contraste
            pad_x, pad_y = 30, 20
            draw.rounded_rectangle(
                [shock_x - pad_x, shock_y - pad_y, shock_x + text_w + pad_x, shock_y + text_h + pad_y + 10],
                radius=24,
                fill=(0, 0, 0, 230),
                outline=(255, 230, 0, 255),
                width=4
            )

            # Texto com contorno (Stroke de 10px) em amarelo vibrante
            stroke_width = 8
            for sx in range(-stroke_width, stroke_width + 1):
                for sy in range(-stroke_width, stroke_width + 1):
                    if sx * sx + sy * sy <= stroke_width * stroke_width:
                        draw.text((shock_x + sx, shock_y + sy), shock_text, font=font_shock, fill=(0, 0, 0, 255))

            # Texto em Amarelo Destaque (#FFE600)
            draw.text((shock_x, shock_y), shock_text, font=font_shock, fill=(255, 230, 0, 255))

            # Sub-gancho secundário: "FULL NARRATION & REVENGE"
            font_sub_shock = get_thumbnail_font(34, bold=True)
            draw.text((shock_x, shock_y + text_h + 46), "🔥 COMPLETE SAGA • INSTANT KARMA", font=font_sub_shock, fill=(255, 255, 255, 230))

            # 5. PROTEÇÃO DA SAFE-AREA DO YOUTUBE (Canto Inferior Direito)
            # O canto x: 1640-1920, y: 960-1080 é reservado para a tarja do YouTube
            # Adiciona sutil vinheta para garantir contraste
            draw.rectangle([canvas_w - 280, canvas_h - 120, canvas_w, canvas_h], fill=(0, 0, 0, 90))

            # Composição Final
            final_img = Image.alpha_composite(bg_img, overlay).convert("RGB")

            # Salva versões em PNG e JPG
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            png_path = output_path if output_path.endswith(".png") else output_path + ".png"
            jpg_path = output_path.replace(".png", ".jpg") if output_path.endswith(".png") else output_path + ".jpg"

            final_img.save(png_path, format="PNG")
            final_img.save(jpg_path, format="JPEG", quality=95, optimize=True)

            app_logger.info(f"[Thumbnail] Miniatura gerada com sucesso: {png_path} & {jpg_path} (1920x1080)")
            return png_path
