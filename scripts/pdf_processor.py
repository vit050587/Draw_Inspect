import fitz  # PyMuPDF
import os

def extract_pages_to_images(pdf_path, output_folder):
    """
    Extract all pages from a PDF file as images.
    Returns a list of dictionaries with image paths and metadata.
    """
    images = []
    
    try:
        doc = fitz.open(pdf_path)
        filename = os.path.basename(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render page to image (zoom=2.0 for better quality)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            # Save image
            image_filename = f"{filename}_page_{page_num + 1}.png"
            image_path = os.path.join(output_folder, image_filename)
            pix.save(image_path)
            
            images.append({
                'path': image_path,
                'page_num': page_num + 1,
                'source_file': filename
            })
        
        doc.close()
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")
    
    return images
