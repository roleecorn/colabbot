import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json
import random
import sqlite3
import pandas as pd
from Module_a.svs import battle,car
from Module_a.calaulate import final
status = sqlite3.connect("data/pokemon.db")

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
        with open(os.path.join("./data/", "pokemon.json"), newline='', encoding='UTF-8') as jsonfile:
            pokemon = json.load(jsonfile)
            jsonfile.close()
        if str(ctx.author.id) not in pokemon.keys():
            await ctx.send("你沒有寶可夢，請先領一隻\n領取寶可夢方法:\n&&create 你的寶可夢的名字")
            return
        with open(os.path.join("./data/", "waiting.csv"), newline='', encoding='UTF-8') as battelfile:
            waiting=battelfile.readline()
            
            battelfile.close()

        if waiting == "1":
            with open(os.path.join("./data/", "waiting.csv"), newline='', encoding='UTF-8',mode='w') as battelfile:   
                battelfile.write(str(ctx.author.id))
                battelfile.close()
            await ctx.send("排隊中")
            return
        
        if waiting == str(ctx.author.id):
            await ctx.send("不能跟自己對打喔")
            return
        with open(os.path.join("./data/", "waiting.csv"), newline='', encoding='UTF-8',mode='w') as battelfile:
            battelfile.write("1")
            battelfile.close()
        pok1=pokemon[waiting][1]
        pok1name=pokemon[waiting][0]
        pok2=pokemon[str(ctx.author.id)][1]
        pok2name=pokemon[str(ctx.author.id)][0]
        blackcar=random.random()
        guild=self.bot.get_guild(689838165347139766)
        channel=guild.get_channel(739739523130327040)
        challenger = await guild.fetch_member(int(waiting))
        # await channel.send(f"展開  {ctx.author.mention}  與  {challenger.mention}  的對戰")
        if blackcar<0.03:
            if random.random()<0.5:
                loser=pok1name
                
                trainer=challenger.name
                blackcar=ctx.author.id
            else :
                loser=pok2name
                
                trainer=ctx.author.name
                blackcar=challenger.id
            rank= changewin(str(blackcar))
            writeback("rank.json",rank)
            descripebox=car(trainer,loser)
            return
        with open(os.path.join("./data/", "skill.json"), newline='', encoding='UTF-8') as jsonfile:
            skill = json.load(jsonfile)
            jsonfile.close()
        skill1=skill[waiting]
        skill2=skill[str(ctx.author.id)]
        descripebox=""
        while (pok1[0]>0 and pok2[0]>0):
            chooseskill1=random.sample(skill1.keys(),1)
            chooseskill2=random.sample(skill2.keys(),1)
            (pok1,pok2,descripe)=battle(pok1,pok2,pok1name,pok2name,chooseskill1[0],chooseskill2[0])
            descripebox=descripebox+descripe+"\n"
        # await channel.send(descripebox)
        print(descripebox)
        if pok1[0]>0:
            #waiting勝
            # await channel.send(f"{pok1name}  獲得了勝利")
            print(f"winner is {waiting}")
            rank=changewin(waiting)
            writeback("rank.json",rank)
            final(int(waiting),ctx.author.id)
            return
        #ctx.author勝
        # await channel.send(f"{pok2name}  獲得了勝利")
        print(f"winner is {ctx.author.id}")
        rank= changewin(str(ctx.author.id))
        writeback("rank.json",rank)
        final(ctx.author.id,int(waiting))
        return

def setup(bot):
    bot.add_cog(game(bot))