from openai import OpenAI

client = None

def initialize_client():
    global client
    try:
        client = OpenAI()
        return True
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")
        return False

def generate_response(vlm_results, question):
    """
    Use LLM to generate a structured response based on VLM analysis results.
    Returns a formatted answer with specific page references.
    """
    if not vlm_results:
        return {
            'answer': 'No analysis results available.',
            'page_references': [],
            'summary': ''
        }
    
    if client is None:
        if not initialize_client():
            return _mock_generate_response(vlm_results, question)
    
    # Prepare context from VLM results
    context_parts = []
    for i, result in enumerate(vlm_results):
        if result.get('relevant', False):
            # Extract page number from image path
            image_path = result['image_path']
            page_num = extract_page_number(image_path)
            
            context_parts.append(f"""
            PAGE {page_num}:
            {result['analysis']}
            """)
    
    context = "\n\n".join(context_parts)
    
    llm_prompt = f"""
    You are an assistant specializing in fire safety analysis of building drawings.
    
    USER QUESTION: {question}
    
    ANALYSIS RESULTS FROM DRAWINGS:
    {context}
    
    Based on the analysis above, provide a structured response:
    
    1. Give a clear, direct answer to the question
    2. List specific findings with exact measurements where available
    3. For each finding, specify which page/drawing it was found on
    4. If information is not available or unclear, state that explicitly
    
    Format your response in JSON like this:
    {{
        "answer": "Direct answer to the question",
        "findings": [
            {{
                "description": "Specific finding",
                "page_number": 5,
                "confidence": "high/medium/low"
            }}
        ],
        "summary": "Brief summary of all findings"
    }}
    
    Respond ONLY with valid JSON, no additional text.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that responds in JSON format."},
                {"role": "user", "content": llm_prompt}
            ],
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content.strip())
        
        # Add page references list for frontend
        page_refs = list(set([f['page_number'] for f in result.get('findings', []) if 'page_number' in f]))
        result['page_references'] = sorted(page_refs)
        
        return result
        
    except Exception as e:
        print(f"Error generating response: {e}")
        return _mock_generate_response(vlm_results, question)

def extract_page_number(image_path):
    """Extract page number from image filename."""
    import re
    match = re.search(r'page_(\d+)', image_path)
    if match:
        return int(match.group(1))
    return 1

def _mock_generate_response(vlm_results, question):
    """Return mock response for development without API."""
    page_numbers = []
    findings = []
    
    for result in vlm_results:
        page_num = extract_page_number(result['image_path'])
        page_numbers.append(page_num)
        findings.append({
            'description': f"Analysis from page {page_num}: Staircases detected, corridor width ~1.5m",
            'page_number': page_num,
            'confidence': 'medium'
        })
    
    return {
        'answer': f"Based on the analysis of {len(page_numbers)} drawing(s), here are the findings related to: {question}",
        'findings': findings,
        'page_references': sorted(list(set(page_numbers))),
        'summary': 'Multiple relevant elements found across the analyzed drawings. Configure OPENAI_API_KEY for detailed analysis.'
    }
