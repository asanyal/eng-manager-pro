# Github API
import requests
import streamlit as st
import json
from datetime import datetime, timedelta
import warnings
import pandas as pd
import plotly.express as px
from urllib3.exceptions import NotOpenSSLWarning

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

class GithubAPI:
    def __init__(self, token):
        self.token = token
        self.user = "rungalileo"
        self.root_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.all_repos = [
            "api",
            "galileo-sdk", 
            "runners",
            "wizard", 
            "ui",
            # "comet", 
            "docs-mintlify", 
            # "feature-flags", 
            "experimental-cluster", 
            "deploy", 
            # "protect",
            # "nttgn-milestone-2", 
            "website", 
        ] 
        self.user_skip_list = ['vercel[bot]', 'dependabot[bot]', 'github-actions[bot]', 'sentry-io[bot]', 'codecov[bot]', 'shortcut-integration[bot]', 'galileo-automation']

    def _get_recent_activity(self, repo_name:str):
        url = f"{self.root_url}/repos/{self.user}/{repo_name}/events?per_page=100&page=1"
        response = requests.get(url, headers=self.headers)
        print(f"Headers: {self.headers}")
        return response.json()

    def get_user_activity(self, last_n_hours: int = 24) -> dict:
        user_activity = {}
        for repo in self.all_repos:
            events = self._get_recent_activity(repo_name=repo)
            events = [event for event in events if datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ') > (datetime.now() - timedelta(hours=last_n_hours+12)) and event['actor']['login'] not in self.user_skip_list]

            events = sorted(events, key=lambda x: x['created_at'], reverse=True)
            for event in events:
                activity = ""
                user = event['actor']['login'] # this is AnkushMalekar
                event_type = event['type']

                if event_type == 'PullRequestEvent' and 'payload' in event and 'pull_request' in event['payload']:
                    print("PullRequestEvent")
                    activity = ". ".join(f"Opened this PR: {event['payload']['pull_request']['title']}")

                elif event_type == 'PullRequestReviewEvent' and 'payload' in event and 'pull_request' in event['payload']:
                    print("PullRequestReviewEvent")
                    if 'payload' in event and 'pull_request' in event['payload']:
                        activity = ". ".join(f"Reviewed this PR: {event['payload']['pull_request']['title']}")

                elif event_type == 'PushEvent' and 'payload' in event and 'commits' in event['payload']:
                    print("PushEvent")
                    # concatenate all the commit messages
                    activity = ". ".join([f"Pushed a commit: {commit['message']}" for commit in event['payload']['commits']])

                elif event_type == 'IssueCommentEvent':
                    print("IssueCommentEvent")
                    issue_title = None
                    comment_body = None
                    if 'payload' in event and 'issue' in event['payload'] and 'comment' in event['payload']['issue']:
                        issue_title = event['payload']['issue']['title']
                    if 'payload' in event and 'issue' in event['payload'] and 'comment' in event['payload']['issue']:
                        comment_body = event['payload']['issue']['comment']['body']
                    if issue_title and comment_body:
                        this_activity = f'Commented on the issue "{issue_title}" - Comment: "{comment_body}"'
                        activity = '. '.join(this_activity)

                if user is not None and activity is not None:
                    activity = f"{activity}. "
                    if user not in user_activity:
                        user_activity[user] = ""
                    user_activity[user] += activity

        user_activity_html = f"<table style='border-collapse: collapse; width: 50%;'><tr><th>User</th><th>Activity</th></tr>"
        from llm_utils import ask_openai

        for user, activity in user_activity.items():
            activity = activity.replace("\n", " ").replace("\r", " ").replace("\t", " ")
            activity = activity.strip()
            instruction = f"""
            You're an expert softare engineer.
            Return a short and concise summary (ideally 1-2 sentences) of the following github activity.
            -- Start of activity --
            {activity}
            -- End of activity-- 
            Instructions:
            1. Return the summary in plain text.
            2. Only add a span with pink background color to github action verbs - pushed, reviewed, opened, commented.
            3. Write in a telegraphic style - use gerund phrases, make it direct, omit articles where possible to keep it short.
            4. Return empty if there is no activity.
            """
            user_activity_html += f"<tr><td>{user}</td><td>{ask_openai(instruction)}</td></tr>"
        user_activity_html += "</table>"

        return user_activity_html


    def get_feed(self, last_n_hours: int = 24) -> list[dict]:
        feed_strings = []
        feed_progress = st.progress(0)
        repo_progress_md = st.markdown("")

        # write a function that takes in last_n_hours, calculates end date and start date, end date is datetime.now() and start date is end date - timedelta(hours=last_n_hours+12)
        def get_start_and_end_dates(last_n_hours: int):
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=last_n_hours+12)
            start_date = start_date.strftime("%b %-d")
            end_date = end_date.strftime("%b %-d")
            if end_date == start_date:
                return start_date, None
            return start_date, end_date

        start_date, end_date = get_start_and_end_dates(last_n_hours)

        if end_date is None:
            st.markdown(f"<h4>Events on {start_date}</h4>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h4>Events from {start_date} to {end_date}</h4>", unsafe_allow_html=True)
        repo_events_count = {}

        for i, repo in enumerate(self.all_repos):
            feed_progress.progress(i / len(self.all_repos))
            repo_progress_md.markdown(f"Processing <b>{repo}</b>...", unsafe_allow_html=True)
            events = self._get_recent_activity(repo_name=repo)

            for event in events:
                print(f"Event type: {event['type']} at {datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ').strftime("%-d %b (%I:%M %p)")} by {event['actor']['login']}")
                if 'payload' in event and 'pull_request' in event['payload']:
                    print(f"Pull request title: {event['payload']['pull_request']['title']}")

            events = [event for event in events if datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ') > datetime.now() - timedelta(hours=last_n_hours+12) and event['actor']['login'] not in self.user_skip_list]

            repo_events_count[repo] = len(events)

            for event in events:
                event_type = event['type']
                user = event['actor']['login']
                repo = event['repo']['name']
                event_time = f"<span style='color: #FF69B4;'>[{datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ').strftime("%-d %b (%I:%M %p)")}]</span>"
                repo_name = f"<span style='color: #7FFFD4;'>[{repo.split('/')[-1]}]</span>"

                if event_type == 'PullRequestEvent' or event_type == 'PullRequestReviewEvent':
                    author = event['payload']['pull_request']['user']['login']
                elif event_type == 'IssuesEvent' or event_type == 'IssueCommentEvent':
                    author = event['payload']['issue']['user']['login']
                elif event_type == 'PushEvent' and 'payload' in event and 'commits' in event['payload'] and len(event['payload']['commits']) > 0 and 'author' in event['payload']['commits'][0]:
                    author = event['payload']['commits'][0]['author']['name']
                else:
                    author = None

                if event_type == 'PullRequestEvent':
                    action = event['payload']['action']
                    pr = event['payload']['pull_request']['url'].replace("api.", "").replace("/repos", "").replace("/pulls", "/pull")
                    feed_strings.append(f"{event_time}{repo_name} <b>{user}</b> {action} <a href='{pr}'>PR</a> on <b>{repo}</b>")
                elif event_type == 'PushEvent':
                    feed_strings.append(f"{event_time}{repo_name} <b>{user}</b> pushed a commit to <b>{repo}</b>")
                elif event_type == 'IssuesEvent':
                    feed_strings.append(f"{event_time}{repo_name} <b>{user}</b> {action} an issue on <b>{repo}</b>")
                elif event_type == 'IssueCommentEvent':
                    pr = event['payload']['issue']['url'].replace("api.", "").replace("/repos", "")
                    if author:
                        feed_strings.append(f"{event_time}{repo_name} <b>{user}</b> commented on <b>{author}'s</b> <a href='{pr}'>PR</a>")
                    else:
                        feed_strings.append(f"{event_time}{repo_name} <b>{user}</b> commented on an issue on <b>{repo}</b>")
                elif event_type == 'PullRequestReviewEvent':
                    pr = event['payload']['pull_request']['url'].replace("api.", "").replace("/repos", "").replace("/pulls", "/pull")
                    if author:
                        feed_strings.append(f"{event_time}{repo_name} <b>{user}</b> reviewed <b>{author}'s</b> <a href='{pr}'>PR</a>")
                    else:
                        feed_strings.append(f"{event_time}{repo_name} <b>{user}</b> reviewed this <a href='{pr}'>PR</a>")
        feed_progress.progress(100)
        repo_progress_md.markdown("")
        st.markdown(f"{len(feed_strings)} events in the last {last_n_hours} hours")
        return feed_strings, repo_events_count

    def get_all_users_for_repo(self, repo_name: str) -> list[str]:
        repo_url = f"{self.root_url}/repos/{self.user}/{repo_name}/contributors"
        response = requests.get(repo_url, headers=self.headers)
        return [user['login'] for user in response.json()]

    def get_repos(self) -> list[str]:
        response = requests.get(f"{self.root_url}/user/repos", headers=self.headers)
        return [repo['name'] for repo in response.json()]

    def get_prs_for_repo(self, repo_name: str, start: str, end: str, author: str = None) -> list[str]:
        start_date = datetime.strptime(start, "%d %b %Y").strftime("%Y-%m-%d")
        end_date = datetime.strptime(end, "%d %b %Y").strftime("%Y-%m-%d")

        # merged PRs
        search_query = f"repo:{self.user}/{repo_name} created:{start_date}..{end_date}"
        if author:
            search_query += f" author:{author}"
        
        print(search_query)
        prs_url = f"{self.root_url}/search/issues?per_page=100&q={search_query}"
        
        response = requests.get(prs_url, headers=self.headers)
        response_json = response.json()

        if "errors" in response_json or ('items' in response_json and len(response_json['items']) == 0):
            return []

        prs = []

        for item in response_json['items']:
            if item['user']['login'] == 'dependabot[bot]':
                continue
            prs.append({
                "title": item['title'],
                "url": item['html_url'],
                "author": item['user']['login'],
                "created_at": datetime.strptime(item['created_at'][:10], '%Y-%m-%d'),
                "state": item['state']
            })

        return prs

    def visualize_contributions(self, prs: list[dict], repo: str, n_days: int):
        if len(prs) == 0:
            return
        # create the dataframe of only the authors
        df = pd.DataFrame(prs)
        df = df['author'].value_counts().reset_index()
        df.columns = ['author', 'count']
        fig = px.pie(df, values='count', names='author', height=300, width=300, title=f'Contributions to {repo}')
        fig.update_traces(marker=dict(colors=px.colors.qualitative.Plotly))
        return fig

    def visualize_activity(self, prs: list[dict], author: str, n_days: int):
        if len(prs) == 0:
            return
        df = pd.DataFrame(prs)

        f_df = df.groupby('created_at').size().reset_index(name='PR count')
        f_df.columns = ['date', 'PR count']
        f_df['date'] = f_df['date'].dt.date

        end_date = datetime.today()
        start_date = end_date - timedelta(days=n_days)
        date_range = pd.date_range(start=start_date, end=end_date)

        continuous_df = pd.DataFrame(date_range, columns=['date'])
        continuous_df['date'] = continuous_df['date'].dt.date

        result_df = pd.merge(continuous_df, f_df, on='date', how='left').fillna({'PR count': 0})

        fig = px.bar(result_df, x='date', y='PR count', width=400, height=300)
        fig.update_traces(marker=dict(color='rgba(0, 100, 0, 0.5)'))
        fig.update_layout(title=f"PRs by {author}", xaxis_title="Date", yaxis_title="PR count")
        fig.update_yaxes(range=[0, result_df['PR count'].max() + 1])
        return fig

    def display_prs(self, prs: list[dict]):
        if len(prs) == 0:
            return
        html_table = "<table style='border-collapse: collapse; width: 100%;'>"
        html_table += "<tr style='border: 1px solid black;'><th>Title</th><th>Author</th><th>Created On</th><th>State</th></tr>"
        open_prs = 0
        closed_prs = 0
        for pr in prs:
            if isinstance(pr['created_at'], str):
                print("Instance of str")
                print(pr['created_at'])
                pr['created_at'] = datetime.strptime(pr['created_at'], "%b %d")
            elif isinstance(pr['created_at'], datetime):
                pr['created_at'] = pr['created_at'].strftime("%b %d")
            if pr['state'] == "open":
                open_prs += 1
            else:
                closed_prs += 1
            state = f"<span style='color: green;'>{pr['state']}</span>" if pr['state'] == "open" else f"<span style='color: red;'>{pr['state']}</span>"
            html_table += f"<tr style='border: 1px solid black;'><td><a href='{pr['url']}'>{pr['title']}</a></td><td>{pr['author']}</td><td>{pr['created_at']}</td><td>{state}</td></tr>"
        html_table += "</table>"
        st.markdown(f"Open PRs: <b>{open_prs}</b>, Closed PRs: <b>{closed_prs}</b>.", unsafe_allow_html=True)
        st.markdown(html_table, unsafe_allow_html=True)
