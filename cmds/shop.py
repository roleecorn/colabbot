from discord.ext import commands
from core.classes import Cog_extension
from Module_a.changeele import changeele


class shop(Cog_extension):
    @commands.command()
    async def buy(self, ctx, item: str):
        items = {"變身藥": 100}
        itemlist = items.keys()

        if (item not in itemlist):
            await ctx.send("歡迎來到商店，我們有以下商品")
            tmp = ""
            for aitem in itemlist:
                tmp = f"{tmp}{aitem} 要價 {items[aitem]} 元\n"
            await ctx.send(tmp)
            return
        if item == "變身藥":
            (be, af, describe) = changeele(ctx.author.id)
            if describe:
                await ctx.send(describe)
                return
            await ctx.send(f"恭喜，你的寶可夢從{be}屬性變為了{af}屬性了")
            return
        return


def setup(bot):
    bot.add_cog(shop(bot))
