import discord
import os
from discord.ext import commands
from core.classes import Cog_extension
import json
import logging
# import http.server
# import socketserver
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--token", help="bots token",
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

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(intents=intents, command_prefix='&&', help_command=None)
# bot = commands.Bot(intents=intents,command_prefix='&&')


@bot.command()
async def load(ctx, extension):
    if ctx.author.id == 534243081135063041:
        bot.load_extension(f'cmds.{extension}')
        await ctx.send(f'load {extension}')


@bot.command()
async def reload(ctx, extension):
    if ctx.author.id == 534243081135063041:
        bot.reload_extension(f'cmds.{extension}')
        await ctx.send(f'reload {extension}')


@bot.command()
async def unload(ctx, extension):
    if ctx.author.id == 534243081135063041:
        bot.unload_extension(f'cmds.{extension}')
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


for filename in os.listdir('./cmds'):
    if filename.endswith('.py'):
        try:
            bot.load_extension(f'cmds.{filename[:-3]}')
            logging.warning(filename)
        except:
            logging.warning(f"{filename} error!error!error!error!error!error!")
if __name__ == "__main__":

    # print(botdata["token"])
    logging.warning('Start the bot')
    token = args.token

    bot.run(token)
