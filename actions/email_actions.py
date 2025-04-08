from actions.actions import ActionInterface
import streamlit as st
from email_utils import fetch_emails_in_last_n_hours


class GetEmails(ActionInterface):
    def __init__(
            self, 
    ):
        
        if "email_summary" not in st.session_state:
            st.session_state.email_summary = None

    def do_action(self):
        col1, col2, col3, _ = st.columns([0.5, 0.5, 0.5, 3.5])
        with col1:
            hours = st.text_input("Hours", value=10)

        with col2:
            st.write(" ")
            st.write(" ")
            emails_button = st.button("Get Emails", key="emails_button", type="primary")

        with col3:
            st.write(" ")
            st.write(" ")
            personal = st.checkbox("Personal", value=False)
        full_width_container = st.container()

        with full_width_container:
            if emails_button:
                
                summary = fetch_emails_in_last_n_hours(
                    n_hours=int(hours), 
                    personal=personal
                )
                st.session_state.email_summary = summary if summary else "<span style='color: #0d7e03;'>No emails!</span>"

            if st.session_state.email_summary is not None:
                st.markdown(st.session_state.email_summary, unsafe_allow_html=True)
            else:
                st.markdown("<span style='color: #0d7e03;'>No emails!</span>", unsafe_allow_html=True)