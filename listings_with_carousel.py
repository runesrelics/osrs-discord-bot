    # Inside AccountListingModal.on_submit
    async def on_submit(self, interaction: discord.Interaction):
        trusted = any("trusted" in role.name.lower() for role in interaction.user.roles)
        target_channels = CHANNELS["trusted"] if trusted else CHANNELS["public"]
        target_channel_id = target_channels[self.channel_type]

        # Create the main listing embed
        listing_embed = discord.Embed(
            title=f"{self.account_type} Account Listing",
            description=self.description.value,
            color=discord.Color.gold()
        )
        listing_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        listing_embed.set_thumbnail(url="https://i.postimg.cc/ZYvXG4Ms/Runes-and-Relics.png")
        listing_embed.add_field(name="Value", value=self.price.value)
        listing_embed.add_field(name="Payment Methods", value=self.payment.value)

        listing_channel = interaction.guild.get_channel(target_channel_id)
        create_trade_channel = interaction.guild.get_channel(CHANNELS["create_trade"])

        await interaction.response.send_message(
            "Please upload up to 5 images in this channel. When finished, type 'done'.",
            ephemeral=True
        )

        images = []
        def check(m):
            return m.channel == create_trade_channel and m.author == interaction.user

        while len(images) < 5:
            try:
                msg = await interaction.client.wait_for("message", timeout=120.0, check=check)
            except asyncio.TimeoutError:
                break

            if msg.content.lower() == "done":
                break

            if msg.attachments:
                images.extend(msg.attachments)
            else:
                await create_trade_channel.send(
                    f"{interaction.user.mention} Please upload images or type 'done' to finish.",
                    delete_after=10
                )

        # Post the main listing embed first
        listing_msg = await listing_channel.send(embed=listing_embed)
        
        # If there are images, create and start the carousel
        if images:
            carousel = ImageCarousel(images, interaction.user)
            carousel_msg = await carousel.start(listing_channel)
            
            # Add the listing controls (trade button, etc.)
            view = ListingView(lister=interaction.user, listing_message=listing_msg)
            await listing_msg.edit(view=view)

        # Clean up user's messages
        async for old_msg in create_trade_channel.history(limit=50):
            if old_msg.author == interaction.user:
                try:
                    await old_msg.delete()
                except:
                    pass

        await interaction.followup.send("✅ Your listing has been posted!", ephemeral=True)