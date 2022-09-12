import discord
from discord.ext import commands
from core.classes import Cog_extension

class help(Cog_extension):    

    
    @commands.command()
    async def help(self,ctx,*arg):
        if len(arg)==0:
            await ctx.send("```指令可以分為\nrole,pokemon,cut\n三類，在help後接著輸入可以確認詳細規則```")
            return
        if arg[0]=="role":
            word="""```\n可分為setrole,rmrole,showrole三個指令，setrole,rmrole需要管理員權限才可操作
setrole 頻道ID 身分組ID 可以將頻道與身分組綁定
rmrole 頻道ID 身分組ID 可以將頻道與身分組綁定解除
showrole 可以顯示伺服器中的全部綁定關係\n```"""
            await ctx.send(word)
            return
        if arg[0]=="pokemon":
            await ctx.send("```寶可夢小遊戲相關指令```")
            
            return
        if arg[0]=="cut":
            await ctx.send("```切割圖片相關指令```")
            return
        await ctx.send("```指令可以分為\nrole,pokemon,cut\n三類，在help後接著輸入可以確認詳細規則```")
        return
def setup(bot):
    bot.add_cog(help(bot))