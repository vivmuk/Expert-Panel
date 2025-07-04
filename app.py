import requests
import json
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration ---
VENICE_API_KEY = 'ntmhtbP2fr_pOQsmuLPuN_nm6lm2INWKiNcvrdEfEC'  # Venice AI API key
VENICE_CHAT_COMPLETIONS_URL = "https://api.venice.ai/api/v1/chat/completions"

# Model Configuration
PERSONA_GENERATION_MODEL = "llama-3.1-405b"      # Llama 405B for expert orchestration
INSIGHT_GENERATION_MODEL = "qwen3-235b"          # Qwen 235B for individual expert analysis  
SEARCH_ANALYSIS_MODEL = "qwen-2.5-qwq-32b"      # Qwen QWQ for search-based market analysis
SYNTHESIS_MODEL = "qwen3-235b"                    # Qwen 235B for final synthesis

# Expert Configuration
TOTAL_EXPERTS = 20
REGULAR_EXPERTS = 15  # Traditional expert analysis
SEARCH_EXPERTS = 5    # Market intelligence and search-based analysis

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app, resources={r"/*":{"origins": "*"}}, supports_credentials=True)

# Add rate limiting and caching
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS" and request.path in ["/process_problem", "/test_venice"]:
        response = jsonify(success=True) # Or app.make_response('')
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "POST,OPTIONS")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

# --- Utility Functions ---
def clean_text_content(text):
    """
    Clean up text content by removing [REF] tags and other unwanted formatting
    that Venice AI might include in its responses.
    """
    if not isinstance(text, str):
        return text
    
    import re
    
    # Remove [REF] tags and their content - matches [REF], [REF1], [REF]5[/REF], etc.
    text = re.sub(r'\[REF[^\]]*\][^[]*\[/REF\]', '', text)  # Remove full [REF]...[/REF] blocks
    text = re.sub(r'\[REF[^\]]*\]', '', text)  # Remove standalone [REF] tags
    text = re.sub(r'\[/REF\]', '', text)  # Remove closing [/REF] tags
    
    # Remove other common unwanted formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Convert **bold** to plain text
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Convert *italic* to plain text
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
    text = text.strip()  # Remove leading/trailing whitespace
    
    return text

def clean_insights_data(insights_data):
    """
    Recursively clean all text content in insights data structure
    """
    if isinstance(insights_data, dict):
        cleaned = {}
        for key, value in insights_data.items():
            if isinstance(value, str):
                cleaned[key] = clean_text_content(value)
            elif isinstance(value, (dict, list)):
                cleaned[key] = clean_insights_data(value)
            else:
                cleaned[key] = value
        return cleaned
    elif isinstance(insights_data, list):
        return [clean_insights_data(item) for item in insights_data]
    elif isinstance(insights_data, str):
        return clean_text_content(insights_data)
    else:
        return insights_data

