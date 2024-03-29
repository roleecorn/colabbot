from discord.ext import commands
from core.classes import Cog_extension
import os
import json
import random
import sqlite3
import pandas as pd
import logging

from Module_a.svs import car, ele2, valuerate, battledemo2
from Module_a.calaulate import final


class battle(Cog_extension):
    @commands.command()
    @commands.cooldown(3, 1200, commands.BucketType.user)
    async def duel(self, ctx):
        # 確認是否跟自己對打
        with open(os.path.join("./data/", "waiting.csv"), newline='',
                  encoding='UTF-8') as battelfile:
            waiting = battelfile.readline()

            battelfile.close()

        if waiting == str(ctx.author.id):
            await ctx.send("不能跟自己對打喔")
            return
        # 確認是否連線正常
        try:
            status = sqlite3.connect("./data/pokemon.db")
            qry = f"SELECT * FROM pokemon where id={ctx.author.id} "

            dfa = pd.read_sql_query(qry, status)
            if (dfa.empty):
                await ctx.send("你沒有寶可夢，請先領一隻\n領取寶可夢方法:\n&&create 你的寶可夢的名字")
                status.close()
                return
        except Exception:
            await ctx.send("抱歉出了bug，請聯繫<@534243081135063041>來修正")
            return
        # 確認是否有人在排隊了，如果有就抓取資料並關閉資料庫連線
        if waiting == "1":
            with open(os.path.join("./data/", "waiting.csv"), newline='',
                      encoding='UTF-8', mode='w') as battelfile:
                battelfile.write(str(ctx.author.id))
                battelfile.close()
            await ctx.send("排隊中")
            return
        try:
            qry = f"SELECT * FROM pokemon where id={waiting} "
            dfd = pd.read_sql_query(qry, status)
            if (dfd.empty):
                await ctx.send("抱歉出了bug，請聯繫<@534243081135063041>來修正")
                return
            status.close()
        except Exception:
            await ctx.send("抱歉出了bug，請聯繫<@534243081135063041>來修正")
            return
        with open(os.path.join("./data/", "waiting.csv"), newline='',
                  encoding='UTF-8', mode='w') as battelfile:
            battelfile.write("1")
            battelfile.close()

        # 換成pandas的形式

        poka = dfa.iloc[0]
        pokd = dfd.iloc[0]
        pok1name = pokd['name']
        pok2name = poka['name']

        guild = self.bot.get_guild(689838165347139766)
        channel = guild.get_channel(739739523130327040)
        challenger = await guild.fetch_member(int(waiting))
        await channel.send("展開  {}  與  {}  的對戰".format(
            ctx.author.mention, challenger.mention
        ))
        blackcar = random.random()
        if blackcar < 0.03:
            if random.random() < 0.5:
                loser = pok1name
                winer = pok2name
                trainer = challenger
                blackcar = ctx.author
            else:
                loser = pok2name
                winer = pok1name
                trainer = ctx.author
                blackcar = challenger

            final(blackcar.id, trainer.id)
            descripebox = car(trainer.name, loser, winer)
            await channel.send(descripebox)
            return
        with open(os.path.join("./data/", "skill.json"), newline='',
                  encoding='UTF-8') as jsonfile:
            skill = json.load(jsonfile)
            jsonfile.close()
        skill1 = skill[waiting]
        skill2 = skill[str(ctx.author.id)]
        descripebox = ""
        # 計算屬性差
        (elerate1, elerate2) = ele2(pokd, poka)
        # 計算數值差
        valuerate1 = valuerate(pokd, poka)
        valuerate2 = valuerate(poka, pokd)
        hpd = pokd['hp']
        hpa = poka["hp"]
        while (hpd > 0 and hpa > 0):
            chooseskill1 = random.sample(skill1.keys(), 1)
            chooseskill2 = random.sample(skill2.keys(), 1)
            (hpd, hpa, descripe) = battledemo2(
                hpd, hpa, pokd, poka,
                chooseskill1[0], chooseskill2[0],
                elerate1*valuerate1, elerate2*valuerate2
                )

            descripebox = descripebox+descripe+"\n"
        await channel.send(descripebox)

        if hpd > 0:
            # waiting勝
            await channel.send(f"{pok1name}  獲得了勝利")
            logging.warning(f"winner is {waiting}")

            final(int(waiting), ctx.author.id)
            return
        # ctx.author勝
        await channel.send(f"{pok2name}  獲得了勝利")
        logging.warning(f"winner is {ctx.author.id}")

        final(ctx.author.id, int(waiting))
        return


async def setup(bot):
    await bot.add_cog(battle(bot))
