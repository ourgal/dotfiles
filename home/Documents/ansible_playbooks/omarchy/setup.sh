#!/usr/bin/env sh

mkdir .ssh
curl https://github.com/ourgal.keys > .ssh/authorized_keys
sudo systemctl enable --now sshd
sudo ufw allow ssh
