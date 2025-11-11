import discord
import os
from discord.ext import commands
from core.classes import Cog_extension
import asyncio

import logging
# import http.server
# import socketserver
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--token", help="bots token",
                    type=str)
parser.add_argument("--ext", help="load extension module",
                    type=str)
args = parser.parse_args()
formatter = '%(levelname)s %(asctime)s %(message)s'
# logging.basicConfig(filename="bot.log",  level=logging.warning,format=formatter, datefmt='%m/%d/%Y %I:%M:%S %p')
# # bot = discord.Client()
# log= logging.Logger(name='bot.log', level='INFO')


# class MyHandler(http.server.SimpleHTTPRequestHandler):
#     def do_GET(self):
#         self.send_response(200)
#         self.end_headers()
#         self.wfile.write(b'Hello, HTTP!')


# PORT = int(os.environ.get('PORT', 8000))
# print(PORT)
# logging.warning(f"PORT={PORT}")
# handler = MyHandler
# httpd = socketserver.TCPServer(("", PORT), handler)

intents = discord.Intents.all()
intents.members = True
bot = commands.Bot(intents=intents, command_prefix='&&', help_command=None)
# bot = commands.Bot(intents=intents,command_prefix='&&')


@bot.command()
async def load(ctx, extension):
    if ctx.author.id == 534243081135063041:
        await bot.load_extension(f'cmds.{extension}')
        await ctx.send(f'load {extension}')


@bot.command()
async def reload(ctx, extension):
    if ctx.author.id == 534243081135063041:
        await bot.reload_extension(f'cmds.{extension}')
        await ctx.send(f'reload {extension}')


@bot.command()
async def unload(ctx, extension):
    if ctx.author.id == 534243081135063041:
        await bot.unload_extension(f'cmds.{extension}')
        await ctx.send(f'unload {extension}')


@bot.event
async def on_ready():
    status_w = discord.Status.online
    activity_w = discord.Activity(
        type=discord.ActivityType.playing, name='AAstoryboard')
    await bot.change_presence(status=status_w, activity=activity_w)

    logging.warning(f'目前登入身份： {bot.user}')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send("說了不要狂刷指令吧?")


async def load_async(bot,filename):
    await bot.load_extension(f'cmds.{filename[:-3]}')


async def load_extensions(ext:str = ""):
    path = './cmds'
    modulePath = 'cmds'
    if(ext):
        path = f'./cmds/{ext}'
        modulePath = f'cmds.{ext}'
    for filename in os.listdir(path):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'{modulePath}.{filename[:-3]}')
                # load_async(bot=bot,filename=filename)
                logging.info(filename)
            except Exception as e:
                logging.warning(f"{filename} error!{e}")
if __name__ == "__main__":

    # print(botdata["token"])
    logging.warning('Start the bot')
    token = args.token
    extension = []
    if(args.ext):
        extension = args.ext.split("-")
    # bot.run(token)
    async def bot_start():
        async with bot:
            await load_extensions()
            if(extension):
                for ext in extension:
                    await load_extensions(ext)
            await bot.start(token)
    asyncio.run(bot_start())