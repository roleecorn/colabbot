import discord
from discord.ext import commands
from core.classes import Cog_extension
import os
from discord import File
import cv2
import zipfile

def check(img,start):
    (tall,wide)=img.shape
    for i in range(40):
        for x in range(wide):    
            if i+start==tall:
                return 1
            if img[i+start][x]<170:
                return 1
    # tmp.append(start+25)

    return (start+25)
class transport(Cog_extension): 
    @commands.command()
    @commands.cooldown(1,120, commands.BucketType.default)
    async def cut(self,ctx,tmp2:int=1):
        # if ctx.author.id != 534243081135063041:
        #     return  
        print(str(ctx.author.name))
        print("cut")
        attachment=ctx.message.attachments[0]
        await ctx.send("讀取中")
        await attachment.save(f"./picture/{attachment.filename}")
        img = cv2.imread(f"./picture/{attachment.filename}", cv2.IMREAD_GRAYSCALE)
        (tall,wide)=img.shape
        tmp=[]
        
        await ctx.send("標記中")
        least_tall=2000
        x=2000
        while(x<tall):
            flag=check(img,x)
            if flag !=1:
                tmp.append(flag)
                x=x+least_tall
                continue
            x=x+10
        
        await ctx.send("切割中")
        img = cv2.imread(f"./picture/{attachment.filename}", cv2.IMREAD_COLOR)
        # tmp2=1
        print(tmp)
        for i in range(len(tmp)):
            if i==0:
                crop_img = img[0:tmp[i], 0:wide]
                if tmp[i]>6000:
                    tmp2=tmp2+1
               
            if i !=0:
                crop_img = img[tmp[i-1]:tmp[i], 0:wide]
                if tmp[i]-tmp[i-1]>6000:
                    tmp2=tmp2+1
                
            cv2.imwrite(f"./picture/{tmp2}.png", crop_img)
            
            tmp2=tmp2+1
        crop_img = img[tmp[i]:tall, 0:wide]
        
        cv2.imwrite(f"./picture/{tmp2}.png", crop_img)
        
        zip_fp = zipfile.ZipFile('cutfile.zip', 'w')
        await ctx.send("打包中")
        os.remove(os.path.join("./picture",attachment.filename))
        cize=0
        for filename in os.listdir(f'./picture'):
            cize=cize+os.path.getsize(os.path.join("./picture",filename))

            
            if cize>7000000:
                cize=os.path.getsize(os.path.join("./picture",filename))
                zip_fp.close()
                
                await ctx.send(file=discord.File("cutfile.zip"))
                
                zip_fp = zipfile.ZipFile('cutfile.zip', 'w')
                
                
            zip_fp.write(os.path.join("./picture",filename))
            
            
            os.remove(os.path.join("./picture",filename))
            
        zip_fp.close()
        await ctx.send(file=discord.File("cutfile.zip"))
        # os.system(f"rm -rf {cutfile.zip}")
        # os.remove(f".\cutfile.zip")
        await ctx.send("完成")
def setup(bot):
    bot.add_cog(transport(bot))
