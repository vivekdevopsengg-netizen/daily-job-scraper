import os
import smtplib
from email.message import EmailMessage
import requests
import pandas as pd
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
from linkedin_jobs_scraper.filters import RelevanceFilters, TimeFilters, TypeFilters, ExperienceLevelFilters

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

def on_data(data: EventData):
    """Callback function to store job data as it is scraped."""
    JOB_LIST.append({
        "site": "LinkedIn", 
        "title": data.title, 
        "company": data.company, 
        "link": data.link
    })

def on_error(error):
    print(f"Scraper Error: {error}")

def gather_jobs_with_scraper():
    """Uses the dedicated LinkedIn scraper library to fetch jobs."""
    global JOB_LIST
    JOB_LIST = []  # Clear previous results
    
    scraper = LinkedinScraper(
        # Note: You can't run this headlessly on GitHub Actions without complex setup, 
        # but this library is more stable than jobspy even in this simple mode.
        chrome_options=['--headless', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage'],
        page_load_timeout=30,
        slow_mo=1,
    )
    
    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    
    queries = []
    for query in QUERIES:
        queries.append(Query(
            query=query,
            options=QueryOptions(
                # Look at jobs posted in the last 24 hours
                time_filter=TimeFilters.PAST_24H, 
                relevance_filter=RelevanceFilters.RECENT,
                limit=100
            )
        ))
    
    print(f"Starting scrape for {len(queries)} queries...")
    scraper.run(queries)
    
    # We will use this list directly for emailing
    return JOB_LIST

def compose_email(jobs):
    """Creates the email message."""
    if not jobs:
        body = "No new jobs found for Performance Test Engineer / Performance Engineer."
    else:
        lines = ["Found the following new jobs:\n"]
        # Deduplicate the list just in case of overlaps or duplicate scraping
        df = pd.DataFrame(jobs)
        df.drop_duplicates(subset=['title', 'company'], inplace=True)
        jobs_deduped = df.to_dict('records')
        
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