# --- Venice AI API Interaction ---
def call_venice_api(model_id, messages, schema_name_for_api, actual_json_schema):
    """
    Helper function to call the Venice AI chat completions API
    using the specific response_format structure required by Venice AI.
    """
    payload = {
        "model": model_id,
        "messages": messages,
        "response_format": {
            "type": "json_schema", # As per Venice AI docs
            "json_schema": {      # This is the wrapper object
                "name": schema_name_for_api,
                "strict": True,
                "schema": actual_json_schema # Our actual schema goes here
            }
        },
        "temperature": 0.7,
        "max_completion_tokens": 3000 # Increased slightly for potentially larger JSONs
    }
    headers = {
        "Authorization": f"Bearer {VENICE_API_KEY}",
        "Content-Type": "application/json"
    }
    response_obj_for_logging = None
    message_content_for_logging = None # To log problematic content if JSON parsing fails
    try:
        print(f"About to call Venice AI API for model {model_id}, schema {schema_name_for_api}")
        print(f"Venice API URL: {VENICE_CHAT_COMPLETIONS_URL}")
        print(f"Timeout set to: 120 seconds")
        response = requests.post(VENICE_CHAT_COMPLETIONS_URL, json=payload, headers=headers, timeout=120) # Increased timeout to 2 minutes for longer processing
        print(f"Venice AI API call completed successfully for {model_id}")
        response_obj_for_logging = response
        response.raise_for_status()
        print(f"Venice AI API response status: {response.status_code}")
        
        full_api_response_json = response.json()
        
        if "choices" not in full_api_response_json or not full_api_response_json["choices"]:
            print(f"Error: 'choices' array missing/empty in API response for model {model_id}, schema {schema_name_for_api}.")
            print(f"Full API response: {full_api_response_json}")
            return {"error": "API response missing 'choices'", "model_id": model_id, "details": "Empty/missing choices."}

        message_content_for_logging = full_api_response_json["choices"][0].get("message", {}).get("content")
        if message_content_for_logging is None:
            print(f"Error: 'content' missing in API message for model {model_id}, schema {schema_name_for_api}.")
            print(f"Full API response: {full_api_response_json}")
            return {"error": "API response missing 'content' in message", "model_id": model_id, "details": "Content missing."}

        # Attempt to extract JSON string if it's embedded or has prefixes/suffixes
        json_string_to_parse = message_content_for_logging
        if isinstance(json_string_to_parse, str):
            # Look for the start of a JSON object '{' or array '['
            first_brace = json_string_to_parse.find('{')
            first_bracket = json_string_to_parse.find('[')

            start_index = -1

            if first_brace != -1 and first_bracket != -1:
                start_index = min(first_brace, first_bracket)
            elif first_brace != -1:
                start_index = first_brace
            elif first_bracket != -1:
                start_index = first_bracket
            
            if start_index != -1:
                # Look for the corresponding end brace '}' or bracket ']'
                # This is a simplified approach; for deeply nested JSON, a more robust parser might be needed
                # if this fails, but often works for LLM outputs that just have a prefix.
                last_brace = json_string_to_parse.rfind('}')
                last_bracket = json_string_to_parse.rfind(']')
                end_index = -1

                if last_brace != -1 and last_bracket != -1:
                    end_index = max(last_brace, last_bracket)
                elif last_brace != -1:
                    end_index = last_brace
                elif last_bracket != -1:
                    end_index = last_bracket
                
                if end_index != -1 and end_index > start_index:
                    json_string_to_parse = json_string_to_parse[start_index : end_index + 1]
                else:
                    # Could not reliably find end, try parsing original if it looks like it might be JSON despite no clear end found by rfind
                    pass # Fall through to json.loads with original string if no clear extraction found
            else:
                # No brace or bracket found, it's unlikely to be JSON
                print(f"Warning: No JSON object/array start found in content for model {model_id}, schema {schema_name_for_api}. Content: {message_content_for_logging[:200]}")
        
        # Now, try to parse the (potentially extracted) string
        if isinstance(json_string_to_parse, str):
            structured_content = json.loads(json_string_to_parse) # Use the modified string
        else: 
            print(f"Warning: Message content was not a string after attempted extraction for model {model_id}, schema {schema_name_for_api}. Type: {type(json_string_to_parse)}")
            structured_content = json_string_to_parse 
        
        # Clean the structured content to remove [REF] tags and other unwanted formatting
        cleaned_content = clean_insights_data(structured_content)
        
        return cleaned_content
        
    except requests.exceptions.Timeout:
        print(f"Timeout error calling Venice AI API for model {model_id}, schema {schema_name_for_api}")
        return {"error": "API call timed out", "model_id": model_id}
    except requests.exceptions.RequestException as e:
        print(f"RequestException for model {model_id}, schema {schema_name_for_api}: {e}")
        error_details = response_obj_for_logging.text if response_obj_for_logging is not None else "No response captured."
        print(f"Response status: {response_obj_for_logging.status_code if response_obj_for_logging is not None else 'N/A'}, Content: {error_details}")
        return {"error": str(e), "model_id": model_id, "details": error_details}
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError for model {model_id}, schema {schema_name_for_api}: {e}")
        print(f"Problematic content string for JSON decoding: {message_content_for_logging}")
        return {"error": "JSON decoding failed", "model_id": model_id, "details": str(e), "problematic_content": message_content_for_logging}
    except KeyError as e:
        print(f"KeyError accessing API response for model {model_id}, schema {schema_name_for_api}: {e}")
        full_response_for_key_error = response_obj_for_logging.json() if response_obj_for_logging and response_obj_for_logging.text else 'No response json available'
        print(f"Full API response causing KeyError: {full_response_for_key_error}")
        return {"error": "Unexpected API response structure (KeyError)", "model_id": model_id, "details": str(e)}
    except Exception as e:
        print(f"Unexpected error in call_venice_api for model {model_id}, schema {schema_name_for_api}: {e}")
        return {"error": "An unexpected error occurred", "model_id": model_id, "details": str(e)}

