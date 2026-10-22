netsh interface ipv4 set address name="Ethernet" source=static address=192.168.0.108 mask=255.255.255.0 gateway=192.168.0.1
netsh interface ipv4 set dns name="Ethernet" source=static address=223.5.5.5

ipconfig /flushdns
