import discord
import os
from discord.ext import commands
from core.classes import Cog_extension
import asyncio

import logging
# import http.server
# import socketserver
import argparse
from cmds.gitRely.startup import EventStartupError, validate_active_event_configuration
parser = argparse.ArgumentParser()
parser.add_argument("--token", help="bots token",
                    type=str)
parser.add_argument("--ext", help="load extension module (e.g. gitRely.event_single or gitRely/event_single.py)",
                    type=str)
parser.add_argument(
    "--noBase",
    help="Won't load base extension",
    action="store_false",
    dest="load_base",
)
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

@bot.event
async def on_ready():
    slash = await bot.tree.sync()
    print(f"目前登入身份 --> {bot.user}")
    print(f"載入 {len(slash)} 個斜線指令")
    
async def load_async(bot,filename):
    await bot.load_extension(f'cmds.{filename[:-3]}')


def _ext_to_module(ext: str):
    ext = ext.strip()
    if not ext:
        return None, "ext is empty"

    raw = ext
    if ext.endswith(".py"):
        ext = ext[:-3]
    ext = ext.replace("\\", "/").strip("/")
    ext = ext.replace("/", ".")

    if ext.startswith("cmds."):
        rel = ext[5:]
        module = ext
    else:
        rel = ext
        module = f"cmds.{ext}"

    file_path = os.path.join("cmds", *rel.split(".")) + ".py"
    dir_path = os.path.join("cmds", *rel.split("."))

    if os.path.isfile(file_path):
        return module, None
    if os.path.isdir(dir_path):
        if os.path.isfile(os.path.join(dir_path, "__init__.py")):
            return module, None
        return None, f"ext '{raw}' looks like a folder; specify a module file under it"

    return module, f"ext '{raw}' not found on disk; trying to load anyway"


async def load_extensions(ext:str = ""):
    if not ext:
        path = './cmds'
        modulePath = 'cmds'
        for filename in os.listdir(path):
            if filename.endswith('.py'):
                try:
                    await bot.load_extension(f'{modulePath}.{filename[:-3]}')
                    # load_async(bot=bot,filename=filename)
                    logging.info(filename)
                except Exception as e:
                    logging.warning(f"{filename} error!{e}")
        return

    module, warn = _ext_to_module(ext)
    if warn:
        logging.warning(warn)
    if not module:
        return
    try:
        await bot.load_extension(module)
        logging.info(module)
    except Exception as e:
        logging.warning(f"{module} error!{e}")
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
            if args.load_base:
                await load_extensions()
            if(extension):
                for ext in extension:
                    await load_extensions(ext)
            try:
                validate_active_event_configuration()
            except EventStartupError as exc:
                logging.critical(str(exc))
                raise SystemExit(1) from exc
            await bot.start(token)
    asyncio.run(bot_start())
