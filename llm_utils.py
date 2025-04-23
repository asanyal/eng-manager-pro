import os
from openai import OpenAI
import streamlit as st

CODE_REVIEW_INSTRUCTIONS_V1 = """
1. Do not add a header saying "Review of code patch".
2. Use telegraphic language and gerund phrases.
3. Add a very short 8-10 word summary on what the changes are about.
4. Suggest up to 3 improvements to the code in bullet points. Add the line number range in brackets in <b> tags.
5. Do not suggest adding "type hints".
6. Put each bullet for improvement in a span with a #8dda92 background.
7. Detect any obvious bug in the code in bullet points. Put the bullet point for bugs in a span with a #da8d8d background.
8. Wrap the word "comment", "comments" or "docstring" or "docstrings" in a span with an orange background and black font.
9. Use the Code Review Guidelines below to guide your review for both improvements and bugs.
10. If no bug is detected, say "No major bugs detected".
11. Return the answer in HTML.
"""

CODE_REVIEW_INSTRUCTIONS_V2 = """
Provide a structured response with the following format:
	1.	Detailed Findings: Break down specific issues and improvements, categorized by the sections above.
	2.	Code Suggestions: If applicable, provide improved code snippets.
	3.	Severity Levels: Mark each issue as one of the following:
	•	🛑 Critical: Must fix (e.g., security vulnerability, major performance issue).
	•	⚠️ High: Should fix (e.g., significant scalability concern, incorrect implementation).
	•	⚡ Medium: Nice to have (e.g., minor optimizations, code style improvements).
	•	✅ Good Practice: Things done well.
Example Response format:
🛑 Critical Issues:
1. **Race Condition in Database Writes**  
   - The `update_user_status` function updates the user status without a transactional lock, leading to potential data inconsistency.  
   - Suggested Fix: Use a database-level lock or an atomic operation.
2. **Memory Leak in Background Worker**  
   - The worker keeps references to large objects unnecessarily, preventing garbage collection.  
   - Suggested Fix: Explicitly delete objects after processing and monitor memory usage.
⚠️ High Priority:
- **Inefficient Query in `fetch_large_dataset()`**
  - The function retrieves all records at once instead of using pagination.
  - Suggested Fix: Implement cursor-based pagination to reduce memory footprint.
⚡ Medium Priority:
- **Logging Improvements**
  - Consider using structured logging instead of plain text logs to enhance observability.
✅ Good Practices:
- Code adheres to PEP8 standards.
- Exception handling is well-implemented.
Final Instructions:
Now, analyze the given PR using the above criteria and provide a detailed review with actionable feedback. Make sure to highlight the most critical issues first while maintaining a balance between necessary fixes and nice-to-have improvements.
"""

CODE_REVIEW_GUIDELINES_V1 = """
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


CODE_REVIEW_GUIDELINES_V2 = """
Task:
Key Aspects to Evaluate:

1. Code Quality & Best Practices
	•	Is the code clean, well-structured, and readable?
	•	Does it follow Python best practices (PEP8, naming conventions, docstrings)?
	•	Are functions/classes modular and reusable?
	•	Are there redundant, unnecessary, or duplicate code blocks?
	•	Are appropriate logging and error-handling mechanisms in place?
	•	Are dependencies used correctly without unnecessary imports?

2. Scalability & Performance
	•	Does the code efficiently handle increasing load and concurrency?
	•	Are there unnecessary loops, inefficient data structures, or performance bottlenecks?
	•	Could database queries be optimized (e.g., use of indexes, pagination, batch operations)?
	•	Does it properly utilize caching (e.g., Redis, memoization) where needed?
	•	Are there potential network call inefficiencies (e.g., unnecessary API calls, blocking I/O operations)?

3. Concurrency & Race Conditions
	•	Does the code properly handle multithreading/multiprocessing (if applicable)?
	•	Are there shared resources that might cause race conditions?
	•	Are locks, semaphores, or atomic operations used where necessary?
	•	If async code is used, is it correctly structured to avoid deadlocks or unexpected behavior?
	•	Are database transactions correctly handled to prevent race conditions?

4. Memory Management & Leaks
	•	Are objects/data structures properly released when no longer needed?
	•	Are there potential memory leaks (e.g., circular references, unclosed file handles, large objects lingering in memory)?
	•	If caching is used, is cache invalidation handled correctly?
	•	Are database connections, file descriptors, and network sockets properly closed?

5. Security Considerations
	•	Are there potential security vulnerabilities (e.g., SQL injection, command injection, sensitive data exposure)?
	•	Are user inputs properly sanitized and validated?
	•	Are authentication and authorization mechanisms correctly implemented?
	•	If external APIs or third-party services are used, are API keys/tokens securely managed?

6. Test Coverage & Maintainability
	•	Are there sufficient unit and integration tests?
	•	Are edge cases and error conditions tested?
	•	Do tests mock dependencies correctly to avoid flaky behavior?
	•	Is the codebase structured for long-term maintainability and ease of extension?
"""

THEME_EXTRACTION_PROMPT = """
Given a list of story titles, identify 10-15 product-focused themes.

INSTRUCTIONS:
1. Extract the product features from the title (e.g., "Metrics Tables", "SSO & Auth", "Alerts", "Documentation" etc.)
2. Ensure the themes are verbose and descriptive (but within 5-10 words)
3. ONLY return a valid JSON array of theme names

For guidance, here are some product areas in Galileo:
Logstreams, Playground, Experiments, Projects, Metrics, Prompts, Datasets, Agentic Evaluation, Multi Modal Evaluation, Integrations, Admin, RBAC, etc, SSO, OAuth, SAML, Bugs and Feature Requests.

RESPONSE FORMAT - ONLY return a JSON array like this:
{
    "themes": [
        "Theme1",
        "Theme2",
        ...
    ]
}

DO NOT include any explanations, text, or markdown before or after the JSON object.
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
    # Clean the response: extract only the JSON object
    output = response.choices[0].message.content
    # Find the first { and last } to extract just the JSON object
    start = output.find('{')
    end = output.rfind('}') + 1
    if start >= 0 and end > start:
        output = output[start:end]
    return output.strip()

def classify_story(story_title: str, available_themes: list) -> str:
    themes_list = "\n".join(f"- {theme}" for theme in available_themes)
    prompt = f"""
Given these themes:
{themes_list}

Classify this story into exactly ONE of the above themes:
"{story_title}"

Return ONLY the exact theme name from the list above. No explanations or additional text.
"""
    response = ask_openai(prompt)
    theme = response.strip()
    return theme if theme in available_themes else available_themes[0]  # fallback to first theme if no match
