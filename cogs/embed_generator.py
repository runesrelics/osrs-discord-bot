from PIL import Image, ImageDraw, ImageFont
import discord
import io
import aiohttp
import os
import unicodedata
import sqlite3
from config.layout import TEXT_CONFIG, PFP_CONFIG  # Removed SHOWCASE_CONFIG from import

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
            'vouches': (121, 119, 121), # #797779 - User vouches
            'image1': (252, 0, 6),      # #fc0006 - Image 1 location
            'image2': (0, 24, 255),     # #0018ff - Image 2 location
            'image3': (255, 222, 0)     # #ffde00 - Image 3 location
        }

        # Create fonts directory if it doesn't exist
        os.makedirs(os.path.dirname(self.font_path), exist_ok=True)
        
        # Database path for vouches
        self.db_path = "/app/data/vouches.db"

    def normalize_text(self, text):
        """Handle special characters in text"""
        try:
            # Try to keep special characters if possible
            return text.encode('utf-8').decode('utf-8')
        except UnicodeError:
            # Fall back to ASCII if needed
            normalized = unicodedata.normalize('NFKD', text)
            ascii_text = normalized.encode('ascii', 'ignore').decode()
            return ascii_text if ascii_text.strip() else text

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
        # Split by actual line breaks first, then by words
        paragraphs = text.split('\n')
        lines = []
        
        for paragraph in paragraphs:
            words = paragraph.split()
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

    def get_user_vouches(self, user_id):
        """Get the total number of vouches for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total vouches for the user
            cursor.execute("SELECT COUNT(*) FROM vouches WHERE user_id = ?", (user_id,))
            vouch_count = cursor.fetchone()[0]
            
            conn.close()
            return vouch_count
        except Exception as e:
            print(f"Error getting vouches for user {user_id}: {e}")
            return 0

    async def generate_listing_image(self, account_type, user, description, price, payment_methods):
        """Generate a listing using the template and mapping system (no showcase image)"""
        try:
            # Load both the clean template and its mapping
            # Handle special case for HCIM template naming
            if account_type.upper() == "HCIM":
                template_path = os.path.join(self.template_dir, "HCIM_TEMPLATE.png")
                map_path = os.path.join(self.template_dir, "HCIM_TEMPLATE_MAP.png")
            else:
                template_path = os.path.join(self.template_dir, f"TEMPLATE_{account_type.upper()}.png")
                map_path = os.path.join(self.template_dir, f"TEMPLATE_{account_type.upper()}_MAP.png")
            
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"Template file not found: {template_path}")
            if not os.path.exists(map_path):
                raise FileNotFoundError(f"Map file not found: {map_path}")
            
            template = Image.open(template_path).convert('RGBA')
            map_image = Image.open(map_path).convert('RGB')
            
            draw = ImageDraw.Draw(template)
            
            # Try to use Roboto font, fallback to system fonts if not available
            try:
                # Double the username font size (100% increase)
                username_font_size = TEXT_CONFIG['username']['font_size'] * 2
                username_font = ImageFont.truetype(self.font_path, username_font_size)
                price_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['price']['font_size'])
                desc_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['description']['font_size'])
                type_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['account_type']['font_size'])
                print(f"✅ Successfully loaded Roboto font from: {self.font_path}")
            except Exception as e:
                print(f"❌ Roboto font loading failed: {str(e)}")
                print(f"Font path attempted: {self.font_path}")
                print("Falling back to system fonts...")
                try:
                    username_font_size = TEXT_CONFIG['username']['font_size'] * 2
                    username_font = ImageFont.truetype("arial", username_font_size)
                    price_font = ImageFont.truetype("arial", TEXT_CONFIG['price']['font_size'])
                    desc_font = ImageFont.truetype("arial", TEXT_CONFIG['description']['font_size'])
                    type_font = ImageFont.truetype("arial", TEXT_CONFIG['account_type']['font_size'])
                except Exception as e2:
                    print(f"System font loading also failed: {str(e2)}, using default font")
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
                price_text = f"${price}"  # Just show the price, no extra text
                
                # Center the text in the zone
                text_width, text_height = draw.textbbox((0, 0), price_text, font=price_font)[2:]
                text_x = value_zone[0] + (value_zone[2] - value_zone[0] - text_width) // 2
                text_y = value_zone[1] + (value_zone[3] - value_zone[1] - text_height) // 2
                
                draw.text((text_x, text_y), price_text, font=price_font, fill=(255, 255, 255))

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
                
                # Calculate text height to ensure it fits within bounds
                lines = wrapped_text.split('\n')
                line_height = desc_font.getbbox('Ay')[3]  # Get line height
                total_height = len(lines) * line_height + (len(lines) - 1) * TEXT_CONFIG['description']['line_spacing']
                
                # If text is too tall, truncate it
                max_lines = (desc_zone[3] - desc_zone[1]) // (line_height + TEXT_CONFIG['description']['line_spacing'])
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    wrapped_text = '\n'.join(lines)
                
                # Draw the text with proper positioning
                draw.text((desc_zone[0], desc_zone[1]), wrapped_text, 
                         font=desc_font, fill=(255, 255, 255),
                         spacing=TEXT_CONFIG['description']['line_spacing'])



            # 6. User Vouches
            vouch_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['vouches'])
            if vouch_zone:
                vouch_count = self.get_user_vouches(user.id)
                vouch_text = str(vouch_count)  # Just the number, no "Vouches:" prefix
                
                # Use a smaller font for vouches
                vouch_font_size = 36  # Smaller than other text
                try:
                    vouch_font = ImageFont.truetype(self.font_path, vouch_font_size)
                except:
                    try:
                        vouch_font = ImageFont.truetype("arial", vouch_font_size)
                    except:
                        vouch_font = ImageFont.load_default()
                
                # Center the text in the zone
                text_width, text_height = draw.textbbox((0, 0), vouch_text, font=vouch_font)[2:]
                text_x = vouch_zone[0] + (vouch_zone[2] - vouch_zone[0] - text_width) // 2
                text_y = vouch_zone[1] + (vouch_zone[3] - vouch_zone[1] - text_height) // 2
                
                draw.text((text_x, text_y), vouch_text, font=vouch_font, fill=(255, 255, 255))

            # Convert to bytes for Discord upload
            final_buffer = io.BytesIO()
            template.save(final_buffer, format='PNG')
            final_buffer.seek(0)
            
            return final_buffer
            
        except Exception as e:
            print(f"Error generating listing image: {str(e)}")
            raise

    async def generate_image_template(self, image_bytes_list):
        """Generate an image template based on the number of images (1-3)"""
        try:
            num_images = len(image_bytes_list)
            if num_images == 0:
                return None
            if num_images > 3:
                num_images = 3  # Limit to 3 images
                image_bytes_list = image_bytes_list[:3]
            
            # Load the appropriate template and map based on number of images
            template_path = os.path.join(self.template_dir, "IMAGE_TEMPLATE.png")
            map_path = os.path.join(self.template_dir, f"IMAGE_TEMPLATE_MAP{num_images}.png")
            
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"Image template file not found: {template_path}")
            if not os.path.exists(map_path):
                raise FileNotFoundError(f"Image map file not found: {map_path}")
            
            template = Image.open(template_path).convert('RGBA')
            map_image = Image.open(map_path).convert('RGB')
            
            # Process each image based on the number of images
            for i, image_bytes in enumerate(image_bytes_list):
                if i >= 3:  # Safety check
                    break
                
                # Determine which color mapping to use based on image position
                if i == 0:
                    color_key = 'image1'
                elif i == 1:
                    color_key = 'image2'
                elif i == 2:
                    color_key = 'image3'
                else:
                    continue
                
                # Find the zone for this image
                image_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS[color_key])
                if image_zone and image_bytes:
                    image_io = io.BytesIO(image_bytes)
                    image = Image.open(image_io).convert('RGBA')
                    
                    # Calculate dimensions to fit within the zone
                    zone_width = image_zone[2] - image_zone[0]
                    zone_height = image_zone[3] - image_zone[1]
                    
                    scale_x = zone_width / image.width
                    scale_y = zone_height / image.height
                    scale_factor = min(scale_x, scale_y)  # Stay within bounds
                    
                    new_width = int(image.width * scale_factor)
                    new_height = int(image.height * scale_factor)
                    image = image.resize((new_width, new_height), Image.LANCZOS)
                    
                    # Center the image in the zone
                    x_offset = image_zone[0] + (zone_width - image.width) // 2
                    y_offset = image_zone[1] + (zone_height - image.height) // 2
                    
                    template.paste(image, (x_offset, y_offset))
            
            # Convert to bytes
            final_buffer = io.BytesIO()
            template.save(final_buffer, format='PNG')
            final_buffer.seek(0)
            
            return final_buffer
            
        except Exception as e:
            print(f"Error generating image template: {str(e)}")
            raise

    async def send_listing(self, channel, account_template_file, image_template_file=None):
        """Send the listing to the channel with both account and image templates"""
        files = [discord.File(account_template_file, filename="account_details.png")]
        
        if image_template_file:
            files.append(discord.File(image_template_file, filename="showcase_images.png"))
        
        return await channel.send(files=files)