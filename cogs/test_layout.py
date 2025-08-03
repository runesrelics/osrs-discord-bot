import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import io
import os

class TestLayoutCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.template_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))

    def create_grid_overlay(self, template_path):
        """Create a grid overlay on the template to help with positioning"""
        try:
            # Load the template
            template = Image.open(template_path).convert('RGBA')
            
            # Create a new transparent layer for the grid
            grid = Image.new('RGBA', template.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(grid)
            
            # Draw grid lines every 50 pixels
            for x in range(0, template.width, 50):
                draw.line([(x, 0), (x, template.height)], fill=(255, 0, 0, 128), width=1)
                # Add coordinate numbers
                draw.text((x+2, 2), str(x), fill=(255, 255, 0, 255))

            for y in range(0, template.height, 50):
                draw.line([(0, y), (template.width, y)], fill=(255, 0, 0, 128), width=1)
                # Add coordinate numbers
                draw.text((2, y+2), str(y), fill=(255, 255, 0, 255))

            # Mark important areas with boxes and labels
            areas = {
                "PFP Area": ((25, 25), (95, 95)),
                "Username": ((110, 45), (300, 70)),
                "Price": ((template.width-300, 45), (template.width-30, 70)),
                "Description": ((50, 200), (template.width-50, 500)),
                "Showcase": ((50, 800), (template.width-50, 1100))
            }

            for label, (start, end) in areas.items():
                # Draw box
                draw.rectangle([start, end], outline=(0, 255, 0, 255), width=2)
                # Add label
                draw.text((start[0], start[1]-20), label, fill=(0, 255, 255, 255))
                # Add coordinates
                coord_text = f"({start[0]},{start[1]}) to ({end[0]},{end[1]})"
                draw.text((start[0], end[1]+5), coord_text, fill=(255, 255, 0, 255))

            # Combine template and grid
            result = Image.alpha_composite(template, grid)
            
            # Save to buffer
            buffer = io.BytesIO()
            result.save(buffer, format='PNG')
            buffer.seek(0)
            
            return buffer

        except Exception as e:
            print(f"Error creating grid overlay: {str(e)}")
            raise

    @commands.command(name="showgrid")
    @commands.has_permissions(administrator=True)
    async def show_grid(self, ctx, template_type: str = "Main"):
        """Show a grid overlay on the template to help with positioning
        Usage: !showgrid [template_type]
        Template types: Main, PvP, HCIM, Iron, Special"""
        
        try:
            template_file = {
                "Main": "TEMPLATE_MAIN.png",
                "PvP": "TEMPLATE_PVP.png",
                "HCIM": "HCIM_TEMPLATE.png",
                "Iron": "TEMPLATE_IRON.png",
                "Special": "TEMPLATE_SPECIAL.png"
            }.get(template_type)

            if not template_file:
                await ctx.send("Invalid template type. Use: Main, PvP, HCIM, Iron, or Special")
                return

            template_path = os.path.join(self.template_dir, template_file)
            if not os.path.exists(template_path):
                await ctx.send(f"Template file not found: {template_file}")
                return

            # Create grid overlay
            grid_image = self.create_grid_overlay(template_path)
            
            # Send the image
            await ctx.send(
                "Grid overlay showing coordinates and areas. Use these numbers in config/layout.py",
                file=discord.File(grid_image, filename="grid_overlay.png")
            )

        except Exception as e:
            await ctx.send(f"Error creating grid overlay: {str(e)}")

async def setup(bot):
    await bot.add_cog(TestLayoutCog(bot))