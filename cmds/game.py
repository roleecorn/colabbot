import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
# from discord import File
import json
import random
import sqlite3
from Module_a.nameformat import checkname
import pandas as pd
class game(Cog_extension):
    @commands.command()
    async def create(self,ctx,name):
        if (checkname(name)):
            await ctx.send(checkname(name))
            return
        id = str(ctx.author.id)
        status = sqlite3.connect("/gdrive/My Drive/colabpractice/dcbot/data/pokemon.db")
        qry = f"SELECT * FROM pokemon where id='{id}';"
        df = pd.read_sql_query(qry, status)

        if(not df.empty):
            await ctx.send("你已經有一隻寶可夢了，請愛他")
            status.close()
            return
        
        tmp=[40,40,40,40,40,40]
        for i in range(len(tmp)) :
            tmp[i]=tmp[i]+(random.randint(0,20))
        tmp.append(5)
        element={
        '1':"水",
        '2':"火",
        '3':"草"}
        tmp.append(element[str(random.randint(1,3))])
        atype=tmp[7]
        btype=""
        level=tmp[6]
        hp=tmp[0]
        speed=tmp[5]
        atk=tmp[1]
        defv=tmp[2]
        spatk=tmp[3]
        spdef=tmp[4]
        
        cmd = "insert into pokemon(id	,name,typea,typeb,level,hp,	speed,	atk,	def,	spatk,	spdef) values('{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}')".format(str(ctx.author.id),name,atype,btype,level,hp,speed,atk,defv,spatk,spdef)
        status.execute(cmd)
        status.commit()
        status.close()

        with open(os.path.join("./data/", "skill.json"), newline='', encoding='UTF-8') as jsonfile:
            skill = json.load(jsonfile)
            jsonfile.close()
        skill[str(ctx.author.id)]={"衝擊":0,"高速星星":0,"居合斬":0,"連環巴掌":0}
        with open(os.path.join("./data/", "skill.json"), "w", encoding='UTF-8') as f:
            json.dump(skill, f, indent = 4)
            f.close()
        win_and_lose =sqlite3.connect("/gdrive/My Drive/colabpractice/dcbot/data/win_and_lose.db")
        cmd = "insert into wl(id,win,lose,money,exp) values('{}','{}','{}','{}','{}')".format(str(ctx.author.id),0,0,0,0)
        win_and_lose.execute(cmd)
        win_and_lose.commit()
        win_and_lose.close()
        # with open(os.path.join("./data/", "rank.json"), newline='', encoding='UTF-8') as jsonfile:
        #     rank = json.load(jsonfile)
        #     jsonfile.close()
        # rank[str(ctx.author.id)]={"win":0, 'lose':0, "排名":11}

        # with open(os.path.join("./data/", "rank.json"), "w", encoding='UTF-8') as f:
        #     json.dump(rank, f, indent = 4)
        #     f.close()
        
        await ctx.send("恭喜，你有了新的寶可夢了")
        await ctx.send(f"他的數值為\n```\n等級：{tmp[6]}\n屬性：{tmp[7]}\nＨＰ：{tmp[0]}\n攻擊：{tmp[1]}\n防禦：{tmp[2]}\n特攻：{tmp[3]}\n特防：{tmp[4]}\n速度：{tmp[5]}\n```")
   

    @commands.command()
    async def pokemonset(self,ctx,mode,arg1="none",arg2="none"):

        status = sqlite3.connect("/gdrive/My Drive/colabpractice/dcbot/data/pokemon.db")
        qry = f"SELECT * FROM pokemon where id='{str(ctx.author.id)}'"
        df = pd.read_sql_query(qry, status)
        if(df.empty):
            await ctx.send("你還沒有領取寶可夢喔\n領取寶可夢方法:\n&&create 你的寶可夢的名字")
            status.close()
            return

        status.close()
        
        if mode=="name":
            if arg1=="none":
                await ctx.send("請輸入名字")
                return
            check=checkname(arg1)    
            if (check):
                await ctx.send(check)
                return


            tmp=df.iloc[0]['name']
            status = sqlite3.connect("/gdrive/My Drive/colabpractice/dcbot/data/pokemon.db")
            cmd=f"update pokemon set name='{arg1}' where id={str(ctx.author.id)};"
            status.execute(cmd)
            status.commit()
            status.close()
            await ctx.send(f"將寶可夢從{tmp}改名為{arg1}了")
            return
        if mode=="skill":
            if (arg2=="none"):
                await ctx.send("請輸入要遺忘的技能與要學會的技能")
                return
            if (len(arg2)>6):
                await ctx.send("技能名稱太長了")
                return
            with open(os.path.join("./data/", "skill.json"), newline='', encoding='UTF-8') as jsonfile:
                skill = json.load(jsonfile)
                jsonfile.close()
            if arg1 not in skill[str(ctx.author.id)].keys():
                await ctx.send("沒有這個技能")
                return
            if arg2 in skill[str(ctx.author.id)].keys():
                await ctx.send("已經有這個技能了")
                return
            tmp=skill[str(ctx.author.id)][arg1]
            del skill[str(ctx.author.id)][arg1]
            skill[str(ctx.author.id)][arg2]=tmp
            print(skill[str(ctx.author.id)])
            with open(os.path.join("./data/", "skill.json"), "w", encoding='UTF-8') as f:
                json.dump(skill, f, indent = 4)
                f.close()
            await ctx.send(f"忘記了{arg1}後學會了{arg2}")
            return
        if mode == "stamp":
            if not(arg1):
                await ctx.send(f"請輸入圖片位置")
                return
            with open(os.path.join("./data/", "stamp.json"), newline='', encoding='UTF-8') as jsonfile:
                stamp = json.load(jsonfile)
                jsonfile.close()
            
            stamp[str(ctx.author.id)]=str(ctx.message.attachments[0])
            

            with open(os.path.join("./data/", "stamp.json"), "w", encoding='UTF-8') as f:
                json.dump(stamp, f, indent = 4)
                f.close()
            await ctx.send("新增了照片")
            return
        await ctx.send(f"還沒有{mode}這個指令")
        return

def setup(bot):
    bot.add_cog(game(bot))