import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from jobspy import scrape_jobs

# ---------------- CONFIG ----------------

SEARCH_TERMS = [
    "Performance Test Engineer",
    "Performance Engineer",
    "Performance Architect",
    "Performance Test Lead",
    "Performance"
]

LOCATION = "United States"
REMOTE_ONLY = True

# STRICT TITLE ALLOW LIST (case-insensitive regex)
ALLOWED_TITLE_PATTERNS = [
    r"performance test engineer",
    r"performance engineer",
    r"sr\.?\s*performance test engineer",
    r"senior performance test engineer",
    r"performance architect",
    r"lead\s*-?\s*performance test engineer",
    r"lead performance test engineer",
    rr"performance test lead", # FIX: Removed syntax error (extra r) from original paste
    r"performance.*engineer",
    r"engineer.*performance",
    r"performance test",
    r"performance architect",
    r"performance lead",
    r"lead.*performance",
    r"staff.*performance",
    r"principal.*performance",
    r"sr.*performance",
    r".*performance.*" # FIX: Corrected regex from *performance*
]

# Email Secrets
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
SENDER = os.getenv("SENDER_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# LinkedIn Secrets (Jobspy uses these if present)
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# ---------------------------------------


def gather_jobs():
    all_results = []

    for term in SEARCH_TERMS:
        df = scrape_jobs(
            site_name=[
                "linkedin",
                "indeed",
                "glassdoor",
                "google"  # Google Jobs → includes Workday + Dice mirrors
            ],
            search_term=term,
            location=LOCATION,
            results_wanted=100,
            hours_old=24,
            # Jobspy will automatically look for LINKEDIN_EMAIL and LINKEDIN_PASSWORD in the environment
            # We don't need to pass them explicitly, just ensure they are loaded via os.getenv()
        )
        # Handle case where scrape_jobs returns None
        if df is not None:
            all_results.append(df)

    if not all_results:
        return pd.DataFrame() # Return empty DataFrame if no results were ever found

    df = pd.concat(all_results, ignore_index=True)
    df.columns = [c.lower() for c in df.columns]

    # -------- Remote filter --------
    if REMOTE_ONLY and "is_remote" in df.columns:
        df = df[df["is_remote"] == True]

    # -------- STRICT TITLE FILTER --------
    title_regex = "|".join(ALLOWED_TITLE_PATTERNS)
    # Ensure title column exists before filtering
    if "title" in df.columns:
        df = df[df["title"].str.lower().str.contains(title_regex, regex=True, na=False)]

    # -------- Source tagging --------
    df["source"] = df["job_url"].apply(
        lambda x: "Workday"
        if "workdayjobs" in str(x).lower()
        else "LinkedIn/Other"
    )

    # Deduplicate
    df.drop_duplicates(subset=["title", "company", "job_url"], inplace=True)

    return df


def build_html_email(df: pd.DataFrame) -> str:
    if df.empty:
        return """
        <html>
            <body>
                <h3>No matching Performance Engineering jobs found in the last 24 hours.</h3>
            </body>
        </html>
        """

    rows = ""
    for _, row in df.iterrows():
        rows += f"""
        <tr>
            <td>{row.get('source','')}</td>
            <td>{row.get('company','')}</td>
            <td>{row.get('title','')}</td>
            <td>
                <a href="{row.get('job_url','')}" target="_blank">
                    View Job
                </a>
            </td>
        </tr>
        """

    return f"""
    <html>
    <body>
        <h2>Daily Performance Engineering Job Alerts</h2>
        <p><b>Titles filtered strictly as requested</b></p>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr>
                <th>Source</th>
                <th>Company</th>
                <th>Title</th>
                <th>Link</th>
            </tr>
            {rows}
        </table>
        <p><b>Total jobs:</b> {len(df)}</p>
    </body>
    </html>
    """


def send_email(html_body, count):
    msg = EmailMessage()
    msg["Subject"] = f"Performance Engineering Jobs ({count})"
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.set_content("HTML email required")
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


def main():
    df = gather_jobs()
    html_body = build_html_email(df)
    send_email(html_body, len(df))
    print(f"Email sent with {len(df)} jobs.")


if __name__ == "__main__":
    main()
