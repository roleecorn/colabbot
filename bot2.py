import discord
import os
from discord.ext import commands
from core.classes import Cog_extension
import json

# bot = discord.Client()
bot = commands.Bot(command_prefix='&&')
@bot.command()
async def load(ctx,extension):
    if ctx.author.id==534243081135063041:
        bot.load_extension(f'cmds.{extension}')
        await ctx.send(f'load {extension}')
@bot.command()
async def reload(ctx,extension):
    if ctx.author.id==534243081135063041:
        bot.reload_extension(f'cmds.{extension}')
        await ctx.send(f'reload {extension}')
@bot.command()
async def unload(ctx,extension):
    if ctx.author.id==534243081135063041:
        bot.unload_extension(f'cmds.{extension}')
        await ctx.send(f'unload {extension}')
@bot.event
async def on_ready():
    status_w=discord.Status.online
    activity_w=discord.Activity(type=discord.ActivityType.playing,name='AAstoryboard')
    await bot.change_presence(status=status_w,activity=activity_w)
    
    print('目前登入身份：', bot.user)
@bot.event
async def on_command_error(ctx,error):
    if isinstance(error,commands.CommandOnCooldown):
        await ctx.send("說了不要狂刷指令吧?")


for filename in os.listdir('./cmds'):
    if filename.endswith('.py'):
        bot.load_extension(f'cmds.{filename[:-3]}')
        print(filename)
if __name__=="__main__":
    with open(os.path.join(".", "botdata.json"), newline='', encoding='UTF-8') as jsonfile:
        botdata = json.load(jsonfile)
        jsonfile.close()
    # print(botdata["token"])
    token=botdata["token"]

    bot.run(token)