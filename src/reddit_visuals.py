import os
import textwrap
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Carrega fontes padrão do Windows com fallback seguro."""
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\tahomabd.ttf" if bold else r"C:\Windows\Fonts\tahoma.ttf"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except:
                pass
    return ImageFont.load_default()

class RedditVisualEngine:
    """
    Motor Gráfico de Cards Oficiais do Reddit em Alta Resolução (Modo Escuro / Dark Theme).
    Renderiza sobreposições transparentes com efeito de sombra e estética oficial do Reddit.
    """
    def __init__(self):
        pass

    def render_reddit_card(
        self,
        card_data: Dict[str, Any],
        output_png: str,
        aspect_ratio: str = "9:16"
    ) -> str:
        is_vertical = (aspect_ratio == "9:16")
        canvas_w = 1080 if is_vertical else 1920
        canvas_h = 1920 if is_vertical else 1080

        # Cria imagem RGBA transparente
        img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Configurações de layout
        subreddit = card_data.get("subreddit", "r/maliciouscompliance")
        if not subreddit.startswith("r/"):
            subreddit = f"r/{subreddit}"
        author = card_data.get("author", "u/RedditUser")
        if not author.startswith("u/"):
            author = f"u/{author}"
        score = card_data.get("score", "24.5k")
        display_title = card_data.get("display_title", card_data.get("title", "Insane Reddit Story"))

        # Dimensões e posicionamento do card central
        if is_vertical:
            card_w = 980
            card_x0 = (canvas_w - card_w) // 2
            card_y0 = 380 # Terço superior para não tampar legendas no centro/inferior
            title_font_size = 44
            meta_font_size = 28
            max_wrap_chars = 34
        else:
            card_w = 1200
            card_x0 = (canvas_w - card_w) // 2
            card_y0 = 180
            title_font_size = 38
            meta_font_size = 24
            max_wrap_chars = 52

        font_sub = get_font(meta_font_size + 2, bold=True)
        font_meta = get_font(meta_font_size, bold=False)
        font_title = get_font(title_font_size, bold=True)
        font_pills = get_font(meta_font_size, bold=True)

        # Quebra do título
        title_lines = textwrap.wrap(display_title, width=max_wrap_chars)
        line_height = int(title_font_size * 1.35)
        title_block_h = len(title_lines) * line_height

        header_h = 75
        footer_h = 75
        padding = 40
        card_h = padding + header_h + title_block_h + padding + footer_h + padding
        card_x1 = card_x0 + card_w
        card_y1 = card_y0 + card_h

        # 1. Sombra suave de profundidade
        shadow_box = [card_x0 - 10, card_y0 + 10, card_x1 + 10, card_y1 + 25]
        shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_layer)
        s_draw.rounded_rectangle(shadow_box, radius=32, fill=(0, 0, 0, 180))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(16))
        img = Image.alpha_composite(img, shadow_layer)
        draw = ImageDraw.Draw(img)

        # 2. Card Principal com Dark Theme do Reddit (#1A1A1B)
        card_box = [card_x0, card_y0, card_x1, card_y1]
        draw.rounded_rectangle(card_box, radius=24, fill=(26, 26, 27, 245), outline=(52, 53, 54, 255), width=3)

        # 3. Ícone do Subreddit (Círculo Laranja #FF4500 com Snoo/R)
        icon_size = 54
        icon_x = card_x0 + padding
        icon_y = card_y0 + padding
        draw.ellipse([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size], fill=(255, 69, 0, 255))
        draw.text((icon_x + 16, icon_y + 8), "r/", font=get_font(28, bold=True), fill=(255, 255, 255, 255))

        # 4. Header: Subreddit + Autor + Timestamp
        text_start_x = icon_x + icon_size + 18
        draw.text((text_start_x, icon_y + 4), subreddit, font=font_sub, fill=(255, 255, 255, 255))
        sub_len = draw.textlength(subreddit, font=font_sub)
        meta_str = f" • Posted by {author} • 4h ago"
        draw.text((text_start_x + sub_len, icon_y + 6), meta_str, font=font_meta, fill=(135, 138, 140, 255))

        # 5. Título em Negrito
        curr_y = icon_y + icon_size + 24
        for line in title_lines:
            draw.text((card_x0 + padding, curr_y), line, font=font_title, fill=(245, 245, 245, 255))
            curr_y += line_height

        # 6. Rodapé com Pills Interativas (Upvotes e Comentários)
        curr_y += 18
        # Pill Upvotes
        pill_up_w = 160
        pill_up_box = [card_x0 + padding, curr_y, card_x0 + padding + pill_up_w, curr_y + 50]
        draw.rounded_rectangle(pill_up_box, radius=25, fill=(45, 45, 46, 255))
        draw.text((card_x0 + padding + 18, curr_y + 10), f"▲  {score}", font=font_pills, fill=(255, 69, 0, 255))

        # Pill Comentários
        pill_com_x = card_x0 + padding + pill_up_w + 16
        pill_com_w = 180
        pill_com_box = [pill_com_x, curr_y, pill_com_x + pill_com_w, curr_y + 50]
        draw.rounded_rectangle(pill_com_box, radius=25, fill=(45, 45, 46, 255))
        draw.text((pill_com_x + 20, curr_y + 10), "💬  1.2k", font=font_pills, fill=(215, 218, 220, 255))

        # Pill Share
        pill_share_x = pill_com_x + pill_com_w + 16
        pill_share_w = 140
        pill_share_box = [pill_share_x, curr_y, pill_share_x + pill_share_w, curr_y + 50]
        draw.rounded_rectangle(pill_share_box, radius=25, fill=(45, 45, 46, 255))
        draw.text((pill_share_x + 22, curr_y + 10), "↗ Share", font=font_pills, fill=(215, 218, 220, 255))

        os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)
        img.save(output_png, "PNG")
        return output_png
