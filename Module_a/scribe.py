from random import randint


def normal(attacker, defender, skill):
    word = [f"{attacker}  使用了{skill}，  {defender}  想閃過去但失敗！",
            f"{attacker}  使出的{skill}被  {defender}  擋下，但還是受傷了！",
            f"{attacker}  的{skill}繞過了  {defender}  的防禦，直接打中了  {defender}  ！",
            f"{attacker}  的{skill}打中了防禦架勢的  {defender}  ，  {defender}  被打飛出去了！",
            f"{defender}  避開了  {attacker}  的{skill}的直擊，但還是被波及到了！"]
    descripe = word[randint(0, len(word)-1)]
    return descripe


def critical(attacker, defender, skill):
    word = [f"{attacker}  的{skill}打中了  {defender}  ，效果絕佳！",
            f"{attacker}  的{skill}從意想不到的角度擊中了  {defender}  ，是會心一擊！"]
    descripe = word[randint(0, len(word)-1)]
    return descripe


def defence(attacker, defender, skill):
    word = [f"{attacker}  使用了{skill}，但  {defender}  用消力將傷害化解了！",
            f"{attacker}  使用了{skill}，但被  {defender}  閃了過去！",
            f"你讓  {attacker}  使用{skill}，但他好像沒有在聽你說話?",
            f"{attacker}  使出的{skill}被  {defender}  擋下了，減輕了傷害！",
            f"{attacker}  的{skill}繞過了  {defender}  的防禦，但被  {defender}  避開了！",
            f"{attacker}  的{skill}打中了防禦架勢的  {defender}  ，  {defender}  後退了幾步！",
            f"{defender}  向上方跳躍迴避，避開了  {attacker}  的{skill}！"]
    descripe = word[randint(0, len(word)-1)]
    return descripe


def counter(attacker, defender, skill):
    word = [f"{attacker}  使用了{skill}，但  {defender}  躲開並給了他一拳！",
            f"{attacker}  不聽你的指揮睡著了，被  {defender}  乘虛而入！"]
    descripe = word[randint(0, len(word)-1)]
    return descripe
