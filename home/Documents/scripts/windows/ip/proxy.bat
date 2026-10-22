netsh interface ipv4 set address name="Ethernet" source=static address=192.168.0.108 mask=255.255.255.0 gateway=192.168.0.115
netsh interface ipv4 set dns name="Ethernet" source=static address=192.168.0.115

ipconfig /flushdns
