import streamlit as st
from sprint_utils import DisplayUtils, ApiRouter, SprintUtils
from email_utils import fetch_emails_in_last_n_hours, base_query
from datetime import datetime, timedelta
from tqdm import tqdm
from IPython.display import display, HTML
from sprint_utils import active_states
from github_utils import GithubAPI
from calendar_utils import analyze_calendar, parse_event, format_time
from google_docs import authenticate, list_docs
import time
code_red_days_after = 10

api_router = ApiRouter()
display_utils = DisplayUtils()
sprint_utils = SprintUtils(api_router)

github_token = st.secrets["github"]["token"]
github_api = GithubAPI(github_token)

all_owners = api_router.get_all_owners()

st.set_page_config(layout="wide") 

st.markdown(
    """
    <style>
    .appview-container .main {
        max-width: 100% !important;  /* Force full width */
        padding-left: 2rem !important;  /* Add some padding */
        padding-right: 2rem !important;
    }
    
    /* Optional: Adjust the sidebar width */
    .st-emotion-cache-1d3bdo9 {
        width: 280px !important;  /* Change as needed */
    }
    div[role="tablist"] {
        display: flex;
        justify-content: space-evenly;  /* Distribute tabs evenly */
    }
    
    div[role="tab"] {
        flex-grow: 1;  /* Make tabs take equal space */
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


col1, col2, _, _ = st.columns([1, 1, 1, 1])
with col1:
    start = st.date_input("Start", value=datetime.now() - timedelta(days=14), format="MM-DD-YYYY")
with col2:
    end = st.date_input("End", value=datetime.now(), format="MM-DD-YYYY")

###
if "email_summary" not in st.session_state:
    st.session_state.email_summary = None
if 'objective_display_string' not in st.session_state:
    st.session_state.objective_display_string = None
if 'objective_results' not in st.session_state:
    st.session_state.objective_results = None
if 'person_analysis_html' not in st.session_state:
    st.session_state.person_analysis_html = None
if 'person_analysis_table' not in st.session_state:
    st.session_state.person_analysis_table = None
if 'user_activity_map' not in st.session_state:
    st.session_state.user_activity_map = None
###


tab_names = [
    "My Day", "Emails","GH Activity", "Objectives", "Person",
    "Epics", "GH Authors", "GH Repo", "Highlight", "Docs"
]

my_day, get_emails, activity_feed, explain_an_objective, analyze_a_person, explain_epics, author_prs, repo_prs, highlighter, google_docs = st.tabs(tab_names)

with get_emails:
    # small textbox to take in Hours
    col1, col2, col3, _ = st.columns([0.5, 0.5, 0.5, 3.5])

    with col1:
        hours = st.text_input("Hours", value=24)

    with col2:
        st.write(" ")
        st.write(" ")
        emails_button = st.button("Get Emails", key="emails_button", type="primary")

    with col3:
        st.write(" ")
        st.write(" ")
        ai_generated = st.checkbox("AI", value=False)
    full_width_container = st.container()

    with full_width_container:
        if emails_button:
            summary = fetch_emails_in_last_n_hours(
                n_hours=int(hours), 
                query=base_query, 
                ai_generated=ai_generated
            )
            st.session_state.email_summary = summary if summary else "<span style='color: #0d7e03;'>No emails!</span>"

        if st.session_state.email_summary is not None:
            st.markdown(st.session_state.email_summary, unsafe_allow_html=True)
        else:
            st.markdown("<span style='color: #0d7e03;'>No emails!</span>", unsafe_allow_html=True)


if "my_day_events" not in st.session_state:
    st.session_state.my_day_events = None

if "skippable_time" not in st.session_state:
    st.session_state.skippable_time = None


with my_day:

    day = ["today", "tomorrow", "day after", "3 days from now", "4 days from now", "5 days from now"]
    col1, col2, _, _ = st.columns([1, 1, 2, 2])
    with col1:
        day_selected = st.selectbox("Day", day)
    with col2:
        st.write(" ")
        st.write(" ")
        day_button = st.button("Gimme my day", key="day_button", type="primary")

    full_width_container = st.container()
    leave_home_at_time = None
    
    with full_width_container:

        if day_button:     
            day_map = {"today": 0, "tomorrow": 1, "day after": 2, "3 days from now": 3, "4 days from now": 4, "5 days from now": 5}
            offset = day_map.get(day_selected, 0)

            start_date = (datetime.now() + timedelta(days=offset)).strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=offset+1)).strftime('%Y-%m-%d')

            events_context = analyze_calendar(start_date, end_date)
            events = [parse_event(event) for event in events_context]
            display_html = []

            idx = 0

            prev_end_time = None

            

            skippable_time = 0
            for i, event in enumerate(events):

                if event['date'] >= datetime.strptime(start_date, '%Y-%m-%d') and event['date'] <= datetime.strptime(end_date, '%Y-%m-%d'):
                    description = event['description']
                    print(f"Appending ----> {i}. {description}")                    
                    
                    current_start_time = datetime.strptime(str(event['start_time']), '%H:%M:%S')

                    # set leave_home_at_time to the earliest start time of all events
                    if leave_home_at_time is None or current_start_time < leave_home_at_time:
                        leave_home_at_time = current_start_time

                    current_start_time_str = current_start_time.strftime('%I.%M %p')
                    current_duration = int(event['duration'])

                    if "standup" in description.lower() or "planning" in description.lower():
                        skippable_time += current_duration
                        description = f"<span style='color: #1f9f8a;'>[Skippable] {description}</span>"
                    
                    if prev_end_time is not None:

                        prev_break_time = (current_start_time - prev_end_time).total_seconds() / 60
                        prev_end_time_str = prev_end_time.strftime('%I.%M %p')
                        current_start_time_str = current_start_time.strftime('%I.%M %p')

                        if i > 0:
                            if prev_break_time > 0:
                                display_html[-1] = display_html[-1].replace("</tr>", f"<td><span style='color: #006400;'>{abs(int(prev_break_time))} min</span> break <span style='font-size: 10px;'>({prev_end_time_str} - {current_start_time_str})</span></td></tr>")
                            elif prev_break_time < 0:
                                display_html[-1] = display_html[-1].replace("</tr>", f"<td><span style='color: #FF0000;'>{abs(int(prev_break_time))} min overlap with next event</span></td></tr>")
                            elif prev_break_time == 0:
                                display_html[-1] = display_html[-1].replace("</tr>", f"<td><span style='color: #FF0000;'>No break!</span></td></tr>")
                    else:
                        prev_duration = 0

                    display_html.append(f"<tr><td>{current_start_time_str} (<span style='color: #FF69B4;'>{format_time(current_duration)}</span>)</td><td>{description}</td></tr>") 
                    prev_end_time = datetime.strptime(str(event['end_time']), '%H:%M:%S')
                    
                    idx += 1

            if idx == 0:
                display_html.append("<tr><td><span style='color: #00FF00;'>Free! Free! Free!</span></td></tr>")

            
            st.session_state.skippable_time = skippable_time

            display_html = ["<table border='1' style='width: 70%;'><tr><th>Event</th><th>Time</th><th>After the event</th></tr>"] + display_html + ["</table>"]


            st.session_state.my_day_events = "".join(display_html)

        if leave_home_at_time is not None:
            lht = leave_home_at_time - timedelta(minutes=50)
            wut = leave_home_at_time - timedelta(minutes=120)
            st.markdown(f"<tr><td><span style='color: #FF6100;'>Wake up at <b>{wut.strftime('%I.%M %p')}</b></span></td></tr>", unsafe_allow_html=True)
            st.markdown(f"<tr><td><span style='color: #0d7e03;'>Leave home at <b>{lht.strftime('%I.%M %p')}</b></span></td></tr>", unsafe_allow_html=True)

        if st.session_state.my_day_events and st.session_state.skippable_time:
            st.markdown(st.session_state.my_day_events, unsafe_allow_html=True)
            st.markdown(f"<span style='color: #FF6100;'>{format_time(st.session_state.skippable_time)} of skippable meetings.</span>", unsafe_allow_html=True)


if 'feed_strings' not in st.session_state:
    st.session_state.feed_strings = []
if 'repo_events_count' not in st.session_state:
    st.session_state.repo_events_count = {}
if 'fetching_activity' not in st.session_state:
    st.session_state.fetching_activity = False
if 'thread_active' not in st.session_state:
    st.session_state.thread_active = False


with activity_feed:

    col1, col2, col3, _ = st.columns([0.5, 0.6, 0.8, 3.5])
    with col1:
        last_n_hours = st.text_input("Last N Hours", value=24)
    with col2:
        st.write(" ")
        st.write(" ")
        refresh_feed_clicked = st.button("🔄")
    with col3:
        st.write(" ")
        st.write(" ")
        smart_summary = st.checkbox("Smart Summary", value=False)
    
    if refresh_feed_clicked:
        feed_strings, repo_events_count = github_api.get_feed(last_n_hours=int(last_n_hours))

        st.session_state.feed_strings = feed_strings
        st.session_state.repo_events_count = repo_events_count

        if smart_summary:
            activity_map = github_api.get_user_activity(last_n_hours=int(last_n_hours))
            st.session_state.user_activity_map = activity_map

    if st.session_state.feed_strings and st.session_state.repo_events_count:
        col1, col2, _ = st.columns([2, 1, 1])
        with col1:
            scrollable_container = st.container(height=300)
            with scrollable_container:
                for feed_string in st.session_state.feed_strings:
                    st.markdown(feed_string, unsafe_allow_html=True)
        with col2:
            st.bar_chart(st.session_state.repo_events_count, color="#9c0000", height=300)

    full_width_container = st.container()
    with full_width_container:
        if st.session_state.user_activity_map:
            st.markdown(st.session_state.user_activity_map, unsafe_allow_html=True)

with explain_an_objective:

    start = start.strftime("%d %b %Y")
    end = end.strftime("%d %b %Y")

    objective_name_to_id_map = api_router.get_all_objectives()
    objective_names = [objective_name for objective_name in objective_name_to_id_map.keys()]

    objective_dropdown = st.selectbox("Objective", objective_names)
    objective_id = objective_name_to_id_map[objective_dropdown]
    objective = api_router.get_objective_from_id(objective_id)

    explain_clicked = st.button("Explain", type="primary")

    full_width_container = st.container()

    with full_width_container:
        if explain_clicked:
            results, display_string = api_router.explain_epics_from_objective(
                objective_id, 
                start,
                end,
                code_red_days_after,
                verbose=True
            )
            st.session_state.objective_display_string = display_string
            st.session_state.objective_results = results

        if st.session_state.objective_display_string and st.session_state.objective_results:
            display_utils.display_epics_results(
                st.session_state.objective_display_string, 
                st.session_state.objective_results, 
                code_red_days_after, 
                start, 
                end
            )


with analyze_a_person:
    owner = st.selectbox("Owner", all_owners)

    analyze_clicked = st.button("Analyze Person", type="primary")

    full_width_container = st.container()

    if analyze_clicked:

        with full_width_container:
            owner_id = api_router.get_owner_id(owner)
            stories = api_router.get_stories_between_dates(
                datetime.strptime(start, "%d %b %Y").strftime('%Y-%m-%d'),
                datetime.strptime(end, "%d %b %Y").strftime('%Y-%m-%d')
            )
            filtered_stories = [story for story in stories if len(story['owner_ids']) > 0 and story['owner_ids'][0] == owner_id]

            html_table = "<table style='width: 100%;'><tr><th>Story</th><th>Created on</th><th>Owner</th><th>Requester</th><th>Complete</th><th>Epic</th></tr>"

            total_owner_stories = 0
            completed_owner_stories = 0
            self_created_count = 0

            for story in tqdm(filtered_stories):
                total_owner_stories += 1
                is_complete = api_router.get_workflow_name(story['workflow_state_id']) in active_states
                if is_complete:
                    completed_owner_stories += 1
                is_complete_str = "<span style='color: #00FF00;'>Yes</span>" if is_complete else "<span style='color: #FF0000;'>No</span>"
                created_at_str = datetime.strptime(story['created_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")
                requester_str = api_router.get_owner_name(story['requested_by_id'])
                self_created = story['requested_by_id'] == owner_id
                if self_created:
                    self_created_count += 1
                epic_str = api_router.get_epic_name(story['epic_id'])
                html_table += f"<tr><td><a href='{story['app_url']}'>{story['name']}</a></td><td>{created_at_str}</td><td>{owner}</td><td>{requester_str}</td><td>{is_complete_str}</td><td>{epic_str}</td></tr>"

            html_table += "</table>"
            
            div_html = "<ul>"
            
            if len(filtered_stories) > 0:
                if completed_owner_stories > 0:
                    div_html += f"<li>{owner} completed <span style='color: #FF69B4;'>{completed_owner_stories}</span> out of <span style='color: #FF69B4;'>{total_owner_stories}</span> stories from {start} to {end}.</li>"
                    div_html += f"<li>That's a completion rate of <span style='color: #FF69B4;'>{completed_owner_stories / total_owner_stories * 100:.2f}%</span>.</li>"

                keywords = api_router.extract_keywords(filtered_stories)
                div_html += f"<li>They solved problems for: <span style='color: #FF69B4;'>{', '.join(keywords)}</span></li>"
                div_html += f"<li><span style='color: #FF69B4;'>{(len(filtered_stories) - self_created_count)/len(filtered_stories) *100:.2f}%</span> of these stories were created by others!</li>"

            div_html += "</ul>"

            st.session_state.person_analysis_html = div_html
            st.session_state.person_analysis_table = html_table

    if st.session_state.person_analysis_html and st.session_state.person_analysis_table:
        st.markdown(st.session_state.person_analysis_html, unsafe_allow_html=True)
        st.markdown(st.session_state.person_analysis_table, unsafe_allow_html=True)


if 'epic_explanation_display' not in st.session_state:
    st.session_state.epic_explanation_display = None
if 'epic_explanation_results' not in st.session_state:
    st.session_state.epic_explanation_results = None


with explain_epics:
    
    epic_ids = st.text_input("Comma separated Epic IDs e.g. 21023, 21024")
    explain_epic_clicked = st.button("Explain Epics", type="primary")
    full_width_container = st.container()

    with full_width_container:
        
        if explain_epic_clicked and epic_ids is not None:
            try:
                epic_ids = [int(id) for id in epic_ids.split(",")]

                epics = [api_router.get_epic_from_id(epic_id) for epic_id in epic_ids]
                results, display_string = api_router.explain_epics(
                    epics, 
                    start, 
                    end, 
                    code_red_days_after, 
                    verbose=True
                )
                st.session_state.epic_explanation_display = display_string
                st.session_state.epic_explanation_results = results
            except ValueError:
                st.error("Invalid input.")
        
        if st.session_state.epic_explanation_display and st.session_state.epic_explanation_results:
            display_utils.display_epics_results(
                st.session_state.epic_explanation_display, 
                st.session_state.epic_explanation_results, 
                code_red_days_after, 
                start, 
                end
            )


if 'author_prs_data' not in st.session_state:
    st.session_state.author_prs_data = None
if 'author_prs_visualization' not in st.session_state:
    st.session_state.author_prs_visualization = None


with author_prs:

    col1, col2, col3, _ = st.columns([1, 1, 1, 1])

    with col1:
        repo = st.selectbox("Repo", ["api", "runners", "wizard", "galileo-sdk", "ui", "deploy", "experimental-cluster"])
    with col2:
        authors = github_api.get_all_users_for_repo(repo_name=repo)
        authors = [author for author in authors if author != "dependabot[bot]"]
        author = st.selectbox("Author", authors)
    with col3:
        st.write(" ")
        st.write(" ")
        show_prs_clicked = st.button("Show PRs", type="primary")


    full_width_container = st.container()
    n = (datetime.strptime(end, "%d %b %Y") - datetime.strptime(start, "%d %b %Y")).days

    with full_width_container:
        if show_prs_clicked:
            
            prs = github_api.get_prs_for_repo(repo_name=repo, start=start, end=end, author=author)

            st.session_state.author_prs_data = prs
            st.session_state.author_prs_visualization = github_api.visualize_activity(prs, author, n_days=n)

        if st.session_state.author_prs_data:
            st.write(f"{repo} PRs by {author}, between {end} and {n} days prior") 
            if st.session_state.author_prs_visualization is not None:
                st.plotly_chart(st.session_state.author_prs_visualization)
            github_api.display_prs(st.session_state.author_prs_data)


if 'repo_prs_data' not in st.session_state:
    st.session_state.repo_prs_data = None
if 'repo_prs_activity_visualization' not in st.session_state:
    st.session_state.repo_prs_activity_visualization = None
if 'repo_prs_contributions_visualization' not in st.session_state:
    st.session_state.repo_prs_contributions_visualization = None
if 'repo_name' not in st.session_state:
    st.session_state.repo_name = None

with repo_prs:

    col1, col2, _, _ = st.columns([1, 1, 1, 1])

    with col1:
        repo = st.selectbox("PR Repo", ["api", "runners", "wizard", "galileo-sdk", "ui"])
    with col2:
        st.write(" ")
        st.write(" ")
        show_prs_clicked = st.button("Show Repo Analytics", type="primary")

    full_width_container = st.container()

    with full_width_container:
        if show_prs_clicked:
            n = (datetime.strptime(end, "%d %b %Y") - datetime.strptime(start, "%d %b %Y")).days
            prs = github_api.get_prs_for_repo(repo_name=repo, start=start, end=end)

            st.session_state.repo_prs_data = prs
            st.session_state.repo_name = repo
            st.session_state.repo_prs_activity_visualization = github_api.visualize_activity(prs, repo, n_days=n)
            st.session_state.repo_prs_contributions_visualization = github_api.visualize_contributions(prs, repo, n_days=n)

        if st.session_state.repo_prs_data:
            st.write(f"Getting PRs for <b>{st.session_state.repo_name}</b> between <b>{end}</b> and <b>{n}</b> days prior.", unsafe_allow_html=True)
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.session_state.repo_prs_activity_visualization:
                    st.plotly_chart(st.session_state.repo_prs_activity_visualization)
            with col2:
                if st.session_state.repo_prs_contributions_visualization:
                    st.plotly_chart(st.session_state.repo_prs_contributions_visualization)
            github_api.display_prs(st.session_state.repo_prs_data)



if 'highlighted_text' not in st.session_state:
    st.session_state.highlighted_text = None


with highlighter:
    # st text area to take in text larger height
    text = st.text_area("Enter text to highlight", height=300)
    col1, col2, _, _, _ = st.columns([1, 1, 2, 2, 2])
    with col1:
        highlight_clicked = st.button("Highlight Text")
    with col2:
        clear_clicked = st.button("Clear Text")

    if clear_clicked:
        text = ""
        st.session_state.highlighted_text = None

    if highlight_clicked:
        from llm_utils import ask_openai

        def highlight_keywords(text: str):
            prompt = f"""
            Firstly, add a 1 line clear and concise summary/conclusion of the text at the top in an <h4> tag.
            Secondly, restate the text (below) following these instructions:
            1. Write in a telegraphic style - use gerund phrases, make it direct, omit articles where possible to keep it short.
            2. ONLY highlight the most important phrases that add to the meaning of the text. 
            3. Don't hightlight too many or too few phrases. Ensure at least 30% of the text is highlighted.
            4. It should be that if I only read the highlighted text, i would understand the main idea of the text.
            5. Add a span tag with #FFC0CB background and a BOLD tag to the highlighted phrases. 
            6. Keep the color of the text black.
            7. Return the answer in HTML.
            
            ---Start of text---
            {text}
            ---End of text---
            """
            return ask_openai(prompt)
        st.session_state.highlighted_text = highlight_keywords(text)

    if st.session_state.highlighted_text:
        st.markdown(st.session_state.highlighted_text, unsafe_allow_html=True)

with google_docs:
    service, creds = authenticate()

    doc_types = ["docs", "sheets", "slides"]
    col1, col2, _, _ = st.columns([1, 1, 2, 2])
    with col1:
        doc_type = st.selectbox("Type", doc_types)
    with col2:
        st.write(" ")
        st.write(" ")
        list_docs_button = st.button("List Docs", key="list_docs_button", type="primary")

    full_width_container = st.container()

    with full_width_container:
        if list_docs_button:
            if doc_type == "docs":
                list_docs(service, number_of_docs=10, type="docs", summarize=True)
            elif doc_type == "sheets":
                list_docs(service, number_of_docs=10, type="sheets", summarize=True)
            elif doc_type == "slides":
                list_docs(service, number_of_docs=10, type="slides", summarize=True)
            else:
                st.error("Invalid document type")