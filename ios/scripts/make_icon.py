#!/usr/bin/env python3
"""アプリアイコン（紺〜青の背景に白い封筒）1024x1024 を描く。"""
from PIL import Image, ImageDraw
import pathlib, sys
S = 1024
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
    pathlib.Path(__file__).resolve().parent.parent / "Meruma/Assets.xcassets/AppIcon.appiconset/icon-1024.png")
img = Image.new("RGB", (S, S))
px = img.load()
top, bot = (28, 52, 110), (52, 112, 190)
for y in range(S):
    t = y / (S - 1)
    c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    for x in range(S):
        px[x, y] = c
d = ImageDraw.Draw(img)
# 封筒本体
L, R, T, B = 170, 854, 280, 744
d.rounded_rectangle((L + 8, T + 18, R + 8, B + 18), 44, fill=(20, 38, 86))  # 影
d.rounded_rectangle((L, T, R, B), 44, fill=(255, 255, 255))
# 折り返し（V字）
line = (88, 130, 200)
mid = (S // 2, 540)
d.line([(L + 30, T + 30), mid, (R - 30, T + 30)], fill=line, width=22, joint="curve")
# 下の斜め線
d.line([(L + 24, B - 24), (400, 480)], fill=(200, 215, 238), width=14)
d.line([(R - 24, B - 24), (624, 480)], fill=(200, 215, 238), width=14)
out.parent.mkdir(parents=True, exist_ok=True)
img.save(out)
print(out)
