
import os
import json
import re
import smtplib
import ssl

from email.message import EmailMessage
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# Website settings
URL = os.environ.get("PPSC_URL", "https://ppsc.gop.pk/")
SEEN_FILE = "seen.json"

# Optional keywords, separated by commas
KEYWORDS = [
    k.strip().lower()
    for k in os.environ.get("KEYWORDS", "").split(",")
    if k.strip()
]

RELEVANT = re.compile(r"advert|job|vacanc|\.pdf", re.IGNORECASE)

# Email settings
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
EMAIL_TO = os.environ.get("EMAIL_TO", EMAIL_USER)


def fetch_links():
    """Fetch job-related links from the PPSC website."""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    response = requests.get(
        URL,
        headers=headers,
        timeout=60
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    links = {}

    for anchor in soup.find_all("a", href=True):
        href = urljoin(URL, anchor["href"].strip())

        if not href.startswith(("http://", "https://")):
            continue

        text = " ".join(anchor.get_text(" ", strip=True).split())

        if RELEVANT.search(href) or RELEVANT.search(text):
            links[href] = text or href

    return links


def send_mail(subject, body):
    """Send an email alert using Gmail SMTP."""

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = EMAIL_USER
    message["To"] = EMAIL_TO
    message.set_content(body)

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465,
        context=ssl.create_default_context()
    ) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(message)


def main():
    try:
        links = fetch_links()
        print(f"Found {len(links)} relevant links on the page.")

        first_run = not os.path.exists(SEEN_FILE)

        if first_run:
            seen = {}
        else:
            with open(SEEN_FILE, "r", encoding="utf-8") as file:
                seen = json.load(file)

        new_links = {
            href: title
            for href, title in links.items()
            if href not in seen
        }

        if first_run:
            send_mail(
                "PPSC monitor is running",
                (
                    f"The monitor is active.\n"
                    f"{len(links)} links recorded as the baseline.\n"
                    "You will receive email alerts for new matching links.\n\n"
                    f"Website: {URL}"
                )
            )
            print("First run completed. Test email sent.")

        elif new_links:
            hits = {
                href: title
                for href, title in new_links.items()
                if not KEYWORDS
                or any(
                    keyword in (title + " " + href).lower()
                    for keyword in KEYWORDS
                )
            }

            if hits:
                lines = [
                    f"- {title}\n  {href}"
                    for href, title in hits.items()
                ]

                send_mail(
                    f"PPSC: {len(hits)} new job link(s)",
                    (
                        "New matching items found:\n\n"
                        + "\n\n".join(lines)
                        + f"\n\nPPSC website: {URL}"
                    )
                )

                print(f"Email sent for {len(hits)} new link(s).")
            else:
                print("New links found, but none matched your keywords.")

        else:
            print("Nothing new found.")

        # Save the latest links only after successful processing.
        seen.update(links)

        with open(SEEN_FILE, "w", encoding="utf-8") as file:
            json.dump(seen, file, ensure_ascii=False, indent=2)

    except requests.RequestException as error:
        print(f"Website request failed: {error}")

    except (OSError, json.JSONDecodeError) as error:
        print(f"File error: {error}")

    except smtplib.SMTPException as error:
        print(f"Email sending failed: {error}")


if __name__ == "__main__":
    main()
