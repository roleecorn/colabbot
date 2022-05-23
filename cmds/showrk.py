import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
from discord import File
import json
import random
class game(Cog_extension):
    @commands.command()
    async def rank(self,ctx):
        with open(os.path.join("./data/", "rank.json"), newline='', encoding='UTF-8') as jsonfile:
            rank = json.load(jsonfile)
            jsonfile.close()
        ranking=rank["rank"]
        # guild=self.bot.get_guild(ctx.guild)
        context=""
        for i in range(10):
            tmp=ranking[str(i+1)]
            member = await ctx.guild.fetch_member(int(tmp["id"]))
            if member.nick==None:
                context=context+f"第{i+1}位:"+str(member.name)
                context=context+f" 勝場:{tmp['win']}\n"
                
                continue
            context=context+f"第{i+1}位:"+str(member.name)+f" 勝場:{tmp['win']}\n"
        await ctx.send(context)


def setup(bot):
    bot.add_cog(game(bot))