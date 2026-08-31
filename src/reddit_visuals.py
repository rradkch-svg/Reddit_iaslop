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
        channel_name = card_data.get("channel_name", "Reddit Minute")
        time_ago = card_data.get("time_ago", "4h ago")
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

        # 3. Ícone do Canal (Avatar Circular a partir de icon.jpg)
        icon_size = 58
        icon_x = card_x0 + padding
        icon_y = card_y0 + padding
        
        # Localiza o arquivo de ícone customizado
        icon_candidate = card_data.get("icon_path", r"C:\Users\Aluno\Downloads\icon.jpg")
        if not (icon_candidate and os.path.exists(icon_candidate)):
            fallback_icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.jpg")
            if os.path.exists(fallback_icon):
                icon_candidate = fallback_icon
            else:
                icon_candidate = None

        icon_rendered = False
        if icon_candidate and os.path.exists(icon_candidate):
            try:
                with Image.open(icon_candidate) as src_icon:
                    src_icon = src_icon.convert("RGBA")
                    # Crop para proporção quadrada centralizada
                    sw, sh = src_icon.size
                    min_side = min(sw, sh)
                    cx, cy = (sw - min_side) // 2, (sh - min_side) // 2
                    src_icon = src_icon.crop((cx, cy, cx + min_side, cy + min_side))
                    
                    # Máscara circular com supersampling para bordas ultra-suaves
                    scale = 4
                    hi_size = icon_size * scale
                    src_icon = src_icon.resize((hi_size, hi_size), Image.Resampling.LANCZOS)
                    
                    mask = Image.new("L", (hi_size, hi_size), 0)
                    mask_d = ImageDraw.Draw(mask)
                    mask_d.ellipse((0, 0, hi_size - 1, hi_size - 1), fill=255)
                    
                    circ_img = Image.new("RGBA", (hi_size, hi_size), (0, 0, 0, 0))
                    circ_img.paste(src_icon, (0, 0), mask=mask)
                    circ_img = circ_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                    
                    img.paste(circ_img, (icon_x, icon_y), mask=circ_img)
                    
                    # Borda sutil de destaque ao redor do avatar
                    draw.ellipse([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size], outline=(255, 69, 0, 180), width=2)
                    icon_rendered = True
            except Exception:
                icon_rendered = False

        if not icon_rendered:
            # Fallback caso a imagem não possa ser carregada
            draw.ellipse([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size], fill=(255, 69, 0, 255))
            draw.text((icon_x + 10, icon_y + 12), "RM", font=get_font(28, bold=True), fill=(255, 255, 255, 255))

        # 4. Header: Nome do Canal "Reddit Minute" + Timestamp
        text_start_x = icon_x + icon_size + 18
        draw.text((text_start_x, icon_y + 4), channel_name, font=font_sub, fill=(255, 255, 255, 255))
        channel_len = draw.textlength(channel_name, font=font_sub)
        meta_str = f" • {time_ago}"
        draw.text((text_start_x + channel_len, icon_y + 8), meta_str, font=font_meta, fill=(145, 148, 150, 255))

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
