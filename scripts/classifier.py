import base64
from openai import OpenAI

# Initialize client - API key should be set via environment variable OPENAI_API_KEY
client = None

def initialize_client():
    global client
    try:
        client = OpenAI()
        return True
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")
        return False

def classify_drawings(images):
    """
    Classify each drawing image into categories.
    Returns a list of classifications with page numbers and types.
    """
    if not images:
        return []
    
    if client is None:
        if not initialize_client():
            # Return mock classifications for development
            return _mock_classifications(images)
    
    classifications = []
    
    classification_prompt = """
    You are an expert in architectural drawings and building plans.
    Classify this drawing into one of these categories:
    - residential_floor_plan (жилой поэтажный план)
    - technical_floor (технический этаж)
    - parking_basement (паркинг/подземный этаж)
    - building_elevation (все здание вид сбоку)
    - site_plan (генплан)
    - section (разрез)
    - other (другое)
    
    Respond ONLY with the category name in English from the list above.
    """
    
    for img_info in images:
        try:
            image_path = img_info['path']
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": classification_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=50
            )
            
            category = response.choices[0].message.content.strip().lower()
            
            classifications.append({
                'page_num': img_info['page_num'],
                'source_file': img_info['source_file'],
                'category': category,
                'image_path': image_path
            })
            
        except Exception as e:
            print(f"Error classifying image {img_info['path']}: {e}")
            classifications.append({
                'page_num': img_info['page_num'],
                'source_file': img_info['source_file'],
                'category': 'unknown',
                'image_path': img_info['path']
            })
    
    return classifications

def _mock_classifications(images):
    """Return mock classifications for development without API."""
    categories = ['residential_floor_plan', 'technical_floor', 'parking_basement', 
                  'building_elevation', 'site_plan', 'section', 'other']
    
    classifications = []
    for i, img_info in enumerate(images):
        classifications.append({
            'page_num': img_info['page_num'],
            'source_file': img_info['source_file'],
            'category': categories[i % len(categories)],
            'image_path': img_info['path']
        })
    
    return classifications
