from actions.actions import ActionInterface
from google_docs import authenticate, list_docs
import streamlit as st
from competitor_utils import get_competitive_analysis
from shortcut_utils import ShortcutGateway
from utils.common_utils import CODE_RED_DAYS_AFTER
from datetime import datetime
import pandas as pd
import altair as alt

class GetGoogleDocs(ActionInterface):

    def do_action(self):
        service, _ = authenticate()

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

class GetCompetitors(ActionInterface):

    def __init__(self):
        self.competitors = None

    def do_action(self):
        col1, col2, _, _ = st.columns([1, 1, 1, 1])
        with col1:
            company_name = st.text_input("Company Name")
        with col2:
            st.write(" ")
            st.write(" ")
            get_competitors_button = st.button("Get Competitors", type="primary")

        full_width_container = st.container()

        with full_width_container:
            if get_competitors_button:
                self.competitors = get_competitive_analysis(company_name)
                st.markdown(self.competitors, unsafe_allow_html=True)

class HighlightText(ActionInterface):

    def __init__(self):
        if 'highlighted_text' not in st.session_state:
            st.session_state.highlighted_text = None


    def do_action(self):
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
                Restate the text (below) following these instructions:
                1. Write in a telegraphic style - use gerund phrases, make it direct, omit articles to keep it short.
                2. ONLY highlight important keywords. Add a span tag with #FFC0CB background and a BOLD tag.
                3. DO NOT highlight articles, verbs, adjectives, etc. 
                4. Return the answer in HTML.
                
                ---Start of text---
                {text}
                ---End of text---
                """
                return ask_openai(prompt)
            st.session_state.highlighted_text = highlight_keywords(text)

        if st.session_state.highlighted_text:
            st.markdown(st.session_state.highlighted_text, unsafe_allow_html=True)

class GetGalileo2Health(ActionInterface):

    def __init__(self, shortcut_gateway: ShortcutGateway):
        self.shortcut_gateway = shortcut_gateway

    def do_action(self, start, end):
        g20_epic_id = 23792
        full_width_container = st.container()
        
        with full_width_container:
            
            g20_health_btn = st.button("G2.0 Health")
            
            if g20_health_btn:
                st.markdown("<h4>G2.0 Backlog Rate</h4>", unsafe_allow_html=True)
                df = self.shortcut_gateway.get_backlog_rate_for_epic(start, end, epic_id=g20_epic_id)
                st.line_chart(df, x="Date", y="Backlog Rate", color="#FF0000")

class AbstractHealth(ActionInterface):

    def __init__(self, shortcut_gateway: ShortcutGateway):
        self.shortcut_gateway = shortcut_gateway

    def get_completion_rate_chart(self, df):
        color_scale = alt.Scale(
            domain=["Filed", "Completed"],
            range=["red", "green"]
        )

        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Count:Q", title="Ticket Count"),
            color=alt.Color("Category:N", scale=color_scale, legend=alt.Legend(title="Category")),
            tooltip=["Date:T", "Category:N", "Count:Q"]
        ).properties(
            width=700,
            height=400,
        )
        return chart

    def get_backlog_rate_chart(self, df):
        chart = alt.Chart(df).mark_line().encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Backlog Rate:Q", title="Backlog Rate"),
        )
        return chart


class GetExecutionHealth(AbstractHealth):

    def __init__(self, shortcut_gateway: ShortcutGateway, epic_id: int, title: str):
        self.execution_health = None
        self.shortcut_gateway = shortcut_gateway
        self.epic_id = epic_id
        self.title = title

    def do_action(self, start: datetime, end: datetime):
        execution_health_btn = st.button(self.title)

        full_width_container = st.container()

        with full_width_container:

            if execution_health_btn:
                epic = self.shortcut_gateway.get_epic_from_id(self.epic_id)
                completion_rate_df = self.shortcut_gateway.get_completion_rate_for_epic(
                    start, 
                    end, 
                    epic
                )
                backlog_df = self.shortcut_gateway.get_backlog_rate_for_epic(start, end, epic_id=self.epic_id)

                col1, col2 = st.columns([1, 1])

                with col1:
                    st.markdown("<h4>Completion Rate</h4>", unsafe_allow_html=True)
                    completion_rate_chart = self.get_completion_rate_chart(completion_rate_df)
                    st.altair_chart(completion_rate_chart, use_container_width=True)
                with col2:
                    st.markdown("<h4>Backlog Rate</h4>", unsafe_allow_html=True)
                    backlog_chart = self.get_backlog_rate_chart(backlog_df)
                    st.altair_chart(backlog_chart, use_container_width=True)