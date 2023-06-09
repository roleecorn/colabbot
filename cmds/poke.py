import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json
import sqlite3
import pandas as pd


def changetofull(datas: int):
    datas = str(datas)
    fullnumber = {"1": "１", "2": "２", "3": "３", "4": "４",
                  "5": "５", "6": "６", "7": "７", "8": "８", "9": "９", "0": "０"}
    fulldata = []
    for i in range(len(datas)):
        fulldata.append(fullnumber[datas[i]])
    for i in range(7-len(datas)):
        fulldata.append("　")
    fulldata = "".join(fulldata)
    return fulldata


def changelong(skill: str):
    for _ in range(7-len(skill)):
        skill = skill+"　"
    return skill


class poke(Cog_extension):

    @commands.command()
    async def mypokemon(self, ctx):
        status = sqlite3.connect("./data/pokemon.db")
        qry = f"SELECT * FROM pokemon where id='{str(ctx.author.id)}'"
        df = pd.read_sql_query(qry, status)
        status.close()
        if (df.empty):
            await ctx.send("你還沒有領取寶可夢喔\n領取寶可夢方法:\n&&create 你的寶可夢的名字")
            return

        with open(os.path.join("./data/", "skill.json"), newline='', encoding='UTF-8') as jsonfile:
            skill = json.load(jsonfile)
            jsonfile.close()
        skills = list(skill[str(ctx.author.id)].keys())
        damage = []
        for i in range(len(skills)):
            damage.append(skill[str(ctx.author.id)][skills[i]])
        with open(os.path.join("./data/", "stamp.json"), newline='', encoding='UTF-8') as jsonfile:
            stamp = json.load(jsonfile)
            jsonfile.close()

        embed = discord.Embed(
            title=df['name'][0], description=chr(173), color=0x5cb3fd)
        if str(ctx.author.id) in stamp.keys():
            embed.set_thumbnail(url=stamp[str(ctx.author.id)])
        # for i in range(7):
        #     pokedata[i]=changetofull(pokedata[i])
        for i in range(4):
            skills[i] = changelong(skills[i])
            damage[i] = changetofull(damage[i])

        types = changelong(df['typea'][0]+df["typeb"][0])

        speed = changetofull(df["speed"][0])
        atk = changetofull(df["atk"][0])
        spatk = changetofull(df["spatk"][0])
        spdef = changetofull(df["spdef"][0])
        defv = changetofull(df["def"][0])
        hp = changetofull(df['hp'][0])
        level = changetofull(df['level'][0])
        embed.add_field(name="屬性　　　　　等級　　　　　",
                        value=f"{types}{level}", inline=False)
        embed.add_field(name="ＨＰ　　　　　速度　　　　　物攻",
                        value=f"{hp}{speed}{atk}", inline=False)
        embed.add_field(name="特攻　　　　　物防　　　　　特防",
                        value=f"{spatk}{defv}{spdef}", inline=False)

        embed.add_field(name="技能", value=chr(173), inline=False)

        embed.add_field(name=skills[0]+skills[1],
                        value=damage[0]+damage[1], inline=False)

        embed.add_field(name=skills[2]+skills[3],
                        value=damage[2]+damage[3], inline=False)
        win_and_lose = sqlite3.connect("./data/win_and_lose.db")
        qry = f"SELECT * FROM wl where id='{str(ctx.author.id)}'"
        df = pd.read_sql_query(qry, win_and_lose)
        win_and_lose.close()
        embed.add_field(name="持有物", value=chr(173), inline=False)
        money = changetofull(df["money"][0])
        exp = changetofull(df["exp"][0])
        win = changetofull(df["win"][0])
        lose = changetofull(df["lose"][0])
        embed.add_field(name="金錢　　　　　ＥＸＰ", value=f"{money}{exp}", inline=False)
        embed.add_field(name="對戰紀錄", value=chr(173), inline=False)
        embed.add_field(name="勝場　　　　　敗場", value=f"{win}{lose}", inline=False)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(poke(bot))
