import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
import json
class React(Cog_extension):

    # @commands.Cog.listener()
    # async def on_message(self,message):
    #     pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self,data):
        
        if str(data.emoji)!="⬆️":
            return  
        guild=self.bot.get_guild(data.guild_id)
        with open(os.path.join("./data/", "output.json"), newline='') as jsonfile:
            parrent = json.load(jsonfile)
            jsonfile.close()
        if str(data.channel_id) in parrent.keys():
            print("inparrent.keys")
            for cid in parrent[str(data.channel_id)]:
                print("add")
                role=guild.get_role(cid)
                if not role :
                    continue
                print(role.name,data.member.name)
                await data.member.add_roles(role)
                
                cid=738348131724427286
                role=guild.get_role(cid)
                await data.member.add_roles(role)
            
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self,data):
        
        if str(data.emoji)=="⬆️":
            guild=self.bot.get_guild(data.guild_id)
            member = await guild.fetch_member(data.user_id)
            print(member)
            with open(os.path.join("./data/", "output.json"), newline='') as jsonfile:
                parrent = json.load(jsonfile)
                jsonfile.close()
            if str(data.channel_id) in parrent.keys():
                for cid in parrent[str(data.channel_id)]:
                    role=guild.get_role(cid)
                    if not role :
                        continue
                    await member.remove_roles(role)
        
def setup(bot):
    bot.add_cog(React(bot))