import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json
from discord import File
import random
class Main(Cog_extension):

    @commands.command()
    async def ping(self,ctx):
        await ctx.send(f'{round(self.bot.latency*1000)}(ms)')
        print(ctx.message.channel_mentions)
        print(ctx.message.role_mentions)
        
        return
    @commands.command()
    async def setrole(self,ctx,channelid:int,roleid:int):
        print(("setrole"))
        flag=0
        #確認admin身分
        for role in ctx.author.roles :
            if "Administrator" == str(role):
                flag=1
        if flag==0:
            await ctx.send("not admin")
            return
        ####
        #json作法
        ####      
        with open(os.path.join("./data/", "output.json"), newline='') as jsonfile:
            parrent = json.load(jsonfile) 
            jsonfile.close()
        channelid=str(channelid)
        #如果頻道已經在列表內
        if channelid in parrent.keys():
            if roleid in parrent[channelid]:
                await ctx.send("already role")
                return

            parrent[channelid].append(roleid)
            await ctx.send("add role")
            with open(os.path.join("./data/", "output.json"), "w") as f:
                json.dump(parrent, f, indent = 4)
                f.close()
            return

        #如果頻道不在列表內
        parrent[channelid]=[roleid]
        with open(os.path.join("./data/", "output.json"), "w") as f:
            json.dump(parrent, f, indent = 4)
            f.close()
        await ctx.send("add role")
        return

    @commands.command()
    async def rmrole(self,ctx,channelid:int,roleid:int):
        #確認admin身分
        flag=0
        for role in ctx.author.roles :
            if "Administrator" == str(role):
                flag=1
        if flag==0:
            await ctx.send("not admin")
            return
        with open(os.path.join("./data/", "output.json"), newline='') as jsonfile:
            parrent = json.load(jsonfile) 
            jsonfile.close()
        channelid=str(channelid)
        #確認頻道在列表內
        if channelid not in parrent.keys():
            await ctx.send("compare loss")
            return
        #確認身分組在列表內  
        if roleid not in parrent[channelid]:
            await ctx.send("compare loss")
            return
        #移除身分組
        tmp=parrent[channelid].index(roleid)
        del parrent[channelid][tmp]
        with open(os.path.join("./data/", "output.json"), "w") as f:
            json.dump(parrent, f, indent = 4)
            f.close()
        await ctx.send("remove role")
        return

    @commands.command()
    async def showrole(self,ctx):
        with open(os.path.join("./data/", "output.json"), newline='') as jsonfile:
            parrent = json.load(jsonfile) 
            jsonfile.close()
        guild=ctx.guild
        channels=guild.text_channels
        tmp="版名/身分組\n"
        keys=parrent.keys()
        for channel in channels:
            if str(channel.id) not in keys:
                continue
            for rol in parrent[str(channel.id)]:
                role=guild.get_role(rol)
                if role == None:
                    continue
                role=str(role)
                tmp2=role.split("|")
                tmp=f"{tmp}__`{channel.name}`__　__`{tmp2[0]}`__\n"
                
                if len(tmp)>1000:
                    print(str(tmp))
                    await ctx.send(str(tmp))
                    tmp="版名/身分組\n"
            
        await ctx.send(str(tmp))
        return
    @commands.command()
    async def lolihelp(self,ctx):
        await ctx.send(f"!ping:確認延遲與機器人是否在線上\n!showrole:提供目前身分組標示\n!setrole 頻道id 身分組id:添加頻道對應身分組\n!rmrole 頻道id 身分組id:移除頻道對應身分組\n!rs arsb:丟a個骰子，其總和要為b")
    @commands.command()
    async def rs(self,ctx,ArsB):
        ArsB=ArsB.split("rs")
        if len(ArsB)!=2 :
            await ctx.send("格式似乎不太對")
            return
        if (not ArsB[0].isnumeric()) or (not ArsB[1].isnumeric()):
            await ctx.send("請輸入正整數喔")
            return
        if int(ArsB[0])<1:
            await ctx.send("你要不要看看你擲多少骰子")
            return
        if int(ArsB[0])>int(ArsB[1]):
            await ctx.send("||擲骰數||太大了，||總和數||吃不下了")
            return
        tmp=[]
        for i in range(int(ArsB[0])):
            tmp.append(random.random())
        tmp2=sum(tmp)
        tmp2=int(ArsB[1])/tmp2
        tmp=[i * tmp2 for i in tmp]
        tmp=[round(i,0) for i in tmp]
        for i in range(int(ArsB[0])):
            if tmp[i]==0:
                tmp[i]=1
        tmp2=sum(tmp)        
        while(tmp2 > int(ArsB[1])):
            tmp2=tmp2-1
            c=max(tmp)
            c=tmp.index(c)
            tmp[c]=tmp[c]-1
        while(tmp2 < int(ArsB[1])):
            tmp2=tmp2+1
            c=max(tmp)
            c=tmp.index(c)
            tmp[c]=tmp[c]+1
        tmp=[int(i) for i in tmp]
        await ctx.send(f"{ArsB[0]}次擲骰，總合為{ArsB[1]}\n{tmp}")
        print(tmp)

        

def setup(bot):
    bot.add_cog(Main(bot))