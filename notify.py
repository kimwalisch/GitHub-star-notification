import os
import requests
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

LOG_FILE = os.path.expanduser("~/status.log")
MAX_LOG_LINES = 1000

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

def get_new_stars(last_checked):
    headers = {'Accept': 'application/vnd.github.v3+json'}
    repos_url = 'https://api.github.com/users/kimwalisch/repos'
    
    repos = get_all_pages(repos_url, headers, {'per_page': 100})
    repo_updates = {}

    for repo in repos:
        repo_name = repo['name']
        stargazers_url = f'https://api.github.com/repos/kimwalisch/{repo_name}/stargazers'
        
        params = {'since': last_checked.isoformat(), 'per_page': 100}
        stargazers = get_all_pages(stargazers_url, headers, params)
        
        if stargazers:
            repo_data = requests.get(f'https://api.github.com/repos/kimwalisch/{repo_name}', headers=headers).json()
            repo_updates[repo_name] = {
                'new_stars': len(stargazers),
                'current_total': repo_data['stargazers_count']
            }

    return repo_updates

def send_email(repo_updates):
    sender_email = os.environ.get('SENDER_EMAIL')
    receiver_email = os.environ.get('RECEIVER_EMAIL')
    email_password = os.environ.get('EMAIL_PASSWORD')

    if not all([sender_email, receiver_email, email_password]):
        missing = []
        if not sender_email: missing.append("SENDER_EMAIL")
        if not receiver_email: missing.append("RECEIVER_EMAIL")
        if not email_password: missing.append("EMAIL_PASSWORD")
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    message = MIMEMultipart("alternative")
    message["Subject"] = "GitHub Star Updates"
    message["From"] = sender_email
    message["To"] = receiver_email

    text = "GitHub Star Updates:\n\n"
    total_new = sum(data['new_stars'] for data in repo_updates.values())

    for repo, data in repo_updates.items():
        if data['new_stars'] > 0:
            text += f"Repository: {repo}\n"
            text += f"New Stars: +{data['new_stars']}\n"
            text += f"Current Total Stars: {data['current_total']}\n\n"

    part = MIMEText(text, "plain")
    message.attach(part)
    
    # Use port 587 with STARTTLS
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()  # Identify ourselves to the server
        server.starttls()  # Upgrade connection to TLS
        server.ehlo()  # Re-identify after TLS handshake
        server.login(sender_email, email_password)
        server.sendmail(sender_email, receiver_email, message.as_string())

def main():
    first_run = False

    try:
        # Check if this is the first run
        try:
            with open('last_checked.txt', 'r') as f:
                last_checked = datetime.fromisoformat(f.read().strip())
        except FileNotFoundError:
            first_run = True
            last_checked = datetime.now(timezone.utc)
            with open('last_checked.txt', 'w') as f:
                f.write(last_checked.isoformat())

        # Check for new stars
        repo_updates = get_new_stars(last_checked)
        total_new = sum(data['new_stars'] for data in repo_updates.values())
        
        # Send email only if it's not the first run
        if repo_updates and not first_run:
            send_email(repo_updates)
        
        # Update last checked time
        current_time = datetime.now(timezone.utc)
        with open('last_checked.txt', 'w') as f:
            f.write(current_time.isoformat())
        
        # Log status with first-run indicator
        log_message = f"Checked successfully - {total_new} new stars found"
        if first_run:
            log_message += " (first run - email skipped)"
        log_status(log_message)

    except Exception as e:
        log_status(f"Script failed: {str(e)}", error=True)
        raise

if __name__ == '__main__':
    main()
