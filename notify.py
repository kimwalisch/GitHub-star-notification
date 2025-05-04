import boto3
import os
import json
import requests
import smtplib
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

LOG_FILE = os.path.expanduser("~/status.log")
MAX_LOG_LINES = 1000
DATA_FILE = "repo_star_counts.json"

def log_status(message, error=False):
    """Append status message to log file with rotation"""
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    if len(lines) >= MAX_LOG_LINES:
        lines = lines[-(MAX_LOG_LINES - 1):]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "ERROR" if error else "SUCCESS"
    new_entry = f"[{timestamp}] [{status}] {message}\n"

    with open(LOG_FILE, 'w') as f:
        f.writelines(lines)
        f.write(new_entry)

    if error:
        raise Exception(message)

def get_all_pages(url, headers, params=None):
    """Fetch all pages from a GitHub API endpoint"""
    results = []
    while url:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        results.extend(response.json())
        url = response.links.get('next', {}).get('url')
        params = {}  # Subsequent pages use link headers
    return results

def get_current_repo_counts():
    """Get current star counts for all repositories"""
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        log_status("Missing environment variable: GITHUB_TOKEN", error=True)

    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    repos_url = 'https://api.github.com/users/kimwalisch/repos'
    repos = get_all_pages(repos_url, headers, {'per_page': 100})
    
    return {repo['name']: repo['stargazers_count'] for repo in repos}

def send_email(repo_updates):
    email_address = os.environ.get('EMAIL_ADDRESS')
    if not email_address:
        log_status("Missing environment variable: EMAIL_ADDRESS", error=True)

    total_new = sum(data['new_stars'] for data in repo_updates.values())
    text = ""

    for repo, data in repo_updates.items():
        if data['new_stars'] > 0:
            text += f"{repo}\n"
            text += f"New Stars: +{data['new_stars']}\n"
            text += f"Total Stars: {data['current_total']}\n\n"

    client = boto3.client('ses', region_name="us-east-2")

    try:
        client.send_email(
            Source=email_address,
            Destination={
                'ToAddresses': [email_address],
            },
            Message={
                'Subject': {'Data': "GitHub star notification"},
                'Body': {
                    'Text': {'Data': text}
                }
            }
        )
    except ClientError as e:
        log_status(e.response['Error']['Message'], error=True)

def main():
    first_run = False

    # Load stored data
    try:
        with open(DATA_FILE, 'r') as f:
            stored_data = json.load(f)
    except FileNotFoundError:
        stored_data = {}
        first_run = True

    # Get current repository counts
    current_counts = get_current_repo_counts()

    # Compare with stored data
    repo_updates = {}
    for repo, current_count in current_counts.items():
        stored_count = stored_data.get(repo, 0)
        new_stars = current_count - stored_count
        
        if new_stars > 0:
            repo_updates[repo] = {
                'new_stars': new_stars,
                'current_total': current_count
            }

    # Update stored data
    with open(DATA_FILE, 'w') as f:
        json.dump(current_counts, f)

    # Send notification if needed
    total_new = sum(data['new_stars'] for data in repo_updates.values())
    if repo_updates and not first_run:
        send_email(repo_updates)

    # Log status
    log_message = f"Checked successfully - {total_new} new stars found"
    if first_run:
        log_message += " (first run - email skipped)"
    log_status(log_message)

if __name__ == '__main__':
    main()
