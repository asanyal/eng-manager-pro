import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from IPython.display import display, HTML
import streamlit as st

from llm_utils import ask_openai

# Scopes for the app
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TABLE_CSS = "border-collapse: collapse;"
TD_CSS = "border: 1px solid black; padding: 8px; text-align: left; min-width: 250px; word-wrap: break-word;"


def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service, creds


def print_sheet(content, interactive=False, columns=None):
    if content is None:
        print("No content to print")
        return
    for sheet_name, rows in content.items():
        print(f"Data from sheet: {sheet_name}")
        for row in rows:
            row_to_print = []
            if columns is None:
                row_to_print = row
        else:
            for i in range(columns[0], columns[1]):
                if i < len(row):
                    row_to_print.append(row[i])
        print(row_to_print)
        if interactive:
            input("Press Enter to continue...")


def get_sheet_data(service, sheet_name, type="sheets"):
    query, _ = get_doc_type(type)
    results = service.files().list(
        q=query,
        pageSize=1000,
        fields="nextPageToken, files(id, name)").execute()
    items = results.get('files', [])
    sheet_id, content = None, []
    for item in items:
        if item['name'] == sheet_name:
            display(HTML(f"Found sheet <a href='https://docs.google.com/{type}/d/{item['id']}/edit'>{sheet_name}</a>"))
            sheet_id =  item['id']

            # mime_type = service.files().get(fileId=sheet_id).execute().get('mimeType')
            sheets_service = build('sheets', 'v4', credentials=creds)
            spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            sheets = spreadsheet.get('sheets', [])

            for sheet in sheets:
                sheet_name = sheet['properties']['title']
                print(f"Fetching data from sub-sheet: {sheet_name}")
                result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=f'{sheet_name}!A1:Z1000'  # Adjust the range as needed
                ).execute()
                sheet_content = result.get('values', [])
                content.append({sheet_name: sheet_content})
            # Single sheet fetch
            # content = fetch_content(mime_type, sheet_id)
            break
    if sheet_id is None:
        print(f"Sheet {sheet_name} not found")
        return None
    return content


def ama(content, query):
    content_str = ""
    for sub_sheet_content in content:
        for sheet_name, rows in sub_sheet_content.items():
            sub_sheet_content_str = "\n".join(["\t".join(row) for row in rows])
            content_str += f"Sheet: {sheet_name}\n Sheet Data:\n{sub_sheet_content_str}\n"

    question = f"""
    Answer the following question, in as short as possible (only the answer to the question, no explanation).
    Question: {query}
    Content: {content_str}
    Double check and be sure of your answer. Think as much as you need to.
    Return the answer in HTML. 
    Add a span tag with #D8B9D6 color background and black text, to the important words conveying key information.
    Make sure each sentence has a span tag.
    """

    return ask_openai(
        user_content=question, 
        system_content="""
        You are a smart data analyst. 
        You are given data from multiple sheets in the following format:
        Sheet: sheet name
        Sheet Data: list of lists of the sheet content
        One of the rows is the header and the following rows are values for the columns in the header row.
        """,
        model="gpt-4o-mini"
    )


def fetch_content(mime_type, file_id):
    """Fetch the raw content of the Google Doc in a variable (decoded)"""
    try:
        if mime_type == "application/vnd.google-apps.spreadsheet":
            # Sheets
            sheets_service = build('sheets', 'v4', credentials=creds)
            result = sheets_service.spreadsheets().values().get(spreadsheetId=file_id, range='A1:Z1000').execute()
            values = result.get('values', [])
            return values
        else:
            # Everything else
            docs_service = build('drive', 'v3', credentials=creds)
            request = docs_service.files().export_media(fileId=file_id, mimeType='text/plain')
            file_content = request.execute()
            return file_content

    except Exception as e:
        print(f"An error occurred while fetching the content for file ID {file_id}: {e}")
        return None


def get_doc_type(type):
    """
    Returns query and document_type based on the given type
    """
    if type == "docs":
        return "mimeType='application/vnd.google-apps.document'", "document"
    elif type == "sheets":
        return "mimeType='application/vnd.google-apps.spreadsheet'", "spreadsheets"
    elif type == "slides":
        return "mimeType='application/vnd.google-apps.presentation'", "presentation"
    else:
        raise ValueError(f"Unsupported document type: {type}")


def list_docs(service, number_of_docs=10, type="docs", summarize=False):
    
    query, document_type = get_doc_type(type)

    results = service.files().list(
        q=query, 
        pageSize=number_of_docs,
        fields="nextPageToken, files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        print('No documents found.')
    else:
        item_progress = st.progress(0)
        for i, item in enumerate(items):
            item_progress.progress(i / number_of_docs)
            html_content = f"<table style='{TABLE_CSS}'>"
            file_id = item['id']
            file_name = item['name']
            summarized_content = ""
            category = ""
            if type == "docs" and summarize:
                categories = ["ENG", "Sales", "SE", "MKT", "HR", "OTHER"]
                mime_type = service.files().get(fileId=file_id).execute().get('mimeType')
                content = fetch_content(mime_type, file_id)

                if content is not None:
                    summarized_content = ask_openai(
                        f"""
                            Provide a short summary, capturing all the key points in the document along with the main conclusion 
                            (capturing the core message) as a final line of the summary. 
                            Use as few words as possible, avoid filler words.
                            {content[:1500]}
                        """
                    )
                    category = ask_openai(
                        f"""
                        Provide a category for the document based on the content.
                        {summarized_content}
                        category should be one of the following: {categories}
                        ENG: Engineering
                        Sales: Sales
                        SE: Sales Engineering (technical sales, POCs, etc.)
                        MKT: Marketing
                        HR: Human Resources (hiring, onboarding, etc.)
                        PRODUCT: Product (product management, roadmap, feature description, etc.)
                        The different between Sales and Sales Engineering is that Sales Engineering is more technical,
                        involves another business or customer.
                        Output only the category, nothing else.
                        """
                    )
            
            html_content += f"<tr><td style='{TD_CSS}'><a href='https://docs.google.com/{document_type}/d/{file_id}/edit'>{file_name}</a></td>"
            if category:
                html_content += f"<td style='{TD_CSS}'>{category}</td>"
            if summarized_content:
                html_content += f"<td style='{TD_CSS}'>{summarized_content}</td>"
            html_content += "</tr></table>"
            st.markdown(html_content, unsafe_allow_html=True)
        item_progress.progress(100)
