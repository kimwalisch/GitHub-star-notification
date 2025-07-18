#!/bin/bash
sudo dnf update -y
sudo dnf install -y cronie python3-pip
sudo systemctl start crond
sudo -u ec2-user bash -c '
  /usr/bin/python3 -m pip install requests urllib3
  curl -s https://raw.githubusercontent.com/kimwalisch/GitHub-star-notification/refs/heads/main/notify.py -o /home/ec2-user/notify.py
  curl -s https://raw.githubusercontent.com/kimwalisch/GitHub-star-notification/refs/heads/main/run.sh -o /home/ec2-user/run.sh
  chmod +x /home/ec2-user/run.sh
  (crontab -l 2>/dev/null; echo "*/15 * * * * /home/ec2-user/run.sh") | crontab -
'
