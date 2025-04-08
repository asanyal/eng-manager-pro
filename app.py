import streamlit as st
from llm_utils import CODE_REVIEW_GUIDELINES_V1, CODE_REVIEW_INSTRUCTIONS_V1
from shortcut_utils import DisplayUtils, ShortcutGateway, SprintUtils
from llm_utils import ask_openai
from datetime import datetime, timedelta
from tqdm import tqdm
from shortcut_utils import active_states
from github_utils import GithubAPI
from collections import defaultdict
import pandas as pd
import altair as alt
from utils.common_utils import CODE_RED_DAYS_AFTER, COMMON_PAGE_CSS
from actions.email_actions import GetEmails
from actions.calendar_actions import GetMyDay
from actions.github_actions import GetGithubActivity, GetSmartReviews, GetRepoPRs, GetAuthorPRs
from actions.shortcut_actions import ExplainAnObjective, AnalyzeAPerson, ExplainEpics
from actions.misc_actions import GetGoogleDocs, GetCompetitors, HighlightText, GetExecutionHealth


shortcut_gateway = ShortcutGateway()
display_utils = DisplayUtils()
sprint_utils = SprintUtils(shortcut_gateway)
github_token = st.secrets["github"]["token"]
github_api = GithubAPI(github_token)

all_owners = shortcut_gateway.get_all_owners()

st.set_page_config(layout="wide") 

st.markdown(
    COMMON_PAGE_CSS,
    unsafe_allow_html=True,
)

col1, col2, _, _ = st.columns([1, 1, 1, 1])
with col1:
    start = st.date_input("Start", value=datetime.now() - timedelta(days=7), format="MM-DD-YYYY")
with col2:
    end = st.date_input("End", value=datetime.now(), format="MM-DD-YYYY")

tab_names = [
    "My Day", "Emails", "GH Activity", "GH Author Activity", "SH Author Activity", "Smart Reviews", "GH Repo Activity", "Execution Health", "Objectives", 
    "Epics", "Highlight", "Docs", "Company Profiling"
]

my_day, get_emails, activity_feed, smart_reviews, author_prs, repo_prs, execution_health, explain_an_objective, explain_epics, analyze_a_person, highlighter, google_docs, competitors = st.tabs(tab_names)


with get_emails:
    GetEmails().do_action()
with my_day:
    GetMyDay().do_action()
with activity_feed:
    GetGithubActivity().do_action()
with explain_an_objective:
    ExplainAnObjective(shortcut_gateway, sprint_utils, display_utils).do_action(start, end)
with execution_health:
    GetExecutionHealth(shortcut_gateway, 27274, "Customer Health").do_action(start, end)
    GetExecutionHealth(shortcut_gateway, 25423, "G2.0 Product Quality").do_action(start, end)
with analyze_a_person:
    AnalyzeAPerson(shortcut_gateway, sprint_utils, display_utils).do_action(start, end)
with explain_epics:
    ExplainEpics(shortcut_gateway, display_utils).do_action(start, end)
with author_prs:
    GetAuthorPRs().do_action(start, end)
with repo_prs:
    GetRepoPRs().do_action(start, end)
with highlighter:
    HighlightText().do_action()
with google_docs:
    GetGoogleDocs().do_action()
with competitors:
    GetCompetitors().do_action()
with smart_reviews:
    GetSmartReviews().do_action()
