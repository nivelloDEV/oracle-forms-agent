from scraper import run_scraper
from send_report import send_report

if __name__ == "__main__":
    print("=== Oracle Forms Agent startar ===")
    results = run_scraper()
    send_report(results)
    print("=== Klar ===")
