from collections import defaultdict
from llm_utils import ask_openai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dateutil import parser
import googleapiclient.discovery
import datetime
import os

INTERNAL_EMAIL_DOMAIN = "galileo.ai"
EXCLUDED_EMAIL_DOMAINS = ["@resource.calendar.google.com"]
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def login():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def format_date(d):
    datetime_obj = parser.isoparse(d)
    return datetime_obj.strftime("%a %b %-d")

def get_start_end_times(date1_str, date2_str):
    date1 = parser.isoparse(date1_str)
    date2 = parser.isoparse(date2_str)
    import pytz
    pacific_tz = pytz.timezone('US/Pacific')
    
    date1_pacific = date1.astimezone(pacific_tz)
    date2_pacific = date2.astimezone(pacific_tz)
    
    start_time = date1_pacific.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
    end_time = date2_pacific.strftime('%I:%M %p').lstrip('0').replace(' 0', ' ')
    
    return start_time, end_time

def calculate_duration_in_minutes(date1_str, date2_str):
    date1 = parser.isoparse(date1_str)
    date2 = parser.isoparse(date2_str)
    duration = abs(date2 - date1)
    total_minutes = duration.total_seconds() // 60
    return f"{int(total_minutes)} mins"

def format_time(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}min"
    else:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours}h"
        return f"{hours}h {remaining_minutes}min"

def analyze_calendar(sd, ed):
    print("Analyzing calendar...")
    creds = login()
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)

    sd_split = sd.split("-")
    ed_split = ed.split("-")

    start_date = datetime.datetime(int(sd_split[0]), int(sd_split[1]), int(sd_split[2])).isoformat() + 'Z'
    end_date = datetime.datetime(int(ed_split[0]), int(ed_split[1]), int(ed_split[2])).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=start_date, 
        timeMax=end_date,
        singleEvents=True, 
        orderBy='startTime').execute()

    events = events_result.get('items', [])
    print(f"{len(events)} events retrieved from Calendar API")
    events_context = []
    if not events:
        print('No upcoming events found.')
    
    def get_attendee_emails(event):
        # Check if 'attendees' key exists in the event dictionary
        if 'attendees' in event:
            # Extract the email for each attendee
            attendee_names = [attendee['email'] for attendee in event['attendees']]
            return attendee_names # ask_openai(f"Get list of first names people from this list {str(attendee_names)}. ONLY return space separated string of names.")
        else:
            # Return an empty list if there are no attendees
            return []
    
    for event in events:
        if event['summary'] == "Block":
            continue
        if 'dateTime' in event['start']:
            attendee_emails = [
                email for email in get_attendee_emails(event)
                if not any(email.endswith(domain) for domain in EXCLUDED_EMAIL_DOMAINS)
            ]
            # meeting type determination
            if len(attendee_emails) == 2:
                meeting_type = "INT 1-1" if all(email.endswith("@" + INTERNAL_EMAIL_DOMAIN) for email in attendee_emails) else "EXT 1-1"
            elif len(attendee_emails) >= 8 and any(not email.endswith("@" + INTERNAL_EMAIL_DOMAIN) for email in attendee_emails):
                meeting_type = "EXT Group - Large"
            elif len(attendee_emails) >= 3:
                meeting_type = "EXT Group" if any(not email.endswith("@" + INTERNAL_EMAIL_DOMAIN) for email in attendee_emails) else "INT Group"
            else:
                meeting_type = "EXT" if any(not email.endswith("@" + INTERNAL_EMAIL_DOMAIN) for email in attendee_emails) else "INT"
            if meeting_type not in ["INT 1-1", "INT Group", "EXT Group", "EXT Group - Large", "EXT 1-1", "EXT", "INT"]:
                print(f"Incorrect meeting type... {meeting_type}")
                continue
            aliases_string = "#".join(email.split('@')[0] for email in attendee_emails[:4])
            event_date = format_date(event['start'].get('dateTime'))
            if 'hangoutLink' in event:
                hangout_link = event.get('hangoutLink')
            elif 'conferenceData' in event and 'entryPoints' in event['conferenceData'] and len(event['conferenceData']['entryPoints']) > 0 and 'uri' in event['conferenceData']['entryPoints'][0]:
                hangout_link = event['conferenceData']['entryPoints'][0]['uri']
            else:
                hangout_link = event['htmlLink']
            st, et = get_start_end_times(event['start']['dateTime'], event['end']['dateTime'])
            duration = calculate_duration_in_minutes(event['start']['dateTime'], event['end']['dateTime'])
            organizer = event['creator']['email']
            event_summary = event['summary'].replace(',', '')
            events_context.append(
                f"{event_date}, {event_summary}, {organizer}, {st}, {et}, {duration}, {hangout_link}, {meeting_type}, {aliases_string}\n")
    print(f"{len(events_context)} events processed")
    return events_context

