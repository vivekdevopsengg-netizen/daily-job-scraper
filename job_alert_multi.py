import os
import smtplib
from email.message import EmailMessage
import pandas as pd
# Removed: linkedin_jobs_scraper, Options import (not needed for this test)

# --- Configuration ---
QUERIES = ["Performance Test Engineer", "Performance Engineer"]
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
SENDER = os.getenv("SENDER_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# Global list to store job data
JOB_LIST = []

# --- TEMPORARY FUNCTION TO TEST EMAIL ---
def gather_jobs_with_scraper():
    """TEMPORARY TEST: Returns static job data to verify email functionality."""
    print("TEMPORARY TEST: Returning static job data for email verification.")
    
    # Test data that should definitely be sent in the email body
    return [{
        "site": "TEST_SITE", 
        "title": "EMAIL_TEST_SUCCESS_TITLE", 
        "company": "TEST_COMPANY", 
        "link": "https://test.link"
    }]
# --- END TEMPORARY FUNCTION ---

# The rest of the functions remain the same for testing the email formatting and sending

def compose_email(jobs):
    """Creates the email message."""
    if not jobs:
        body = "No new jobs found for Performance Test Engineer / Performance Engineer."
        jobs_deduped = []
    else:
        # Deduplicate the list just in case of overlaps or duplicate scraping
        df = pd.DataFrame(jobs)
        df.drop_duplicates(subset=['title', 'company'], inplace=True)
        jobs_deduped = df.to_dict('records')
        
        lines = ["Found the following new jobs:\n"]
        for j in jobs_deduped:
            lines.append(f"Source: {j['site']}")
            lines.append(f"Title: {j['title']}")
            lines.append(f"Company: {j['company']}")
            lines.append(f"Link: {j['link']}\n" + "-"*30 + "\n")
        body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f"Daily Performance-Engineer Job Search Results ({len(jobs_deduped)} New Jobs)"
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.set_content(body)
    return msg

def send_email(msg):
    """Sends the email using SMTP."""
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
            print("Email sent successfully.")
    except Exception as e:
        print(f"Email sending failed: {e}")

def main():
    jobs = gather_jobs_with_scraper()
    msg = compose_email(jobs)
    send_email(msg)
    print(f"Finished. Processed {len(jobs)} job(s).")

if __name__ == "__main__":
    main()
