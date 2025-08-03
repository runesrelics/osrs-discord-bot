from PIL import Image, ImageDraw, ImageFont
import discord
import io
import aiohttp
import os

class EmbedGenerator:
    def __init__(self):
        self.template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        # Adjusted font sizes for better visibility
        self.font_size_title = 32
        self.font_size_normal = 24
        self.font_size_small = 20
        
        # Define template paths
        self.templates = {
            "Main": "TEMPLATE_MAIN.png",
            "PvP": "TEMPLATE_PVP.png",
            "HCIM": "HCIM_TEMPLATE.png",
            "Iron": "TEMPLATE_IRON.png",
            "Special": "TEMPLATE_SPECIAL.png"
        }

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
                font_title = ImageFont.truetype("arial.ttf", self.font_size_title)
                font_normal = ImageFont.truetype("arial.ttf", self.font_size_normal)
                font_small = ImageFont.truetype("arial.ttf", self.font_size_small)
            except:
                font_title = ImageFont.load_default()
                font_normal = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Add user avatar to top left (pfp area)
            avatar_bytes = await self.download_avatar(user.display_avatar.url)
            if avatar_bytes:
                avatar = Image.open(avatar_bytes).convert('RGBA')
                avatar = avatar.resize((60, 60))  # Smaller avatar to fit pfp area
                template.paste(avatar, (30, 30), avatar)  # Adjusted position to fit pfp area

            # Add username next to pfp area
            draw.text((100, 45), user.display_name, 
                     font=font_normal, fill=(255, 215, 0))  # Gold color for username

            # Add price and payment info in top right box
            draw.text((template.width - 250, 30), f"{price}", 
                     font=font_normal, fill=(255, 215, 0))  # Gold color for price
            draw.text((template.width - 250, 65), f"{payment_methods}", 
                     font=font_small, fill=(255, 255, 255))

            # Add description in the main center box
            # Adjusted position and width to fit the template's box
            description_box_width = template.width - 200  # Narrower width to fit box
            description_wrapped = self.wrap_text(description, font_normal, description_box_width)
            
            # Calculate text height to center vertically in the description box
            text_height = len(description_wrapped.split('\n')) * self.font_size_normal
            description_box_y = 200  # Top of description box
            description_box_height = 300  # Height of description box
            text_y = description_box_y + (description_box_height - text_height) // 2
            
            draw.text((100, text_y), description_wrapped, 
                     font=font_normal, fill=(255, 255, 255))

            # Add showcase image in bottom box
            if showcase_image_bytes:
                showcase_io = io.BytesIO(showcase_image_bytes)
                showcase = Image.open(showcase_io).convert('RGBA')
                
                # Calculate dimensions to fit the bottom box while maintaining aspect ratio
                showcase_box_height = 300
                showcase_box_width = template.width - 100
                
                # Resize image to fit box while maintaining aspect ratio
                showcase.thumbnail((showcase_box_width, showcase_box_height))
                
                # Center the image in the box
                x_offset = (showcase_box_width - showcase.width) // 2 + 50
                y_offset = template.height - showcase_box_height - 50
                
                template.paste(showcase, (x_offset, y_offset), showcase)

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