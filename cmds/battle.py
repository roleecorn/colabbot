import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
from discord import File
import json
import random
import csv

def battle(player1:list,player2:list,player1name:str,player2name:str,skill1name,skill2name):
    # 速度：tmp[5]
    fast=random.randint(1,player1[5]+player2[5])
    if fast<= player1[5]:
        attacker=player1name
        attackdata=player1
        defender=player2name
        defenddata=player2
        skill=skill1name
    else :
        attacker=player2name
        attackdata=player2
        defender=player1name
        defenddata=player1
        skill=skill2name
    attackmode=random.random()
    # ＨＰ：tmp[0]
    if attackmode<0.1:
        word=[f"{attacker}  使用了{skill}，但  {defender}  躲開並給了他一拳！",
        f"{attacker}  不聽你的指揮睡著了，被  {defender}  乘虛而入！"]
        tmp=random.randint(5,10)
        damage =f"{defender} 造成了  {tmp}  點傷害"
        attackdata[0]=attackdata[0]-tmp
        detail=f"，{attacker}  剩下  {attackdata[0]}  點HP"
        descripe=word[random.randint(0,len(word)-1)]+damage+detail
        
        return (player1,player2,descripe)
    if attackmode<0.3:
        word=[f"{attacker}  使用了{skill}，但  {defender}  用消力將傷害化解了！",
        f"{attacker}  使用了{skill}，但被  {defender}  閃了過去！",
        f"你讓  {attacker}  使用{skill}，但他好像沒有在聽你說話?",
        f"{attacker}  使出的{skill}被  {defender}  擋下了，減輕了傷害！",
        f"{attacker}  的{skill}繞過了  {defender}  的防禦，但被  {defender}  避開了！",
        f"{attacker}  的{skill}打中了防禦架勢的  {defender}  ，  {defender}  後退了幾步！",
        f"{defender}  向上方跳躍迴避，避開了  {attacker}  的{skill}！"]
        tmp=0
        damage =f"{attacker}  沒有造成任何傷害"
        defenddata[0]=defenddata[0]-tmp
        detail=f"，{defender}  剩下  {defenddata[0]}  點HP"
        descripe=word[random.randint(0,len(word)-1)]+damage+detail
        return (player1,player2,descripe)
      

    
    if attackmode<0.9:
        word=[f"{attacker}  使用了{skill}，  {defender}  想閃過去但失敗！",
        f"{attacker}  使出的{skill}被  {defender}  擋下，但還是受傷了！",
        f"{attacker}  的{skill}繞過了  {defender}  的防禦，直接打中了  {defender}  ！",
        f"{attacker}  的{skill}打中了防禦架勢的  {defender}  ，  {defender}  被打飛出去了！",
        f"{defender}  避開了  {attacker}  的{skill}的直擊，但還是被波及到了！"]
        tmp=random.randint(5,15)
        damage =f"{attacker} 造成了  {tmp}  點傷害"
        defenddata[0]=defenddata[0]-tmp
        detail=f"，{defender}  剩下  {defenddata[0]}  點HP"
        descripe=word[random.randint(0,len(word)-1)]+damage+detail
        return (player1,player2,descripe)
    word=[f"{attacker}  的{skill}打中了  {defender}  ，效果絕佳！",
    f"{attacker}  的{skill}從意想不到的角度擊中了  {defender}  ，是會心一擊！"]
    tmp=random.randint(15,20)
    damage =f"{attacker} 造成了  {tmp}  點傷害"
    defenddata[0]=defenddata[0]-tmp
    detail=f"，{defender}  剩下  {defenddata[0]}  點HP"
    descripe=word[random.randint(0,len(word)-1)]+damage+detail
    return (player1,player2,descripe)
