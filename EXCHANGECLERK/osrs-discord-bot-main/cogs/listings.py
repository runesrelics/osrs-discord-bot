import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
from .embed_generator import EmbedGenerator

class AccountListingModal(Modal):
    def __init__(self, account_type: str, channel_type: str):
        super().__init__(title=f"List an OSRS {account_type} Account")
        self.account_type = account_type
        self.channel_type = channel_type
        
        self.description = TextInput(
            label="Account Description",
            style=discord.TextStyle.paragraph,
            placeholder="Describe your account's stats, quests, achievements, etc.",
            max_length=500  # Limit to ensure it fits in template
        )
        
        self.price = TextInput(
            label="Price / Value",
            placeholder="Enter your asking price",
            max_length=50
        )
        
        self.payment = TextInput(
            label="Payment Methods",
            placeholder="List accepted payment methods",
            max_length=100
        )

        self.add_item(self.description)
        self.add_item(self.price)
        self.add_item(self.payment)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)
        target_channels = CHANNELS["trusted"] if trusted else CHANNELS["public"]
        target_channel_id = target_channels[self.channel_type]
        listing_channel = interaction.guild.get_channel(target_channel_id)

        # Ask for showcase image
        await interaction.followup.send(
            "Please upload ONE showcase image for your listing (30 seconds).",
            ephemeral=True
        )

        def check(m):
            return (m.author == interaction.user and 
                   m.channel == interaction.channel and 
                   m.attachments)

        try:
            msg = await interaction.client.wait_for("message", timeout=30.0, check=check)
            if msg.attachments:
                showcase_image = await msg.attachments[0].read()
                
                # Generate the custom listing image
                embed_generator = EmbedGenerator()
                listing_image = await embed_generator.generate_listing_image(
                    self.account_type,
                    interaction.user,
                    self.description.value,
                    self.price.value,
                    self.payment.value,
                    showcase_image
                )

                # Create and send the listing
                file = discord.File(listing_image, filename="listing.png")
                embed = embed_generator.create_listing_embed(
                    self.account_type,
                    interaction.user,
                    file
                )
                
                listing_msg = await listing_channel.send(file=file, embed=embed)
                
                # Add the listing controls
                view = ListingView(lister=interaction.user, listing_message=listing_msg)
                await listing_msg.edit(view=view)
                
                await interaction.followup.send("✅ Your listing has been posted!", ephemeral=True)
                
                # Clean up the showcase image message
                try:
                    await msg.delete()
                except:
                    pass
                    
            else:
                await interaction.followup.send("❌ No image was provided. Please try listing again.", ephemeral=True)
                
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ No image was provided in time. Please try listing again.", ephemeral=True)
            return