import discord
from discord.ext import commands
from .embed_generator import EmbedGenerator

class TestLayoutCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_generator = EmbedGenerator()

    @commands.command(name="testlayout")
    @commands.has_permissions(administrator=True)
    async def test_layout(self, ctx, account_type: str = "Main"):
        """Test the layout of a listing template
        Usage: !testlayout [account_type]
        Account types: Main, PvP, HCIM, Iron, Special"""
        
        # Test data
        test_description = "Test description for layout purposes. This is where the account details would go."
        test_price = "150"
        test_payment = "USD/Crypto/GP"

        try:
            # Use a test image or the first image attachment if provided
            test_image = None
            if ctx.message.attachments:
                test_image = await ctx.message.attachments[0].read()

            # Generate test listing
            listing_image = await self.embed_generator.generate_listing_image(
                account_type,
                ctx.author,
                test_description,
                test_price,
                test_payment,
                test_image
            )

            # Send the test listing
            file = discord.File(listing_image, filename="test_listing.png")
            await ctx.send(f"Test listing for {account_type} template:", file=file)

        except Exception as e:
            await ctx.send(f"Error generating test listing: {str(e)}")

async def setup(bot):
    await bot.add_cog(TestLayoutCog(bot))