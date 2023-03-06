import sqlite3
import random
import pandas as pd
def changeele(id):
    win_and_lose =sqlite3.connect("./data/win_and_lose.db")
    qry = f"SELECT * FROM wl where id={id} "
    df = pd.read_sql_query(qry, win_and_lose)
    if df.empty:
        win_and_lose.close()
        return (None,None,"你還沒有領取寶可夢")
    money=df['money'][0]
    if money<100:
        win_and_lose.close()
        return (None,None,"錢不夠呢")
    cmd=f"update wl set money={money-100} where id={id};"
    win_and_lose.execute(cmd)
    win_and_lose.commit()
    win_and_lose.close()
    eles=["一般",'格鬥',"飛行",'毒',"地面",'岩石',"蟲",'幽靈',"鋼",'火',"水",'草',"電",'超能力',"冰",'龍',"惡",'妖精']
    afele1=eles[random.randint(0,len(eles)-1)]
    if random.random()>0.9:
        afele2=eles[random.randint(0,len(eles)-1)]
    else :
        afele2=""
    status = sqlite3.connect("./data/pokemon.db")
    qry = f"SELECT * FROM pokemon where id='{id}'"
    df = pd.read_sql_query(qry, status)
    cmd=f"update pokemon set typea='{afele1}'  where id={id};"
    status.execute(cmd)
    cmd=f"update pokemon set typeb='{afele2}'  where id={id};"
    status.execute(cmd)
    status.commit()
    status.close()
    beele1=df['typea'][0]
    beele2=df['typeb'][0]
    return (f"{beele1}{beele2}",f"{afele1}{afele2}",None)