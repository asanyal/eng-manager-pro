import os
from openai import OpenAI


def ask_openai(
    user_content,
    system_content="You are a smart assistant", 
    api_key="sk-IeRyqWbbS1uGEwxRKMVqOJaK4aSUtlJY4sD50zhacTT3BlbkFJFKKv1ANslg96TeOQddTkB7GKDnZzk1meXhbr69CWYA", 
    model="gpt-4o-mini"
):
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
