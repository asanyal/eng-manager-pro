from actions.actions import ActionInterface
import streamlit as st
from shortcut_utils import ShortcutGateway, SprintUtils, DisplayUtils
from utils.common_utils import CODE_RED_DAYS_AFTER
from datetime import datetime
from tqdm import tqdm
from collections import defaultdict


class ExplainAnObjective(ActionInterface):
    def __init__(self, 
                 shortcut_gateway: ShortcutGateway,
                 sprint_utils: SprintUtils,
                 display_utils: DisplayUtils
    ):
        self.shortcut_gateway = shortcut_gateway
        self.sprint_utils = sprint_utils
        self.display_utils = display_utils
        if "objective_display_string" not in st.session_state:
            st.session_state.objective_display_string = None
        if "objective_results" not in st.session_state:
            st.session_state.objective_results = None

    def do_action(self, start, end):
        start_str = start.strftime("%d %b %Y")
        end_str = end.strftime("%d %b %Y")
        objective_name_to_id_map = self.shortcut_gateway.get_all_objectives()
        objective_names = [objective_name for objective_name in objective_name_to_id_map.keys()]

        objective_dropdown = st.selectbox("Objective", objective_names)
        objective_id = objective_name_to_id_map[objective_dropdown]
        objective = self.shortcut_gateway.get_objective_from_id(objective_id)

        explain_clicked = st.button("Explain", type="primary")

        full_width_container = st.container()

        with full_width_container:
            if explain_clicked:
                results, display_string, _, _ = self.shortcut_gateway.explain_epics_from_objective(
                    objective_id,
                    start,
                    end,
                    CODE_RED_DAYS_AFTER,
                    verbose=True
                )
                st.session_state.objective_display_string = display_string
                st.session_state.objective_results = results

            if st.session_state.objective_display_string and st.session_state.objective_results:
                self.display_utils.display_epics_results(
                    st.session_state.objective_display_string, 
                    st.session_state.objective_results, 
                    CODE_RED_DAYS_AFTER, 
                    start_str, 
                    end_str
                )


