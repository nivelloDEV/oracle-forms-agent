import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

GMAIL_USER = os.environ.get("SMTP_USER")
GMAIL_APP_PASSWORD = os.environ.get("SMTP_PASSWORD")
REPORT_TO = os.environ.get("EMAIL_TO", GMAIL_USER)


def build_html(results: list[dict]) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")

    if not results:
        body_content = """
        <div class="no-results">
            Inga nya företag hittades denna vecka.
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
            date_tag = f'<span class="tag date">📅 {date_raw}</span>' if date_raw else ""
            cards += f"""
            <div class="card">
                <a href="{link}" class="card-title">{title}</a>
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
        .card-title {{ color: #c74b00; font-size: 16px; font-weight: bold; text-decoration: none; display: block; margin-bottom: 6px; }}
        .card-title:hover {{ text-decoration: underline; }}
        .snippet {{ color: #555; font-size: 14px; margin: 0 0 10px; line-height: 1.5; }}
        .tag {{ display: inline-block; background: #f0f0f0; color: #666; font-size: 12px; padding: 3px 8px; border-radius: 12px; }}
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
                🔍 Hittade <strong>{len(results)} nya träffar</strong> denna vecka.
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
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("GMAIL_USER eller GMAIL_APP_PASSWORD saknas – hoppar över e-post.")
        return

    html = build_html(results)
    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"Oracle Forms-rapport {date_str} – {len(results)} nya fynd"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = REPORT_TO
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, REPORT_TO, msg.as_string())

    print(f"E-post skickad till {REPORT_TO}")


if __name__ == "__main__":
    # Testar med dummydata
    test = [
        {
            "title": "Oracle Forms Developer – Testföretag AB",
            "link": "https://linkedin.com/jobs/test",
            "snippet": "Vi söker en erfaren Oracle Forms-utvecklare till vårt team i Stockholm.",
            "query": 'site:linkedin.com/jobs "oracle forms" sweden',
        }
    ]
    send_report(test)
