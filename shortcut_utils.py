import requests
from datetime import datetime
from typing import List, Dict, Any
from tqdm import tqdm
from IPython.display import display, HTML
from collections import defaultdict, Counter
import streamlit as st
import pandas as pd
from datetime import timedelta
from utils.common_utils import CODE_RED_DAYS_AFTER

PRODUCT_ROADMAP_OBJECTIVE = "Product Roadmap (2025)"
CUSTOMER_ISSUES_EPIC = "Customer Tickets: 2025H1"
PIOTR_EPIC = "LLM QA: 2025H1"
ON_CALL_EPIC = "On Call Issues: 2025H1" 
BACKEND_ENHANCEMENTS_EPIC = "Backend Enhancements: 2025H1"
UI_CORE_EPIC = "UI Core Application Improvements"

active_states = {'In Review', 'Merged to Main', 'In Development', 'Completed / In Prod'}
not_worked_on_states = {'Draft', 'Upcoming (Future Sprint)', 'Ready for Development (Current Sprint)'}
blocked_states = {'Eng Blocked'}

class DisplayUtils:

    def display_epics_results(self, display_string, results, code_red_days_after, start_date, end_date):
        st.markdown("<h3>Summary</h3>", unsafe_allow_html=True)
        st.markdown(f"<div>Between <b>{start_date}</b> and <b>{end_date}</b> there were:</div>", unsafe_allow_html=True)
        def html_display(label, value, postfix=""):
            st.markdown(f"<li><b>{label}:</b> <span style='color: #FF69B4;'>{value}{postfix}</span></li>", unsafe_allow_html=True)

        total_stories = results['num_stories']
        completed = results['completed']
        not_completed = results['not_completed']
        num_stories_code_red = results['num_stories_code_red']
        days_for_completion = results['days_for_completion_cumulative']
        days_since_filed = results['days_since_filed_cumulative']
        best_epic = results['best_epic']
        worst_epic = results['worst_epic']

        st.markdown("<ul>", unsafe_allow_html=True)
        html_display("Tickets filed", total_stories)
        if total_stories > 0:
            html_display("Tickets Completed", f"{completed} ({completed / total_stories * 100:.2f}%)")
        else:
            html_display("No tickets completed", "")
        if not_completed > 0:
            html_display("Avg backlog (time ticket sits without being worked on)", f"{days_since_filed / not_completed:.2f}", " days")
        else:
            html_display("No backlog. All tickets completed", "")

        if completed > 0:
            html_display("Avg time to complete 1 ticket", f"{days_for_completion / completed:.2f}", " days")
        else:
            html_display("No tickets completed", "")

        

        html_display("Not yet completed", not_completed)
        html_display(f"Tickets that took over {code_red_days_after} days", num_stories_code_red)

        html_display("Best epic", best_epic)
        html_display("Worst epic", worst_epic)
        
        st.markdown("</ul><hr/>", unsafe_allow_html=True)
        st.markdown(display_string, unsafe_allow_html=True)
        


    def display_single_epic_results(
        self,
        display_string,
        total_stories,
        completed_count,
        not_yet_completed_count,
        code_red,
        cumulative_days_for_completion,
        cumulative_days_since_filed,
        code_red_days_after,
    ):
        def html_display(label, value, postfix=""):
            display(HTML(f"<b>{label}:</b> <span style='color: #FF69B4;'>{value}{postfix}</span>"))

        if total_stories == 0:
            html_display("Total stories", total_stories)
            return

        html_display("Total stories", total_stories)
        html_display("Not yet completed", not_yet_completed_count)
        html_display("Completed", f"{completed_count} ({completed_count / total_stories * 100:.2f}%)")
        html_display(f"Tickets that took over {code_red_days_after} days", code_red)

        if completed_count > 0:
            html_display("Avg time to complete 1 ticket", f"{cumulative_days_for_completion / completed_count:.2f}", " days")
        else:
            html_display("No tickets completed", "")

        if not_yet_completed_count > 0:
            html_display("Avg backlog (time ticket sits without being worked on)", f"{cumulative_days_since_filed / not_yet_completed_count:.2f}", " days")
        else:
            html_display("No backlog", "")

        display(HTML(display_string))

