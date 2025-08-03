from PIL import Image, ImageDraw, ImageFont
import discord
import io
import aiohttp
import os
import numpy as np

class EmbedGenerator:
    def __init__(self):
        self.template_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))
        
        # Color mappings (RGB format)
        self.COLOR_MAPPINGS = {
            'pfp': (255, 0, 255),      # #ff00ff - Discord user pfp
            'name': (68, 255, 37),      # #44ff25 - Discord display name
            'value': (255, 232, 37),    # #ffe825 - Account value
            'description': (0, 180, 255),# #00b4ff - Account description
            'image': (252, 0, 6)        # #fc0006 - Image location
        }
        
        # Define template paths
        self.templates = {
            "Main": ("TEMPLATE_MAIN.png", "TEMPLATE_MAIN_MAP.png"),
            "PvP": ("TEMPLATE_PVP.png", "TEMPLATE_PVP_MAP.png"),
            "HCIM": ("HCIM_TEMPLATE.png", "HCIM_TEMPLATE_MAP.png"),
            "Iron": ("TEMPLATE_IRON.png", "TEMPLATE_IRON_MAP.png"),
            "Special": ("TEMPLATE_SPECIAL.png", "TEMPLATE_SPECIAL_MAP.png")
        }

    def find_color_zone(self, map_image, target_color):
        """Find the bounding box of a specific color zone"""
        # Convert image to numpy array for faster processing
        img_array = np.array(map_image)
        
        # Find pixels matching the target color
        matches = np.all(img_array[:, :, :3] == target_color, axis=2)
        
        if not np.any(matches):
            return None
        
        # Get bounding box coordinates
        y_coords, x_coords = np.where(matches)
        return (
            int(x_coords.min()),  # left
            int(y_coords.min()),  # top
            int(x_coords.max()),  # right
            int(y_coords.max())   # bottom
        )

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

    def fit_text_to_box(self, text, font, max_width, max_height):
        """Fit and wrap text to a given box size"""
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
        """Generate a listing using the template and mapping system"""
        try:
            # Load both the clean template and its mapping
            template_path = os.path.join(self.template_dir, self.templates[account_type][0])
            map_path = os.path.join(self.template_dir, self.templates[account_type][1])
            
            template = Image.open(template_path).convert('RGBA')
            map_image = Image.open(map_path).convert('RGB')
            
            draw = ImageDraw.Draw(template)
            
            # Load font
            try:
                font = ImageFont.truetype("arial.ttf", 24)  # Default size, will scale if needed
            except:
                font = ImageFont.load_default()

            # Process each zone based on the mapping colors
            
            # 1. Profile Picture
            pfp_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['pfp'])
            if pfp_zone:
                avatar_bytes = await self.download_avatar(user.display_avatar.url)
                if avatar_bytes:
                    avatar = Image.open(avatar_bytes).convert('RGBA')
                    size = (pfp_zone[2] - pfp_zone[0], pfp_zone[3] - pfp_zone[1])
                    avatar = avatar.resize(size)
                    mask = self.create_circular_mask(size)
                    template.paste(avatar, (pfp_zone[0], pfp_zone[1]), mask)

            # 2. Username
            name_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['name'])
            if name_zone:
                # Scale font to fit zone
                zone_width = name_zone[2] - name_zone[0]
                zone_height = name_zone[3] - name_zone[1]
                font_size = 24
                while font_size > 8:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
                    if font.getlength(user.name) <= zone_width:
                        break
                    font_size -= 1
                draw.text((name_zone[0], name_zone[1]), user.name, font=font, fill=(255, 255, 255))

            # 3. Account Value
            value_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['value'])
            if value_zone:
                price_text = f"${price}USD/Crypto/GP"
                zone_width = value_zone[2] - value_zone[0]
                font_size = 24
                while font_size > 8:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
                    if font.getlength(price_text) <= zone_width:
                        break
                    font_size -= 1
                draw.text((value_zone[0], value_zone[1]), price_text, font=font, fill=(255, 255, 255))

            # 4. Description
            desc_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['description'])
            if desc_zone:
                zone_width = desc_zone[2] - desc_zone[0]
                zone_height = desc_zone[3] - desc_zone[1]
                wrapped_text = self.fit_text_to_box(description, font, zone_width, zone_height)
                draw.text((desc_zone[0], desc_zone[1]), wrapped_text, font=font, fill=(255, 255, 255))

            # 5. Showcase Image
            image_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['image'])
            if image_zone and showcase_image_bytes:
                showcase_io = io.BytesIO(showcase_image_bytes)
                showcase = Image.open(showcase_io).convert('RGBA')
                
                # Calculate dimensions to fit zone while maintaining aspect ratio
                zone_width = image_zone[2] - image_zone[0]
                zone_height = image_zone[3] - image_zone[1]
                
                showcase.thumbnail((zone_width, zone_height))
                
                # Center the image in the zone
                x_offset = image_zone[0] + (zone_width - showcase.width) // 2
                y_offset = image_zone[1] + (zone_height - showcase.height) // 2
                
                template.paste(showcase, (x_offset, y_offset))

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