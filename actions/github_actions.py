from actions.actions import ActionInterface
import streamlit as st
from github_utils import GithubAPI
from llm_utils import CODE_REVIEW_INSTRUCTIONS, CODE_REVIEW_GUIDELINES
from llm_utils import ask_openai
from datetime import datetime, timedelta

class GetGithubActivity(ActionInterface):
    def __init__(self):
        github_token = st.secrets["github"]["token"]
        self.github_api = GithubAPI(github_token)
        if "feed_strings" not in st.session_state:
            st.session_state.feed_strings = None
        if "repo_events_count" not in st.session_state:
            st.session_state.repo_events_count = None
        if 'user_activity_map' not in st.session_state:
            st.session_state.user_activity_map = None


    def do_action(self):
        col1, col2, col3, _ = st.columns([0.5, 0.6, 0.8, 3.5])
        with col1:
            last_n_hours = st.text_input("Last N Hours", value=12)
        with col2:
            st.write(" ")
            st.write(" ")
            refresh_feed_clicked = st.button("🔄")
        with col3:
            st.write(" ")
            st.write(" ")
            smart_summary = st.checkbox("Smart Summary", value=False)

        if refresh_feed_clicked:
            feed_strings, repo_events_count = self.github_api.get_feed(last_n_hours=int(last_n_hours))

            st.session_state.feed_strings = feed_strings
            st.session_state.repo_events_count = repo_events_count

            if smart_summary:
                activity_map = self.github_api.get_user_activity(last_n_hours=int(last_n_hours))
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


class GetSmartReviews(ActionInterface):
    def __init__(self):
        self.github_api = GithubAPI(st.secrets["github"]["token"])
        if "latest_prs" not in st.session_state:
            st.session_state.latest_prs = []

    def do_action(self):
        pr_review_col, latest_prs_col = st.columns([3, 2])

        with pr_review_col:
            col1, col2, _, _ = st.columns([2, 1, 1, 1])
            with col1:
                pr_url = st.text_input("PR URL")
            with col2:
                st.write(" ")
                st.write(" ")
                get_pr_diff_button = st.button("Get PR Diff", type="primary")

            full_width_container = st.container()

            with full_width_container:
                if get_pr_diff_button:
                    pr_diff = self.github_api.get_pr_diff(pr_url)
                    for patch in pr_diff:
                        st.write("")
                        st.write(f"Path: <b><a href='{pr_url}/files'>{patch['path']}</a></b>, Additions: <b>{patch['additions']}</b>, Deletions: <b>{patch['deletions']}</b>", unsafe_allow_html=True)
                        html_content = "<table style='width: 50%;'><tr><th>Review</th></tr>"
                        smart_review = ask_openai(
                            system_content="You are the smartest python programmer in the world.",
                            user_content=f"""
                                Below is a patch of code from a Github PR.
                                + suggests additions.
                                - suggests deletions.
                                Provide a short and concise expert review of the following patch of code:
                                --start of patch--
                                {patch['patch']}
                                --end of patch--

                                INSTRUCTIONS:
                                {CODE_REVIEW_INSTRUCTIONS}

                                CODE REVIEW GUIDELINES:
                                {CODE_REVIEW_GUIDELINES}
                        """)
                        html_content = f"""
                            <tr>
                                <td>{smart_review}</td>
                            </tr>
                        """
                        html_content += "</table>"
                        st.markdown(html_content, unsafe_allow_html=True)

        with latest_prs_col:
            st.write("")
            st.write("")
            refresh_latest_prs_button = st.button("Refresh Latest PRs")

            full_width_container = st.container()

            with full_width_container:

                if refresh_latest_prs_button:
                    
                    start_minus_2_days = (datetime.now() - timedelta(days=2))
                    end_today = datetime.now()
                    st.session_state.latest_prs = []
                    html_content = "<h3>PRs for your review</h3>"
                    for repo in ["api", "runners", "wizard", "galileo-sdk", "ui"]:
                        html_content += f"<b>{repo.capitalize()} PRs</b>"
                        prs = self.github_api.get_prs_for_repo(repo_name=repo, start=start_minus_2_days, end=end_today)
                        html_content += "<ul>"
                        for pr in prs[:5]:
                            created_at = pr['created_at'].strftime("%d %b")
                            html_content += f"<li>[<b>{created_at}</b>][<b>{pr['author']}</b>] <a href='{pr['url']}'>{pr['url']}</a></li>"
                        html_content += "</ul>"
                    
                    st.session_state.latest_prs.append(html_content)

            if st.session_state.latest_prs:
                for pr in st.session_state.latest_prs:
                    st.markdown(pr, unsafe_allow_html=True)


