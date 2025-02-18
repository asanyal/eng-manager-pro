

CODE_RED_DAYS_AFTER = 10

COMMON_PAGE_CSS = """
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
    """

CODE_REVIEW_INSTRUCTIONS = """
    You are the smartest python programmer in the world.
    You are reviewing a PR.
    You are given a PR diff.
    You are given a PR description.
    You are given a PR title.
"""

CODE_REVIEW_GUIDELINES = """
You are reviewing a PR.
You are given a PR diff.
You are given a PR description.
You are given a PR title.
"""
