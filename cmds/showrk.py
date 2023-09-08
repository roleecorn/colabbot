from discord.ext import commands
from core.classes import Cog_extension
import sqlite3
import pandas as pd


class showrk(Cog_extension):
    @commands.command()
    async def rank(self, ctx):

        win_and_lose = sqlite3.connect("./data/win_and_lose.db")
        qry = "SELECT id,win,lose FROM wl order by win DESC limit 10"
        df = pd.read_sql_query(qry, win_and_lose)
        win_and_lose.close()

        context = "```\n"
        for i in range(10):
            try:
                member = await ctx.guild.fetch_member(int(df.iloc[i]["id"]))
            except Exception:
                context = context+f"第{i+1}位:noname\n"
                context = context+f" 勝場:{df.iloc[i]['win']}　"
                context = context+f" 敗場:{df.iloc[i]['lose']}　\n"
                continue
            if not member.nick:
                context = context+f"第{i+1}位:{str(member.name)}\n"
                context = context+f" 勝場:{df.iloc[i]['win']}　"
                context = context+f" 敗場:{df.iloc[i]['lose']}　\n"
                continue
            context = context+f"第{i+1}位:{str(member.nick)}\n"
            context = context+f" 勝場:{df.iloc[i]['win']}　"
            context = context+f" 敗場:{df.iloc[i]['lose']} \n"
        context = context+"```"
        await ctx.send(context)


async def setup(bot):
    await bot.add_cog(showrk(bot))
