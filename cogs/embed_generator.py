from PIL import Image, ImageDraw, ImageFont
import discord
import io
import aiohttp
import os
from config.layout import PFP_CONFIG, TEXT_CONFIG, SHOWCASE_CONFIG

class EmbedGenerator:
    def __init__(self):
        self.template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        
        # Define template paths
        self.templates = {
            "Main": "TEMPLATE_MAIN.png",
            "PvP": "TEMPLATE_PVP.png",
            "HCIM": "HCIM_TEMPLATE.png",
            "Iron": "TEMPLATE_IRON.png",
            "Special": "TEMPLATE_SPECIAL.png"
        }

    def create_circular_mask(self, size):
        """Create a circular mask for the avatar"""
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        return mask

    async def download_avatar(self, avatar_url):
        """Download user's avatar"""
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                if resp.status == 200:
                    return io.BytesIO(await resp.read())
        return None

    def wrap_text(self, text, font, max_width):
        """Wrap text to fit within a given width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            current_line.append(word)
            line_width = font.getlength(" ".join(current_line))
            if line_width > max_width:
                if len(current_line) == 1:
                    lines.append(current_line[0])
                    current_line = []
                else:
                    current_line.pop()
                    lines.append(" ".join(current_line))
                    current_line = [word]
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return "\n".join(lines)

    async def generate_listing_image(self, account_type, user, description, price, payment_methods, showcase_image_bytes):
        """Generate a listing using the pre-made template"""
        try:
            # Load the appropriate template
            template_path = os.path.join(self.template_dir, self.templates[account_type])
            template = Image.open(template_path).convert('RGBA')
            draw = ImageDraw.Draw(template)

            # Load fonts
            username_font = ImageFont.truetype("arial.ttf", TEXT_CONFIG['username']['font_size'])
            price_font = ImageFont.truetype("arial.ttf", TEXT_CONFIG['price']['font_size'])
            desc_font = ImageFont.truetype("arial.ttf", TEXT_CONFIG['description']['font_size'])
            type_font = ImageFont.truetype("arial.ttf", TEXT_CONFIG['account_type']['font_size'])

            # Add circular avatar
            avatar_bytes = await self.download_avatar(user.display_avatar.url)
            if avatar_bytes:
                avatar = Image.open(avatar_bytes).convert('RGBA')
                avatar = avatar.resize(PFP_CONFIG['size'])
                mask = self.create_circular_mask(PFP_CONFIG['size'])
                template.paste(avatar, PFP_CONFIG['position'], mask)

            # Add username
            draw.text(
                TEXT_CONFIG['username']['position'],
                user.name,
                font=username_font,
                fill=TEXT_CONFIG['username']['color']
            )

            # Add price/payment info
            price_text = f"${price}USD/Crypto/GP"
            text_width = price_font.getlength(price_text)
            price_pos = (
                template.width - text_width - TEXT_CONFIG['price']['right_padding'],
                TEXT_CONFIG['price']['position'][1]
            )
            draw.text(price_pos, price_text, font=price_font, fill=TEXT_CONFIG['price']['color'])

            # Add description
            description_wrapped = self.wrap_text(
                description,
                desc_font,
                TEXT_CONFIG['description']['max_width']
            )
            draw.text(
                TEXT_CONFIG['description']['position'],
                description_wrapped,
                font=desc_font,
                fill=TEXT_CONFIG['description']['color'],
                spacing=TEXT_CONFIG['description']['line_spacing']
            )

            # Add showcase image
            if showcase_image_bytes:
                showcase_io = io.BytesIO(showcase_image_bytes)
                showcase = Image.open(showcase_io).convert('RGBA')
                
                # Resize image maintaining aspect ratio
                showcase.thumbnail((
                    SHOWCASE_CONFIG['max_width'],
                    SHOWCASE_CONFIG['max_height']
                ))
                
                # Center the image
                x_offset = SHOWCASE_CONFIG['position'][0] + (
                    SHOWCASE_CONFIG['max_width'] - showcase.width
                ) // 2
                y_offset = SHOWCASE_CONFIG['position'][1]
                
                template.paste(showcase, (x_offset, y_offset))

            # Add account type label
            if account_type.upper() != "SPECIAL":
                account_type_text = account_type.upper()
                text_width = type_font.getlength(account_type_text)
                type_pos = (
                    template.width - text_width - TEXT_CONFIG['account_type']['right_padding'],
                    TEXT_CONFIG['account_type']['position'][1]
                )
                draw.text(
                    type_pos,
                    account_type_text,
                    font=type_font,
                    fill=TEXT_CONFIG['account_type']['color']
                )

            # Convert to bytes for Discord upload
            final_buffer = io.BytesIO()
            template.save(final_buffer, format='PNG')
            final_buffer.seek(0)
            
            return final_buffer
            
        except Exception as e:
            print(f"Error generating listing image: {str(e)}")
            raise

    async def send_listing(self, channel, file):
        """Send the listing to the channel"""
        return await channel.send(file=discord.File(file, filename="listing.png"))