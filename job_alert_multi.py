import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData
from linkedin_jobs_scraper.query import Query, QueryOptions
from selenium.webdriver.chrome.options import Options
from linkedin_jobs_scraper.strategies import AuthenticatedStrategy 

# --- Configuration ---
QUERIES = ["Performance Test Engineer", "Performance Engineer"]
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
SENDER = os.getenv("SENDER_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

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
    
    # 1. Create the required Options object for the Chrome browser
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Defensive check for missing secrets
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        raise ValueError("LinkedIn email or password secrets are missing or empty.")

    # 2. Configure Authentication Strategy (Trying 'email' keyword)
    auth_strategy = AuthenticatedStrategy(
        email=LINKEDIN_EMAIL, 
        password=LINKEDIN_PASSWORD
    )

    # 3. Initialize the Scraper
    scraper = LinkedinScraper(
        chrome_options=chrome_options, 
        auth_strategy=auth_strategy, 
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
                # Filters removed due to TypeErrors. Using only limit.
                limit=100 
            )
        ))
    
    print(f"Starting scrape for {len(queries)} queries...")
    scraper.run(queries)
    
    return JOB_LIST

def compose_email(jobs):
    """Creates the email message."""
    if not jobs:
        body = "No new jobs found for Performance Test Engineer / Performance Engineer. (The scraper ran successfully but returned zero results)."
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
