import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json
from discord import File
import random
# from disnake import AllowedMentions
class post(Cog_extension):    

    
    @commands.command()
    async def post(self,ctx,*arg):
        # guild=self.bot.get_guild(ctx.guild_id)
        if ctx.author.id != 534243081135063041:
            return
        channelid=739739523130327040
        
        guild=self.bot.get_guild(689838165347139766)
        #aa形象區738239898716471377
        #dice區739739523130327040
        #2版777541172100857888
        
        # channel=guild.get_channel(channelid)
        try :
            channelid=int(arg[-1])
            channel=guild.get_channel(channelid)
        except :
            channel = None
        
        if channel != None:
            flag=True
        if channel==None:
            channel=guild.get_channel(739739523130327040)
            flag=False
        message=None
        
        
        allowed_mention=discord.AllowedMentions(
        users=False,         # Whether to ping individual user @mentions
        everyone=False,      # Whether to ping @everyone or @here mentions
        roles=False,         # Whether to ping role @mentions
        replied_user=False    # Whether to ping on replies to messages
        )
        if len(arg)>0:
            tmp=" "
            if flag:
                for i in range(len(arg)-1):
                    tmp=tmp+"\n"+arg[i]
                await channel.send(content=tmp,reference=None)
            if (not flag):
                for i in range(len(arg)):
                    tmp=tmp+"\n"+arg[i]
                await channel.send(content=tmp,reference=None)
        if len(ctx.message.attachments)>0:
            await channel.send(ctx.message.attachments[0])
    @commands.command()
    async def pin(self,ctx,url:str):
        if ctx.author.id != 534243081135063041:
            return
        tmp=url.split('/')
        guildId=int(tmp[-3])
        channelID=int(tmp[-2])
        messageID=int(tmp[-1])
        guild=self.bot.get_guild(guildId)
        channel=guild.get_channel(channelID)
        message=await channel.fetch_message(messageID)
        await message.pin(reason="test")
    @commands.command()
    async def unpin(self,ctx,url:str):
        if ctx.author.id != 534243081135063041:
            return
        tmp=url.split('/')
        guildId=int(tmp[-3])
        channelID=int(tmp[-2])
        messageID=int(tmp[-1])
        guild=self.bot.get_guild(guildId)
        channel=guild.get_channel(channelID)
        message=await channel.fetch_message(messageID)
        await message.unpin()

    @commands.command()
    async def read(self,ctx,arg:int ):
        if ctx.author.id != 534243081135063041:
            return
        message= await ctx.send("test")
        
        await message.edit(content ="done")
    @commands.command()
    async def edit(self,ctx,url:str,text:str):
        if ctx.author.id != 534243081135063041:
            return
        tmp=url.split('/')
        guildId=int(tmp[-3])
        channelID=int(tmp[-2])
        messageID=int(tmp[-1])
        guild=self.bot.get_guild(guildId)
        channel=guild.get_channel(channelID)
        message=await channel.fetch_message(messageID)
        await message.edit(content =text)
    @commands.command()
    async def upload(self,ctx,board,chapter):
        users=[534243081135063041]
        if ctx.author.id not in users:
            await ctx.send("你不是檔案持有人")
            return
        
        guild=self.bot.get_guild(689838165347139766)
        channel=guild.get_channel(864319397979750401)
        tmp=ctx.message.jump_url
        for filename in os.listdir(f'D:/python-training/AAwork/{board}版搬運/{chapter}'):
            
            await channel.send(file=discord.File(os.path.join(f"D:/python-training/AAwork/{board}版搬運/{chapter}",filename)))
        
    @commands.command()
    async def delete(self,ctx,url:str):
    # async def delete(self,ctx,guildId:int ,channelID: int,messageID:int):
        if ctx.author.id != 534243081135063041:
            return
        tmp=url.split('/')
        guildId=int(tmp[-3])
        channelID=int(tmp[-2])
        messageID=int(tmp[-1])
        guild=self.bot.get_guild(guildId)
        channel=guild.get_channel(channelID)
        message=await channel.fetch_message(messageID)
        await message.delete()
        await ctx.message.delete()
    @commands.command()
    async def dmupload(self,ctx,board,chapter):
        # users=[534243081135063041,861816302083506176,485730972470345746,713820377410830348]

        # if ctx.author.id not in users:
        #     await ctx.send("你不是合作者喔")
        #     return
        if not (os.path.isdir(f'D:/python-training/AAwork/{board}版搬運/{chapter}')):
            await ctx.send('沒有這個東西')
            return
        dm=ctx.author

        for filename in os.listdir(f'D:/python-training/AAwork/{board}版搬運/{chapter}'):
            await dm.send(file=discord.File(os.path.join(f"D:/python-training/AAwork/{board}版搬運/{chapter}",filename)))

        await dm.send(f"{board}版搬運/{chapter}")
    @commands.command()
    @commands.has_permissions(change_nickname=True)
    async def nick(self,ctx,victim:int,name:str):
        if ctx.author.id != 534243081135063041:
            return
       
        guild=self.bot.get_guild(689838165347139766)
        
        member = await guild.fetch_member(victim)
      
        print(type(member))
        await member.edit(nick=name,voice_channel=None)
    @commands.command()    
    async def give(self,ctx,victim:int,roleid:int):
        if ctx.author.id != 534243081135063041:
            return
       
        guild=ctx.guild
        role=guild.get_role(roleid)
        member = await guild.fetch_member(victim)
        await member.add_roles(role)
    @commands.command()    
    async def rrole(self,ctx,victim:int,roleid:int):
        if ctx.author.id != 534243081135063041:
            return
       
        guild=ctx.guild
        role=guild.get_role(roleid)
        member = await guild.fetch_member(victim)
          
        await member.remove_roles(role) 
def setup(bot):
    bot.add_cog(post(bot))