def changewin(userid):
    with open(os.path.join("./data/", "rank.json"), newline='', encoding='UTF-8') as jsonfile:
        rank = json.load(jsonfile)
        jsonfile.close()
    rank[userid]["win"]=rank[userid]["win"]+1
    tmp=rank[userid]["排名"]
    print(userid)
    if tmp==1:
        
        rank["rank"][str(tmp)]["win"]=rank["rank"][str(tmp)]["win"]+1
        
        return rank
    if tmp<11:
        rank["rank"][str(tmp)]["win"]=rank["rank"][str(tmp)]["win"]+1
        
        if rank["rank"][str(tmp)]["win"]>rank["rank"][str(tmp-1)]["win"]:
            
            rank=changerank(userid,tmp,rank)
            
            return rank
        
        return rank
    if tmp==11:
        
        if rank[userid]["win"]>rank["rank"]["10"]["win"]:
            print("debug0643")
            tmp = rank["rank"]["10"]["id"]
            rank[tmp]["排名"]=11
            rank["rank"]["10"]["id"]=userid
            rank["rank"]["10"]["win"]=rank[userid]["win"]
            if rank["rank"]["10"]["win"]>rank["rank"]["9"]["win"]:
                rank=changerank(userid,10,rank)
            return rank
        return rank 
def changerank(userid,userrank,rankfile):
    winer=rankfile["rank"][str(userrank)]["id"]
    loser=rankfile["rank"][str(userrank-1)]["id"]
    rankfile[winer]["排名"]=rankfile[winer]["排名"]-1
    rankfile[loser]["排名"]=rankfile[loser]["排名"]+1
    print("debugchangerank")
    print(rankfile["rank"])
    tmp=rankfile["rank"][str(userrank)]
    rankfile["rank"][str(userrank)]=rankfile["rank"][str(userrank-1)]
    rankfile["rank"][str(userrank-1)]=tmp
    
    tmp=rankfile["rank"][str(userrank)]
    if userrank==2:
        return rankfile
    if rankfile["rank"][str(userrank-1)]["win"]>rankfile["rank"][str(userrank-2)]["win"]:
        rankfile=changerank(userid,userrank-1,rankfile)
        return rankfile
    return rankfile
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
            print(waiting)
            battelfile.close()

            if waiting == "1":
                with open(os.path.join("./data/", "waiting.csv"), newline='', encoding='UTF-8',mode='w') as battelfile:
                    print(ctx.author)
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
            await channel.send(f"展開  {ctx.author.mention}  與  {challenger.mention}  的對戰")
            if blackcar<0.03:
                if random.random()<0.5:
                    loser=pok1name
                    winer=pok2name
                    trainer=challenger
                else :
                    loser=pok2name
                    winer=pok1name
                    trainer=ctx.author
                descripebox=""
                descripebox=descripebox+"突然一輛黑色高級車駛來急剎並打開車門，三名訓練家打開車門用超重球持續攻擊你們！\n裁判試圖前沖但肩部中了一記超重球而倒下！\n"
                descripebox=descripebox+f"由於抱着{trainer.name}，後背多次中球！\n{trainer.name}「  {loser}  ，你在幹什麼啊，  {loser}  ！」\n"
                descripebox=descripebox+f"{loser}  「呃呃啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊！！！」\n  {loser}  使出三記破壞死光，擊倒一個訓練家！\n"
                descripebox=descripebox+f"一發破壞死光擊中  {winer}  ！其他訓練家見狀不妙隨即駕車逃離！\n  {loser}  「什麼嘛，我的破壞死光還挺準的嘛，呵」\n"
                descripebox=descripebox+f"{loser}...{loser}啊…啊……\n"
                descripebox=descripebox+f"你的聲音為什麼要顫抖，{trainer.name}\n"
                descripebox=descripebox+f"我可是（停頓）銀河團團長，(站起){loser}啊，這點小傷無關緊要。\n"
                descripebox=descripebox+f"{trainer.name}「為什麼，要為了保護我——」\n"
                descripebox=descripebox+"保護訓練師就是我的使命！"
                await channel.send(descripebox)    
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
            await channel.send(descripebox)
            if pok1[0]>0:
                #waiting勝
                await channel.send(f"{pok1name}  獲得了勝利")
                rank=changewin(waiting)
                with open(os.path.join("./data/", "rank.json"), "w", encoding='UTF-8') as f:
                    json.dump(rank, f, indent = 4)
                    f.close()
                return
            #ctx.author勝
            await channel.send(f"{pok2name}  獲得了勝利")
            rank= changewin(str(ctx.author.id))
            with open(os.path.join("./data/", "rank.json"), "w", encoding='UTF-8') as f:
                json.dump(rank, f, indent = 4)
                f.close()
            return

def setup(bot):
    bot.add_cog(game(bot))