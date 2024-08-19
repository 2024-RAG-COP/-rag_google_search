import streamlit as st
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
import anthropic
import re
from urllib.parse import unquote

# API 키를 st.secrets에서 가져옵니다
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
GOOGLE_CSE_ID = st.secrets["GOOGLE_CSE_ID"]
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Utility functions
def clean_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def format_url(url):
    decoded_url = unquote(url)
    if len(decoded_url) > 70:
        return decoded_url[:70] + "..."
    return decoded_url

def format_answer(answer):
    if isinstance(answer, list) and len(answer) > 0 and hasattr(answer[0], 'text'):
        text = answer[0].text
    else:
        text = str(answer)
    text = re.sub(r'\n+', '\n', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines)

# Main functions
def google_search(query, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=cse_id, **kwargs).execute()
    return res.get('items', [])

def scrape_content(url):
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = ' '.join([tag.get_text() for tag in soup.find_all(['p', 'h1', 'h2', 'h3'])])
        return text[:1000]
    except:
        return "Failed to scrape content"

def generate_related_queries(question):
    prompt = f"""
    Generate two related search queries for the following question. 
    The queries should be different from the original question but related to its topic.
    Provide only the queries, separated by a newline.

    Question: {question}

    Related Queries:
    """
    
    message = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=100,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    content = message.content
    if isinstance(content, str):
        queries = content.strip().split('\n')
    elif isinstance(content, list) and len(content) > 0 and hasattr(content[0], 'text'):
        queries = content[0].text.strip().split('\n')
    else:
        queries = []
    
    return queries[:2]

def generate_answer(question, search_results, related_queries):
    prompt = f"""
    You are an AI assistant tasked with answering questions based on the latest information available.
    Use the following search results and scraped content to answer the user's question. If the information
    provided doesn't contain relevant details, use your own knowledge to provide the best possible answer.

    Original Question: {question}

    Related Queries:
    {', '.join(related_queries)}

    Search Results and Scraped Content:
    {search_results}

    Please provide a comprehensive and accurate answer. Include relevant sources if available.
    Also, mention how the related queries contributed to the answer, if applicable.
    """
    
    message = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content

# Streamlit UI
st.title("AI-Powered Q&A System with Related Queries")

user_question = st.text_input("Enter your question:")

if user_question:
    try:
        with st.spinner("Generating related queries..."):
            related_queries = generate_related_queries(user_question)
        
        with st.spinner("Searching and scraping content..."):
            all_search_results = []
            for query in [user_question] + related_queries:
                results = google_search(query, GOOGLE_API_KEY, GOOGLE_CSE_ID, num=3)
                all_search_results.extend(results)
            
            combined_results = []
            for item in all_search_results:
                title = item.get('title', 'No title')
                link = item.get('link', 'No link')
                content = scrape_content(link)
                combined_results.append(f"Title: {title}\nURL: {link}\nContent: {content}\n")
            
            combined_results_str = "\n".join(combined_results)

        with st.spinner("Generating answer..."):
            response = generate_answer(user_question, combined_results_str, related_queries)

        st.subheader("Answer:")
        formatted_answer = format_answer(response)
        st.markdown(formatted_answer)

        st.subheader("Related Queries:")
        for query in related_queries:
            st.write(f"- {query}")

        st.subheader("Search Results and Scraped Content:")
        for item in all_search_results:
            with st.expander(f"Title: {item.get('title', 'No title')}"):
                st.markdown(f"**URL:** {format_url(item.get('link', 'No link'))}")
                content = scrape_content(item.get('link', ''))
                st.markdown(f"**Content:** {clean_text(content)}")
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error("Please check your API keys and try again.")
