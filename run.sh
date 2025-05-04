#!/bin/bash
EMAIL_ADDRESS=$(aws ssm get-parameter --name "EMAIL_ADDRESS" --with-decryption --query "Parameter.Value" --output text --region us-east-2)
EMAIL_PASSWORD=$(aws ssm get-parameter --name "EMAIL_PASSWORD" --with-decryption --query "Parameter.Value" --output text --region us-east-2)
GITHUB_TOKEN=$(aws ssm get-parameter --name "GITHUB_TOKEN" --with-decryption --query "Parameter.Value" --output text --region us-east-2)
export EMAIL_ADDRESS="$EMAIL_ADDRESS"
export EMAIL_PASSWORD="$EMAIL_PASSWORD"
export GITHUB_TOKEN="$GITHUB_TOKEN"
/usr/bin/python3 /home/ec2-user/notify.py
