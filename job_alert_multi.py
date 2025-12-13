import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from jobspy import scrape_jobs

# ---------------- CONFIG ----------------
QUERIES = ["Performance Test Engineer", "Performance Engineer"]
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
SENDER = os.getenv("SENDER_EMAIL")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# ---------------------------------------

def gather_jobs():
    jobs = []

    for query in QUERIES:
        results = scrape_jobs(
            site_name=["indeed", "glassdoor", "linkedin"],
            search_term=query,
            location="United States",
            results_wanted=50,
            hours_old=24
        )
        jobs.append(results)

    df = pd.concat(jobs, ignore_index=True)
    df.drop_duplicates(subset=["title", "company", "job_url"], inplace=True)
    return df

def compose_email(df):
    if df.empty:
        body = "No new Performance Engineering jobs found in the last 24 hours."
    else:
        lines = []
        for _, row in df.iterrows():
            lines.append(
                f"{row['site']}\n"
                f"{row['title']} - {row['company']}\n"
                f"{row['job_url']}\n"
                + "-" * 40
            )
        body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f"Daily Performance Engineer Jobs ({len(df)} new)"
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.set_content(body)
    return msg

def send_email(msg):
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

def main():
    df = gather_jobs()
    msg = compose_email(df)
    send_email(msg)
    print(f"Email sent with {len(df)} jobs.")

if __name__ == "__main__":
    main()