def call_venice_search_api(query, model_id="qwen-2.5-qwq-32b"):
    """
    Call Venice AI search API for real-time information gathering.
    """
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user", 
                "content": query
            }
        ],
        "search": True,  # Enable search functionality
        "temperature": 0.7,
        "max_completion_tokens": 2000
    }
    headers = {
        "Authorization": f"Bearer {VENICE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"Calling Venice Search API for query: {query[:100]}...")
        response = requests.post(VENICE_CHAT_COMPLETIONS_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        
        full_api_response_json = response.json()
        if "choices" not in full_api_response_json or not full_api_response_json["choices"]:
            return {"error": "Search API response missing 'choices'", "query": query}
            
        content = full_api_response_json["choices"][0].get("message", {}).get("content")
        if content is None:
            return {"error": "Search API response missing 'content'", "query": query}
            
        return {"content": clean_text_content(content), "query": query}
        
    except Exception as e:
        print(f"Error in Venice Search API call: {e}")
        return {"error": str(e), "query": query}


# --- Stage 2: Persona Generation & Definition ---
def generate_expert_personas(business_problem):
    persona_generation_prompt = f"""
    Given the business problem: "{business_problem}"

    Identify and define exactly 15 diverse expert personas that could offer unique and valuable insights.
    
    IMPORTANT GUIDELINES:
    - NO quantum computing, quantum physics, or quantum technology experts
    - Focus on the widest breadth of relevant expertise
    - Include traditional business disciplines (strategy, finance, operations, marketing, HR, legal)
    - Include industry-specific experts relevant to the problem domain
    - Include technology and digital transformation experts
    - Include customer experience and behavioral experts
    - Include risk management and compliance experts
    - Include innovation and R&D experts
    - Include sustainability and ESG experts
    - Include international/global market experts
    - Include data analytics and AI/ML experts (non-quantum)
    - Include supply chain and logistics experts
    - Include regulatory and policy experts

    Each expert should have distinct expertise that doesn't significantly overlap with others.
    Ensure the experts collectively cover all major aspects that could impact the business problem.

    Your response MUST be a JSON object adhering to the specified schema. 
    The JSON should contain a single key "personas", which is an array of 15 persona objects.
    Each persona object must have 'name' (string), 'description' (string), and 'focus_areas' (array of strings).
    """
    messages = [{"role": "user", "content": persona_generation_prompt}]
    
    # This is the *actual* schema definition as per Venice AI's nested structure
    actual_schema_for_personas = {
        "type": "object",
        "properties": {
            "personas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "focus_areas": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["name", "description", "focus_areas"],
                    "additionalProperties": False 
                }
            }
        },
        "required": ["personas"],
        "additionalProperties": False 
    }

    print(f"Generating personas for problem: {business_problem[:100]}...")
    api_response_data = call_venice_api(
        model_id=PERSONA_GENERATION_MODEL,
        messages=messages,
        schema_name_for_api="ExpertPersonasListGenerator", # Name for the Venice API schema config
        actual_json_schema=actual_schema_for_personas
    )
    
    if api_response_data and "personas" in api_response_data and not api_response_data.get("error"):
        print(f"Successfully generated {len(api_response_data['personas'])} personas.")
        return api_response_data["personas"]
    else:
        print("Error: Persona generation failed or returned error structure.")
        print("API Response Data for persona generation:", api_response_data)
        return []

