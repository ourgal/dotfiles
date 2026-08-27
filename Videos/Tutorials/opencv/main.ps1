$num=$(cat num)
mpv --speed=2 --fullscreen https://www.bilibili.com/video/BV1Fo4y1d7JL?p=$num
[int]$num+1 > num
