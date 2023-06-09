import pandas as pd
import csv
from random import randint

poketype = pd.read_csv("data/屬性克制.csv", index_col="屬性")


def ele(p11, p12, p21, p22):

    # poketype=pd.read_csv("data/屬性克制.csv",index_col="屬性")
    tmp1 = poketype.loc[p11][p21]
    try:
        tmp2 = poketype.loc[p11][p22]
    except:
        tmp2 = 1
    try:
        tmp3 = poketype.loc[p12][p21]
    except:
        tmp3 = 1
    try:
        tmp4 = poketype.loc[p12][p22]
    except:
        tmp4 = 1
    tmp = tmp1*tmp2*tmp3*tmp4
    print(f"{tmp}倍傷害")
    return tmp


def damagecal(attacker, defender):

    rate = 1

    atk = attacker['atk']
    defv = defender['def']
    spatk = attacker['spatk']
    spdef = defender['spdef']
    if (atk > defv):
        rate = rate+atk/defv-1
    if (spatk > spdef):
        rate = rate+spatk/spdef-1
    element = ele(attacker["typea"], attacker["typeb"],
                  defender["typea"], defender["typeb"])
    total = randint(5, 15)*rate*element
    total = round(total)

    return total
