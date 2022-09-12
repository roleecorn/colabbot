import random
from Module_a.scribe import normal,critical,defence,counter
from Module_a.damageclaculate import damagecal,ele,poketype
import copy
def battledemo(player1,player2,player1name:str,player2name:str,skill1name,skill2name):

    fast=random.randint(1,player1["speed"]+player2["speed"])
    if fast<= player1["speed"]:
        attacker=player1name
        attackdata=player1
        defender=player2name
        defenddata=player2
        skill=skill1name
    else :
        attacker=player2name
        attackdata=player2
        defender=player1name
        defenddata=player1
        skill=skill2name
    attackmode=random.random()
    tmp=damagecal(player1,player2)
    

    if attackmode<0.1:
        tmp=tmp
        word=counter(attacker,defender,skill)
        
        damage =f"{defender} 造成了  {tmp}  點傷害"
        attackdata['hp']=attackdata['hp']-tmp
        detail=f"，{attacker}  剩下  {attackdata['hp']}  點HP"
        descripe=word+damage+detail
        
        return (player1,player2,descripe)
    if attackmode<0.3:
        tmp=0
        word=defence(attacker,defender,skill)
        # tmp=0
        damage =f"{attacker}  沒有造成任何傷害"
        defenddata['hp']=defenddata['hp']-tmp
        detail=f"，{defender}  剩下  {defenddata['hp']}  點HP"
        descripe=word+damage+detail
        return (player1,player2,descripe)
      

    
    if attackmode<0.9:
        word=normal(attacker,defender,skill)
        # tmp=random.randint(5,15)
        tmp=tmp
        damage =f"{attacker} 造成了  {tmp}  點傷害"
        defenddata['hp']=defenddata['hp']-tmp
        detail=f"，{defender}  剩下  {defenddata['hp']}  點HP"
        descripe=word+damage+detail
        return (player1,player2,descripe)
    if attackmode >= 0.9:
        word=critical(attacker,defender,skill)
        tmp=tmp*2
        # tmp=random.randint(15,20)
        damage =f"{attacker} 造成了  {tmp}  點傷害"
        defenddata['hp']=defenddata['hp']-tmp
        detail=f"，{defender}  剩下  {defenddata['hp']}  點HP"
        descripe=word+damage+detail
        return (player1,player2,descripe)
    return (player1,player2,"")
def car(trainer,loser,winer):

    descripebox=""
    descripebox=descripebox+"突然一輛黑色高級車駛來急剎並打開車門，三名訓練家打開車門用超重球持續攻擊你們！\n裁判試圖前沖但肩部中了一記超重球而倒下！\n"
    descripebox=descripebox+f"由於抱着{trainer}，後背多次中球！\n{trainer}「  {loser}  ，你在幹什麼啊，  {loser}  ！」\n"
    descripebox=descripebox+f"{loser}  「呃呃啊啊啊啊啊啊啊啊啊啊啊啊啊啊啊！！！」\n  {loser}  使出三記破壞死光，擊倒一個訓練家！\n"
    descripebox=descripebox+f"一發破壞死光擊中  {winer}  ！其他訓練家見狀不妙隨即駕車逃離！\n  {loser}  「什麼嘛，我的破壞死光還挺準的嘛，呵」\n"
    descripebox=descripebox+f"{loser}...{loser}啊…啊……\n"
    descripebox=descripebox+f"你的聲音為什麼要顫抖，{trainer}\n"
    descripebox=descripebox+f"我可是（停頓）銀河團團長，(站起){loser}啊，這點小傷無關緊要。\n"
    descripebox=descripebox+f"{trainer}「為什麼，要為了保護我——」\n"
    descripebox=descripebox+"保護訓練師就是我的使命！"
    
    return descripebox