class ShortcutGateway:
    def __init__(self):
        self._base_url = 'https://api.app.shortcut.com/api'
        self._token = 'c8bcc9eb-0588-439b-9d35-3f8a75d3deee'
        # self.headers = {
        #     "Authorization": f"Bearer {self._token}",
        #     "Content-Type": "application/json",
        # }
        self.session = requests.Session()
        self._iteration_map = dict()

    def make_api_call(self, url: str, additional_params: Dict[str, Any] = {}) -> Any:
        try:
            response = self.session.get(
                f"{url}?token={self._token}",
                timeout=10, 
                params=additional_params,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API call failed: {e}")
            return None

    # @lru_cache(maxsize=1)  # Cache the result of iterations for quick reuse
    def _load_iterations(self) -> None:
        all_iterations = self.make_api_call(f"{self._base_url}/v3/iterations")
        if all_iterations:
            self._iteration_map = {iteration['name']: iteration for iteration in all_iterations}

    # @lru_cache(maxsize=1)  # Cache workflows to avoid repeated API calls
    def _create_workflows_map(self) -> Dict[int, str]:
        workflows_dict: Dict[int, str] = {}
        workflows = self.make_api_call(f"{self._base_url}/v3/workflows")
        if workflows:
            for workflow in workflows:
                for state in workflow['states']:
                    workflows_dict[state['id']] = state['name']
        return workflows_dict

    def extract_keywords(self, stories):
        keywords = set()
        import re
        for story in stories:
            matches = re.findall(r'\[(.*?)\]', story['name'])
            for match in matches:
                keywords.update(match.split(" "))
        return list(keywords)

    def get_owner_id(self, person_name):
        owner_info = self.make_api_call(f"{self._base_url}/v3/members")
        for owner in owner_info:
            if owner['profile']['name'] == person_name:
                return owner['id']
        return None

    def get_tickets_closed_assigned(self, person_name, start_date_str, end_date_str):
        owner_id = self.get_owner_id(person_name)
        stories = self.get_stories_for_owner(owner_id)
        date_map = {}
        start_date = datetime.strptime(start_date_str, "%d %b %Y")
        end_date = datetime.strptime(end_date_str, "%d %b %Y")

        from datetime import timedelta

        for date in range((end_date - start_date).days + 1):
            current_date = start_date + timedelta(days=date)
            stories_assigned_to_person = [story for story in stories if datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ') == current_date]
            stories_completed_by_person = [story for story in stories_assigned_to_person if story['completed']]

            current_date_str = current_date.strftime("%d %b %Y")
            date_map[current_date_str] = (len(stories_assigned_to_person), len(stories_completed_by_person))
        return date_map

    def get_top_owners_for_epic(self, epic_id: int, start_date: datetime=None, end_date: datetime=None) -> List[str]:
        stories = self.get_stories_for_epic(epic_id)
        if start_date is not None and end_date is not None:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            stories = [story for story in stories if start_datetime <= datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ') <= end_datetime]
        completed_stories = [story for story in stories if story['completed']]
        incomplete_stories = [story for story in stories if not story['completed']]
        owners_of_completed_stories = [story['owner_ids'] for story in completed_stories]
        owners_of_incomplete_stories = [story['owner_ids'] for story in incomplete_stories]
        owners_1 = [owner for sublist in owners_of_completed_stories for owner in sublist]
        owners_2 = [owner for sublist in owners_of_incomplete_stories for owner in sublist]
        completed_owner_names = [self.get_owner_name(owner_id) for owner_id in owners_1]
        completed_owner_counts = Counter(completed_owner_names)
        incomplete_owner_names = [self.get_owner_name(owner_id) for owner_id in owners_2]
        incomplete_owner_counts = Counter(incomplete_owner_names)
        all_owners = set(completed_owner_counts.keys()).union(incomplete_owner_counts.keys())
        merged_counts = {
            name: (completed_owner_counts.get(name, 0), incomplete_owner_counts.get(name, 0))
            for name in all_owners
        }
        sorted_counts = sorted(merged_counts.items(), key=lambda x: x[1][0], reverse=True)
        return [
            f"{name} (<span style='color: #00FF00;'>{completed_count}</span>, <span style='color: #FF0000;'>{incomplete_count}</span>)"
            for name, (completed_count, incomplete_count) in sorted_counts
        ]

    def get_workflow_name(self, workflow_state_id: int) -> str:
        workflows_dict = self._create_workflows_map()
        return workflows_dict.get(workflow_state_id, 'Unknown')

    def get_owner_name(self, owner_id: str) -> str:
        url = f"{self._base_url}/v3/members/{owner_id}"
        owner_info = self.make_api_call(url)
        return owner_info.get('profile', {}).get('name', 'Unknown')

    def get_iteration(self, iteration_name: str) -> Dict[str, Any]:
        self._load_iterations()  # Ensure the cache is populated
        return self._iteration_map.get(iteration_name)

    def get_all_objectives(self):
        url = f"{self._base_url}/v3/objectives"
        objectives = self.make_api_call(url)
        objective_name_to_id_map = {}
        for objective in objectives:
            objective_name_to_id_map[objective['name']] = objective['id']
        return objective_name_to_id_map

    def get_objective_from_id(self, objective_id: int) -> str:
        objective_url = f"{self._base_url}/v3/objectives/{objective_id}"
        objective_info = self.make_api_call(objective_url)
        return objective_info

    def get_epic_from_id(self, epic_id: int) -> str:
        epic_url = f"{self._base_url}/v3/epics/{epic_id}"
        epic_info = self.make_api_call(epic_url)
        return epic_info

    def get_objective_for_epic(self, epic_id: int) -> str:
        if epic_id is None:
            return "No Epic"
        epic_url = f"{self._base_url}/v3/epics/{epic_id}"
        epic_info = self.make_api_call(epic_url)
        if not epic_info:
            return "No Epic"

        objective_id = epic_info.get('milestone_id')
        if not objective_id:
            return "No Objective Associated"

        objective_url = f"{self._base_url}/v3/objectives/{objective_id}"
        objective_info = self.make_api_call(objective_url)
        return objective_info.get('name', 'Unknown Objective')

    def get_owner_name_from_id(self, owner_id: int) -> str:
        owner_url = f"{self._base_url}/v3/members/{owner_id}"
        owner_info = self.make_api_call(owner_url)
        return owner_info.get('profile', {}).get('name', 'Unknown')

    def get_objective_for_story(self, story_id: int) -> str:
        story_url = f"{self._base_url}/v3/stories/{story_id}"
        story_info = self.make_api_call(story_url)
        epic_id = story_info.get('epic_id')
        return self.get_objective_for_epic(epic_id) if epic_id else "Unknown Epic"

    def get_epic_for_story(self, story_id: int) -> str:
        story_url = f"{self._base_url}/v3/stories/{story_id}"
        story_info = self.make_api_call(story_url)
        epic_id = story_info.get('epic_id')
        if not epic_id:
            return "Unknown Epic"
        epic_url = f"{self._base_url}/v3/epics/{epic_id}"
        epic_info = self.make_api_call(epic_url)
        return epic_info.get('name', 'Unknown Epic')

    def get_stories_for_epic(self, epic_id: int) -> List[Dict[str, Any]]:
        url = f"{self._base_url}/v3/epics/{epic_id}/stories"
        return self.make_api_call(url) or []

    def get_stories_for_iteration(self, iteration_id: int) -> List[Dict[str, Any]]:
        url = f"{self._base_url}/v3/iterations/{iteration_id}/stories"
        return self.make_api_call(url) or []

    def get_stories_between_dates(self, start_date, end_date):
        start_date_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')

        main_objectives = [23491, 13782, 18604]
        stories = []

        progress_bar = st.progress(0)

        for i, objective_id in tqdm(enumerate(main_objectives)):
            progress_bar.progress(i / len(main_objectives))
            epics = self.get_epics_for_objective(objective_id)
            for epic in epics:
                stories_for_epic = self.get_stories_for_epic(epic['id'])
                filtered_stories = [
                    story for story in stories_for_epic 
                    if 'created_at' in story and start_date_dt <= datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ') <= end_date_dt
                ]
                stories.extend(filtered_stories)
        
        progress_bar.progress(100)

        return stories

    def get_stories(
        self,
        iteration_name: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        iteration = self.get_iteration(iteration_name)
        if not iteration:
            print(f"Iteration with name '{iteration_name}' not found.")
            return []

        iteration_id = iteration['id']
        start_date_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')

        stories = self.get_stories_for_iteration(iteration_id)
        filtered_stories = [
            story for story in stories
            if 'created_at' in story and start_date_dt <= datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ') <= end_date_dt
        ]
        filtered_stories = [
            story for story in filtered_stories
            if self.get_workflow_name(story['workflow_state_id']) != 'Duplicate / Unneeded'
        ]

        return sorted(
            filtered_stories, 
            key=lambda story: datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ'),
            reverse=True
        )

    def get_all_owners(self):
        owner_url = f"{self._base_url}/v3/members"
        owner_info = self.make_api_call(owner_url)
        owner_names = [owner['profile']['name'] for owner in owner_info if owner['disabled'] == False]
        owner_names.sort()
        return owner_names

    def get_epic_name(self, epic_id: int) -> str:
        epic_url = f"{self._base_url}/v3/epics/{epic_id}"
        epic_info = self.make_api_call(epic_url)
        return epic_info.get('name', 'Unknown Epic')

    def get_epics_for_objective(self, objective_id: int, exclude_completed: bool=False) -> List[Dict[str, Any]]:
        url = f"{self._base_url}/v3/objectives/{objective_id}/epics"
        epics = self.make_api_call(url) or []
        if exclude_completed:
            epics = [epic for epic in epics if not epic['completed']]
        return epics

    def get_2week_trailing_backlog(self, epic_id: int, start_date: datetime, end_date: datetime) -> list:
        from datetime import timedelta
        epic = self.get_epic_from_id(epic_id)
        tuples = []
        for i in range((end_date - start_date).days):
            current_date = start_date + timedelta(days=i)
            s = (current_date - timedelta(days=14))
            e = current_date
            _,_,_,cum_days_filed,_,_,incomplete_count,_,_ = self.explain_epic(epic['id'], s, e)
            backlog_rate = 0
            if incomplete_count > 0:
                backlog_rate = cum_days_filed / incomplete_count
            tuples.append((current_date, backlog_rate))
        return tuples

    def explain_epic(
            self, 
            epic_id: int, 
            start_date: datetime, 
            end_date: datetime=datetime.now(), 
            code_red_days_after: int=10):

        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        epic_name = self.get_epic_name(epic_id)
        stories = self.get_stories_for_epic(epic_id)

        stories_in_date_range = [story for story in stories if datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ') >= datetime.strptime(start_date_str, '%Y-%m-%d') and datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ') <= datetime.strptime(end_date_str, '%Y-%m-%d')]
        total_stories_before_date = len(stories_in_date_range)

        if total_stories_before_date == 0:
            return "No stories", 0, 0, 0, 0, 0, 0, {}, {}

        num_stories_code_red = 0
        not_yet_completed_count = 0
        cumulative_days_for_completion = 0
        completed_count = 0
        cumulative_days_filed_since = 0

        display_string = f"<h3>Epic: {epic_name}</h3>"

        c1_map = defaultdict(int) # map to store total tickets per customer
        c2_map = defaultdict(int) # map to store completed tickets per customer

        for i, story in enumerate(stories_in_date_range):

            simplified_title = story['name']

            created_at = datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ').strftime('%d %b %y')

            num_days_to_complete = None

            completed_at = story.get('completed_at')
            completed_or_not = "Completed" if story['completed'] else "Not yet completed"

            labels = story.get('labels', [])
            label_names = [label['name'] for label in labels]
            if story['completed']:
                completed_count += 1
                completed_at = datetime.strptime(completed_at, '%Y-%m-%dT%H:%M:%SZ').strftime('%d %b %y')
                x = f"took {num_days_to_complete} day(s) to complete from filing"
                for l in label_names:
                    if l.startswith('customer/'):
                        label_name = l.replace('customer/', '')
                    else:
                        label_name = l
                    c2_map[label_name] += 1
            else:
                days_filed_since = (datetime.now() - datetime.strptime(created_at, '%d %b %y')).days
                x = f"been {days_filed_since} day(s) since filing"
                completed_at = "N/A"
                cumulative_days_filed_since += days_filed_since
                not_yet_completed_count += 1
            for l in label_names:
                if l.startswith('customer/'):
                    customer_name = l.replace('customer/', '')
                else:
                    customer_name = l
                c1_map[customer_name] += 1

            if completed_at != "N/A":
                num_days_to_complete = (datetime.strptime(completed_at, '%d %b %y') - datetime.strptime(created_at, '%d %b %y')).days
                cumulative_days_for_completion += num_days_to_complete

            color = 'red' if num_days_to_complete and num_days_to_complete > code_red_days_after else 'white'
            num_stories_code_red += 1 if color == 'red' else 0

            completed_or_not = f"<span style='color: #FF69B4;'>{completed_or_not}</span>" if completed_or_not == "Not yet completed" else completed_or_not
            display_string = f"<span style='color: {color};'>{i+1}. <a href='https://app.shortcut.com/galileo/story/{story['id']}'>{simplified_title}</a> ({story['story_type']}) -- {x} ({completed_or_not})</span>"

        return display_string, total_stories_before_date, completed_count, not_yet_completed_count, num_stories_code_red, cumulative_days_for_completion, cumulative_days_filed_since, c1_map, c2_map

    def explain_epics_from_objective(
            self, 
            objective_id: int, 
            start_date: datetime, 
            end_date: datetime=datetime.now(), 
            code_red_days_after: int=10, 
            verbose: bool=False
    ):
        epics: List[Dict[str, Any]] = self.get_epics_for_objective(objective_id, exclude_completed=True)
        return self.explain_epics(epics, start_date, end_date, code_red_days_after, verbose)

    def get_first_story_date(self, epic_id: int) -> str:
        stories = self.get_stories_for_epic(epic_id)
        # ignore the ones where story['created_at'] is None
        stories = [story for story in stories if story['created_at'] is not None]
        # throws min iterable argument is empty
        if len(stories) == 0:
            return datetime.now()
        return min([datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ') for story in stories])

    def get_story_tags(self, story_id: int) -> List[str]:
        url = f"{self._base_url}/v3/stories/{story_id}/tags"
        tags = self.make_api_call(url)
        return tags

    def get_completion_rate_for_epic(self, start, end, epic):
        dates = [start + timedelta(days=i) for i in range((end - start).days)]
        tuples = []
        for date in dates:
            insights, table, c1m, c2m = self.explain_epics(
                epics=[epic], 
                start_date=date,
                end_date=date + timedelta(days=1), 
                code_red_days_after=CODE_RED_DAYS_AFTER, 
                verbose=False,
                show_progress_bar=False
            )
            total_tickets = sum(c1m.values())
            completed_tickets = sum(c2m.values())
            tuples.append((date, total_tickets, completed_tickets))

        tuples.sort(key=lambda x: x[0], reverse=True)
        df = pd.DataFrame(tuples, columns=["Date", "Filed", "Completed"])
        df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y")
        df = df.sort_values("Date")

        df_melted = df.melt(id_vars=["Date"], var_name="Category", value_name="Count")
        return df_melted

    def get_backlog_rate_for_epic(self, start, end, epic_id):
        res = self.get_2week_trailing_backlog(epic_id=epic_id, start_date=start, end_date=end)
        df = pd.DataFrame(res, columns=["Date", "Backlog Rate"])
        df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y")
        df = df.sort_values("Date")
        return df

    def explain_epics(
            self,
            epics: List[Dict[str, Any]],
            start_date: datetime,
            end_date: datetime=datetime.now(),
            code_red_days_after: int=10,
            verbose: bool=False,
            show_progress_bar: bool=True
    ):
        epic_insights = {
            'num_stories': 0,
            'completed': 0,
            'not_completed': 0,
            'num_stories_code_red': 0,
            'days_for_completion_cumulative': 0,
            'days_since_filed_cumulative': 0,
            'best_epic': None,
            'worst_epic': None,
        }
        min_weighted_score = float('inf')
        max_weighted_score = float('-inf')
        epics_table = ""
        if verbose:
            epics_table = """
            <table style='width: 100%;'><tr>
                <th>Epic</th>
                <th>Started on</th>
                <th>% Done</th>
                <th>Total Stories</th>
                <th>Done</th>
                <th>Days to complete 1 ticket (since filing)</th>
                <th>Cum. backlog (days)</th>
                <th>Owners</th>
            </tr>
            """
        completion_percent = 0

        if show_progress_bar:
            progress_bar_x = st.progress(0)

        c1_map_epic_level = defaultdict(int)
        c2_map_epic_level = defaultdict(int)

        for i, epic in tqdm(enumerate(epics)):
            if show_progress_bar:
                progress_bar_x.progress(i/len(epics))

            first_story_date = self.get_first_story_date(epic['id'])

            first_story_date = first_story_date.strftime('%d %b %y')

            story_title, a, b, c, d, e, f, c1_map, c2_map = self.explain_epic(epic['id'], start_date, end_date, code_red_days_after)

            if story_title == "No stories":
                continue

            # loop through both maps and update the epic-level maps
            for l, c in c1_map.items():
                c1_map_epic_level[l] += c
            for l, c in c2_map.items():
                c2_map_epic_level[l] += c

            if a > 0:   
                completion_percent = b / a
                days_backlog = f
                if b > 0:
                    weighted_score = (completion_percent * 0.25) - ((e / b) * 0.25) - (days_backlog * 0.25)
                    if weighted_score > max_weighted_score:
                        max_weighted_score = weighted_score
                        epic_insights['best_epic'] = f"'{epic['name']}' ({completion_percent * 100:.2f}% complete) with {a} stories, <span style='color: #FF69B4;'>{e/b:.2f} days</span> to complete 1 ticket, {f} days of cumulative backlog."
                    if weighted_score < min_weighted_score:
                        min_weighted_score = weighted_score
                        epic_insights['worst_epic'] = f"'{epic['name']}' ({completion_percent * 100:.2f}% complete) with {a} stories, {e/b:.2f} days to complete 1 ticket, {f} days</span> of cumulative backlog."
                if verbose:
                    W = f"{completion_percent*100:.2f}%"
                    X = a
                    Y = f"{e/b:.2f}" if b > 0 else 'N/A'
                    Z = f"{f:.2f}" if f > 0 else 'N/A'
                    owners = self.get_top_owners_for_epic(epic['id'], start_date, end_date)

                    owner_strings = []
                    for owner in owners:
                        first_name = owner.split()[0]
                        counts = owner[owner.find('('):]
                        owner_strings.append(f"{first_name} {counts}")
                    owners = "<br>".join(owner_strings)

                    epics_table += f"<tr><td><a href='https://app.shortcut.com/galileo/epic/{epic['id']}'>{epic['name']}</a></td><td>{first_story_date}</td><td>{W}</td><td>{X}</td><td>{b}</td><td>{Y}</td><td>{Z}</td><td  style='font-size: 10px;'>{owners}</td></tr>"

            epic_insights['num_stories'] += a
            epic_insights['completed'] += b
            epic_insights['not_completed'] += c
            epic_insights['num_stories_code_red'] += d
            epic_insights['days_for_completion_cumulative'] += e
            epic_insights['days_since_filed_cumulative'] += f

        # make progress bar full 
        if show_progress_bar:
            progress_bar_x.progress(100)

        if verbose:
            epics_table += "</table>"
        
        return epic_insights, epics_table, c1_map_epic_level, c2_map_epic_level

class SprintUtils:
    def __init__(self, shortcut_gateway: ShortcutGateway):
        self.shortcut_gateway = shortcut_gateway

    def categorize(self, stories):
        data = []
        if len(stories) == 0:
            return

        for story in tqdm(stories):
            owner = "Unassigned"
            # if it's not assigned, use the requester
            if len(story['owner_ids']) > 0:
                owner = self.shortcut_gateway.get_owner_name(story['owner_ids'][0])
            story_type = story.get('story_type', 'Unknown')
            story_state = self.shortcut_gateway.get_workflow_name(story['workflow_state_id'])
            objective_name = self.shortcut_gateway.get_objective(story['id'])
            epic_name = self.shortcut_gateway.get_epic(story['id'])
            workstream = "Other Things"
            if objective_name == PRODUCT_ROADMAP_OBJECTIVE:
                workstream = "Roadmap"
            elif epic_name == CUSTOMER_ISSUES_EPIC:
                workstream = "Customer Issues"
            elif epic_name == PIOTR_EPIC:
                workstream = "Piotr"
            elif epic_name == ON_CALL_EPIC:
                workstream = "On Call"
            elif epic_name == BACKEND_ENHANCEMENTS_EPIC:
                workstream = "Backend Enhancements"
            elif epic_name == UI_CORE_EPIC:
                workstream = "UI Core"
            data.append((story['name'], owner, story_type, story_state, workstream))

        complete_states = {'In Review', 'Merged to Main', 'In Development', 'Completed / In Prod'}
        workstream_counts = defaultdict(lambda: {'total': 0, 'complete': 0})
        for _, owner, story_type, story_state, workstream in data:
            if not workstream:
                workstream = 'Unk'
            workstream_counts[workstream]['total'] += 1
            if story_state in complete_states:
                workstream_counts[workstream]['complete'] += 1
        table_rows = []
        for workstream, counts in sorted(workstream_counts.items(), key=lambda x: -x[1]['total']):
            table_rows.append(f"<tr><td>{counts['total']} {workstream}</td><td>{counts['complete']} active</td></tr>")
        workstream_table_html = f"""
        <table style="border-collapse: collapse; width: 20%; margin: 0 auto;">
            <thead>
                <tr>
                    <th>Workstream</th>
                    <th>Active</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
        """
        display(HTML(workstream_table_html))

    def analyze(self, stories, total_stories_in_timeframe, heading="Analysis", save_to_file=False, ignore_list=[], person=None):
        display(HTML(f"<h3>{heading}</h3>"))
        data = []
        style = """
            <style>
                table {
                    table-layout: auto;
                    width: 50%;
                }
                th, td {
                    padding: 10px 5px;
                    text-align: left;
                }
            </style>
        """

        story_table_html = style + """
        <table style='width:70%;'>
            <tr>
                <th>Filed on</th>
                <th>Type</th>
                <th>Belongs to</th>
                <th>Owner</th>
                <th>Status</th>
                <th>Story</th>
            </tr>
        """

        for story in tqdm(stories):
            # Get owner name
            owner = "Unassigned"
            if len(story['owner_ids']) != 0:
                owner = self.shortcut_gateway.get_owner(story['owner_ids'][0])
            if owner in ignore_list:
                continue
            # If person is not None, only show stories for that person
            if ((person is None) or (owner == person)):
                story_type = story.get('story_type', 'Unknown')
                story_state = self.shortcut_gateway.get_workflow_name(story['workflow_state_id'])
                
                objective = self.shortcut_gateway.get_objective(story['id'])
                epic = self.shortcut_gateway.get_epic(story['id'])

                workstream = "Other Things"
                if objective == PRODUCT_ROADMAP_OBJECTIVE:
                    workstream = "Roadmap"
                elif epic == CUSTOMER_ISSUES_EPIC:
                    workstream = "Customer Issues"
                elif epic == PIOTR_EPIC:
                    workstream = "Piotr"
                elif epic == ON_CALL_EPIC:
                    workstream = "On Call"
                elif epic == BACKEND_ENHANCEMENTS_EPIC:
                    workstream = "Backend Enhancements"
                elif epic == UI_CORE_EPIC:
                    workstream = "UI Core"

                data.append((story['id'], story['name'], owner, story_type, story_state, workstream))
                active_color = 'green' if story_type == 'feature' else 'red'

                story_table_html += f"""
                <tr>
                    <td>{datetime.strptime(story['created_at'], '%Y-%m-%dT%H:%M:%SZ').strftime('%d %b (%I:%M %p)')}</td>
                    <td style="color: {active_color};">{story_type}</td>
                    <td>{workstream}</td>
                    <td>{owner}</td>
                    <td>{story_state}</td>
                    <td><a href="https://app.shortcut.com/galileo/story/{story['id']}">{story['name'][:150]}...</a></td>
                </tr>
                """
        story_table_html += "</table>"

        # Save to file
        if save_to_file:
            with open('tickets.csv', 'w') as f:
                for d in data:
                    f.write(f"{d[1]} (https://app.shortcut.com/galileo/story/{d[0]}/)\n")

        # ANALYTICS
        # Categorize tickets into groups
        active_tickets = []
        not_worked_on_tickets = []
        blocked_tickets = []

        # Count tickets per owner
        owner_ticket_counts = defaultdict(lambda: {'active': 0, 'not_worked_on': 0, 'blocked': 0})

        # Iterate through each story in data and categorize it
        for story_id, story_name, owner, story_type, story_state, workstream in data:
            if story_state in active_states:
                active_tickets.append((story_name, owner, story_type, story_state))
                owner_ticket_counts[owner]['active'] += 1
            elif story_state in not_worked_on_states:
                not_worked_on_tickets.append((story_name, owner, story_type, story_state))
                owner_ticket_counts[owner]['not_worked_on'] += 1
            elif story_state in blocked_states:
                blocked_tickets.append((story_name, owner, story_type, story_state))
                owner_ticket_counts[owner]['blocked'] += 1

        story_count_table_html = f"""
            <table border="1" style="width: 20%;">
                <tr>
                <th>Owner</th>
                <th>{heading}</th>
                </tr>
            """

        # Iterate through the owner_ticket_counts to create rows with color coding
        for owner, counts in owner_ticket_counts.items():
            active_color = 'green' if counts['active'] > 0 else 'red'
            not_working_color = 'red' if counts['not_worked_on'] > 0 else 'green'
            blocked_color = 'red' if counts['blocked'] > 0 else 'green'

            # If counts of not_wokred_on or blocked are 0, don't show them
            if counts['not_worked_on'] == 0 and counts['blocked'] == 0:
                story_count_table_html += f"""
                <tr>
                    <td>{owner}</td>
                    <td style="color: {active_color};">{counts['active']}</td>
                </tr>
                """
            elif counts['active'] == 0:
                story_count_table_html += f"""
                <tr>
                    <td>{owner}</td>
                    <td style="color: {not_working_color};">{counts['not_worked_on']}</td>
                    <td style="color: {blocked_color};">{counts['blocked']}</td>
                </tr>
                """
        total_tickets_for_category = len(active_tickets) if "Active" in heading else len(not_worked_on_tickets) if "Inactive" in heading else len(blocked_tickets)

        story_count_table_html += f"""
        <tr>
                <td>Total</td>
                <td>{total_tickets_for_category}</td>
            </tr>
        """
        
        story_count_table_html += "</table>"
        total_tix = len(active_tickets) + len(not_worked_on_tickets) + len(blocked_tickets)
        print(f"{total_tix/total_stories_in_timeframe * 100:.2f}% of the {total_stories_in_timeframe} stories")

        # instead of displaying one below another, add a parent div and display them side by side
        display(HTML(f"""
        <div style="display: flex; align-items: flex-start; justify-content: space-between;">
            <div style="display: inline-block; margin-right: 150px;">
                {story_count_table_html}
            </div>
            <div style="display: inline-block;">
                {story_table_html}
            </div>
        </div>
        """))
