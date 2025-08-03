import discord
from discord.ui import View, Button

class ImageCarousel(View):
    def __init__(self, images: list, user: discord.User):
        super().__init__(timeout=None)  # Carousel never times out
        self.images = images
        self.current_index = 0
        self.user = user
        self.message = None
        
        # Add navigation buttons
        self.add_item(Button(emoji="⬅️", custom_id="prev", style=discord.ButtonStyle.secondary))
        self.add_item(Button(emoji="➡️", custom_id="next", style=discord.ButtonStyle.secondary))
        
    async def update_message(self):
        """Updates the carousel message with current image"""
        if not self.message:
            return
            
        # Create embed for current image
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url=self.images[self.current_index].url)
        embed.set_footer(text=f"Image {self.current_index + 1}/{len(self.images)}")
        
        await self.message.edit(embed=embed, view=self)
        
    @discord.ui.button(custom_id="prev", label="", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        # Only allow the listing owner to change images
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only the listing owner can change images.", ephemeral=True)
            return
            
        self.current_index = (self.current_index - 1) % len(self.images)
        await self.update_message()
        await interaction.response.defer()
        
    @discord.ui.button(custom_id="next", label="", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        # Only allow the listing owner to change images
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Only the listing owner can change images.", ephemeral=True)
            return
            
        self.current_index = (self.current_index + 1) % len(self.images)
        await self.update_message()
        await interaction.response.defer()

    async def start(self, channel: discord.TextChannel):
        """Starts the image carousel"""
        if not self.images:
            return None
            
        # Create initial embed
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url=self.images[0].url)
        embed.set_footer(text=f"Image {self.current_index + 1}/{len(self.images)}")
        
        # Send carousel message
        self.message = await channel.send(embed=embed, view=self)
        return self.message