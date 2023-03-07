def checkname(name):
    if len(name) > 9:
        return "名字不能這麼長"
    if ("-" in name) or ("*" in name) or ("/" in name) or ("|" in name) or ("`" in name) or ("_" in name):
        return "名字不能含有奇怪的符號"

    return 0
