"""疯狂症状判定，迁移自 nonebot_plugin_cocdicer 的 madness.py"""

import random

from .constant import madness_end, manias, phobias, temporary_madness


def ti() -> str:
    i = random.randint(1, 10)
    r = f"临时疯狂判定1D10={i}\n"
    r += temporary_madness[i - 1]
    if i == 9:
        j = random.randint(1, 100)
        r += "\n恐惧症状为：\n"
        r += phobias[j - 1]
    elif i == 10:
        j = random.randint(1, 100)
        r += "\n狂躁症状为：\n"
        r += manias[j - 1]
    r += f"\n该症状将会持续1D10={random.randint(1, 10)}"
    return r


def li() -> str:
    i = random.randint(1, 10)
    r = f"总结疯狂判定1D10={i}\n"
    r += madness_end[i - 1]
    if i in (2, 3, 6, 9, 10):
        r += f"\n调查员将在1D10={random.randint(1, 10)}小时后醒来"
    if i == 9:
        j = random.randint(1, 100)
        r += "\n恐惧症状为：\n"
        r += phobias[j - 1]
    elif i == 10:
        j = random.randint(1, 100)
        r += "\n狂躁症状为：\n"
        r += manias[j - 1]
    return r
