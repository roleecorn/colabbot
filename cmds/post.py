import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json
from discord import File
import zipfile
import random
import datetime
# from disnake import AllowedMentions


class post(Cog_extension):

    @commands.command()
    async def post(self, ctx, *arg):
        # guild=self.bot.get_guild(ctx.guild_id)
        if ctx.author.id != 534243081135063041:
            return
        channelid = 739739523130327040

        guild = self.bot.get_guild(689838165347139766)
        # aa形象區738239898716471377
        # dice區739739523130327040
        # 2版777541172100857888

        # channel=guild.get_channel(channelid)
        try:
            channelid = int(arg[-1])
            channel = guild.get_channel(channelid)
        except:
            channel = None

        if channel != None:
            flag = True
        if channel == None:
            channel = guild.get_channel(739739523130327040)
            flag = False
        message = None

        allowed_mention = discord.AllowedMentions(
            users=False,         # Whether to ping individual user @mentions
            everyone=False,      # Whether to ping @everyone or @here mentions
            roles=False,         # Whether to ping role @mentions
            replied_user=False    # Whether to ping on replies to messages
        )
        if len(arg) > 0:
            tmp = " "
            if flag:
                for i in range(len(arg)-1):
                    tmp = tmp+"\n"+arg[i]
                await channel.send(content=tmp, reference=None)
            if (not flag):
                for i in range(len(arg)):
                    tmp = tmp+"\n"+arg[i]
                await channel.send(content=tmp, reference=None)
        if len(ctx.message.attachments) > 0:
            await channel.send(ctx.message.attachments[0])

    @commands.command()
    async def pin(self, ctx, url: str):
        if ctx.author.id != 534243081135063041:
            return
        tmp = url.split('/')
        guildId = int(tmp[-3])
        channelID = int(tmp[-2])
        messageID = int(tmp[-1])
        guild = self.bot.get_guild(guildId)
        channel = guild.get_channel(channelID)
        message = await channel.fetch_message(messageID)
        await message.pin(reason="test")

    @commands.command()
    async def unpin(self, ctx, url: str):
        if ctx.author.id != 534243081135063041:
            return
        tmp = url.split('/')
        guildId = int(tmp[-3])
        channelID = int(tmp[-2])
        messageID = int(tmp[-1])
        guild = self.bot.get_guild(guildId)
        channel = guild.get_channel(channelID)
        message = await channel.fetch_message(messageID)
        await message.unpin()

    @commands.command()
    async def read(self, ctx, arg: int):
        if ctx.author.id != 534243081135063041:
            return
        message = await ctx.send("test")

        await message.edit(content="done")

    @commands.command()
    async def edit(self, ctx, url: str, text: str):
        if ctx.author.id != 534243081135063041:
            return
        tmp = url.split('/')
        guildId = int(tmp[-3])
        channelID = int(tmp[-2])
        messageID = int(tmp[-1])
        guild = self.bot.get_guild(guildId)
        channel = guild.get_channel(channelID)
        message = await channel.fetch_message(messageID)
        await message.edit(content=text)

    @commands.command()
    async def delete(self, ctx, url: str):
        # async def delete(self,ctx,guildId:int ,channelID: int,messageID:int):
        if ctx.author.id != 534243081135063041:
            return
        tmp = url.split('/')
        guildId = int(tmp[-3])
        channelID = int(tmp[-2])
        messageID = int(tmp[-1])
        guild = self.bot.get_guild(guildId)
        channel = guild.get_channel(channelID)
        message = await channel.fetch_message(messageID)
        await message.delete()
        await ctx.message.delete()

    @commands.command()
    async def data_upload(self, ctx):
        if ctx.author.id != 534243081135063041:
            return
        zip_fp = zipfile.ZipFile('data.zip', 'w')
        await ctx.send("打包中")
        for filename in os.listdir('./data'):

            zip_fp = zipfile.ZipFile('data.zip', 'w')

            zip_fp.write(os.path.join("./data", filename))

            os.remove(os.path.join("./data", filename))

        zip_fp.close()
        await ctx.send(file=discord.File("data.zip"))

    @commands.command()
    @commands.has_permissions(change_nickname=True)
    async def nick(self, ctx, victim: int, name: str):
        if ctx.author.id != 534243081135063041:
            return

        guild = self.bot.get_guild(689838165347139766)

        member = await guild.fetch_member(victim)

        print(type(member))
        await member.edit(nick=name, voice_channel=None)

    @commands.command()
    async def give(self, ctx, victim: int, roleid: int):
        if ctx.author.id != 534243081135063041:
            return

        guild = ctx.guild
        role = guild.get_role(roleid)
        member = await guild.fetch_member(victim)
        await member.add_roles(role)

    @commands.command()
    async def rrole(self, ctx, victim: int, roleid: int):
        if ctx.author.id != 534243081135063041:
            return

        guild = ctx.guild
        role = guild.get_role(roleid)
        member = await guild.fetch_member(victim)

        await member.remove_roles(role)

    @commands.command()
    async def ban(self, ctx, banner: int):
        if ctx.author.id != 534243081135063041:
            return
        guild = self.bot.get_guild(689838165347139766)
        banner = await self.bot.fetch_user(banner)
        print(banner)

        await guild.ban(user=banner, reason="bot", delete_message_days=0)
        print(guild.banner_url)


def setup(bot):
    bot.add_cog(post(bot))
