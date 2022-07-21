import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json
import random
import sqlite3
import pandas as pd
from Module_a.svs import car,battledemo

from Module_a.calaulate import final


def writeback(filename:str,jsondata):
    with open(os.path.join("./data/", filename), "w", encoding='UTF-8') as f:
        json.dump(jsondata, f, indent = 4)
        f.close()


def changerank(rankboard,userrank):
    tmp=rankboard["rank"][str(userrank)]
    #本體排名-1
    rankboard[tmp["id"]]['排名'] = rankboard[tmp["id"]]['排名']-1
    #交換
    rankboard["rank"][str(userrank)] = rankboard["rank"][str(userrank-1)]
    rankboard["rank"][str(userrank-1)]=tmp
    #敵人排名+1
    tmp=rankboard["rank"][str(userrank)]
    rankboard[tmp["id"]]['排名'] = rankboard[tmp["id"]]['排名']+1
    
    return rankboard
def checkbalnece(rankboard,userrank):
    if userrank==1:
        return True
    if userrank !=11:
        challenger = rankboard["rank"][str(userrank)]['win']

    defender = rankboard["rank"][str(userrank-1)]['win']
    if challenger>defender:
        return False
    return True
def changewin(userid):
    with open(os.path.join("./data/", "rank.json"), newline='', encoding='UTF-8') as jsonfile:
        rank = json.load(jsonfile)
        jsonfile.close()

    rank[userid]["win"]=rank[userid]["win"]+1

    tmp=rank[userid]["排名"]
    
    if tmp !=11:
        rank["rank"][str(tmp)]["win"]=rank["rank"][str(tmp)]["win"]+1
    if tmp == 11:
        if rank[userid]["win"]>rank['rank']["10"]['win']:
            out_of_rank=rank['rank']["10"]['id']
            rank[str(out_of_rank)]["排名"]=11
            rank['rank']["10"]['id']=str(userid)
            rank['rank']["10"]['win']=rank[userid]["win"]
            rank[userid]["排名"]=10
            tmp=10
        else :
            return rank
    flagbalnece=checkbalnece(rank,tmp)
    while (not flagbalnece):
        rank=changerank(rank,tmp)
        tmp=tmp-1
        flagbalnece=checkbalnece(rank,tmp)

    return rank
class game(Cog_extension):
    @commands.command()
    @commands.cooldown(3, 1200, commands.BucketType.user)
    async def duel(self,ctx):
        #確認是否跟自己對打
        with open(os.path.join("./data/", "waiting.csv"), newline='', encoding='UTF-8') as battelfile:
            waiting=battelfile.readline()
            
            battelfile.close()

        if waiting == str(ctx.author.id):
            await ctx.send("不能跟自己對打喔")
            return
        #確認是否連線正常
        try:
            status = sqlite3.connect("/gdrive/My Drive/colabpractice/dcbot/data/pokemon.db")
            qry = f"SELECT * FROM pokemon where id={ctx.author.id} "
            
            dfa = pd.read_sql_query(qry, status)
            if (dfa.empty):
                await ctx.send("你沒有寶可夢，請先領一隻\n領取寶可夢方法:\n&&create 你的寶可夢的名字")
                status.close()
                return
        except:
            await ctx.send("抱歉出了bug，請聯繫<@534243081135063041>來修正")
            return
        #確認是否有人在排隊了，如果有就抓取資料並關閉資料庫連線
        if waiting == "1":
            with open(os.path.join("./data/", "waiting.csv"), newline='', encoding='UTF-8',mode='w') as battelfile:   
                battelfile.write(str(ctx.author.id))
                battelfile.close()
            await ctx.send("排隊中")
            return
        try:
            qry = f"SELECT * FROM pokemon where id={waiting} "
            dfd = pd.read_sql_query(qry, status)
            if(dfd.empty):
                await ctx.send("抱歉出了bug，請聯繫<@534243081135063041>來修正")
                return
            status.close()
        except:
            await ctx.send("抱歉出了bug，請聯繫<@534243081135063041>來修正")
            return
        with open(os.path.join("./data/", "waiting.csv"), newline='', encoding='UTF-8',mode='w') as battelfile:
            battelfile.write("1")
            battelfile.close()
        
        #換成pandas的形式
        try:
            poka=dfa.iloc[0]
            
            pokd=dfd.iloc[0]
            pok1name=pokd['name']
            pok2name=poka['name']

        except:
            await ctx.send("抱歉出了bug，請聯繫<@534243081135063041>來修正")
        
        
        guild=self.bot.get_guild(689838165347139766)
        channel=guild.get_channel(739739523130327040)
        challenger = await guild.fetch_member(int(waiting))
        await channel.send(f"展開  {ctx.author.mention}  與  {challenger.mention}  的對戰")
        blackcar=random.random()
        if blackcar<0.03:
            if random.random()<0.5:
                loser=pok1name
                winer=pok2name
                trainer=challenger
                blackcar=ctx.author
            else :
                loser=pok2name
                winer=pok1name
                trainer=ctx.author
                blackcar=challenger

            final(blackcar.id,trainer.id)
            descripebox=car(trainer.name,loser,winer)
            await channel.send(descripebox)
            return
        with open(os.path.join("./data/", "skill.json"), newline='', encoding='UTF-8') as jsonfile:
            skill = json.load(jsonfile)
            jsonfile.close()
        skill1=skill[waiting]
        skill2=skill[str(ctx.author.id)]
        descripebox=""

        while (pokd['hp']>0 and poka["hp"]>0):
            chooseskill1=random.sample(skill1.keys(),1)
            chooseskill2=random.sample(skill2.keys(),1)

            (pokd,poka,descripe)=battledemo(pokd,poka,pok1name,pok2name,chooseskill1[0],chooseskill2[0])
        

            descripebox=descripebox+descripe+"\n"
        await channel.send(descripebox)
        
        if pokd['hp']>0:
            #waiting勝
            await channel.send(f"{pok1name}  獲得了勝利")
            print(f"winner is {waiting}")

            final(int(waiting),ctx.author.id)
            return
        #ctx.author勝
        await channel.send(f"{pok2name}  獲得了勝利")
        print(f"winner is {ctx.author.id}")

        final(ctx.author.id,int(waiting))
        return

def setup(bot):
    bot.add_cog(game(bot))