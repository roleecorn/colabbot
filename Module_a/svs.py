import random
def battle(player1:list,player2:list,player1name:str,player2name:str,skill1name,skill2name):
    # 速度：tmp[5]
    fast=random.randint(1,player1[5]+player2[5])
    if fast<= player1[5]:
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
    # ＨＰ：tmp[0]
    if attackmode<0.1:
        word=[f"{attacker}  使用了{skill}，但  {defender}  躲開並給了他一拳！",
        f"{attacker}  不聽你的指揮睡著了，被  {defender}  乘虛而入！"]
        tmp=random.randint(5,10)
        damage =f"{defender} 造成了  {tmp}  點傷害"
        attackdata[0]=attackdata[0]-tmp
        detail=f"，{attacker}  剩下  {attackdata[0]}  點HP"
        descripe=word[random.randint(0,len(word)-1)]+damage+detail
        
        return (player1,player2,descripe)
    if attackmode<0.3:
        word=[f"{attacker}  使用了{skill}，但  {defender}  用消力將傷害化解了！",
        f"{attacker}  使用了{skill}，但被  {defender}  閃了過去！",
        f"你讓  {attacker}  使用{skill}，但他好像沒有在聽你說話?",
        f"{attacker}  使出的{skill}被  {defender}  擋下了，減輕了傷害！",
        f"{attacker}  的{skill}繞過了  {defender}  的防禦，但被  {defender}  避開了！",
        f"{attacker}  的{skill}打中了防禦架勢的  {defender}  ，  {defender}  後退了幾步！",
        f"{defender}  向上方跳躍迴避，避開了  {attacker}  的{skill}！"]
        tmp=0
        damage =f"{attacker}  沒有造成任何傷害"
        defenddata[0]=defenddata[0]-tmp
        detail=f"，{defender}  剩下  {defenddata[0]}  點HP"
        descripe=word[random.randint(0,len(word)-1)]+damage+detail
        return (player1,player2,descripe)
      

    
    if attackmode<0.9:
        word=[f"{attacker}  使用了{skill}，  {defender}  想閃過去但失敗！",
        f"{attacker}  使出的{skill}被  {defender}  擋下，但還是受傷了！",
        f"{attacker}  的{skill}繞過了  {defender}  的防禦，直接打中了  {defender}  ！",
        f"{attacker}  的{skill}打中了防禦架勢的  {defender}  ，  {defender}  被打飛出去了！",
        f"{defender}  避開了  {attacker}  的{skill}的直擊，但還是被波及到了！"]
        tmp=random.randint(5,15)
        damage =f"{attacker} 造成了  {tmp}  點傷害"
        defenddata[0]=defenddata[0]-tmp
        detail=f"，{defender}  剩下  {defenddata[0]}  點HP"
        descripe=word[random.randint(0,len(word)-1)]+damage+detail
        return (player1,player2,descripe)
    word=[f"{attacker}  的{skill}打中了  {defender}  ，效果絕佳！",
    f"{attacker}  的{skill}從意想不到的角度擊中了  {defender}  ，是會心一擊！"]
    tmp=random.randint(15,20)
    damage =f"{attacker} 造成了  {tmp}  點傷害"
    defenddata[0]=defenddata[0]-tmp
    detail=f"，{defender}  剩下  {defenddata[0]}  點HP"
    descripe=word[random.randint(0,len(word)-1)]+damage+detail
    return (player1,player2,descripe)

def car(trainer,loser):

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