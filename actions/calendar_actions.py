from actions.actions import ActionInterface
from datetime import datetime, timedelta
from calendar_utils import generate_schedule_html, format_time

import streamlit as st
import pytz

class GetMyDay(ActionInterface):
    def __init__(self):
        if "my_day_events" not in st.session_state:
            st.session_state.my_day_events = None
        if "skippable_time" not in st.session_state:
            st.session_state.skippable_time = None
        if "leave_home_at_time" not in st.session_state:
            st.session_state.leave_home_at_time = None
        self.DAYS = ["today", "tomorrow", "day after", "3 days from now", "4 days from now", "5 days from now"]

    def show_highlights(self, st_first_event, et_last_event, skippable_time):
        st.markdown("<h3>Make each day count!</h3>", unsafe_allow_html=True)
        if st_first_event is not None:
            wake_up_at_time = st_first_event - timedelta(minutes=160)
            reach_gym_time = wake_up_at_time + timedelta(minutes=25)
            end_gym_time = reach_gym_time + timedelta(minutes=60)
            leave_home_at_time = st_first_event - timedelta(minutes=50)
            st.markdown(f"<li>Wake up: <span style='color: #39FF14;'><b>{wake_up_at_time.strftime('%-I:%M %p').lstrip('0').lower()}</b></span></li>", unsafe_allow_html=True)
            st.markdown(f"<li>Head to work: <span style='color: #39FF14;'><b>{leave_home_at_time.strftime('%-I:%M %p').lstrip('0').lower()}</b></span></li>", unsafe_allow_html=True)
        # if et_last_event is not None:
        #     leave_home_at_time = et_last_event + timedelta(minutes=10)
        #     st.markdown(f"<li><span style='color: #0d7e03;'>Can leave for home earliest by <b>{leave_home_at_time.strftime('%I.%M %p')}</b></span></li>", unsafe_allow_html=True)
        if skippable_time is not None:
            st.markdown(f"<li><span style='color: #3266a8;'>{format_time(skippable_time)} of skippable meetings.</span></li>", unsafe_allow_html=True)
        else:
            st.markdown("<li><span style='color: #3266a8;'>No skippable meetings today.</span></li>", unsafe_allow_html=True)

    def do_action(self):
        col1, col2, col3, _ = st.columns([1, 1, 1, 3])
        tof = tol = skippable_time = None

        with col1:
            timezone_dropdown = st.selectbox("Timezone", ["US/Pacific", "US/Eastern", "US/Central", "US/Mountain"], index=0)
            # get UTC now and then use pytz to convert to the selected timezone
            now_utc = datetime.utcnow()
            now_in_timezone = now_utc.astimezone(pytz.timezone(timezone_dropdown))
            print(f"Current time in {timezone_dropdown}: {now_in_timezone.strftime('%I.%M %p')}")

        with col2:
            day_selected = st.selectbox("Day", self.DAYS)

        with col3:
            st.write(" ")
            st.write(" ")
            day_button = st.button("Gimme my day", key="day_button", type="primary")

        full_width_container = st.container()

        with full_width_container:
            if day_button:
                display_html, tof, tol, skippable_time = generate_schedule_html(day_selected, now_in_timezone)
                st.session_state.my_day_events = "".join(display_html)
                self.show_highlights(tof, tol, skippable_time)

            if st.session_state.my_day_events:
                st.markdown(st.session_state.my_day_events, unsafe_allow_html=True)