def get_free_time(events):
    # Define working hours
    from datetime import time
    work_start = time(8, 0)  # 8 AM
    work_end = time(18, 0)  # 6 PM

    # Group events by date
    events_by_date = defaultdict(list)
    for event in events:
        events_by_date[event["date"]].append(event)

    free_time_slots = defaultdict(list)

    for date, day_events in events_by_date.items():
        # Sort events by start time for each day
        day_events.sort(key=lambda x: x["start_time"])

        # Initialize the start of free time
        current_time = work_start

        for event in day_events:
            if event["description"] == "Block":
                continue
            event["start_time"] = max(event["start_time"], work_start)
            # If there's a gap between the current free time and the next event's start time, add it
            if event["start_time"] > current_time:
                free_time_slots[date.strftime("%b %d")].append(
                    (current_time.strftime("%I:%M %p"), event["start_time"].strftime("%I:%M %p"))
                )
            # Update the current time to the end of the current event
            current_time = max(current_time, event["end_time"])

        # Check for free time after the last event until the end of the working hours
        if current_time < work_end:
            free_time_slots[date.strftime("%b %d")].append(
                (current_time.strftime("%I:%M %p"), work_end.strftime("%I:%M %p"))
            )

    # Add days with no events
    all_dates = set(event["date"].strftime("%b %d") for event in events)
    for event_date in all_dates:
        if event_date not in free_time_slots:
            free_time_slots[event_date].append(
                (work_start.strftime("%I:%M %p"), work_end.strftime("%I:%M %p"))
            )
    return dict(free_time_slots)

def convert_to_markdown(schedule):
    from datetime import datetime
    from collections import defaultdict

    def calculate_duration(start, end):
        """Calculate duration in minutes between two time strings."""
        start_dt = datetime.strptime(start, "%I:%M %p")
        end_dt = datetime.strptime(end, "%I:%M %p")
        duration = (end_dt - start_dt).seconds // 60
        return duration

    def format_time(time_str):
        """Format time from 12-hour clock (08:00 AM) to a readable format (8 am)."""
        dt = datetime.strptime(time_str, "%I:%M %p")
        return dt.strftime("%-I %p").lower()

    markdown_output = []

    for date, intervals in schedule.items():
        free_times = defaultdict(list)

        # Process schedule to group by duration for each date
        for start, end in intervals:
            duration = calculate_duration(start, end)
            formatted_time = format_time(start)
            free_times[duration].append(formatted_time)

        # Sort durations in descending order
        sorted_durations = sorted(free_times.keys(), reverse=True)

        markdown_output.append(f"## {date}")

        for duration in sorted_durations:
            times = sorted(free_times[duration])  # Sort times for each duration
            times_str = ', '.join(times)
            markdown_output.append(f"- **{duration} MINS** free at {times_str}")

    return "\n".join(markdown_output)

def parse_event(event_string):
    from datetime import datetime
    import re

    parts = event_string.split(",")

    current_year = datetime.now().year
    date_string_with_year = f"{parts[0].strip()} {current_year}"
    date = datetime.strptime(date_string_with_year, "%a %b %d %Y")

    description = parts[1].strip()
    organizer = parts[2].strip()
    start_time = parts[3].strip()
    end_time = parts[4].strip()
    duration = float(re.search(r"\d+(\.\d+)?", parts[5].strip()).group())
    link = parts[6].strip()
    meeting_type = parts[7].strip()
    aliases = parts[8].strip().split("#")

    return {
        "date": date,
        "description": description,
        "organizer": organizer,
        "start_time": datetime.strptime(start_time, "%I:%M %p").time(),
        "end_time": datetime.strptime(end_time, "%I:%M %p").time(),
        "duration": duration,
        "link": link,
        "type": meeting_type,
        "aliases": aliases,
    }

def categorize_meetings(events):
    meeting_summary = {}
    for event in events:
        date_str = event['date'].strftime('%a')
        duration = event['duration']
        if date_str not in meeting_summary:
            meeting_summary[date_str] = {
                'Date': date_str,
                'Total Meetings': 0,
                '0-25 min': 0,
                '30 min': 0,
                '30-55 min': 0,
                '60 min': 0,
                '60+ min': 0
            }
        
        time_in_hours = duration > 0 and duration < 12
        meeting_summary[date_str]['Total Meetings'] += 1

        if time_in_hours:
            meeting_summary[date_str]['60 min' if duration == 1.0 else '60+ min'] += 1
        else:
            if 15 <= duration < 30:
                meeting_summary[date_str]['0-25 min'] += 1
            elif duration == 30:
                meeting_summary[date_str]['30 min'] += 1
            elif 30 < duration < 55:
                meeting_summary[date_str]['30-55 min'] += 1
            elif 55 <= duration <= 60:
                meeting_summary[date_str]['60 min'] += 1
            elif duration > 60:
                meeting_summary[date_str]['60+ min'] += 1
    return list(meeting_summary.values())

def summarize_events(events):
    event_summary = defaultdict(lambda: {"Count": 0, "Description": ""})
    for event in events:
        meeting_type = event['type']
        description = event['description']
        event_summary[meeting_type]["Count"] += 1
        event_summary[meeting_type]["Description"] = f"{event_summary[meeting_type]['Description']}, {description}" if event_summary[meeting_type]["Description"] else description
    
    prompt = """
        Shorten and clean up in one sentence: {x}
        Do not use the word Galileo (our company name) in the response as it's repetitive.
        Do not use words like daily, weekly, days of the week in the response.
        Do not use words like meeting, call, sync, etc. in the response.
        For meetings with other companies e.g. Galileo<>HeadspaceHealth, just mention HeadspaceHealth
    """
    summarized_list = [
        {
            "Meeting Type": meeting_type, 
            "Count": data["Count"], 
            "Description": ask_openai(prompt.format(x=data["Description"]))
         }
        for meeting_type, data in event_summary.items()
    ]
    return summarized_list

def generate_markdown_table(data, headers):
    table = "| " + " | ".join(headers) + " |\n"
    table += "|-" * len(headers) + "|\n"
    for row in data:
        table += "| " + " | ".join(str(row[header]) for header in headers) + " |\n"
    return table
