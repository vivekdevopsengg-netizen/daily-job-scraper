import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from jobspy import scrape_jobs
from datetime import datetime, timezone

# ---------------- CONFIG ----------------

SEARCH_TERMS = [
    "Performance Test Engineer",
    "Performance Engineer",
    "Performance Architect",
    "Performance Test Lead",
    "Performance"
]

LOCATION = "United States"
REMOTE_ONLY = False

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


def gather_jobs():
    all_results = []

    for term in SEARCH_TERMS:
        df = scrape_jobs(
            site_name=["linkedin", "indeed", "google"],
            search_term=term,
            location=LOCATION,
            results_wanted=200,
            hours_old=48
        )
        if df is not None and not df.empty:
            all_results.append(df)

    if not all_results:
        return pd.DataFrame()

    df = pd.concat(all_results, ignore_index=True)
    df.columns = [c.lower() for c in df.columns]

    # -------- Title filter --------
    title_regex = "|".join(ALLOWED_TITLE_PATTERNS)
    df = df[df["title"].str.lower().str.contains(title_regex, regex=True, na=False)]

    # -------- Source tagging --------
    df["source"] = df["job_url"].apply(
        lambda x: "Workday" if "workdayjobs" in str(x).lower() else "LinkedIn / Other"
    )

    # Deduplicate
    df.drop_duplicates(subset=["title", "company", "job_url"], inplace=True)

    # -------- Normalize date column --------
    for col in ["date_posted", "posted_date", "posted_at"]:
        if col in df.columns:
            df["posted_dt"] = pd.to_datetime(df[col], errors="coerce", utc=True)
            break
    else:
        df["posted_dt"] = pd.NaT

    # -------- Sort latest first --------
    df.sort_values(by="posted_dt", ascending=False, inplace=True)

    # -------- Human readable age --------
    df["posted"] = df["posted_dt"].apply(compute_posted_ago)

    df.reset_index(drop=True, inplace=True)
    return df


def build_html_email(df):
    if df.empty:
        return "<h3>No matching Performance Engineering jobs found in last 48 hours.</h3>"

    remote_df = df[df.get("is_remote") == True]
    onsite_df = df[df.get("is_remote") != True]

    def build_table(title, data):
        if data.empty:
            return f"<h3>{title}</h3><p>No jobs found.</p>"

        rows = ""
        for _, row in data.iterrows():
            rows += f"""
            <tr>
                <td>{row['posted']}</td>
                <td>{row['source']}</td>
                <td>{row['company']}</td>
                <td>{row['title']}</td>
                <td><a href="{row['job_url']}" target="_blank">View Job</a></td>
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
        <h2>Daily Performance Engineering Job Alerts (Last 48 Hours)</h2>
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
    df = gather_jobs()
    send_email(build_html_email(df), len(df))
    print(f"Email sent with {len(df)} jobs.")


if __name__ == "__main__":
    main()
