$num=$(cat num)
mpv --speed=2 --fullscreen https://bilibili.com/video/BV1uBn1z2EZv?p=$num
[int]$num+1 > num
