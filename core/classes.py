import discord
from discord.ext import commands


class Cog_extension(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @staticmethod
    def bIsDeveloper(nId:int = 0):
        if nId == 534243081135063041:
            return True
        return False
    @staticmethod
    def bIsAdmin(author) -> bool:
        # DM 情境下沒有 guild_permissions，直接 False
        if not hasattr(author, "guild_permissions"):
            return False
        return author.guild_permissions.administrator
    @staticmethod
    def bIsAAFanclub(ctx):
        if ctx.guild.id == 689838165347139766:
            return True
        return False
