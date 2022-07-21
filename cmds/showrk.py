import discord
from discord.ext import commands
from core.classes import Cog_extension
# import os
# from discord import File
# import json
import sqlite3
import pandas as pd

class game(Cog_extension):
    @commands.command()
    async def rank(self,ctx):

        win_and_lose =sqlite3.connect("/gdrive/My Drive/colabpractice/dcbot/data/win_and_lose.db")
        qry = f"SELECT id,win,lose FROM wl order by win DESC limit 10"
        df = pd.read_sql_query(qry, win_and_lose)
        win_and_lose.close()
        
        # with open(os.path.join("./data/", "rank.json"), newline='', encoding='UTF-8') as jsonfile:
        #     rank = json.load(jsonfile)
        #     jsonfile.close()
        # ranking=rank["rank"]

        context=""
        for i in range(10):
            # tmp=ranking[str(i+1)]
            # member = await ctx.guild.fetch_member(int(tmp["id"]))
            member = await ctx.guild.fetch_member(int(df.iloc[i]["id"]))
            if member.nick==None:
                context=context+f"第{i+1}位:"+str(member.name)
                context=context+f" 勝場:{df.iloc[i]['win']}　"
                context=context+f" 敗場:{df.iloc[i]['lose']}　\n"
                continue
            context=context+f"第{i+1}位:"+str(member.nick)
            context=context+f" 勝場:{df.iloc[i]['win']}　"
            context=context+f" 敗場:{df.iloc[i]['lose']} \n"
        await ctx.send(context)


def setup(bot):
    bot.add_cog(game(bot))