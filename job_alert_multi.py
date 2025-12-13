import os
import smtplib
from email.message import EmailMessage
import pandas as pd
from jobspy import scrape_jobs

# ---------------- CONFIG ----------------
SEARCH_TERMS = [
    "Performance Test Engineer",
    "Performance Engineer",
    "Senior Performance Engineer"
]

LOCATION = "United States"

REMOTE_ONLY = True
SENIOR_KEYWORDS = ["senior", "sr", "lead", "staff", "principal"]
MIN_SALARY = 120000  # USD

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
                "indeed",
                "linkedin",
                "glassdoor",
                "google"   # Google Jobs → includes Workday
            ],
            search_term=term,
            location=LOCATION,
            results_wanted=80,
            hours_old=24
        )
        all_results.append(df)

    df = pd.concat(all_results, ignore_index=True)
    df.columns = [c.lower() for c in df.columns]

    # -------- Filters --------
    if REMOTE_ONLY and "is_remote" in df.columns:
        df = df[df["is_remote"] == True]

    df = df[df["title"].str.lower().str.contains("|".join(SENIOR_KEYWORDS), na=False)]

    if "min_salary" in df.columns:
        df = df[df["min_salary"].fillna(0) >= MIN_SALARY]

    # Workday tagging
    df["source"] = df["job_url"].apply(
        lambda x: "Workday" if "workdayjobs" in str(x).lower() else "Job Board"
    )

    df.drop_duplicates(subset=["title", "company", "job_url"], inplace=True)
    return df


def build_html_email(df: pd.DataFrame) -> str:
    if df.empty:
        return """
        <html>
            <body>
                <h3>No new Performance Engineering jobs found in the last 24 hours.</h3>
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
        <h2>Daily Performance Engineer Jobs</h2>
        <ul>
            <li>Remote only</li>
            <li>Senior / Lead / Staff</li>
            <li>Salary ≥ ${MIN_SALARY:,}</li>
        </ul>
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
    msg["Subject"] = f"Daily Performance Engineer Jobs ({count})"
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
