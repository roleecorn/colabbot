from discord.ext import commands
from core.classes import Cog_extension


class channels(Cog_extension):
    @commands.command()
    async def find(self, ctx, channelID: int):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        print("debug")
        # guild=self.bot.get_guild(guildId)
        channel = guild.get_channel(channelID)
        print(channel.position)

    @commands.command()
    async def move(self, ctx, channelID: int, movement: int):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild

        # guild=self.bot.get_guild(guildId)
        channel = guild.get_channel(channelID)

        tmp = channel.position

        await channel.edit(position=tmp+movement)

    @commands.command()
    async def createch(self, ctx, chname: str):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        await guild.create_text_channel(name=chname)

    @commands.command()
    async def belong(self, ctx, channelID: int, CategoryID: int):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        channel = guild.get_channel(channelID)
        Categ = guild.get_channel(CategoryID)
        await channel.edit(category=Categ)

    @commands.command()
    async def rename(self, ctx, channelID: int, channelname: str):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        channel = guild.get_channel(channelID)

        await channel.edit(name=channelname)

    @commands.command()
    async def boom(self, ctx, channelID: int):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        channel = guild.get_channel(channelID)

        await channel.delete()

    @commands.command()
    async def history(self, ctx, channelID: int, howmany: int):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        channel = guild.get_channel(channelID)
        async for message in channel.history(limit=howmany):
            print(message.content)

    @commands.command()
    async def myhistory(self, ctx, channelID: int, howmany: int):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        channel = guild.get_channel(channelID)
        if howmany == 0:
            howmany = None
        async for message in channel.history(limit=howmany):
            if message.id == 965922393451278387:
                continue
            if message.author.id == 534243081135063041:
                await message.delete()

    @commands.command()
    async def createvc(self, ctx, channelID: int, newname: str):
        if ctx.author.id != 534243081135063041:
            return
        guild = ctx.guild
        channel = guild.get_channel(channelID)
        print(channel)
        channel.clone(name=newname)
        # await guild.create_voice_channel(name=chname)


async def setup(bot):
    await bot.add_cog(channels(bot))