class GetRepoPRs(ActionInterface):
    def __init__(self):
        self.github_api = GithubAPI(st.secrets["github"]["token"])
        if 'repo_prs_data' not in st.session_state:
            st.session_state.repo_prs_data = None
        if 'repo_prs_activity_visualization' not in st.session_state:
            st.session_state.repo_prs_activity_visualization = None
        if 'repo_prs_contributions_visualization' not in st.session_state:
            st.session_state.repo_prs_contributions_visualization = None
        if 'repo_name' not in st.session_state:
            st.session_state.repo_name = None

    def do_action(self, start, end):
        col1, col2, _, _ = st.columns([1, 1, 1, 1])
        n = (end - start).days
        with col1:
            repo = st.selectbox("PR Repo", ["api","core", "runners", "wizard", "galileo-sdk", "ui"])
        with col2:
            st.write(" ")
            st.write(" ")
            show_prs_clicked = st.button("Show Repo Analytics", type="primary")

        full_width_container = st.container()

        with full_width_container:
            if show_prs_clicked:
                
                prs = self.github_api.get_prs_for_repo(repo_name=repo, start=start, end=end)

                st.session_state.repo_prs_data = prs
                st.session_state.repo_name = repo
                st.session_state.repo_prs_activity_visualization = self.github_api.visualize_activity(prs, repo, n_days=n)
                st.session_state.repo_prs_contributions_visualization = self.github_api.visualize_contributions(prs, repo, n_days=n)

            if st.session_state.repo_prs_data:
                st.write(f"Getting PRs for <b>{st.session_state.repo_name}</b> between <b>{end}</b> and <b>{n}</b> days prior.", unsafe_allow_html=True)
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.session_state.repo_prs_activity_visualization:
                        st.plotly_chart(st.session_state.repo_prs_activity_visualization)
                with col2:
                    if st.session_state.repo_prs_contributions_visualization:
                        st.plotly_chart(st.session_state.repo_prs_contributions_visualization)
                self.github_api.display_prs(st.session_state.repo_prs_data)

class GetAuthorPRs(ActionInterface):
    def __init__(self):
        self.github_api = GithubAPI(st.secrets["github"]["token"])
        if 'author_prs_data' not in st.session_state:
            st.session_state.author_prs_data = None
        if 'author_prs_visualization' not in st.session_state:
            st.session_state.author_prs_visualization = None

    def do_action(self, start, end):
        col1, col2, col3, _ = st.columns([1, 1, 1, 1])

        with col1:
            repo = st.selectbox("Repo", 
                                ["api", "runners", "core","wizard", "galileo-sdk", "ui", "deploy", "experimental-cluster"])
        with col2:
            authors = self.github_api.get_all_users_for_repo(repo_name=repo)
            authors = [author for author in authors if author != "dependabot[bot]"]
            author = st.selectbox("Author", authors)
        with col3:
            st.write(" ")
            st.write(" ")
            show_prs_clicked = st.button("Show PRs", type="primary")

        full_width_container = st.container()
        n = (end - start).days

        with full_width_container:
            if show_prs_clicked:
                
                prs = self.github_api.get_prs_for_repo(repo_name=repo, start=start, end=end, author=author)

                st.session_state.author_prs_data = prs
                st.session_state.author_prs_visualization = self.github_api.visualize_activity(prs, author, n_days=n)

            if st.session_state.author_prs_data:
                st.write(f"{repo} PRs by {author}, between {end} and {n} days prior") 
                if st.session_state.author_prs_visualization is not None:
                    st.plotly_chart(st.session_state.author_prs_visualization)
                self.github_api.display_prs(st.session_state.author_prs_data)

