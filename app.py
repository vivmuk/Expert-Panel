import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

# --- Configuration ---
VENICE_API_KEY = "GeD9cKbx1c54CWCTcGUold361VXLgFkMrDwu5iV6qJ" # Your hardcoded API key
VENICE_CHAT_COMPLETIONS_URL = "https://api.venice.ai/api/v1/chat/completions"
PERSONA_GENERATION_MODEL = "qwen-2.5-qwq-32b"
INSIGHT_GENERATION_MODEL = "qwen-2.5-qwq-32b"

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app, resources={r"/*":{"origins": "*"}}, supports_credentials=True)

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
        response = requests.post(VENICE_CHAT_COMPLETIONS_URL, json=payload, headers=headers, timeout=60) # Reduced timeout
        response_obj_for_logging = response
        response.raise_for_status()
        
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
        
        return structured_content
        
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


# --- Stage 2: Persona Generation & Definition ---
def generate_expert_personas(business_problem):
    persona_generation_prompt = f"""
    Given the business problem: "{business_problem}"

    Identify and define exactly 10 diverse expert personas that could offer unique and valuable insights.
    Include a mix of traditional business roles and some non-traditional or creative/futuristic roles.

    Your response MUST be a JSON object adhering to the specified schema. 
    The JSON should contain a single key "personas", which is an array of 10 persona objects.
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

# --- Stage 3.5: Synthesis Report Generation ---
def generate_synthesis_report(original_problem, all_expert_insights, persona_definitions_for_context):
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

@app.route('/process_problem', methods=['POST'])
@cross_origin(supports_credentials=True)
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
    print("\n--- Stage 3: Getting Insights from Each Persona ---")
    for persona in personas:
        if not isinstance(persona, dict):
            print(f"Skipping invalid persona object: {persona}")
            all_insights_by_persona.append({"persona_name": "Invalid Persona Object", "insights_and_analysis": [], "error": "Invalid persona structure received."})
            continue
        
        try:
            persona_insights = get_insights_from_persona(business_problem_text, persona)
            all_insights_by_persona.append(persona_insights)
        except Exception as e:
            print(f"Error getting insights from {persona.get('name', 'Unknown')}: {e}")
            all_insights_by_persona.append({
                "persona_name": persona.get('name', 'Unknown Persona'),
                "insights_and_analysis": [],
                "error": f"Processing failed: {str(e)}"
            })
    
    # Call the new synthesis function
    synthesis_report = generate_synthesis_report(business_problem_text, all_insights_by_persona, personas)

    # Stage 4 is now effectively handled by the synthesis report generation and what's returned below.
    print("\n--- Processing Complete (including synthesis) ---")
    final_output = {
        "original_problem": business_problem_text,
        "generated_personas_count": len(personas) if isinstance(personas, list) else 0,
        "persona_definitions": personas,
        "expert_insights": all_insights_by_persona,
        "synthesis_report": synthesis_report # Add the new report here
    }
    return jsonify(final_output)

# --- Main Execution ---
if __name__ == '__main__':
    import os
    print("Starting Flask app...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 