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

        # Configurações de dados
        subreddit = card_data.get("subreddit", "r/maliciouscompliance")
        if not subreddit.startswith("r/"):
            subreddit = f"r/{subreddit}"
        author = card_data.get("author", "u/RedditUser")
        if not author.startswith("u/"):
            author = f"u/{author}"
        score = card_data.get("score", "38.2k")
        display_title = card_data.get("display_title", card_data.get("title", "Insane Reddit Story"))

        # Dimensões e posicionamento do card central
        if is_vertical:
            card_w = 980
            card_x0 = (canvas_w - card_w) // 2
            card_y0 = 320 # Posição superior/central limpa
            title_font_size = 46
            meta_font_size = 28
            max_wrap_chars = 34
        else:
            card_w = 1350
            card_x0 = (canvas_w - card_w) // 2
            card_y0 = 220
            title_font_size = 42
            meta_font_size = 26
            max_wrap_chars = 54

        font_sub = get_font(meta_font_size + 4, bold=True)
        font_meta = get_font(meta_font_size, bold=False)
        font_title = get_font(title_font_size, bold=True)
        font_pills = get_font(meta_font_size, bold=True)

        # Quebra do título
        title_lines = textwrap.wrap(display_title, width=max_wrap_chars)
        line_height = int(title_font_size * 1.35)
        title_block_h = len(title_lines) * line_height

        header_h = 80
        footer_h = 75
        padding = 42
        card_h = padding + header_h + title_block_h + padding + footer_h + padding
        card_x1 = card_x0 + card_w
        card_y1 = card_y0 + card_h

        # 1. Sombra suave e profunda
        shadow_box = [card_x0 - 16, card_y0 + 12, card_x1 + 16, card_y1 + 28]
        shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_layer)
        s_draw.rounded_rectangle(shadow_box, radius=36, fill=(0, 0, 0, 220))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(24))
        img = Image.alpha_composite(img, shadow_layer)
        draw = ImageDraw.Draw(img)

        # 2. Card Principal com Dark Theme Oficial do Reddit (#121213 / #1A1A1B)
        card_box = [card_x0, card_y0, card_x1, card_y1]
        draw.rounded_rectangle(card_box, radius=28, fill=(18, 18, 19, 255), outline=(60, 62, 65, 255), width=3)

        # 3. Ícone do Subreddit (Círculo Laranja #FF4500 com Snoo/R)
        icon_size = 58
        icon_x = card_x0 + padding
        icon_y = card_y0 + padding
        draw.ellipse([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size], fill=(255, 69, 0, 255))
        draw.text((icon_x + 18, icon_y + 10), "r/", font=get_font(30, bold=True), fill=(255, 255, 255, 255))

        # 4. Header: Subreddit + Autor + Timestamp
        text_start_x = icon_x + icon_size + 18
        draw.text((text_start_x, icon_y + 4), subreddit, font=font_sub, fill=(255, 255, 255, 255))
        sub_len = draw.textlength(subreddit, font=font_sub)
        meta_str = f" • Posted by {author} • 4h ago"
        draw.text((text_start_x + sub_len, icon_y + 8), meta_str, font=font_meta, fill=(145, 148, 150, 255))

        # 5. Título em Negrito e Alta Nitidez
        curr_y = icon_y + icon_size + 26
        for line in title_lines:
            draw.text((card_x0 + padding, curr_y), line, font=font_title, fill=(255, 255, 255, 255))
            curr_y += line_height

        # 6. Rodapé com Pills Interativas (Upvotes, Comentários, Share)
        curr_y += 20
        # Pill Upvotes (#FF4500)
        pill_up_w = 175
        pill_up_box = [card_x0 + padding, curr_y, card_x0 + padding + pill_up_w, curr_y + 54]
        draw.rounded_rectangle(pill_up_box, radius=27, fill=(45, 47, 50, 255))
        draw.text((card_x0 + padding + 20, curr_y + 12), f"▲  {score}", font=font_pills, fill=(255, 69, 0, 255))

        # Pill Comentários
        pill_com_x = card_x0 + padding + pill_up_w + 18
        pill_com_w = 190
        pill_com_box = [pill_com_x, curr_y, pill_com_x + pill_com_w, curr_y + 54]
        draw.rounded_rectangle(pill_com_box, radius=27, fill=(45, 47, 50, 255))
        draw.text((pill_com_x + 22, curr_y + 12), "💬  1.8k", font=font_pills, fill=(225, 228, 230, 255))

        # Pill Share
        pill_share_x = pill_com_x + pill_com_w + 18
        pill_share_w = 150
        pill_share_box = [pill_share_x, curr_y, pill_share_x + pill_share_w, curr_y + 54]
        draw.rounded_rectangle(pill_share_box, radius=27, fill=(45, 47, 50, 255))
        draw.text((pill_share_x + 24, curr_y + 12), "↗ Share", font=font_pills, fill=(225, 228, 230, 255))

        os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)
        img.save(output_png, "PNG")
        return output_png
