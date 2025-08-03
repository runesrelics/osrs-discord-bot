from PIL import Image, ImageDraw, ImageFont
import discord
import io
import aiohttp
import os
import math

class EmbedGenerator:
    def __init__(self):
        self.template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        self.font_size_normal = 24
        
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

            try:
                font = ImageFont.truetype("arial.ttf", self.font_size_normal)
            except:
                font = ImageFont.load_default()

            # Add circular avatar in pfp area
            avatar_bytes = await self.download_avatar(user.display_avatar.url)
            if avatar_bytes:
                avatar = Image.open(avatar_bytes).convert('RGBA')
                # Create circular avatar
                size = (70, 70)  # Size for pfp circle
                avatar = avatar.resize(size)
                mask = self.create_circular_mask(size)
                # Position for pfp (adjusted to match example)
                avatar_pos = (25, 25)
                template.paste(avatar, avatar_pos, mask)

            # Add username (just the username, no "Account Listing by")
            username_pos = (110, 45)  # Adjusted to align with pfp
            draw.text(username_pos, user.name, font=font, fill=(255, 255, 255))

            # Add price/payment info in top right
            # Adjusted to match example's positioning
            price_text = f"${price}USD/Crypto/GP"
            text_width = font.getlength(price_text)
            price_pos = (template.width - text_width - 30, 45)  # Right-aligned with padding
            draw.text(price_pos, price_text, font=font, fill=(255, 255, 255))

            # Add description in the center box
            # Adjusted to match example's text area
            description_box_width = template.width - 100  # Padding on both sides
            description_wrapped = self.wrap_text(description, font, description_box_width)
            description_pos = (50, 200)  # Adjusted to match example
            draw.text(description_pos, description_wrapped, font=font, fill=(255, 255, 255))

            # Add showcase image in bottom box
            if showcase_image_bytes:
                showcase_io = io.BytesIO(showcase_image_bytes)
                showcase = Image.open(showcase_io).convert('RGBA')
                
                # Calculate dimensions to fit the bottom box
                showcase_box_height = 300
                showcase_box_width = template.width - 100
                
                # Resize image maintaining aspect ratio
                showcase.thumbnail((showcase_box_width, showcase_box_height))
                
                # Center the image in the bottom box
                x_offset = (showcase_box_width - showcase.width) // 2 + 50
                y_offset = template.height - showcase_box_height - 50
                
                template.paste(showcase, (x_offset, y_offset))

            # Add account type label at bottom (if needed)
            if account_type.upper() != "SPECIAL":
                account_type_text = account_type.upper()
                text_width = font.getlength(account_type_text)
                type_pos = (template.width - text_width - 30, template.height - 40)
                draw.text(type_pos, account_type_text, font=font, fill=(0, 255, 255))  # Cyan color

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