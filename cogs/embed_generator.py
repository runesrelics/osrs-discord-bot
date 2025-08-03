from PIL import Image, ImageDraw, ImageFont
import discord
import io
import aiohttp
import os
import unicodedata
from config.layout import TEXT_CONFIG, PFP_CONFIG, SHOWCASE_CONFIG

class EmbedGenerator:
    def __init__(self):
        self.template_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))
        self.font_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "Roboto-Bold.ttf"))
        
        # Color mappings (RGB format)
        self.COLOR_MAPPINGS = {
            'pfp': (255, 0, 255),      # #ff00ff - Discord user pfp
            'name': (68, 255, 37),      # #44ff25 - Discord display name
            'value': (255, 232, 37),    # #ffe825 - Account value
            'description': (0, 180, 255),# #00b4ff - Account description
            'image': (252, 0, 6)        # #fc0006 - Image location
        }

    def normalize_text(self, text):
        """Handle special characters in text"""
        # Convert special characters to their closest ASCII representation
        normalized = unicodedata.normalize('NFKD', text)
        # Remove any remaining non-ASCII characters
        ascii_text = normalized.encode('ascii', 'ignore').decode()
        return ascii_text if ascii_text.strip() else text  # Use original if conversion results in empty string

    def find_color_zone(self, map_image, target_color):
        """Find the bounding box of a specific color zone"""
        width, height = map_image.size
        left = width
        top = height
        right = 0
        bottom = 0
        found = False

        # Convert target_color to RGB if it's not already
        if len(target_color) > 3:
            target_color = target_color[:3]

        # Scan the image for matching pixels
        for y in range(height):
            for x in range(width):
                pixel = map_image.getpixel((x, y))
                # Convert pixel to RGB if it's not already
                if len(pixel) > 3:
                    pixel = pixel[:3]
                
                if pixel == target_color:
                    found = True
                    left = min(left, x)
                    top = min(top, y)
                    right = max(right, x)
                    bottom = max(bottom, y)

        if not found:
            return None

        return (left, top, right, bottom)

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
            template_path = os.path.join(self.template_dir, f"TEMPLATE_{account_type.upper()}.png")
            map_path = os.path.join(self.template_dir, f"TEMPLATE_{account_type.upper()}_MAP.png")
            
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"Template file not found: {template_path}")
            if not os.path.exists(map_path):
                raise FileNotFoundError(f"Map file not found: {map_path}")
            
            template = Image.open(template_path).convert('RGBA')
            map_image = Image.open(map_path).convert('RGB')
            
            draw = ImageDraw.Draw(template)
            
            # Load fonts with larger sizes
            try:
                if os.path.exists(self.font_path):
                    username_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['username']['font_size'])
                    price_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['price']['font_size'])
                    desc_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['description']['font_size'])
                    type_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['account_type']['font_size'])
                else:
                    print(f"Font not found at: {self.font_path}")
                    raise FileNotFoundError("Font file not found")
            except Exception as e:
                print(f"Font loading error: {str(e)}")
                username_font = ImageFont.load_default()
                price_font = ImageFont.load_default()
                desc_font = ImageFont.load_default()
                type_font = ImageFont.load_default()

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

            # 2. Username (using server nickname with special character handling)
            name_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['name'])
            if name_zone:
                # Get display name and handle special characters
                display_name = user.display_name
                display_name = self.normalize_text(display_name)
                draw.text((name_zone[0], name_zone[1]), display_name, 
                         font=username_font, fill=(255, 255, 255))

            # 3. Account Value
            value_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['value'])
            if value_zone:
                price_text = f"${price}USD/Crypto/GP"
                draw.text((value_zone[0], value_zone[1]), price_text, 
                         font=price_font, fill=(255, 255, 255))

            # 4. Description
            desc_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['description'])
            if desc_zone:
                # Handle special characters in description
                description = self.normalize_text(description)
                wrapped_text = self.fit_text_to_box(
                    description,
                    desc_font,
                    desc_zone[2] - desc_zone[0],
                    desc_zone[3] - desc_zone[1]
                )
                draw.text((desc_zone[0], desc_zone[1]), wrapped_text, 
                         font=desc_font, fill=(255, 255, 255),
                         spacing=TEXT_CONFIG['description']['line_spacing'])

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