#Requires AutoHotkey v2.0
#SingleInstance Force


Run "gopass show -c keepassxc/main", ,"Hide"
WinWait "Message from User"

Run "keepassxc"
WinWaitActive " - KeePassXC"
WinActive " - KeePassXC"

Send "^v"
Send "{Enter}"
return
