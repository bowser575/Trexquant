import pandas as pd 
from bs4 import BeautifulSoup
import os 
import re

def extract_numeric_value(text):
    """
    Extract and normalize a numeric value, handling negative numbers in various formats.
    
    Args:
        text: Text containing a potential numeric value
        
    Returns:
        Normalized numeric value as a string, or None if no valid number found
    """
    if not text:
        return None
        
    # Clean the text
    cleaned_text = text.replace('$', '').replace(',', '').strip()
    
    # Handle case where opening parenthesis is present but closing one is missing
    # This happens when parentheses are split across cells
    if cleaned_text.startswith('(') and not cleaned_text.endswith(')'):
        match = re.search(r'\(?([\d\.]+)', cleaned_text)
        if match:
            return f"-{match.group(1)}"
    
    # Handle normal parentheses case
    if '(' in cleaned_text and ')' in cleaned_text:
        # Extract the number inside parentheses
        match = re.search(r'\(([\d\.]+)\)', cleaned_text)
        if match:
            return f"-{match.group(1)}"
    
    # Handle numbers with explicit negative signs
    if re.search(r'^\s*[\-−–]', cleaned_text):  # Handle various dash characters
        match = re.search(r'([\d\.]+)', cleaned_text)
        if match:
            return f"-{match.group(1)}"
    
    # Special case for closing parenthesis only - ignore it
    if cleaned_text == ')':
        return None
    
    # Normal number extraction
    match = re.search(r'([\d\.]+)', cleaned_text)
    if match:
        return match.group(1)
    
    return None

def check_eps_pattern(text):
    """
    Check if text contains patterns indicating EPS (Earnings Per Share) information.
    
    Args:
        text: Text to check for EPS patterns
        
    Returns:
        Boolean indicating if an EPS pattern was found
    """
    text = text.lower().strip()
    patterns = [
        r'(?:basic|diluted)?\s*earnings\s*(?:\(loss\))?\s*per\s*(?:common|outstanding|ordinary)?\s*share',
        r'(?:basic|diluted)?\s*loss\s*per\s*(?:common|outstanding|ordinary)?\s*share',
        r'earnings\s*\(loss\)\s*per\s*(?:common|outstanding|ordinary)?\s*share',
        r'net\s*(?:income|loss|earnings)\s*(?:attributable\s*to\s*[a-z\s]+)?\s*per\s*share',
        r'income\s*\(loss\)\s*per\s*share',
        r'\beps\b',
        r'earnings\s*per\s*share',
        r'net\s+income\s+available\s+to\s+common\s+stockholders\s+per\s+share',
        r'net\s+income\s+per\s+common\s+share',
        r'net\s*(?:\(loss\)\s*income|income\s*\(loss\))\s*per\s*share',
        

    ]
    
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            # Exclude weighted average share patterns
            if re.search(r'weighted|average|shares\s*outstanding', text, re.IGNORECASE):
                continue
            return True
    
    return False

def is_basic_eps(text):
    """
    Check if text refers to basic EPS, diluted EPS, or both.
    
    Args:
        text: Text to check for basic/diluted indicators
        
    Returns:
        Tuple of (is_basic, is_diluted) booleans
    """
    try:
        text = text.lower()
        has_basic = bool(re.search(r'\bbasic\b', text))
        has_diluted = bool(re.search(r'\bdiluted\b', text))
                # Special case: "basic and diluted" or "basic & diluted" should count as both
        if re.search(r'basic\s+(?:and|&)\s+diluted', text) or re.search(r'diluted\s+(?:and|&)\s+basic', text):
            has_basic = True
            has_diluted = True
        return has_basic, has_diluted
    except Exception as e:
        print(f"Error in is_basic_eps: {e}")
        return False, False

def is_gaap_eps(text):
    """
    Check if text refers to GAAP (not non-GAAP/adjusted) EPS.
    
    Args:
        text: Text to check for GAAP/non-GAAP indicators
        
    Returns:
        Boolean indicating if EPS is GAAP (True) or non-GAAP (False)
    """
    text = text.lower()
    return not re.search(r'non-gaap|non\s*gaap|adjusted', text)

