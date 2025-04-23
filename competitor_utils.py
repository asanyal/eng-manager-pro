import json
from firecrawl import FirecrawlApp
import yfinance as yf
from llm_utils import ask_openai
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

def get_competitive_analysis(company_name, beautify=False):
    fc_key = os.getenv('FIRECRAWL_API_KEY')
    if fc_key is None:
        fc_key = st.secrets["FIRECRAWL_API_KEY"]

    app = FirecrawlApp(api_key=fc_key)

    # Scrape a single URL
    url = ask_openai(
        system_content=f"You are a smart financial analyst",
        user_content=f"What's the full website URL of the company {company_name}. Only return the full URL."
    )
    st.write(f"URL: {url}")

    scraped_data = app.scrape_url(
        url, 
        params={
            'onlyMainContent': True
        }, 
    )

    formatted_crawl_result = json.dumps(scraped_data, indent=4)
    content = f"""
        {formatted_crawl_result}
    """

    user_content = f"""
        You are an expert in competitor analysis. 
        I am providing you with content extracted from a competitor's website. 
        Your task is to analyze the text and extract detailed information about the company based on the following criteria:

    1. Company Overview:
    - Briefly summarize what the company does, including its main products or services.

    2. Features:
    - List all the features of the company's products or services mentioned in the content.

    3. Return on Investment (ROI) Claims:
    - Identify any ROI metrics or performance claims the company makes, such as percentage improvements, cost savings, or other quantifiable benefits (e.g., "97% decrease in denial rates").

    4. Target Audience:
    - Describe the types of users or customers the company targets, including specific industries, roles, or user personas.

    5. Pricing Information:
    - Extract any pricing details, plans, or cost-related information, if available.

    6. Funding and Financial Information:
    - Identify any information about the amount of funding the company has raised or its financial standing, if present.

    7. Team Information:
    - List key team members, founders, or executives mentioned, along with their roles or titles, if available.

    8. Business Model or Go to Market Strategy:
    - Describe the company's business model or go to market strategy, including how it generates revenue, its market approach, and any unique selling points (USPs).

    Please provide your analysis in a structured format, clearly separating each section.

    Additional instructions:
    Display the information in a simple 2 column HTML Table.
    - Column 1: Titles of the sections. 
    - Column 2: Extracted information.
     Make the titles capital letters. Don't use ** or _ symbols so the generated text is clean. 
     If available, get information on the industry, founding year, current funding status, the founders, the company's mission, and the company's services. 
     Ensure all information is directly referenced from the document.

    Content to Analyze:
        {content}
    """

    if beautify:
        user_content += "\nDisplay output in beautiful formatted HTML. Underline the key phrases and terms."

    ticker = ask_openai(
        system_content="You are a smart financial analyst",
        user_content=f"Stock symbol associated with company website {url}. Only return the symbol. If you cannot find it, return NONE."
    )

    company_summary = ask_openai(
        user_content=user_content
    )

    if ticker == "NONE":
        company_summary += "Company likely not public."
    else:
        stock = yf.Ticker(ticker=ticker)
        company_summary += "ABOUT THE COMPANY"
        company_summary += f"Industry: {stock.info['industry']}, {stock.info['sector']}"
        company_summary += f"City: {stock.info['city']}"
        company_summary += f"Description: {stock.info['longBusinessSummary']}"
    return company_summary