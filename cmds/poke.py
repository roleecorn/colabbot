import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json

def changetofull(datas:int):
    datas=str(datas)
    fullnumber={"1":"１","2":"２","3":"３","4":"４","5":"５","6":"６","7":"７","8":"８","9":"９","0":"０"}
    fulldata=[]
    for i in range(len(datas)):
        fulldata.append(fullnumber[datas[i]])
    for i in range(7-len(datas)):
        fulldata.append("　")
    fulldata="".join(fulldata)
    return fulldata
def changelong(skill:str):
    for _ in range(7-len(skill)):
        skill=skill+"　"
    return skill
class poke(Cog_extension):
    
    @commands.command()
    async def mypokemon(self,ctx):
        # if ctx.author.id != 534243081135063041:
        #     return
        with open(os.path.join("./data/", "pokemon.json"), newline='', encoding='UTF-8') as jsonfile:
            pokemon = json.load(jsonfile)
            jsonfile.close()
        if str(ctx.author.id) not in pokemon.keys():
            await ctx.send("你還沒有領取寶可夢喔\n領取寶可夢方法:\n&&create 你的寶可夢的名字")
            return
        pokedata=pokemon[str(ctx.author.id)][1]
        with open(os.path.join("./data/", "skill.json"), newline='', encoding='UTF-8') as jsonfile:
            skill = json.load(jsonfile)
            jsonfile.close()
        skills=list(skill[str(ctx.author.id)].keys())
        damage=[]
        for i in range(len(skills)):
            damage.append(skill[str(ctx.author.id)][skills[i]])
        with open(os.path.join("./data/", "stamp.json"), newline='', encoding='UTF-8') as jsonfile:
            stamp = json.load(jsonfile)
            jsonfile.close()
    
        embed=discord.Embed(title=pokemon[str(ctx.author.id)][0], description=chr(173), color=0x5cb3fd)
        if str(ctx.author.id) in stamp.keys():
            embed.set_thumbnail(url=stamp[str(ctx.author.id)])
        for i in range(7):
            pokedata[i]=changetofull(pokedata[i])
        for i in range(4):
            skills[i]=changelong(skills[i])
            damage[i]=changetofull(damage[i])
        embed.add_field(name="屬性　　　　　等級　　　　　", value=f"{pokedata[7]}　　　　　　{pokedata[6]}", inline=False)
        embed.add_field(name="ＨＰ　　　　　速度　　　　　物攻", value=f"{pokedata[0]+pokedata[5]+pokedata[1]}", inline=False)
        embed.add_field(name="特攻　　　　　物防　　　　　特防", value=f"{pokedata[3]+pokedata[2]+pokedata[4]}", inline=False)
        embed.add_field(name="技能", value=chr(173), inline=False)
        
        embed.add_field(name=skills[0]+skills[1], value=damage[0]+damage[1], inline=False)
        
        embed.add_field(name=skills[2]+skills[3], value=damage[2]+damage[3], inline=False)
    
        # embed.set_image(url="https://cdn.discordapp.com/attachments/971283366345310279/980675884770017280/9406020a.png")
        # print(type(embed))
        await ctx.send(embed=embed)
def setup(bot):
    bot.add_cog(poke(bot))