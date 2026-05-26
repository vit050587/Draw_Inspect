#!/usr/bin/env python3
import json
import re

def parse_elements_file(filepath):
    """Parse elements.txt and convert to hierarchical JSON structure."""
    
    result = []
    
    # Dictionary to store hierarchy
    categories = {}  # code_category -> {category_name, purposes: {}}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            content = line
            
            # Parse the line: code parts + name + optional IFC class
            tokens = content.split()
            if len(tokens) < 2:
                continue
            
            # Extract code parts (ЭЛ XX XX XX XX format)
            code_parts = []
            name_start_idx = 0
            
            # First token should be 'ЭЛ'
            if tokens[0] == 'ЭЛ':
                code_parts.append('ЭЛ')
                # Second token is the category number
                if len(tokens) > 1 and tokens[1].isdigit():
                    code_parts.append(tokens[1])
                    name_start_idx = 2
                    
                    # Continue collecting numeric tokens for deeper levels
                    for j in range(2, len(tokens)):
                        if tokens[j].isdigit():
                            code_parts.append(tokens[j])
                            name_start_idx = j + 1
                        else:
                            break
            
            # Reconstruct the full code
            full_code = ' '.join(code_parts)
            
            # Extract name and IFC class
            remaining_tokens = tokens[name_start_idx:]
            ifc_class = None
            
            # Check if last token is an IFC class (starts with Ifc or ifc)
            if remaining_tokens and (remaining_tokens[-1].startswith('Ifc') or remaining_tokens[-1].startswith('ifc')):
                ifc_class = remaining_tokens[-1]
                # Fix case: ifcBeam -> IfcBeam
                if ifc_class.startswith('ifc'):
                    ifc_class = 'Ifc' + ifc_class[3:]
                name_tokens = remaining_tokens[:-1]
            else:
                name_tokens = remaining_tokens
            
            name = ' '.join(name_tokens) if name_tokens else None
            
            # Determine level based on number of code parts (after ЭЛ)
            # ЭЛ 10 -> category (level 1)
            # ЭЛ 10 10 -> purpose (level 2)
            # ЭЛ 10 10 10 -> class (level 3)
            # ЭЛ 10 10 10 01 -> subclass (level 4)
            
            level = len(code_parts) - 1  # Subtract 1 for "ЭЛ"
            
            if level == 1:  # Category
                cat_code = full_code
                categories[cat_code] = {
                    'category': name,
                    'purposes': {}
                }
                
            elif level == 2:  # Purpose
                cat_code = ' '.join(code_parts[:2])
                purpose_code = full_code
                
                if cat_code in categories:
                    categories[cat_code]['purposes'][purpose_code] = {
                        'purpose': name,
                        'classes': {}
                    }
                    
            elif level == 3:  # Class
                cat_code = ' '.join(code_parts[:2])
                purpose_code = ' '.join(code_parts[:3])
                class_code = full_code
                
                if cat_code in categories and purpose_code in categories[cat_code]['purposes']:
                    categories[cat_code]['purposes'][purpose_code]['classes'][class_code] = {
                        'class': name,
                        'ifcClass': ifc_class,
                        'subclasses': {}
                    }
                    
            elif level == 4:  # Subclass
                cat_code = ' '.join(code_parts[:2])
                purpose_code = ' '.join(code_parts[:3])
                class_code = ' '.join(code_parts[:4])
                subclass_code = full_code
                
                if cat_code in categories and purpose_code in categories[cat_code]['purposes']:
                    if class_code in categories[cat_code]['purposes'][purpose_code]['classes']:
                        categories[cat_code]['purposes'][purpose_code]['classes'][class_code]['subclasses'][subclass_code] = {
                            'subclass': name,
                            'ifcClass': ifc_class
                        }
    
    # Build the result list
    for cat_code, cat_data in categories.items():
        # Level 1: Category only
        result.append({
            'code_category': cat_code,
            'code_purpose': None,
            'code_class': None,
            'code_subclass': None,
            'category': cat_data['category'],
            'purpose': None,
            'class': None,
            'subclass': None,
            'ifcClass': None
        })
        
        # Level 2: Purpose
        for purpose_code, purpose_data in cat_data['purposes'].items():
            result.append({
                'code_category': cat_code,
                'code_purpose': purpose_code,
                'code_class': None,
                'code_subclass': None,
                'category': cat_data['category'],
                'purpose': purpose_data['purpose'],
                'class': None,
                'subclass': None,
                'ifcClass': None
            })
            
            # Level 3: Class
            for class_code, class_data in purpose_data['classes'].items():
                result.append({
                    'code_category': cat_code,
                    'code_purpose': purpose_code,
                    'code_class': class_code,
                    'code_subclass': None,
                    'category': cat_data['category'],
                    'purpose': purpose_data['purpose'],
                    'class': class_data['class'],
                    'subclass': None,
                    'ifcClass': class_data['ifcClass']
                })
                
                # Level 4: Subclass
                for subclass_code, subclass_data in class_data['subclasses'].items():
                    result.append({
                        'code_category': cat_code,
                        'code_purpose': purpose_code,
                        'code_class': class_code,
                        'code_subclass': subclass_code,
                        'category': cat_data['category'],
                        'purpose': purpose_data['purpose'],
                        'class': class_data['class'],
                        'subclass': subclass_data['subclass'],
                        'ifcClass': subclass_data['ifcClass']
                    })
    
    return result


def main():
    input_file = '/workspace/data/elements.txt'
    output_file = '/workspace/data/elements.json'
    
    result = parse_elements_file(input_file)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Converted {len(result)} entries to {output_file}")


if __name__ == '__main__':
    main()
