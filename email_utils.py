# All the code

import datetime
import streamlit as st
from bs4 import BeautifulSoup

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from IPython.display import display, HTML
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
import time
import datetime
from llm_utils import ask_openai
import os
from tqdm import tqdm
import re

# Run Galileo
token_json = "gmail_token.json"
api_credentials_json = "gmail_api_credentials.json"
my_email = "atin@rungalileo.io"

base_query = f'to:{my_email} OR cc:{my_email} OR bcc:{my_email} -from:notifications@github.com -from:{my_email} -from:team@netlify.com -from:notifications@shortcut.com -from:notifications@vercel.com'

def parse_email(email_string):
    email_details = {}
    parts = email_string.split(", ")
    for part in parts:
        if part.startswith("From:"):
            name_email = part.split(": ", 1)[1]
            match = re.search(r'"?(.*?)"?\s*<([^>]+)>', name_email)
            if match:
                name = match.group(1)
                email = match.group(2)
                domain = email.split("@")[1].split(".")[0]
                email_details["Sender"] = f"{name} ({domain})"
                email_details["Type"] = "Internal" if domain == "rungalileo" or domain == "galileo" else "External"
            else:
                email_details["Sender"] = name_email
                email_details["Type"] = "Internal" if "rungalileo.io" in name_email or "galileo.ai" in name_email else "External"
        
        elif part.startswith("Time:"):
            email_details["DateTime"] = part.split(": ", 1)[1]
        
        elif part.startswith("Subject:"):
            subject = part.split(": ", 1)[1]
            email_details["Subject"] = (subject[:80] + "...") if len(subject) > 50 else subject
        
        elif part.startswith("Link:"):
            if "rungalileo.io" in my_email:
                email_details["Link"] = part.split(": ", 1)[1]
            else:
                email_details["Link"] = part.split(": ", 1)[1].replace("/u/0/", "/u/2/")
    return email_details

# Generate HTML table
def generate_html_table(email_data):
    # Create the HTML table structure
    style = """
        <style>
            table {
                border-collapse: collapse;
                table-layout: auto;
            }
            th, td {
                border: 1px solid white;
                padding: 10px 5px; /* 10px top and bottom, 5px left and right */
                text-align: left;
            }
        </style>
    """
    html = style + "<table border='1' style='width:100%; border-collapse:collapse;'>"
    html += "<tr><th>Date and time</th><th>Type</th><th>Sender</th><th>Subject</th><th>Link</th></tr>"
    
    for email in email_data:
        html += "<tr>"
        html += f"<td>{email['DateTime']}</td>"
        color = "green" if email["Type"] == "Internal" else "red"
        html += f"<td style='color:{color};'>{email['Type']}</td>"
        html += f"<td>{email['Sender']}</td>"
        html += f"<td>{email['Subject']}</td>"
        html += f"<td><a href='{email['Link']}' target='_blank'>Link</a></td>"
        html += "</tr>"
    
    html += "</table>"
    return BeautifulSoup(html, "html.parser").prettify()


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

recruiter_emails = [
    'jivaroinc.com',
    'intelletec.com',
    'codreamwork.com',
    'signify-tech.com',
    'jbizzell@rungalileo.io',
]

def login():
    creds = None
    if os.path.exists(token_json):
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(api_credentials_json, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_json, "w") as token:
            token.write(creds.to_json())
    return creds



def fetch_emails_in_last_n_hours(
        n_hours=3, query=None, additional_prompt=None, details=False, new_only=False, ai_generated=False):
    creds = login()
    try:
        service = build("gmail", "v1", credentials=creds)
        n_hours_ago_epoch = None
        if isinstance(n_hours, int):
            n_hours_ago_epoch = int(time.time()) - n_hours * 60 * 60
            query = f' after:{n_hours_ago_epoch} ' + query
        elif isinstance(n_hours, tuple):
            end_hours, start_hours = n_hours
            start_hours_ago_epoch = int(time.time()) - start_hours * 60 * 60
            end_hours_ago_epoch = int(time.time()) - end_hours * 60 * 60
            query = f'before:{end_hours_ago_epoch} after:{start_hours_ago_epoch} ' + query
        else:
            raise ValueError("n_hours must be an integer or a tuple with two elements.")

        if new_only:
            query += ' is:unread'
        results = service.users().messages().list(
            userId='me',
            q=query,
        ).execute()
        messages = results.get('messages', [])
        if not messages:
            print("You've got no emails!")
            return
        emails = []
        email_progress = st.progress(0)
        for i, message in enumerate(tqdm(messages)):
            email_progress.progress(i / len(messages))
            # Get the Subject and From for that message ID
            format = 'full' if details else 'metadata'
            msg =  service.users().messages().get(userId='me', id=message['id'], format=format, metadataHeaders=['Subject','From']).execute()
            from_email = None
            subject = None
            msg_id = msg['id']
            for header in msg['payload']['headers']:
                if header['name'] == 'From':
                    from_email = header['value']
                    company_email = None
                    import re
                    match = re.search(r'@([a-zA-Z0-9-]+)\.', from_email)
                    if match:
                        domain = match.group(1)
                        company_email = domain
                if header['name'] == 'Subject':
                    subject = header['value']
            timestamp_ms = int(msg['internalDate'])
            email_time = datetime.datetime.fromtimestamp(timestamp_ms / 1000).astimezone().strftime('%a %b %-d %I.%M %p')
            email_str = f"From: {from_email}, Time: {email_time}, Subject: {subject}, Link: https://mail.google.com/mail/u/0/#inbox/{msg_id}"
            if company_email is not None:
                email_str += f", Company Alias: {company_email}"
            #body
            if details:
                decoded_body = None
                payload = msg['payload']
                parts = payload.get('parts', [])
                body = ""

                for part in parts:
                    if part['mimeType'] == 'text/plain':  # For plain text emails
                        body = part['body'].get('data')
                        break
                    elif part['mimeType'] == 'text/html':  # If email is in HTML format
                        body = part['body'].get('data')
                        break

                # Decode the email body if it's base64 encoded
                import base64
                import html
                
                if body:
                    decoded_body = base64.urlsafe_b64decode(body).decode('utf-8')
                    decoded_body = html.unescape(decoded_body)

                if body:
                    decoded_body = ask_openai(f"""
                        Simplify in clear language and in 2-3 sentences a summary of the email:
                        {decoded_body}
                    """)
                email_str += f", Body: {decoded_body}"
            emails.append(email_str)
        
        email_progress.progress(100)
        if len(emails) == 0:
            return "You've received no emails."

        st.markdown(f"You've got {len(emails)} emails!")
        emails_string = '\n'.join(emails)
        if not ai_generated:
            parsed_emails = [parse_email(email) for email in emails]
            return generate_html_table(parsed_emails)
        else:
            st.markdown("Generating AI summaries...")
            return ask_openai(f"""
                Provide me a summary of all emails received in the format below (only show values, not keys).
                An email ins "Internal" if the sender email has a rungalileo.io domain. Else it is "Extenral".
                    - "Date & Time" 
                    - "Type" Internal or External, 
                    - "Sender name" in short (3-5 keywords) with the Company Alias in brackets,
                    - "Subject" clean and shortened, 
                    - "Body" (ONLY include IF the 'body' key is present in the emails below), 
                    - "Link" to the email.
                Display content in a beautiful HTML table format with the columns listed above. 
                Color the keyword "Internal" Green, and "External" Red.
                Only output the table.
                Additional Instructions: {additional_prompt}
                Emails:
                {emails_string}
            """)
    except HttpError as error:
        print(f"An error occurred: {error}")
