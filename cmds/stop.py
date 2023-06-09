import discord
from discord.ext import commands
from core.classes import Cog_extension
import sys


class stop(Cog_extension):

    @commands.command()
    async def exit(self, ctx):
        flag = 0
        for role in ctx.author.roles:
            if "Administrator" == str(role):
                flag = 1
        if ctx.author.id == 534243081135063041:
            flag = 1
        if flag == 0:
            await ctx.send("not admin")
            return
        await ctx.send("おやすみ")
        sys.exit()


def setup(bot):
    bot.add_cog(stop(bot))
