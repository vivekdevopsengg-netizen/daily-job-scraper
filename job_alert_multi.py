import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from jobspy.scrapers.linkedin import LinkedIn
from jobspy.scrapers.indeed import Indeed
from jobspy.scrapers.glassdoor import Glassdoor
from jobspy.scrapers.dice import Dice

# --- Configuration ---
QUERIES = ["Performance Test Engineer", "Performance Engineer"]
SITES = [Indeed, Glassdoor, LinkedIn, Dice]
# Adjust to your desired search radius (e.g., 10 miles from a major city)
LOCATION = "" 
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
SENDER = os.getenv("SENDER_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

def gather_jobs_with_jobspy():
    """Uses jobspy to fetch and aggregate jobs across all sites."""
    all_jobs_df = pd.DataFrame()
    for query in QUERIES:
        print(f"Searching for: {query}")
        try:
            # JobSpy's search function handles all sites concurrently
            jobs = jobspy.search(
                sites=SITES,
                search_term=query,
                location=LOCATION,
                # Fetching jobs posted in the last 24 hours (a good daily setting)
                # NOTE: This filter is approximate based on the site.
                results_wanted=100, 
                country_filter='usa'
            )
            # Add to the main DataFrame
            all_jobs_df = pd.concat([all_jobs_df, jobs], ignore_index=True)
            
        except Exception as e:
            print(f"JobSpy search failed for {query}: {e}")
            
    # Clean up and deduplicate results
    if all_jobs_df.empty:
        return []
    
    # Simple deduplication based on job title and company
    all_jobs_df.drop_duplicates(subset=['title', 'company'], inplace=True, keep='first')
    
    # Convert DataFrame rows to a list of job dictionaries for emailing
    job_list = all_jobs_df[['site', 'title', 'company', 'link']].to_dict('records')
    return job_list

def compose_email(jobs):
    """Creates the email message."""
    if not jobs:
        body = "No new jobs found for Performance Test Engineer / Performance Engineer."
    else:
        lines = ["Found the following new jobs:\n"]
        for j in jobs:
            # Format the output for a clean email text body
            lines.append(f"Source: {j['site']}")
            lines.append(f"Title: {j['title']}")
            lines.append(f"Company: {j['company']}")
            lines.append(f"Link: {j['link']}\n" + "-"*30 + "\n")
        body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f"Daily Performance-Engineer Job Search Results ({len(jobs)} New Jobs)"
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
    jobs = gather_jobs_with_jobspy()
    msg = compose_email(jobs)
    send_email(msg)
    print(f"Finished. Processed {len(jobs)} job(s).")

if __name__ == "__main__":
    main()