def select_eps_value(row_values, row_text, table_idx):
    """
    Select the appropriate EPS value based on priority rules and create the final EPS entry.
    
    Args:
        row_values: List of dictionaries containing EPS values and classifications
        row_text: Text from the row where EPS pattern was found
        table_idx: Table index for reference
        
    Returns:
        Dictionary with selected EPS information
    """
    if not row_values:
        return None
        
    # Default to the first value entry
    selected_entry = row_values[0]
    
    # First try to find basic EPS (highest priority)
    basic_values = [item for item in row_values if item['basic']]
    if basic_values:
        selected_entry = basic_values[0]
    else:
        # If no basic found, try diluted
        diluted_values = [item for item in row_values if item['diluted']]
        if diluted_values:
            selected_entry = diluted_values[0]
    
    # Extract just the values for cleaner output
    value_list = [item['value'] for item in row_values]
    
    # Create the final EPS entry
    return {
        'table_idx': table_idx,
        'row_text': row_text[:100],  # Truncate for readability
        'basic': selected_entry['basic'],
        'diluted': selected_entry['diluted'],
        'gaap': selected_entry['gaap'],
        'value': selected_entry['value'],  # Prioritized value
        'all_values': value_list
    }

def extract_eps_from_filing(file_path, verbose=False):
    """
    Extract EPS values from an HTML financial filing.
    
    Args:
        file_path: Path to the HTML filing
        verbose: Whether to print detailed information during extraction
        
    Returns:
        List of dictionaries containing extracted EPS information
    """
    if verbose:
        print(f"Processing file: {file_path}")
    
    # Initialize the results list
    eps_values = []
    
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    
    for table_idx, table in enumerate(tables):
        # Get all rows for sequential access
        rows = table.find_all('tr')
        
        for i, row in enumerate(rows):
            row_text = row.get_text().lower().strip().replace(':', '')
            
            if check_eps_pattern(row_text):
                # Look for cells containing a value in current row
                cells = row.find_all('td')
                if verbose:
                    print(f"Found EPS pattern in row: {row_text[:100]}...")
                
                # Get basic/diluted classification
                basic, diluted = is_basic_eps(row_text)
                
                # Get GAAP classification
                gaap = is_gaap_eps(row_text)
                
                # Check if this row has values
                found_value = False
                row_values = []
                
                for cell in cells:
                    cell_text = cell.get_text().strip()
                    
                    value = extract_numeric_value(cell_text)
    
                    if value is not None:
                        found_value = True
                        
                        row_values.append({
                            'value': value,
                            'basic': basic,
                            'diluted': diluted,
                            'gaap': gaap
                        })
                        
                        if verbose:
                            print(f"Found value in current row: {value}")
                
                # If no values found in current row or we suspect partial parentheses, check the next row
                while (not found_value and i + 1 < len(rows)):
                    next_row = rows[i + 1]
                    next_cells = next_row.find_all('td')
                    next_row_text = next_row.get_text().lower().strip().replace(':', '')
                    
                    # Get classifications from next row
                    if not(basic and diluted):
                        basic, diluted = is_basic_eps(next_row_text)
                    gaap = is_gaap_eps(next_row_text)
                    
                    if verbose:
                        print(f"Checking next row for values...")
                        print(next_row_text)
                    for cell in next_cells:
                        cell_text = cell.get_text().strip()
                        value = extract_numeric_value(cell_text)
                        
                        if value is not None:
                            found_value = True
                            row_values.append({
                                'value': value,
                                'basic': basic,
                                'diluted': diluted,
                                'gaap': gaap
                            })
                            
                            if verbose:
                                print(f"Found value in next row: {value}")
                    i+=1
                # If we found at least one value, use helper method to select and create entry
                if row_values:
                    eps_entry = select_eps_value(row_values, row_text, table_idx)
                    eps_values.append(eps_entry)
    
    return eps_values

def process_directory(directory_path, verbose=False):
    """
    Process all HTML files in a directory to extract EPS values.
    
    Args:
        directory_path: Path to directory containing HTML filings
        verbose: Whether to print detailed information during extraction
        
    Returns:
        DataFrame containing all extracted EPS information
    """
    all_results = []
    
    for filename in os.listdir(directory_path):
        if filename.endswith('.html'):
            file_path = os.path.join(directory_path, filename)
            results = extract_eps_from_filing(file_path, verbose=verbose)
            value = select_final_eps(results)

            all_results.append({ "filename": filename,"eps": value})
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(all_results)
    return df
