import os
from openai import OpenAI
import streamlit as st

def ask_openai(
    user_content,
    system_content="You are a smart assistant", 
    model="gpt-4o-mini"
):
    api_key = st.secrets["OPENAI_API_KEY"]
    os.environ['OPENAI_API_KEY'] = api_key
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
