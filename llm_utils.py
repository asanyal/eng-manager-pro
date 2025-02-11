import os
from openai import OpenAI
import streamlit as st

CODE_REVIEW_INSTRUCTIONS = """
1. Do not add a header saying "Review of code patch".
2. Use telegraphic language and gerund phrases.
3. Add a very short 8-10 word summary on what the changes are about.
4. Suggest up to 3 improvements to the code in bullet points. Add the line number range in brackets in <b> tags.
5. Do not suggest adding "type hints".
6. Put each bullet for improvement in a span with a #8dda92 background.
7. Detect any obvious bug in the code in bullet points. Put the bullet point for bugs in a span with a #da8d8d background.
8. Use the Code Review Guidelines below to guide your review for both improvements and bugs.
9. If no bug is detected, say "No major bugs detected".
10. Return the answer in HTML.

"""

CODE_REVIEW_GUIDELINES = """
Here are the top three technical areas to check:

1. Performance Issues (Memory Leaks, Inefficient Data Structures & Algorithms)
	•	Memory Leaks: Look for objects that are never released (e.g., large lists or dictionaries accumulating indefinitely). Check for improper use of del, gc.collect(), or missing close() calls for file handlers, database connections, and sockets.
	•	Inefficient Loops: Avoid unnecessary list traversals, especially nested loops that can be replaced with set operations or dictionary lookups.
	•	Unnecessary Object Copies: Check for redundant .copy() calls on lists/dictionaries and improper usage of mutable default arguments.
2. Edge Case Handling (Concurrency, Exception Handling, Overflow)
	•	Threading & Async Pitfalls: Check if shared resources are protected (use locks where needed) and ensure async functions use proper await calls.
	•	Exception Handling: Ensure specific exceptions are caught instead of broad except Exception: which can mask real issues.
	•	Overflow and Boundary Conditions: Validate input sizes, avoid integer overflows (especially when working with recursion or large numbers).
3. Silent Failures & Hidden Bugs (Mutability Issues, Floating-Point Precision, Unintended Side Effects)
	•	Mutability Issues: Check if mutable default arguments (like lists) are used incorrectly.
	•	Floating-Point Precision Errors: Ensure floating-point calculations do not accumulate small errors, especially in financial or scientific applications.
	•	Unintended Side Effects: Look for global variables modified within functions that can cause unpredictable behavior.
"""

def ask_openai(
    user_content,
    system_content="You are a smart assistant", 
    model="gpt-4o-mini"
):
    api_key = st.secrets['openai']["api_key"]
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
    )
    output = response.choices[0].message.content.replace("```markdown", "").replace("```code", "").replace("```html", "").replace("```", "")
    return output
