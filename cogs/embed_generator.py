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
            'header': (156, 0, 255),    # #9c00ff - Account type header
            'details_left': (0, 180, 255), # #00b4ff - Left side account details
            'details_right': (255, 0, 0),  # #ff0000 - Right side account details
            'vouches': (121, 119, 121), # #797779 - User vouches
            'image1': (252, 0, 6),      # #fc0006 - Image 1 location
            'image2': (0, 24, 255),     # #0018ff - Image 2 location
            'image3': (156, 0, 255),    # #9c00ff - Image 3 location (changed from yellow)
            # GP Listing color mappings
            'gp_pfp': (255, 255, 255),  # #ffffff - Discord user pfp
            'gp_name': (128, 128, 128), # #808080 - Discord server name
            'gp_price': (0, 29, 243),   # #001df3 - Price
            'gp_vouches': (243, 114, 0), # #f37200 - Vouch count
            'gp_amount': (0, 255, 255), # #00ffff - Amount
            'gp_payment': (255, 0, 255) # #ff00ff - Payment method
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

    def draw_multiline_text(self, draw, text_lines, font, zone, max_lines=4):
        """Draw multiple lines with proper spacing"""
        # Filter out empty lines
        non_empty_lines = [line.strip() for line in text_lines if line.strip()]
        
        # Limit to max_lines
        lines_to_draw = non_empty_lines[:max_lines]
        
        if not lines_to_draw:
            return
        
        line_height = font.getbbox('Ay')[3]  # Get line height
        spacing = 5  # Pixels between lines
        
        for i, line in enumerate(lines_to_draw):
            y_position = zone[1] + 15 + (i * (line_height + spacing))  # Add 15px padding down
            draw.text((zone[0], y_position), line, font=font, fill=(255, 255, 255))

    def get_user_vouches(self, user_id):
        """Get the total number of vouches for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total vouches for the user from the count column
            cursor.execute("SELECT count FROM vouches WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            conn.close()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error getting vouches for user {user_id}: {e}")
            return 0

    async def generate_listing_image(self, account_type, user, account_header, details_left, details_right, price, payment_methods):
        """Generate a listing using the template and mapping system with header and split details"""
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
                # Use normal font sizes (removed the doubling)
                username_font_size = TEXT_CONFIG['username']['font_size']
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
                    username_font_size = TEXT_CONFIG['username']['font_size']
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

            # 4. Account Header
            header_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['header'])
            if header_zone:
                # Handle special characters in header
                account_header = self.normalize_text(account_header)
                # Use a smaller font for the header
                header_font = ImageFont.truetype(self.font_path, TEXT_CONFIG['account_type']['font_size']) if os.path.exists(self.font_path) else ImageFont.load_default()
                
                # Center the text in the zone
                text_width, text_height = draw.textbbox((0, 0), account_header, font=header_font)[2:]
                text_x = header_zone[0] + (header_zone[2] - header_zone[0] - text_width) // 2
                text_y = header_zone[1] + (header_zone[3] - header_zone[1] - text_height) // 2
                
                draw.text((text_x, text_y), account_header, 
                         font=header_font, fill=(231, 185, 57))

            # 5. Left Side Details
            details_left_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['details_left'])
            if details_left_zone:
                # Split details_left into lines and add bullet points
                details_left_lines = [f"• {line.strip()}" for line in details_left.split('\n') if line.strip()]
                self.draw_multiline_text(draw, details_left_lines, desc_font, details_left_zone, max_lines=4)

            # 6. Right Side Details
            details_right_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['details_right'])
            if details_right_zone:
                # Split details_right into lines and add bullet points
                details_right_lines = [f"• {line.strip()}" for line in details_right.split('\n') if line.strip()]
                self.draw_multiline_text(draw, details_right_lines, desc_font, details_right_zone, max_lines=4)



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
            
            print(f"Debug: Loading template from: {template_path}")
            print(f"Debug: Loading map from: {map_path}")
            
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"Image template file not found: {template_path}")
            if not os.path.exists(map_path):
                raise FileNotFoundError(f"Image map file not found: {map_path}")
            
            template = Image.open(template_path).convert('RGBA')
            map_image = Image.open(map_path).convert('RGB')
            
            print(f"Debug: Template size: {template.size}")
            print(f"Debug: Map size: {map_image.size}")
            print(f"Debug: Processing {num_images} images")
            
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
                print(f"Debug: Image {i+1} zone for color {color_key}: {image_zone}")
                
                if image_zone and image_bytes:
                    image_io = io.BytesIO(image_bytes)
                    image = Image.open(image_io).convert('RGBA')
                    
                    # Calculate dimensions to fit within the zone
                    zone_width = image_zone[2] - image_zone[0]
                    zone_height = image_zone[3] - image_zone[1]
                    
                    print(f"Debug: Image {i+1} original size: {image.size}, zone size: {zone_width}x{zone_height}")
                    
                    scale_x = zone_width / image.width
                    scale_y = zone_height / image.height
                    scale_factor = min(scale_x, scale_y)  # Stay within bounds
                    
                    new_width = int(image.width * scale_factor)
                    new_height = int(image.height * scale_factor)
                    image = image.resize((new_width, new_height), Image.LANCZOS)
                    
                    # Center the image in the zone
                    x_offset = image_zone[0] + (zone_width - new_width) // 2
                    y_offset = image_zone[1] + (zone_height - new_height) // 2
                    
                    print(f"Debug: Image {i+1} final size: {image.size}, position: ({x_offset}, {y_offset})")
                    print(f"Debug: Image {i+1} zone bounds: ({image_zone[0]}, {image_zone[1]}) to ({image_zone[2]}, {image_zone[3]})")
                    
                    # Check if image is within template bounds
                    template_width, template_height = template.size
                    if (x_offset + new_width > template_width or y_offset + new_height > template_height or 
                        x_offset < 0 or y_offset < 0):
                        print(f"Debug: Image {i+1} would be outside template bounds! Template: {template.size}")
                    else:
                        print(f"Debug: Image {i+1} is within template bounds")
                    
                    # Check for zone overlap with previous images
                    for j in range(i):
                        prev_color_key = f'image{j+1}'
                        prev_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS[prev_color_key])
                        if prev_zone:
                            # Check if current image overlaps with previous image's zone
                            if (x_offset < prev_zone[2] and x_offset + new_width > prev_zone[0] and
                                y_offset < prev_zone[3] and y_offset + new_height > prev_zone[1]):
                                print(f"Debug: WARNING - Image {i+1} overlaps with Image {j+1}!")
                    
                    template.paste(image, (x_offset, y_offset))
                    print(f"Debug: Image {i+1} pasted successfully")
                else:
                    print(f"Debug: No zone found for image {i+1} or no image bytes")
                    if not image_zone:
                        print(f"Debug: Color {color_key} ({self.COLOR_MAPPINGS[color_key]}) not found in map")
                    if not image_bytes:
                        print(f"Debug: No image bytes for image {i+1}")
            
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
        # Send account details template first
        account_msg = await channel.send(files=[discord.File(account_template_file, filename="account_details.png")])
        
        # Send image template as a separate message if provided (this will be the main listing message)
        if image_template_file:
            listing_msg = await channel.send(files=[discord.File(image_template_file, filename="showcase_images.png")])
            return listing_msg, account_msg
        else:
            # If no image template, return the account details message
            listing_msg = await channel.send(files=[discord.File(account_template_file, filename="account_details.png")])
            return listing_msg, account_msg

    async def generate_gp_listing_image(self, gp_type, user, price, amount, payment_method):
        """Generate a GP listing image based on the template"""
        try:
            # Determine template based on GP type
            template_name = f"GPLISTING_{gp_type.upper()}.png"
            template_path = os.path.join(self.template_dir, template_name)
            map_path = os.path.join(self.template_dir, "GPLISTING_MAP.png")
            
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"GP template file not found: {template_path}")
            if not os.path.exists(map_path):
                raise FileNotFoundError(f"GP map file not found: {map_path}")
            
            # Load template and map
            template = Image.open(template_path).convert('RGBA')
            map_image = Image.open(map_path).convert('RGBA')
            
            # Scale template to 800x1200 (HxW) for optimal Discord display
            template = template.resize((1200, 800), Image.LANCZOS)
            map_image = map_image.resize((1200, 800), Image.LANCZOS)
            
            # Load font
            try:
                font_large = ImageFont.truetype(self.font_path, 48)
                font_medium = ImageFont.truetype(self.font_path, 36)
                font_small = ImageFont.truetype(self.font_path, 24)
            except OSError:
                print("Font loading error: cannot open resource, using default font")
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Get user vouches
            vouches = self.get_user_vouches(user.id)
            
            # Download and process user avatar
            avatar_bytes = await self.download_avatar(user.avatar)
            if avatar_bytes:
                avatar = Image.open(avatar_bytes).convert('RGBA')
                avatar = avatar.resize((80, 80), Image.LANCZOS)
                
                # Create circular mask
                mask = self.create_circular_mask((80, 80))
                avatar.putalpha(mask)
                
                # Find PFP zone and paste
                pfp_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['gp_pfp'])
                if pfp_zone:
                    x_offset = pfp_zone[0] + (pfp_zone[2] - pfp_zone[0] - 80) // 2
                    y_offset = pfp_zone[1] + (pfp_zone[3] - pfp_zone[1] - 80) // 2
                    template.paste(avatar, (x_offset, y_offset), avatar)
            
            # Draw text elements
            draw = ImageDraw.Draw(template)
            
            # User server name (100% larger than account listings)
            name_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['gp_name'])
            if name_zone:
                name_text = self.normalize_text(user.display_name)
                name_font = ImageFont.truetype(self.font_path, 72) if os.path.exists(self.font_path) else ImageFont.load_default()
                name_bbox = name_font.getbbox(name_text)
                name_width = name_bbox[2] - name_bbox[0]
                name_height = name_bbox[3] - name_bbox[1]
                
                name_x = name_zone[0] + (name_zone[2] - name_zone[0] - name_width) // 2
                name_y = name_zone[1] + (name_zone[3] - name_zone[1] - name_height) // 2
                draw.text((name_x, name_y), name_text, fill=(255, 255, 255), font=name_font)
            
            # Price
            price_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['gp_price'])
            if price_zone:
                price_text = f"${price}"  # Only show the price value
                price_font = ImageFont.truetype(self.font_path, 48) if os.path.exists(self.font_path) else ImageFont.load_default()
                price_bbox = price_font.getbbox(price_text)
                price_width = price_bbox[2] - price_bbox[0]
                price_height = price_bbox[3] - price_bbox[1]
                
                price_x = price_zone[0] + (price_zone[2] - price_zone[0] - price_width) // 2
                price_y = price_zone[1] + (price_zone[3] - price_zone[1] - price_height) // 2
                draw.text((price_x, price_y), price_text, fill=(255, 255, 255), font=price_font)
            
            # Vouch count (just the number)
            vouch_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['gp_vouches'])
            if vouch_zone:
                vouch_text = str(vouches)
                vouch_font = ImageFont.truetype(self.font_path, 36) if os.path.exists(self.font_path) else ImageFont.load_default()
                vouch_bbox = vouch_font.getbbox(vouch_text)
                vouch_width = vouch_bbox[2] - vouch_bbox[0]
                vouch_height = vouch_bbox[3] - vouch_bbox[1]
                
                vouch_x = vouch_zone[0] + (vouch_zone[2] - vouch_zone[0] - vouch_width) // 2
                vouch_y = vouch_zone[1] + (vouch_zone[3] - vouch_zone[1] - vouch_height) // 2
                draw.text((vouch_x, vouch_y), vouch_text, fill=(255, 255, 255), font=vouch_font)
            
            # Amount
            amount_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['gp_amount'])
            if amount_zone:
                amount_text = self.normalize_text(amount)
                amount_font = ImageFont.truetype(self.font_path, 48) if os.path.exists(self.font_path) else ImageFont.load_default()
                amount_bbox = amount_font.getbbox(amount_text)
                amount_width = amount_bbox[2] - amount_bbox[0]
                amount_height = amount_bbox[3] - amount_bbox[1]
                
                amount_x = amount_zone[0] + (amount_zone[2] - amount_zone[0] - amount_width) // 2
                amount_y = amount_zone[1] + (amount_zone[3] - amount_zone[1] - amount_height) // 2
                draw.text((amount_x, amount_y), amount_text, fill=(255, 255, 255), font=amount_font)
            
            # Payment method
            payment_zone = self.find_color_zone(map_image, self.COLOR_MAPPINGS['gp_payment'])
            if payment_zone:
                payment_text = self.normalize_text(payment_method)
                payment_font = ImageFont.truetype(self.font_path, 36) if os.path.exists(self.font_path) else ImageFont.load_default()
                payment_bbox = payment_font.getbbox(payment_text)
                payment_width = payment_bbox[2] - payment_bbox[0]
                payment_height = payment_bbox[3] - payment_bbox[1]
                
                payment_x = payment_zone[0] + (payment_zone[2] - payment_zone[0] - payment_width) // 2
                payment_y = payment_zone[1] + (payment_zone[3] - payment_zone[1] - payment_height) // 2
                draw.text((payment_x, payment_y), payment_text, fill=(255, 255, 255), font=payment_font)
            
            # Convert to bytes
            final_buffer = io.BytesIO()
            template.save(final_buffer, format='PNG')
            final_buffer.seek(0)
            
            return final_buffer
            
        except Exception as e:
            print(f"Error generating GP listing image: {str(e)}")
            raise

    async def send_gp_listing(self, channel, gp_template_file):
        """Send the GP listing to the channel"""
        listing_msg = await channel.send(files=[discord.File(gp_template_file, filename="gp_listing.png")])
        return listing_msg