# --- Stage 3: Multi-Persona Insight Generation ---
def get_insights_from_persona(business_problem, persona_profile):
    persona_name = persona_profile.get("name", "Unknown Persona")
    persona_desc = persona_profile.get("description", "No description provided.")
    persona_focus = ", ".join(persona_profile.get("focus_areas", []))

    insight_prompt = f"""
    You are '{persona_name}'. Your expertise: {persona_desc}. Focus: {persona_focus}.
    Analyze the business problem: "{business_problem}" strictly from your unique perspective as '{persona_name}'.
    
    Your response MUST be a JSON object adhering to the specified schema.
    The JSON should contain 'persona_name' (string, matching "{persona_name}") and 'insights_and_analysis' (array of objects).
    Each item in 'insights_and_analysis' must have 'insight' (string), 'supporting_reasoning' (string), 'confidence_level' (enum: "High", "Medium", "Low"), 
    and optionally 'identified_risks' (array of strings) and 'identified_opportunities' (array of strings).
    """
    messages = [{"role": "user", "content": insight_prompt}]

    # This is the *actual* schema definition
    actual_schema_for_insights = {
        "type": "object",
        "properties": {
            "persona_name": {"type": "string", "const": persona_name}, 
            "insights_and_analysis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "insight": {"type": "string"},
                        "identified_risks": {"type": ["array", "null"], "items": {"type": "string"}},
                        "identified_opportunities": {"type": ["array", "null"], "items": {"type": "string"}},
                        "supporting_reasoning": {"type": "string"},
                        "confidence_level": {"type": "string", "enum": ["High", "Medium", "Low"]}
                    },
                    "required": ["insight", "supporting_reasoning", "confidence_level"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["persona_name", "insights_and_analysis"],
        "additionalProperties": False
    }

    print(f"Getting insights from persona: {persona_name}...")
    api_response_data = call_venice_api(
        model_id=INSIGHT_GENERATION_MODEL,
        messages=messages,
        schema_name_for_api=f"{persona_name.replace(' ', '')}InsightGenerator", # Dynamic name for API
        actual_json_schema=actual_schema_for_insights
    )

    if api_response_data and "persona_name" in api_response_data and "insights_and_analysis" in api_response_data and not api_response_data.get("error"):
        print(f"Successfully received insights from {api_response_data['persona_name']}.")
        return api_response_data
    else:
        print(f"Error: Insight generation failed for {persona_name} or returned error structure.")
        print("API Response Data for insight generation:", api_response_data)
        error_message = "Failed to get insights"
        if isinstance(api_response_data, dict) and "error" in api_response_data:
            error_message = api_response_data.get("details", api_response_data.get("error", error_message))
        return {"persona_name": persona_name, "insights_and_analysis": [], "error": error_message}

# --- Stage 3.2: Market Intelligence & Search-Based Analysis ---
def generate_market_intelligence(business_problem):
    """
    Generate 5 market intelligence reports using Venice AI search functionality.
    Covers: Key Players, Consulting Firm Insights, Porter's Five Forces, Threats, Latest Trends
    """
    print("\n--- Stage 3.2: Generating Market Intelligence ---")
    
    # Define enhanced search queries for different market intelligence areas
    search_queries = [
        {
            "type": "key_players",
            "title": "Key Market Players & Competitors",
            "query": f"""Search for comprehensive competitive landscape analysis related to: {business_problem}

Find information about:
- Top 5-10 market leaders and their market share percentages
- Recent mergers, acquisitions, and strategic partnerships in this space
- Competitive positioning and differentiation strategies
- Revenue figures, growth rates, and financial performance of key players
- Geographic presence and market penetration
- Recent product launches, innovations, or strategic initiatives
- Venture capital investments and funding rounds in this sector

Focus on data from the last 6 months (since mid-2024) and include specific company names, figures, and dates where available."""
        },
        {
            "type": "consulting_insights", 
            "title": "Top Consulting Firm Recommendations",
            "query": f"""Search for recent strategic consulting reports and recommendations from top-tier firms regarding: {business_problem}

Look for insights from:
- McKinsey & Company reports and articles
- Boston Consulting Group (BCG) research and perspectives  
- Bain & Company insights and case studies
- Deloitte industry reports and strategic recommendations
- PwC analysis and market outlooks
- Accenture research and technology insights

Focus on:
- Published reports, white papers, and thought leadership from the last 6 months (mid-2024 onwards)
- Strategic frameworks and methodologies recommended for similar challenges
- Industry benchmarks and best practices
- Digital transformation recommendations
- Cost optimization and efficiency strategies
- Future-focused strategic advice and predictions"""
        },
        {
            "type": "porters_five",
            "title": "Porter's Five Forces Analysis",
            "query": f"""Conduct a comprehensive Porter's Five Forces analysis for the industry/market context of: {business_problem}

Analyze and provide specific details for each force:

1. COMPETITIVE RIVALRY:
- Number of competitors and market concentration
- Price competition intensity and profit margins
- Product differentiation levels
- Exit barriers and switching costs

2. SUPPLIER POWER:
- Number of suppliers and concentration
- Switching costs for suppliers
- Forward integration threats
- Input cost pressures and supply chain disruptions

3. BUYER POWER:
- Customer concentration and purchasing volume
- Price sensitivity and elasticity
- Backward integration potential
- Availability of substitute products

4. THREAT OF SUBSTITUTES:
- Alternative solutions and technologies
- Performance-to-price ratios of substitutes
- Customer propensity to substitute
- Disruptive innovation threats

5. BARRIERS TO ENTRY:
- Capital requirements and economies of scale
- Regulatory requirements and licensing
- Technology and expertise barriers
- Brand loyalty and network effects

Include recent examples from the last 6 months, specific companies, and quantitative data where available."""
        },
        {
            "type": "threats_risks",
            "title": "Market Threats & Emerging Risks", 
            "query": f"""Identify and analyze current and emerging threats, risks, and challenges for businesses dealing with: {business_problem}

Search for comprehensive risk assessment covering:

REGULATORY & COMPLIANCE RISKS:
- New legislation and regulatory changes (last 6 months)
- Compliance requirements and penalties
- Data privacy and security regulations
- Environmental and sustainability mandates

TECHNOLOGICAL THREATS:
- Disruptive technologies and innovation threats
- Cybersecurity risks and data breaches
- Technology obsolescence risks
- AI and automation displacement

ECONOMIC & MARKET RISKS:
- Economic downturn and recession impacts
- Inflation, interest rate changes, and currency fluctuations
- Supply chain disruptions and geopolitical tensions
- Market saturation and declining demand

COMPETITIVE THREATS:
- New entrants and disruptors
- Price wars and margin compression
- Technology disruption from startups
- Platform and ecosystem competition

Include specific examples from the last 6 months, recent incidents, probability assessments, and potential impact levels."""
        },
        {
            "type": "latest_trends",
            "title": "Latest Market Trends & Innovations",
            "query": f"""Research the latest market trends, emerging technologies, and innovation developments relevant to: {business_problem}

Focus on cutting-edge developments from the last 6 months (mid-2024 onwards):

TECHNOLOGY TRENDS:
- Artificial Intelligence and Machine Learning applications
- Automation and robotics adoption
- Cloud computing and edge technologies
- Internet of Things (IoT) and connectivity solutions
- Blockchain and Web3 applications

BUSINESS MODEL INNOVATIONS:
- Platform and ecosystem strategies
- Subscription and as-a-Service models
- Direct-to-consumer approaches
- Circular economy and sustainability initiatives
- Remote and hybrid work solutions

MARKET OPPORTUNITIES:
- Emerging market segments and demographics
- Sustainability and ESG-driven opportunities
- Digital transformation acceleration
- Health and wellness trends
- Gen Z and millennial consumption patterns

INVESTMENT & FUNDING TRENDS:
- Venture capital and private equity focus areas
- IPO trends and valuations
- Corporate innovation investments
- Government funding and incentives

Include specific company examples, investment amounts, growth projections, and adoption timelines from the last 6 months."""
        }
    ]
    
    market_intelligence = []
    
    for idx, search_item in enumerate(search_queries):
        print(f"Generating {search_item['title']} ({idx+1}/5)...")
        
        # Add delay between searches to avoid hitting model limits
        if idx > 0:
            import time
            print(f"Waiting 2 seconds before next search to avoid rate limits...")
            time.sleep(2)
        
        search_result = call_venice_search_api(search_item["query"], SEARCH_ANALYSIS_MODEL)
        
        if search_result.get("error"):
            print(f"Error in search for {search_item['type']}: {search_result['error']}")
            intelligence_item = {
                "type": search_item["type"],
                "title": search_item["title"],
                "content": f"Error retrieving data: {search_result['error']}",
                "key_insights": [],
                "confidence_level": "Low"
            }
        else:
            # Process the search result into structured intelligence
            content = search_result.get("content", "No content retrieved")
            
            intelligence_item = {
                "type": search_item["type"],
                "title": search_item["title"],
                "content": content,
                "key_insights": extract_key_insights_from_content(content),
                "confidence_level": "High" if len(content) > 200 else "Medium"
            }
        
        market_intelligence.append(intelligence_item)
    
    return market_intelligence

def extract_key_insights_from_content(content):
    """
    Extract key insights from search content using enhanced text analysis.
    Returns a list of key insights/bullet points.
    """
    if not content or len(content) < 50:
        return ["Limited information available"]
    
    import re
    
    # Enhanced extraction with multiple strategies
    key_insights = []
    
    # Strategy 1: Look for bullet points and numbered lists
    bullet_patterns = [
        r'[•\-\*]\s+([^.\n]+(?:\.[^.\n]*)*)',
        r'\d+\.\s+([^.\n]+(?:\.[^.\n]*)*)',
        r'>\s+([^.\n]+(?:\.[^.\n]*)*)'
    ]
    
    for pattern in bullet_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            insight = match.strip()
            if 30 < len(insight) < 150 and insight not in key_insights:
                key_insights.append(insight)
                if len(key_insights) >= 8:
                    break
    
    # Strategy 2: Look for sentences with high-value indicators
    if len(key_insights) < 5:
        sentences = re.split(r'[.!?]+', content)
        
        # Enhanced insight indicators with weights
        high_value_indicators = [
            "market share", "revenue", "growth rate", "billion", "million", "percent", "%",
            "leading", "dominant", "competitive advantage", "market leader", "first mover",
            "breakthrough", "innovation", "disruption", "transformation", "strategic",
            "investment", "funding", "acquisition", "merger", "partnership",
            "forecast", "projection", "expected", "anticipated", "emerging", "trend"
        ]
        
        medium_value_indicators = [
            "key", "important", "significant", "major", "critical", "essential",
            "opportunity", "risk", "challenge", "recommendation", "should", "must",
            "analysis", "study", "research", "report", "survey", "data"
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if 25 < len(sentence) < 180:
                sentence_lower = sentence.lower()
                
                # Score the sentence based on indicators
                score = 0
                score += sum(2 for indicator in high_value_indicators if indicator in sentence_lower)
                score += sum(1 for indicator in medium_value_indicators if indicator in sentence_lower)
                
                # Look for numerical data
                if re.search(r'\d+[%$]|\$\d+|\d+\s*(billion|million|percent|%)', sentence_lower):
                    score += 3
                
                # Look for company/brand names (capitalized words)
                if re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', sentence):
                    score += 1
                
                if score >= 3 and sentence not in key_insights:
                    key_insights.append(sentence)
                    if len(key_insights) >= 8:
                        break
    
    # Strategy 3: Extract specific data points
    if len(key_insights) < 3:
        # Look for specific patterns like percentages, dollar amounts, company names
        data_patterns = [
            r'([A-Z][a-zA-Z\s&]+(?:Inc|Corp|Company|LLC|Ltd)?)\s+(?:reported|achieved|announced|generated|posted|recorded)\s+[^.]{20,80}',
            r'(?:Market\s+share|Revenue|Growth|Sales|Profit)\s+(?:of|reached|increased|decreased|grew)\s+[^.]{20,80}',
            r'(?:\$\d+(?:\.\d+)?\s*(?:billion|million)|>\d+%|\d+%\s+(?:growth|increase|decrease))[^.]{0,60}'
        ]
        
        for pattern in data_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                insight = match.strip() if isinstance(match, str) else ' '.join(match).strip()
                if 20 < len(insight) < 150 and insight not in key_insights:
                    key_insights.append(insight)
                    if len(key_insights) >= 6:
                        break
    
    # Clean up and deduplicate
    cleaned_insights = []
    for insight in key_insights:
        # Remove extra whitespace and clean up
        cleaned = re.sub(r'\s+', ' ', insight).strip()
        # Remove duplicates and very similar insights
        if cleaned and len(cleaned) > 20 and cleaned not in cleaned_insights:
            # Check for substantial overlap with existing insights
            is_duplicate = False
            for existing in cleaned_insights:
                overlap = len(set(cleaned.lower().split()) & set(existing.lower().split()))
                if overlap > len(cleaned.split()) * 0.7:  # 70% word overlap
                    is_duplicate = True
                    break
            if not is_duplicate:
                cleaned_insights.append(cleaned)
    
    return cleaned_insights[:6] if cleaned_insights else ["Analysis completed - see full content for details"]

# --- Stage 3.5: Synthesis Report Generation ---
def generate_synthesis_report(original_problem, all_expert_insights, persona_definitions_for_context, market_intelligence=None):
    print("\n--- Stage 3.5: Generating Synthesis Report ---")
    
    # Prepare the context for the synthesis model
    insights_context = "\n\nOriginal Business Problem: " + original_problem + "\n"
    insights_context += "\n--- Collected Expert Insights ---\n"
    for idx, insight_package in enumerate(all_expert_insights):
        persona_name = insight_package.get("persona_name", f"Expert {idx+1}")
        definition = next((p.get("description", "N/A") for p in persona_definitions_for_context if p.get("name") == persona_name), "N/A")
        insights_context += f"\n**Expert: {persona_name}** (Role: {definition})\n"
        if insight_package.get("error"):
            insights_context += f"  Error: {insight_package.get('error')}\n"
            continue
        if insight_package.get("insights_and_analysis"):
            for item_idx, item in enumerate(insight_package["insights_and_analysis"]):
                insights_context += f"  - Insight {item_idx+1}: {item.get('insight', 'N/A')}\n"
                insights_context += f"    Reasoning: {item.get('supporting_reasoning', 'N/A')}\n"
                insights_context += f"    Confidence: {item.get('confidence_level', 'N/A')}\n"
                if item.get("identified_risks") and len(item["identified_risks"]) > 0:
                    risks_list = ', '.join(item["identified_risks"])
                    insights_context += f"    Risks: {risks_list}\n"
                if item.get("identified_opportunities") and len(item["identified_opportunities"]) > 0:
                    opportunities_list = ', '.join(item["identified_opportunities"])
                    insights_context += f"    Opportunities: {opportunities_list}\n"
        else:
            insights_context += "  No specific insights provided.\n"
    
    # Add market intelligence context
    if market_intelligence:
        insights_context += "\n--- Market Intelligence & Real-Time Analysis ---\n"
        for intel in market_intelligence:
            insights_context += f"\n**{intel.get('title', 'Market Analysis')}**\n"
            insights_context += f"  Confidence: {intel.get('confidence_level', 'Medium')}\n"
            if intel.get('key_insights'):
                for insight in intel['key_insights']:
                    insights_context += f"  • {insight}\n"
            insights_context += f"  Full Content: {intel.get('content', 'No content')[:300]}...\n"
    
    insights_context += "\n---\n"

    synthesis_prompt = f"""
    You are a Chief Synthesis Officer. Your task is to analyze the provided original business problem and a collection of insights from various expert personas.
    Based on all this information, generate a concise and actionable synthesis report.

    {insights_context}

    Your response MUST be a JSON object adhering to the specified schema. The report should include:
    1.  `cohesive_summary`: A brief overall summary of the situation and key findings (2-3 sentences).
    2.  `key_themes`: A list of 2-4 dominant themes or patterns that emerged from the expert analyses.
    3.  `potential_blind_spots`: A list of 1-3 areas that might have been overlooked, have conflicting opinions, or carry notable uncertainty/low confidence across personas.
    4.  `actionable_next_steps`: A list of 3-5 concrete, actionable next steps to address the business problem. Each step should include:
        *   `step_description` (string): What needs to be done.
        *   `priority` (string enum: "High", "Medium", "Low").
        *   `suggested_rationale` (string, optional): Brief reason why this step is important based on the insights.
    """

    messages = [{"role": "user", "content": synthesis_prompt}]

    actual_schema_for_synthesis = {
        "type": "object",
        "properties": {
            "cohesive_summary": {"type": "string"},
            "key_themes": {"type": "array", "items": {"type": "string"}},
            "potential_blind_spots": {"type": "array", "items": {"type": "string"}},
            "actionable_next_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step_description": {"type": "string"},
                        "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "suggested_rationale": {"type": ["string", "null"]}
                    },
                    "required": ["step_description", "priority"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["cohesive_summary", "key_themes", "potential_blind_spots", "actionable_next_steps"],
        "additionalProperties": False
    }

    api_response_data = call_venice_api(
        model_id=INSIGHT_GENERATION_MODEL, # Can use the same model, or a more powerful one if available/needed
        messages=messages,
        schema_name_for_api="SynthesisReportGenerator",
        actual_json_schema=actual_schema_for_synthesis
    )

    if api_response_data and not api_response_data.get("error"):
        print("Successfully generated synthesis report.")
        return api_response_data
    else:
        print("Error: Synthesis report generation failed or returned error structure.")
        print("API Response Data for synthesis:", api_response_data)
        return {"error": "Failed to generate synthesis report", "details": api_response_data.get("details", api_response_data.get("error"))}


# --- API Endpoints ---
@app.route('/health', methods=['GET'])
@cross_origin(supports_credentials=True)
def health_check():
    return jsonify({"status": "healthy", "message": "AI Expert Panel backend is running"}), 200

@app.route('/test', methods=['POST'])
@cross_origin(supports_credentials=True)
def test_cors():
    return jsonify({"status": "success", "message": "CORS is working for POST requests"}), 200

@app.route('/test_venice', methods=['POST'])
@cross_origin(supports_credentials=True)
def test_venice_api():
    """Simple test endpoint to check Venice AI connectivity"""
    try:
        print("Testing basic Venice AI connectivity...")
        simple_payload = {
            "model": "qwen-2.5-qwq-32b",
            "messages": [{"role": "user", "content": "Say hello"}],
            "temperature": 0.7,
            "max_completion_tokens": 50
        }
        headers = {
            "Authorization": f"Bearer {VENICE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        print("Sending simple request to Venice AI...")
        response = requests.post(VENICE_CHAT_COMPLETIONS_URL, json=simple_payload, headers=headers, timeout=120) # Increased timeout to match main API calls
        print(f"Venice AI response status: {response.status_code}")
        
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Venice AI is accessible", "response_preview": str(response.text)[:200]})
        else:
            return jsonify({"status": "error", "message": f"Venice AI returned status {response.status_code}", "details": response.text})
            
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "message": "Venice AI request timed out after 120 seconds"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Venice AI test failed: {str(e)}"})

@app.route('/process_problem', methods=['POST'])
@cross_origin(supports_credentials=True)
@limiter.limit("10 per hour")  # Limit expensive AI operations
def handle_process_problem():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    business_problem_text = data.get('business_problem')

    if not business_problem_text:
        return jsonify({"error": "Missing 'business_problem' in request"}), 400

    print(f"\n--- Received problem: {business_problem_text[:100]}... ---")

    print("\n--- Stage 2: Generating Expert Personas ---")
    personas = generate_expert_personas(business_problem_text)

    if not personas: 
        print("Could not generate personas. Aborting.")
        return jsonify({"error": "Persona generation failed. Check backend console for details."}), 500

    all_insights_by_persona = []
    print(f"\n--- Stage 3: Getting Insights from Each Persona (Total: {len(personas)}) ---")
    for idx, persona in enumerate(personas):
        persona_name = persona.get('name', f'Persona {idx+1}') if isinstance(persona, dict) else f'Persona {idx+1}'
        print(f"Processing {idx+1}/{len(personas)}: {persona_name}")
        
        if not isinstance(persona, dict):
            print(f"Skipping invalid persona object: {persona}")
            all_insights_by_persona.append({"persona_name": "Invalid Persona Object", "insights_and_analysis": [], "error": "Invalid persona structure received."})
            continue
        
        try:
            persona_insights = get_insights_from_persona(business_problem_text, persona)
            all_insights_by_persona.append(persona_insights)
            print(f"Completed {idx+1}/{len(personas)}: {persona_name}")
        except Exception as e:
            print(f"Error getting insights from {persona.get('name', 'Unknown')}: {e}")
            all_insights_by_persona.append({
                "persona_name": persona.get('name', 'Unknown Persona'),
                "insights_and_analysis": [],
                "error": f"Processing failed: {str(e)}"
            })
            print(f"Failed {idx+1}/{len(personas)}: {persona_name} - continuing with next persona")
    
    # Generate market intelligence 
    print("\n--- Stage 3.2: Generating Market Intelligence ---")
    market_intelligence = generate_market_intelligence(business_problem_text)
    
    # Call the new synthesis function with market intelligence
    synthesis_report = generate_synthesis_report(business_problem_text, all_insights_by_persona, personas, market_intelligence)

    # Stage 4 is now effectively handled by the synthesis report generation and what's returned below.
    print("\n--- Processing Complete (including synthesis) ---")
    final_output = {
        "original_problem": business_problem_text,
        "generated_personas_count": len(personas) if isinstance(personas, list) else 0,
        "persona_definitions": personas,
        "expert_insights": all_insights_by_persona,
        "market_intelligence": market_intelligence,
        "synthesis_report": synthesis_report,
        "analysis_summary": {
            "total_experts": TOTAL_EXPERTS,
            "regular_experts": len(personas) if isinstance(personas, list) else 0,
            "search_experts": len(market_intelligence) if market_intelligence else 0,
            "models_used": {
                "persona_generation": PERSONA_GENERATION_MODEL,
                "expert_analysis": INSIGHT_GENERATION_MODEL,
                "market_intelligence": SEARCH_ANALYSIS_MODEL,
                "synthesis": SYNTHESIS_MODEL
            }
        }
    }
    return jsonify(final_output)

# --- Main Execution ---
if __name__ == '__main__':
    import os
    print("Starting Flask app...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 