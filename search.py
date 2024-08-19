import streamlit as st
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
import os
import anthropic
import re
from urllib.parse import unquote

# Set your API keys
os.environ["GOOGLE_API_KEY"] = "your_google_api_key_here"
os.environ["GOOGLE_CSE_ID"] = "your_google_cse_id_here"
os.environ["ANTHROPIC_API_KEY"] = "your_anthropic_api_key_here"
api_key = os.getenv("ANTHROPIC_API_KEY")

# Initialize Google Custom Search API
def google_search(query, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=cse_id, **kwargs).execute()
    return res.get('items', [])

# Web scraping function
def scrape_content(url):
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract text from p, h1, h2, h3 tags
        text = ' '.join([tag.get_text() for tag in soup.find_all(['p', 'h1', 'h2', 'h3'])])
        
        # Limit to first 1000 characters
        return text[:1000]
    except:
        return "Failed to scrape content"

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
    
    content = message.content
    if isinstance(content, str):
        return content
    elif isinstance(content, list) and len(content) > 0 and hasattr(content[0], 'text'):
        return content[0].text
    else:
        return "Sorry, I couldn't generate an answer at this time."

def clean_text(text):
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def format_url(url):
    # URL 디코딩
    decoded_url = unquote(url)
    # URL이 너무 길면 줄임
    if len(decoded_url) > 70:
        return decoded_url[:70] + "..."
    return decoded_url

def extract_text_from_content_block(content):
    # ContentBlock 객체에서 텍스트 추출
    if isinstance(content, list) and len(content) > 0 and hasattr(content[0], 'text'):
        return content[0].text
    return str(content)

def format_answer(answer):
    # 텍스트 추출 및 줄바꿈 처리
    text = extract_text_from_content_block(answer)
    # 연속된 줄바꿈을 하나로 통일
    text = re.sub(r'\n+', '\n', text)
    # 각 줄 앞뒤 공백 제거
    lines = [line.strip() for line in text.split('\n')]
    # 빈 줄 제거
    lines = [line for line in lines if line]
    return '\n\n'.join(lines)

# Streamlit UI
st.title("AI-Powered Q&A System with Related Queries")

# User input
user_question = st.text_input("Enter your question:")

if user_question:
    # Generate related queries
    related_queries = generate_related_queries(user_question)
    
    # Perform searches
    all_search_results = []
    for query in [user_question] + related_queries:
        results = google_search(
            query, 
            os.environ["GOOGLE_API_KEY"], 
            os.environ["GOOGLE_CSE_ID"], 
            num=3
        )
        all_search_results.extend(results)
    
    # Prepare search results for Claude
    combined_results = []
    for item in all_search_results:
        title = item.get('title', 'No title')
        link = item.get('link', 'No link')
        content = scrape_content(link)
        combined_results.append(f"Title: {title}\nURL: {link}\nContent: {content}\n")
    
    combined_results_str = "\n".join(combined_results)

    # Generate answer using Claude
    response = generate_answer(user_question, combined_results_str, related_queries)

    # Display the answer
    st.subheader("Answer:")
    formatted_answer = format_answer(response)
    st.markdown(formatted_answer)

    # Display related queries
    st.subheader("Related Queries:")
    for query in related_queries:
        st.write(f"- {query}")

    # Display search results
    st.subheader("Search Results and Scraped Content:")
    for item in all_search_results:
        with st.expander(f"Title: {item.get('title', 'No title')}"):
            st.markdown(f"**URL:** {format_url(item.get('link', 'No link'))}")
            content = scrape_content(item.get('link', ''))
            st.markdown(f"**Content:** {clean_text(content)}")
