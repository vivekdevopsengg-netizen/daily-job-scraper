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
REMOTE_ONLY = False  # Keep FALSE to allow both remote & onsite jobs

# STRICT TITLE ALLOW LIST (case-insensitive regex)
ALLOWED_TITLE_PATTERNS = [
    r"performance test engineer",
    r"performance engineer",
    r"sr\.?\s*performance test engineer",
    r"senior performance test engineer",
    r"performance architect",
    r"lead\s*-?\s*performance test engineer",
    r"lead performance test engineer",
    r"performance test lead",
    r"performance\s*specialist",
    r"performance\s*consultant",
    r"performance\s*smts",
    r"performance\s*mts",
    r"performance.*engineer",
    r"engineer.*performance",
    r"performance test",
    r"performance lead",
    r"lead.*performance",
    r"staff.*performance",
    r"principal.*performance",
    r"sr.*performance",
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


def gather_jobs():
    all_results = []

    for term in SEARCH_TERMS:
        df = scrape_jobs(
            site_name=[
                "linkedin",
                "indeed",
                "google"  # Google Jobs → Workday + Dice mirrors
            ],
            search_term=term,
            location=LOCATION,
            results_wanted=200,
            hours_old=48  # ✅ Last 48 hours ONLY
        )

        if df is not None and not df.empty:
            all_results.append(df)

    if not all_results:
        return pd.DataFrame()

    df = pd.concat(all_results, ignore_index=True)
    df.columns = [c.lower() for c in df.columns]

    # -------- Remote filter --------
    if REMOTE_ONLY and "is_remote" in df.columns:
        df = df[df["is_remote"] == True]

    # -------- STRICT TITLE FILTER --------
    title_regex = "|".join(ALLOWED_TITLE_PATTERNS)
    if "title" in df.columns:
        df = df[df["title"].str.lower().str.contains(title_regex, regex=True, na=False)]

    # -------- Source tagging --------
    df["source"] = df["job_url"].apply(
        lambda x: "Workday"
        if "workdayjobs" in str(x).lower()
        else "LinkedIn / Other"
    )

    # Deduplicate
    df.drop_duplicates(subset=["title", "company", "job_url"], inplace=True)

    # -------- Sort by latest posting first --------
    date_columns = ["date_posted", "posted_date", "posted_at"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df.sort_values(by=col, ascending=False, inplace=True)
            break

    df.reset_index(drop=True, inplace=True)
    return df


def build_html_email(df: pd.DataFrame) -> str:
    if df.empty:
        return """
        <html>
            <body>
                <h3>No matching Performance Engineering jobs found in the last 48 hours.</h3>
            </body>
        </html>
        """

    remote_df = df[df.get("is_remote") == True]
    onsite_df = df[df.get("is_remote") != True]

    def build_table(title, data):
        if data.empty:
            return f"<h3>{title}</h3><p>No jobs found.</p>"

        rows = ""
        for _, row in data.iterrows():
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
        <h3>{title} ({len(data)})</h3>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr>
                <th>Source</th>
                <th>Company</th>
                <th>Title</th>
                <th>Link</th>
            </tr>
            {rows}
        </table>
        <br/>
        """

    return f"""
    <html>
    <body>
        <h2>Daily Performance Engineering Job Alerts</h2>

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
    msg.set_content("This email requires an HTML-capable email client.")
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
