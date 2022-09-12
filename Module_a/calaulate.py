import sqlite3
import pandas as pd
import pathlib
import os
from datetime import date

import json

def final(winer:int,loser:int):
    #給勝者加100金，一勝，10exp
    #給敗者加1敗


    win_and_lose =sqlite3.connect("/gdrive/My Drive/colabpractice/dcbot/data/win_and_lose.db")

    qry = f"SELECT * FROM wl where id={winer} "
    df = pd.read_sql_query(qry, win_and_lose)
    money=df['money'][0]
    win=df['win'][0]
    exp=df['exp'][0]
    cmd=f"update wl set money={money+100} where id={winer};"
    win_and_lose.execute(cmd)
    cmd=f"update wl set win={win+1} where id={winer};"
    win_and_lose.execute(cmd)
    cmd=f"update wl set exp={exp+10} where id={winer};"
    win_and_lose.execute(cmd)
    qry = f"SELECT * FROM wl where id={loser} "
    df = pd.read_sql_query(qry, win_and_lose)
    lose=df['lose'][0]
    cmd=f"update wl set lose={lose+1} where id={loser};"
    win_and_lose.execute(cmd)
    win_and_lose.commit()
    win_and_lose.close()