def extract_numeric_value(text):
    """
    Extract and normalize a numeric value, handling negative numbers in various formats.
    Prioritizes decimal numbers over likely footnote references (small integers).
    
    Args:
        text: Text containing a potential numeric value
        
    Returns:
        Normalized numeric value as a string, or None if no valid number found
    """
    if not text:
        return None
        
    # Clean the text
    cleaned_text = text.replace('$', '').replace(',', '').strip()
    
    # First try to find decimal numbers (more likely to be actual values)
    decimal_match = re.search(r'([\d]+\.[\d]+)', cleaned_text)
    if decimal_match:
        # Found a number with decimal places - likely the real value
        
        # Check if it's in parentheses (negative)
        if (f"({decimal_match.group(1)})" in cleaned_text or 
            f"( {decimal_match.group(1)} )" in cleaned_text):
            return f"-{decimal_match.group(1)}"
            
        # Check for explicit negative signs
        if re.search(r'^\s*[\-−–]', cleaned_text):
            return f"-{decimal_match.group(1)}"
            
        # Check for opening parenthesis without closing (split across cells)
        if cleaned_text.startswith('(') and not cleaned_text.endswith(')'):
            return f"-{decimal_match.group(1)}"
            
        return decimal_match.group(1)
    
    # Handle case where opening parenthesis is present but closing one is missing
    if cleaned_text.startswith('(') and not cleaned_text.endswith(')'):
        match = re.search(r'\(?([\d\.]+)', cleaned_text)
        if match:
            return f"-{match.group(1)}"
    
    # Handle normal parentheses case
    if '(' in cleaned_text and ')' in cleaned_text:
        # Extract the number inside parentheses
        match = re.search(r'\(([\d\.]+)\)', cleaned_text)
        if match:
            return f"-{match.group(1)}"
    
    # Handle numbers with explicit negative signs
    if re.search(r'^\s*[\-−–]', cleaned_text):  # Handle various dash characters
        match = re.search(r'([\d\.]+)', cleaned_text)
        if match:
            return f"-{match.group(1)}"
    
    # Special case for closing parenthesis only - ignore it
    if cleaned_text == ')':
        return None
    
    # Look for integers, but filter out likely footnote references
    int_matches = re.findall(r'\b(\d+)\b', cleaned_text)
    if int_matches:
        # Filter out small integers that are likely footnotes
        valid_ints = [n for n in int_matches if len(n) > 2 or int(n) > 20]
        if valid_ints:
            # Return the first valid integer
            return valid_ints[0]
        
        # If only small integers found, return the largest one as a fallback
        # (Less likely to be a footnote reference)
        if int_matches:
            largest = max(int_matches, key=lambda x: int(x))
            # Only return if it's part of a longer text (not standalone footnote)
            if len(cleaned_text) > len(largest) + 3:
                return largest
    
    return None
def select_final_eps(eps_values):
    """
    Select the final EPS value from all extracted values based on priority rules.
    
    Args:
        eps_values: List of dictionaries containing extracted EPS information.
        
    Returns:
        Single EPS value or None if no valid value found.
    """
    if not eps_values:
        return None
    # Filter out irrelevant entries (e.g., weighted average shares)
    filtered_values = [
        entry for entry in eps_values
        if not re.search(r'shares\s*outstanding', entry['row_text'], re.IGNORECASE)
    ]

    if not filtered_values:
        return None

    # Sort EPS values by priority (highest first)
    filtered_values.sort(key=lambda x: get_priority(x), reverse=True)

    # Group values by row text (to handle split values or duplicates)
    grouped_values = {}
    for entry in filtered_values:
        row_text = entry['row_text']
        if row_text not in grouped_values:
            grouped_values[row_text] = []
        grouped_values[row_text].append(entry)

    # Select the highest priority group
    top_group_text = next(iter(grouped_values))  # Get the first group (highest priority)
    top_group = grouped_values[top_group_text]

    # Check if all values in the group are the same (duplicates)
    unique_values = set(entry['value'] for entry in top_group)
    if len(unique_values) == 1:
        # If all values are the same, return the first one (no need to sum)
        return top_group[0]['value']
    else:
        # If values differ, sum them (to handle split values)
        try:
            total_value = sum(float(entry['value']) for entry in top_group)
            # Format the result to match the original precision
            decimal_places = len(top_group[0]['value'].split('.')[-1]) if '.' in top_group[0]['value'] else 0
            return f"{total_value:.{decimal_places}f}"
        except ValueError:
            # Fallback to the first value if summation fails
            return top_group[0]['value']

def get_priority(entry):
    """
    Assign a priority score to an EPS entry.
    Higher scores indicate higher priority.
    """
    priority = 0
    if entry['basic']:
        priority += 100  # Basic EPS has higher priority
    if entry['gaap']:
        priority += 50   # GAAP EPS has higher priority
    
    # Add score for specificity of row_text
    row_text = entry['row_text'].lower()
    if "basic" in row_text:
        priority += 30  # Boost for explicit "basic"
    elif "diluted" in row_text:
        priority += 20  # Boost for explicit "diluted"
    
    # Penalty for unrealistic EPS values
    try:
        value_float = float(entry['value'])
        if not (-100 <= value_float <= 100):  # EPS values are typically within this range
            priority -= 1000  # Large penalty for unrealistic values
    except ValueError:
        # Skip if value cannot be converted to float
        pass
    
    return priority
if __name__ == "__main__":
    df =process_directory('Training_Filings_test', verbose=False)
    df.to_csv('output.csv')