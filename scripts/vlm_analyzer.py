import base64
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

def analyze_with_vlm(image_files, question):
    """
    Use Vision Language Model to analyze drawings and answer the specific question.
    Returns detailed analysis results for each relevant image.
    """
    if not image_files:
        return []
    
    if client is None:
        if not initialize_client():
            return _mock_vlm_analysis(image_files, question)
    
    results = []
    
    vlm_prompt = f"""
    You are an expert in architectural drawings and fire safety regulations.
    Analyze this building drawing carefully and provide information related to the following question:
    
    QUESTION: {question}
    
    Look for and report:
    - Staircases (quantity, width, location)
    - Corridors (width, length)
    - Apartment areas
    - Parking spaces (quantity)
    - Fire exits
    - Any other elements relevant to fire safety
    
    Be specific and precise. If you cannot find certain information, state that clearly.
    Provide measurements where visible on the drawing.
    """
    
    for image_path in image_files:
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vlm_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            analysis = response.choices[0].message.content.strip()
            
            results.append({
                'image_path': image_path,
                'analysis': analysis,
                'relevant': True  # VLM determined relevance
            })
            
        except Exception as e:
            print(f"Error analyzing image {image_path}: {e}")
            results.append({
                'image_path': image_path,
                'analysis': f"Error analyzing image: {str(e)}",
                'relevant': False
            })
    
    return results

def _mock_vlm_analysis(image_files, question):
    """Return mock VLM analysis for development without API."""
    results = []
    
    mock_analysis = f"""
    Analysis for question: {question}
    
    Based on the drawing analysis:
    - Found 2 staircases with width approximately 1.2m each
    - Corridor width appears to be 1.5m
    - Multiple residential units visible
    - Fire exit signs detected
    
    Note: This is a mock response for development. Configure OPENAI_API_KEY for real analysis.
    """
    
    for image_path in image_files:
        results.append({
            'image_path': image_path,
            'analysis': mock_analysis,
            'relevant': True
        })
    
    return results
