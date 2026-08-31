"""
High-Fidelity Dynamic Music Streaming Card Generator.
Renders unified glassmorphic 1280x720 (16:9) now-playing cards and start banners with 16:9 YouTube artwork,
ambient glow backdrop, progress bar, and Elite Bots branding.
"""
import io
import os
import ssl
import urllib.request
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


class CardGenerator:
    CARD_WIDTH = 1280
    CARD_HEIGHT = 720

    @classmethod
    def _get_font(cls, size: int, bold: bool = False):
        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except Exception:
            pass
        return ImageFont.load_default()

    @classmethod
    def _fetch_image(cls, url: Optional[str]) -> Optional[Image.Image]:
        if not url:
            return None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=5) as resp:
                data = resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception:
            return None

    @classmethod
    def generate_player_card(
        cls,
        title: str,
        artist: str,
        duration_sec: int,
        thumbnail_url: Optional[str] = None,
        requested_by: str = "User",
        is_playing: bool = True
    ) -> io.BytesIO:
        """Render modern glassmorphic 1280x720 (16:9) now-playing card."""
        # 1. Base dark canvas
        base = Image.new("RGBA", (cls.CARD_WIDTH, cls.CARD_HEIGHT), (12, 16, 26, 255))
        
        # 2. Thumbnail & Ambient Glow Backdrop
        thumb = cls._fetch_image(thumbnail_url)
        if thumb:
            # Ambient 16:9 glow background
            glow = thumb.resize((cls.CARD_WIDTH, cls.CARD_HEIGHT), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(50))
            dimmer = Image.new("RGBA", (cls.CARD_WIDTH, cls.CARD_HEIGHT), (10, 14, 24, 210))
            glow_dimmed = Image.alpha_composite(glow.convert("RGBA"), dimmer)
            base = Image.alpha_composite(base, glow_dimmed)
        else:
            thumb = Image.new("RGBA", (480, 270), (30, 40, 65, 255))

        # 3. Glassmorphic Card Container
        card_rect = [50, 50, cls.CARD_WIDTH - 50, cls.CARD_HEIGHT - 50]
        card_overlay = Image.new("RGBA", (cls.CARD_WIDTH, cls.CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_overlay)
        card_draw.rounded_rectangle(card_rect, radius=32, fill=(16, 22, 38, 225), outline=(70, 110, 210, 130), width=2)
        base = Image.alpha_composite(base, card_overlay)
        
        draw = ImageDraw.Draw(base)

        # 4. Fitted 16:9 YouTube Thumbnail Box on Left
        t_width = 440
        t_height = int(t_width * 9 / 16)  # 248px (exact 16:9)
        thumb_16_9 = ImageOps.fit(thumb, (t_width, t_height), Image.Resampling.LANCZOS).convert("RGBA")
        
        # Rounded mask for 16:9 thumbnail
        mask = Image.new("L", (t_width, t_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, t_width, t_height], radius=20, fill=255)
        
        t_x = 90
        t_y = 135
        base.paste(thumb_16_9, (t_x, t_y), mask)

        # Quality Badge under 16:9 Thumbnail
        draw.rounded_rectangle([t_x, t_y + t_height + 25, t_x + t_width, t_y + t_height + 68], radius=12, fill=(25, 35, 60, 200), outline=(50, 85, 160, 100))
        draw.text((t_x + 100, t_y + t_height + 36), "HD 1080p • 320 kbps Lossless", font=cls._get_font(18, bold=True), fill=(160, 195, 255))

        # 5. Badges & Metadata on Right
        badge_font = cls._get_font(18, bold=True)
        title_font = cls._get_font(34, bold=True)
        artist_font = cls._get_font(24, bold=False)
        meta_font = cls._get_font(20, bold=False)
        footer_font = cls._get_font(18, bold=True)

        right_x = 570

        # Top Badge: "▶ NOW STREAMING • 48 kHz"
        draw.rounded_rectangle([right_x, 135, right_x + 320, 175], radius=10, fill=(35, 75, 190, 230))
        draw.text((right_x + 20, 145), "▶ NOW STREAMING • 48 kHz", font=badge_font, fill=(240, 245, 255))

        # Title (Truncate with clean ellipsis)
        display_title = title if len(title) <= 28 else title[:26] + "..."
        draw.text((right_x, 200), display_title, font=title_font, fill=(255, 255, 255))

        # Artist
        display_artist = artist if len(artist) <= 36 else artist[:34] + "..."
        draw.text((right_x, 250), f"by {display_artist}", font=artist_font, fill=(185, 205, 240))

        # Requested by
        draw.text((right_x, 300), f"Requested by: {requested_by[:22]}", font=meta_font, fill=(140, 165, 210))

        # 6. Progress Bar
        bar_x = right_x
        bar_y = 365
        bar_w = 600
        bar_h = 12
        # Background bar
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=6, fill=(45, 60, 95, 220))
        # Active progress bar (simulate ~35%)
        active_w = int(bar_w * 0.35)
        draw.rounded_rectangle([bar_x, bar_y, bar_x + active_w, bar_y + bar_h], radius=6, fill=(70, 145, 255, 255))
        # Handle knob
        draw.ellipse([bar_x + active_w - 8, bar_y - 4, bar_x + active_w + 10, bar_y + 16], fill=(255, 255, 255))

        # Timers
        mins, secs = divmod(duration_sec, 60)
        curr_m, curr_s = divmod(int(duration_sec * 0.35), 60)
        draw.text((bar_x, bar_y + 22), f"{curr_m:02d}:{curr_s:02d}", font=meta_font, fill=(180, 200, 230))
        draw.text((bar_x + bar_w - 60, bar_y + 22), f"{mins:02d}:{secs:02d}", font=meta_font, fill=(180, 200, 230))

        # 7. Sleek Footer Branding
        draw.line([(90, 580), (cls.CARD_WIDTH - 90, 580)], fill=(45, 65, 110, 150), width=1)
        draw.text((90, 605), "⚡ Powered by Elite Bots (@EliteBotsTelegram)", font=footer_font, fill=(100, 175, 255))
        draw.text((cls.CARD_WIDTH - 300, 605), "TELEGRAM VOICE CHAT ENGINE", font=cls._get_font(16, bold=False), fill=(120, 150, 200))

        # Output to BytesIO
        output = io.BytesIO()
        base.convert("RGB").save(output, format="JPEG", quality=92)
        output.seek(0)
        return output

    @classmethod
    def generate_start_banner(cls) -> io.BytesIO:
        """Render high-res 1280x720 (16:9) start banner for bot DM."""
        base = Image.new("RGBA", (1280, 720), (12, 16, 28, 255))
        draw = ImageDraw.Draw(base)

        # Gradient accents
        for i in range(1280):
            r = int(12 + (i / 1280) * 22)
            g = int(20 + (i / 1280) * 38)
            b = int(55 + (i / 1280) * 65)
            draw.line([(i, 0), (i, 720)], fill=(r, g, b, 255))

        # Card overlay
        card = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(card)
        cdraw.rounded_rectangle([50, 50, 1230, 670], radius=32, fill=(16, 22, 38, 225), outline=(70, 110, 210, 130), width=2)
        base = Image.alpha_composite(base, card)
        draw = ImageDraw.Draw(base)

        title_font = cls._get_font(52, bold=True)
        sub_font = cls._get_font(26, bold=False)
        tag_font = cls._get_font(22, bold=True)

        draw.rounded_rectangle([100, 100, 420, 150], radius=12, fill=(45, 95, 230, 230))
        draw.text((115, 112), "OFFICIAL MUSIC API", font=tag_font, fill=(255, 255, 255))

        draw.text((100, 190), "ELITE MUSIC ENGINE", font=title_font, fill=(255, 255, 255))
        draw.text((100, 280), "Ultra-Low Latency Lossless 48kHz Voice Chat Streaming", font=sub_font, fill=(185, 210, 250))
        draw.text((100, 335), "7 Multi-Assistant Priority Fleet • Dynamic DSP • Bot Clone Engine", font=sub_font, fill=(145, 175, 220))
        draw.text((100, 390), "YouTube Data API v3 • 320kbps Crystal Audio • Real-Time Queue", font=sub_font, fill=(125, 155, 200))

        draw.line([(100, 520), (1180, 520)], fill=(45, 65, 110, 150), width=1)
        draw.text((100, 570), "⚡ Powered by Elite Bots (@EliteBotsTelegram)", font=tag_font, fill=(100, 175, 255))

        out = io.BytesIO()
        base.convert("RGB").save(out, format="JPEG", quality=92)
        out.seek(0)
        return out


card_generator = CardGenerator()