def ele2(p1,p2):

    p11=p1["typea"]
    p12=p1["typeb"]
    p21=p2["typea"]
    p22=p2["typeb"]
    tmp1=poketype.loc[p11][p21]
    try:
        tmp2=poketype.loc[p11][p22]
    except:
        tmp2=1
    try:
        tmp3=poketype.loc[p12][p21]
    except:
        tmp3=1
    try:
        tmp4=poketype.loc[p12][p22]
    except:
        tmp4=1

    tmp5=poketype.loc[p21][p11]
    try:
        tmp6=poketype.loc[p22][p11]
    except:
        tmp6=1
    try:
        tmp7=poketype.loc[p21][p12]
    except:
        tmp7=1
    try:
        tmp8=poketype.loc[p22][p12]
    except:
        tmp8=1
    tmp=tmp1*tmp2*tmp3*tmp4
    tmpr=tmp5*tmp6*tmp7*tmp8
    
    return tmp,tmpr

def valuerate(attacker,defender):
    rate=1

    atk=attacker['atk']
    defv=defender['def']
    spatk=attacker['spatk']
    spdef=defender['spdef']
    if(atk>defv):
        rate=rate+atk/defv-1
    if(spatk>spdef):
        rate=rate+spatk/spdef-1
    return rate
def battledemo2(hp1,hp2,player1,player2,skill1name,skill2name,ottrate,toorate):
    
    fast=random.randint(1,player1['speed']+player1['speed'])
    #player1比較快
    if fast<= player1['speed']:
        attacker=player1
        attackerhp=hp1
        defenderhp=hp2
        defender=player2
        skill=skill1name
        rate=ottrate
    #player2比較快
    else :
        attacker=player2
        defender=player1
        attackerhp=hp2
        defenderhp=hp1
        skill=skill2name
        rate=toorate
    attackmode=random.random()
    tmp=random.randint(5,15)*rate
    tmp=round(tmp)

    if attackmode<0.1:
        tmp=tmp
        word=counter(attacker['name'],defender['name'],skill)
        # tmp=random.randint(5,10)
        damage =defender['name'] + f"造成了  {tmp}  點傷害"
        attackerhp=attackerhp-tmp
        detail="，"+attacker['name']+"  剩下  "+str(attackerhp)+ '  點HP'
        descripe=word+damage+detail
        if fast<= player1['speed']:
            return (attackerhp,defenderhp,descripe)
        else:
            return (defenderhp,attackerhp,descripe)
        # return (hp1,hp2,descripe)
    if attackmode<0.3:
        
        word=defence(attacker['name'],defender['name'],skill)
        
        damage =attacker['name']+"  沒有造成任何傷害"
        
        detail=defender['name']+"  剩下  "+str(defenderhp)+"  點HP"
        descripe=word+damage+detail
        if fast<= player1['speed']:
            return (attackerhp,defenderhp,descripe)
        else:
            return (defenderhp,attackerhp,descripe)
        # return (hp1,hp2,descripe)
    if attackmode<0.9:
        word=normal(attacker['name'],defender['name'],skill)
        
        tmp=tmp
        damage =attacker['name']+f"造成了  {tmp}  點傷害"
        defenderhp=defenderhp-tmp
        detail=defender['name']+"  剩下  "+str(defenderhp)+"  點HP"
        descripe=word+damage+detail
        if fast<= player1['speed']:
            return (attackerhp,defenderhp,descripe)
        else:
            return (defenderhp,attackerhp,descripe)
        # return (hp1,hp2,descripe)
    if attackmode >= 0.9:
        word=critical(attacker['name'],defender['name'],skill)
        tmp=tmp*2
        # tmp=random.randint(15,20)
        damage =attacker['name']+f"造成了  {tmp}  點傷害"
        defenderhp=defenderhp-tmp
        detail=defender['name']+"  剩下  "+str(defenderhp)+"  點HP"
        descripe=word+damage+detail
        if fast<= player1['speed']:
            return (attackerhp,defenderhp,descripe)
        else:
            return (defenderhp,attackerhp,descripe)
        # return (hp1,hp2,descripe)