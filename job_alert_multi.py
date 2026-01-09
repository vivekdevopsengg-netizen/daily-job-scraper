import os
import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime, timezone

import pandas as pd
from jobspy import scrape_jobs

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- CONFIG ----------------

SEARCH_TERMS = [
    "Performance Test Engineer",
    "Performance Engineer",
    "Performance Architect",
    "Performance Test Lead",
    "Performance"
]

SITES = ["linkedin", "indeed", "google"]
LOCATION = "United States"
REMOTE_ONLY = False
HOURS_OLD = 48
RESULTS_WANTED = 200

ALLOWED_TITLE_PATTERNS = [
    r"performance test engineer",
    r"performance engineer",
    r"sr\.?\s*performance test engineer",
    r"senior performance test engineer",
    r"performance architect",
    r"lead\s*-?\s*performance test engineer",
    r"lead performance test engineer",
    r"performance test lead",
    r"performance.*engineer",
    r".*performance.*"
]

# Email Secrets
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
SENDER = os.getenv("SENDER_EMAIL")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# ---------------------------------------


def compute_posted_ago(dt):
    if pd.isna(dt):
        return "Unknown"
    now = datetime.now(timezone.utc)
    delta = now - dt
    hours = int(delta.total_seconds() // 3600)
    if hours < 24:
        return f"{hours} hours ago"
    return f"{hours // 24} days ago"


def safe_scrape(site, term):
    """
    Scrape a single site safely.
    Failure here NEVER crashes the job.
    """
    try:
        logging.info(f"Scraping {site} for '{term}'")
        df = scrape_jobs(
            site_name=[site],
            search_term=term,
            location=LOCATION,
            results_wanted=RESULTS_WANTED,
            hours_old=HOURS_OLD
        )
        if df is None or df.empty:
            logging.warning(f"No results from {site} for '{term}'")
            return pd.DataFrame()
        return df

    except Exception as e:
        logging.error(f"{site.upper()} failed for '{term}': {e}")
        return pd.DataFrame()


def gather_jobs():
    all_results = []

    for term in SEARCH_TERMS:
        for site in SITES:
            df = safe_scrape(site, term)
            if not df.empty:
                df["site"] = site
                all_results.append(df)

    if not all_results:
        logging.error("All sources failed. Returning empty DataFrame.")
        return pd.DataFrame()

    df = pd.concat(all_results, ignore_index=True)
    df.columns = [c.lower() for c in df.columns]

    # -------- Remote filter --------
    if REMOTE_ONLY and "is_remote" in df.columns:
        df = df[df["is_remote"] == True]

    # -------- Title filter --------
    title_regex = "|".join(ALLOWED_TITLE_PATTERNS)
    df = df[df["title"].str.lower().str.contains(title_regex, regex=True, na=False)]

    # -------- Source tagging --------
    def tag_source(url, site):
        if "workdayjobs" in str(url).lower():
            return "Workday"
        if site == "indeed":
            return "Indeed"
        if site == "linkedin":
            return "LinkedIn"
        return "Google Jobs"

    df["source"] = df.apply(
        lambda r: tag_source(r.get("job_url"), r.get("site")),
        axis=1
    )

    # -------- Deduplicate --------
    df.drop_duplicates(subset=["title", "company", "job_url"], inplace=True)

    # -------- Normalize date --------
    df["posted_dt"] = pd.NaT
    for col in ["date_posted", "posted_date", "posted_at"]:
        if col in df.columns:
            df["posted_dt"] = pd.to_datetime(df[col], errors="coerce", utc=True)
            break

    # -------- Sort newest first --------
    df.sort_values(by="posted_dt", ascending=False, inplace=True)

    # -------- Human readable time --------
    df["posted"] = df["posted_dt"].apply(compute_posted_ago)

    df.reset_index(drop=True, inplace=True)
    return df


def build_html_email(df):
    if df.empty:
        return """
        <html><body>
        <h3>No matching Performance Engineering jobs found in last 48 hours.</h3>
        </body></html>
        """

    remote_df = df[df.get("is_remote") == True]
    onsite_df = df[df.get("is_remote") != True]

    def build_table(title, data):
        if data.empty:
            return f"<h3>{title}</h3><p>No jobs found.</p>"

        rows = ""
        for _, r in data.iterrows():
            rows += f"""
            <tr>
                <td>{r['posted']}</td>
                <td>{r['source']}</td>
                <td>{r.get('company','')}</td>
                <td>{r.get('title','')}</td>
                <td><a href="{r.get('job_url')}" target="_blank">View Job</a></td>
            </tr>
            """

        return f"""
        <h3>{title} ({len(data)})</h3>
        <table border="1" cellpadding="6" cellspacing="0">
            <tr>
                <th>Posted</th>
                <th>Source</th>
                <th>Company</th>
                <th>Title</th>
                <th>Link</th>
            </tr>
            {rows}
        </table><br/>
        """

    return f"""
    <html>
    <body>
        <h2>Performance Engineering Job Alerts (Last 48 Hours)</h2>
        {build_table("🟢 Remote Roles", remote_df)}
        {build_table("🔵 Onsite / Hybrid Roles", onsite_df)}
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
    try:
        df = gather_jobs()
        send_email(build_html_email(df), len(df))
        logging.info(f"Email sent with {len(df)} jobs.")
    except Exception as e:
        # FINAL safety net — job NEVER fails
        logging.critical(f"Fatal error avoided: {e}")
        send_email(
            "<h3>Job ran but encountered errors. Check logs.</h3>",
            0
        )


if __name__ == "__main__":
    main()
