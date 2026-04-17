import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
EMAIL_TO = os.environ.get("EMAIL_TO", SMTP_USER)


def build_html(results: list[dict]) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")

    new_count = sum(1 for r in results if r.get("is_new"))
    returning_count = len(results) - new_count

    if not results:
        body_content = """
        <div class="no-results">
            Inga träffar hittades denna vecka.
        </div>
        """
    else:
        cards = ""
        for r in results:
            snippet = r.get("snippet", "").replace("<", "&lt;").replace(">", "&gt;")
            title = r.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
            link = r.get("link", "")
            query = r.get("query", "")
            date_raw = r.get("date", "")
            date_tag = f'<span class="tag">📅 {date_raw}</span>' if date_raw else ""
            is_new = r.get("is_new", True)

            if is_new:
                badge = '<span class="badge badge-new">✨ Ny</span>'
                card_class = "card card-new"
            else:
                badge = '<span class="badge badge-returning">🔁 Återkommande</span>'
                card_class = "card card-returning"

            cards += f"""
            <div class="{card_class}">
                <div class="card-header">
                    {badge}
                    <a href="{link}" class="card-title">{title}</a>
                </div>
                <p class="snippet">{snippet}</p>
                <span class="tag">Sök: {query}</span>{date_tag}
            </div>
            """
        body_content = cards

    return f"""
    <!DOCTYPE html>
    <html lang="sv">
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; color: #333; }}
        .wrapper {{ max-width: 700px; margin: auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: #c74b00; color: white; padding: 24px 32px; }}
        .header h1 {{ margin: 0; font-size: 22px; }}
        .header p {{ margin: 4px 0 0; opacity: 0.85; font-size: 14px; }}
        .body {{ padding: 24px 32px; }}
        .summary {{ background: #fff8f5; border-left: 4px solid #c74b00; padding: 12px 16px; margin-bottom: 24px; border-radius: 4px; font-size: 15px; }}
        .card {{ border: 1px solid #e8e8e8; border-radius: 6px; padding: 16px; margin-bottom: 16px; }}
        .card-new {{ border-left: 4px solid #2e7d32; }}
        .card-returning {{ border-left: 4px solid #999; }}
        .card-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }}
        .card-title {{ color: #c74b00; font-size: 16px; font-weight: bold; text-decoration: none; }}
        .card-title:hover {{ text-decoration: underline; }}
        .badge {{ font-size: 12px; padding: 3px 10px; border-radius: 12px; font-weight: bold; white-space: nowrap; }}
        .badge-new {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-returning {{ background: #f0f0f0; color: #666; }}
        .snippet {{ color: #555; font-size: 14px; margin: 0 0 10px; line-height: 1.5; }}
        .tag {{ display: inline-block; background: #f0f0f0; color: #666; font-size: 12px; padding: 3px 8px; border-radius: 12px; margin-right: 6px; }}
        .no-results {{ text-align: center; color: #888; padding: 40px 0; font-size: 15px; }}
        .footer {{ background: #f5f5f5; padding: 16px 32px; font-size: 12px; color: #999; text-align: center; }}
    </style>
    </head>
    <body>
    <div class="wrapper">
        <div class="header">
            <h1>Oracle Forms – Veckorapport</h1>
            <p>Sverige &amp; Danmark · {date_str}</p>
        </div>
        <div class="body">
            <div class="summary">
                🔍 <strong>{len(results)} träffar</strong> denna vecka &nbsp;·&nbsp;
                ✨ <strong>{new_count} nya</strong> &nbsp;·&nbsp;
                🔁 <strong>{returning_count} återkommande</strong>
            </div>
            {body_content}
        </div>
        <div class="footer">
            Rapporten genereras automatiskt varje måndag. Powered by GitHub Actions + SerpAPI.
        </div>
    </div>
    </body>
    </html>
    """


def send_report(results: list[dict]):
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP_USER eller SMTP_PASSWORD saknas – hoppar över e-post.")
        return

    html = build_html(results)
    date_str = datetime.now().strftime("%Y-%m-%d")
    new_count = sum(1 for r in results if r.get("is_new"))
    subject = f"Oracle Forms-rapport {date_str} – {len(results)} träffar ({new_count} nya)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())

    print(f"E-post skickad till {EMAIL_TO}")


if __name__ == "__main__":
    test = [
        {
            "title": "Oracle Forms Developer – Testföretag AB",
            "link": "https://linkedin.com/jobs/test1",
            "snippet": "Vi söker en erfaren Oracle Forms-utvecklare till vårt team i Stockholm.",
            "query": 'site:linkedin.com/jobs "oracle forms" sweden',
            "date": "2 weeks ago",
            "is_new": True,
        },
        {
            "title": "Oracle Forms Consultant – Gamla Bolaget AS",
            "link": "https://linkedin.com/jobs/test2",
            "snippet": "Oracle Forms-konsult sökes till projekt i Köpenhamn.",
            "query": 'site:linkedin.com/jobs "oracle forms" denmark',
            "date": "3 months ago",
            "is_new": False,
        },
    ]
    send_report(test)