class AnalyzeAPerson(ActionInterface):
    def __init__(self, 
                 shortcut_gateway: ShortcutGateway,
                 sprint_utils: SprintUtils,
                 display_utils: DisplayUtils
    ):
        self.shortcut_gateway = shortcut_gateway
        self.sprint_utils = sprint_utils
        self.display_utils = display_utils
        if 'person_analysis_html' not in st.session_state:
            st.session_state.person_analysis_html = None
        if 'person_analysis_table' not in st.session_state:
            st.session_state.person_analysis_table = None
        self.active_states = {'In Review', 'Merged to Main', 'In Development', 'Completed / In Prod'}
        self.not_worked_on_states = {'Draft', 'Upcoming (Future Sprint)', 'Ready for Development (Current Sprint)'}
        self.blocked_states = {'Eng Blocked'}


    def do_action(self, start, end):
        all_owners = self.shortcut_gateway.get_all_owners()
        owner = st.selectbox("Owner", all_owners)
        analyze_clicked = st.button("Analyze Person", type="primary")
        full_width_container = st.container()

        if analyze_clicked:

            with full_width_container:
                owner_id = self.shortcut_gateway.get_owner_id(owner)
                stories = self.shortcut_gateway.get_stories_between_dates(
                    start.strftime('%Y-%m-%d'),
                    end.strftime('%Y-%m-%d')
                )
                filtered_stories = [story for story in stories if len(story['owner_ids']) > 0 and story['owner_ids'][0] == owner_id]

                html_table = "<table style='width: 100%;'><tr><th>Story</th><th>Created on</th><th>Owner</th><th>Requester</th><th>Complete</th><th>Epic</th></tr>"

                total_owner_stories = 0
                completed_owner_stories = 0
                self_created_count = 0

                for story in tqdm(filtered_stories):
                    total_owner_stories += 1
                    is_complete = self.shortcut_gateway.get_workflow_name(story['workflow_state_id']) in self.active_states
                    if is_complete:
                        completed_owner_stories += 1
                    is_complete_str = "<span style='color: #00FF00;'>Yes</span>" if is_complete else "<span style='color: #FF0000;'>No</span>"
                    created_at_str = datetime.strptime(story['created_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")
                    requester_str = self.shortcut_gateway.get_owner_name(story['requested_by_id'])
                    self_created = story['requested_by_id'] == owner_id
                    if self_created:
                        self_created_count += 1
                    epic_str = self.shortcut_gateway.get_epic_name(story['epic_id'])
                    html_table += f"<tr><td><a href='{story['app_url']}'>{story['name']}</a></td><td>{created_at_str}</td><td>{owner}</td><td>{requester_str}</td><td>{is_complete_str}</td><td>{epic_str}</td></tr>"

                html_table += "</table>"
                
                div_html = "<ul>"
                
                if len(filtered_stories) > 0:
                    if completed_owner_stories > 0:
                        div_html += f"<li>{owner} completed <span style='color: #FF69B4;'>{completed_owner_stories}</span> out of <span style='color: #FF69B4;'>{total_owner_stories}</span> stories from {start} to {end}.</li>"
                        div_html += f"<li>That's a <u>completion rate</u> of <span style='color: #FF69B4;'>{completed_owner_stories / total_owner_stories * 100:.2f}%</span>.</li>"

                    keywords = self.shortcut_gateway.extract_keywords(filtered_stories)
                    div_html += f"<li>They solved problems for: <span style='color: #FF69B4;'>{', '.join(keywords)}</span></li>"
                    div_html += f"<li><span style='color: #FF69B4;'>{(len(filtered_stories) - self_created_count)/len(filtered_stories) *100:.2f}%</span> of these stories were created by others!</li>"

                div_html += "</ul>"

                st.session_state.person_analysis_html = div_html
                st.session_state.person_analysis_table = html_table

        if st.session_state.person_analysis_html and st.session_state.person_analysis_table:
            st.markdown(st.session_state.person_analysis_html, unsafe_allow_html=True)
            st.markdown(st.session_state.person_analysis_table, unsafe_allow_html=True)

class ExplainEpics(ActionInterface):
    
    def __init__(self, 
                 shortcut_gateway: ShortcutGateway,
                 display_utils: DisplayUtils
    ):
        self.shortcut_gateway = shortcut_gateway
        self.display_utils = display_utils
        if 'epic_explanation_display' not in st.session_state:
            st.session_state.epic_explanation_display = None
        if 'epic_explanation_results' not in st.session_state:
            st.session_state.epic_explanation_results = None
        if 'c1_map' not in st.session_state:
            st.session_state.c1_map = defaultdict(int)
        if 'c2_map' not in st.session_state:
            st.session_state.c2_map = defaultdict(int)

    def do_action(self, start: datetime, end: datetime):
        epic_ids = st.text_input("Comma separated Epic IDs e.g. 21023, 21024")
        explain_epic_clicked = st.button("Explain Epics", type="primary")

        full_width_container = st.container()

        with full_width_container:
            
            if explain_epic_clicked and epic_ids is not None:
                try:

                    epic_ids = [int(id) for id in epic_ids.split(",")]

                    epics = [self.shortcut_gateway.get_epic_from_id(epic_id) for epic_id in epic_ids]

                    results, display_string, c1_map, c2_map = self.shortcut_gateway.explain_epics(
                        epics, 
                        start, 
                        end, 
                        CODE_RED_DAYS_AFTER, 
                        verbose=True
                    )
                    st.session_state.epic_explanation_display = display_string
                    st.session_state.epic_explanation_results = results
                    st.session_state.c1_map = c1_map
                    st.session_state.c2_map = c2_map
                except ValueError:
                    st.error("Invalid input.")
            
            if st.session_state.epic_explanation_display and st.session_state.epic_explanation_results:
                self.display_utils.display_epics_results(
                    st.session_state.epic_explanation_display, 
                    st.session_state.epic_explanation_results, 
                    CODE_RED_DAYS_AFTER, 
                    start, 
                    end
                )
            if st.session_state.c1_map and st.session_state.c2_map:
                completed_stories = sum(st.session_state.c2_map.values())
                total_stories = sum(st.session_state.c1_map.values())
                customer_labels = list(st.session_state.c1_map.keys())

                if len(customer_labels) == 1 and customer_labels[0] == None:
                    pass
                else:
                    st.markdown(f"<h3>Labels</h3>", unsafe_allow_html=True)

                    # ignore the None key
                    c1_map_without_none = {k: v for k, v in st.session_state.c1_map.items() if k is not None}
                    c2_map_without_none = {k: v for k, v in st.session_state.c2_map.items() if k is not None}

                    completed_stories = sum(c2_map_without_none.values())
                    total_stories = sum(c1_map_without_none.values())

                    completion_rate = completed_stories / total_stories * 100

                    st.markdown(f"Completed <b>{completed_stories}</b> out of <b>{total_stories}</b> labeled tickets between <b>{start}</b> and <b>{end}</b>. That's a <u>completion rate of <b>{completion_rate:.2f}%</b></u>.", unsafe_allow_html=True)

                    completed_column, total_column = st.columns([1, 1])
                    with completed_column:
                        st.markdown(f"<b>Dates</b>: {start} - {end}", unsafe_allow_html=True)
                        st.markdown(f"<span> Total Tickets: {sum(st.session_state.c2_map.values())}</span>", unsafe_allow_html=True)
                        st.bar_chart(st.session_state.c2_map, color="#00FF00", height=300)
                    with total_column:
                        st.markdown(f"<b>Total tickets between {start} and {end}</b>", unsafe_allow_html=True)
                        st.markdown(f"<span> Total Tickets: {sum(st.session_state.c1_map.values())}</span>", unsafe_allow_html=True)
                        st.bar_chart(st.session_state.c1_map, color="#9c0000", height=300)
