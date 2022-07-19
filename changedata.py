import json
import os
import random
with open(os.path.join("./data/", "pokemon.json"), newline='', encoding='UTF-8') as jsonfile:
    pokemon = json.load(jsonfile)
    jsonfile.close()
status = { }
for user in pokemon.keys():
    hisstatus=pokemon[user][1]
    status[user]={"type":[hisstatus[7]],"level":hisstatus[6],"hp":hisstatus[0],"speed":hisstatus[5],"atk":hisstatus[1],"def":hisstatus[2],"spatk":hisstatus[3],"spdef":hisstatus[4],"name":pokemon[user][0]}

with open(os.path.join("./data/", "test.json"), "w", encoding='UTF-8') as f:
    json.dump(status, f, indent = 4)


       
    