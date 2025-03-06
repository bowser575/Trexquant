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
        r'(?:basic|diluted)?\s*earnings\s*(?:\(loss\))?\s*per\s*(?:common|outstanding)?\s*share',
        r'(?:basic|diluted)?\s*loss\s*per\s*(?:common|outstanding)?\s*share',
        r'earnings\s*\(loss\)\s*per\s*(?:common|outstanding)?\s*share',
        r'net\s*(?:income|loss|earnings)\s*(?:attributable\s*to\s*[a-z\s]+)?\s*per\s*share',
        r'income\s*\(loss\)\s*per\s*share',
        r'\beps\b',
        r'earnings\s*per\s*share'
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
            row_text = row.get_text().lower().strip()
            
            if check_eps_pattern(row_text):
                # Look for cells containing a value in current row
                cells = row.find_all('td')
                if verbose:
                    print(f"Found EPS pattern in row: {row_text[:100]}...")
                
                # Get basic/diluted classification
                current_basic, current_diluted = is_basic_eps(row_text)
                
                # Get GAAP classification
                current_gaap = is_gaap_eps(row_text)
                
                # Check if this row has values
                found_value = False
                row_values = []
                possible_negative = False  # Flag for checking split parentheses
                
                for cell in cells:
                    cell_text = cell.get_text().strip()
                    
                    # Check if this cell might be the start of a split negative number
                    if '(' in cell_text and not ')' in cell_text and re.search(r'([\d\.]+)', cell_text):
                        possible_negative = True
                    
                    value = extract_numeric_value(cell_text)
                    
                    # If the value starts with an opening parenthesis and has a number, mark it as negative
                    if value is not None and cell_text.strip().startswith('(') and not cell_text.strip().endswith(')'):
                        # Ensure the value is negative if it came from a cell with an opening parenthesis
                        if not value.startswith('-'):
                            value = f"-{value}"
                    
                    if value is not None:
                        found_value = True
                        
                        # Determine if this specific cell is likely basic or diluted
                        cell_is_basic = 'basic' in cell_text.lower() or (current_basic and not current_diluted)
                        cell_is_diluted = 'diluted' in cell_text.lower() or (current_diluted and not current_basic)
                        
                        row_values.append({
                            'value': value,
                            'basic': cell_is_basic,
                            'diluted': cell_is_diluted,
                            'gaap': current_gaap
                        })
                        
                        if verbose:
                            print(f"Found value in current row: {value}")
                
                # If no values found in current row or we suspect partial parentheses, check the next row
                if (not found_value or possible_negative) and i + 1 < len(rows):
                    next_row = rows[i + 1]
                    next_cells = next_row.find_all('td')
                    next_row_text = next_row.get_text().lower().strip()
                    
                    # Get classifications from next row
                    next_basic, next_diluted = is_basic_eps(next_row_text)
                    next_gaap = is_gaap_eps(next_row_text)
                    
                    if verbose:
                        print(f"Checking next row for values...")
                    
                    for cell in next_cells:
                        cell_text = cell.get_text().strip()
                        value = extract_numeric_value(cell_text)
                        
                        if value is not None:
                            # If previous row had a potential negative start, mark this as negative
                            if possible_negative and not value.startswith('-'):
                                value = f"-{value}"
                                
                            # Determine if this specific cell is likely basic or diluted
                            cell_is_basic = 'basic' in cell_text.lower() or (next_basic and not next_diluted)
                            cell_is_diluted = 'diluted' in cell_text.lower() or (next_diluted and not next_basic)
                            
                            row_values.append({
                                'value': value,
                                'basic': cell_is_basic,
                                'diluted': cell_is_diluted,
                                'gaap': next_gaap
                            })
                            
                            if verbose:
                                print(f"Found value in next row: {value}")
                
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
            
            for result in results:
                result['filename'] = filename
            
            all_results.extend(results)
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(all_results)
    return df

# Example usage
if __name__ == "__main__":
    # Process a single file
    file_path = 'Training_Filings/0000008947-20-000044.html'
    results = extract_eps_from_filing(file_path, verbose=True)
    
    print("\nExtracted EPS values:")
    for i, result in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(f"Row text: {result['row_text']}")
        print(f"Basic: {result['basic']}, Diluted: {result['diluted']}, GAAP: {result['gaap']}")
        print(f"Value: {result['value']}")
        print(f"All values: {result['all_values']}")
    
    # Uncomment to process an entire directory
    # directory_path = 'Training_Filings'
    # results_df = process_directory(directory_path)
    # results_df.to_csv('eps_results.csv', index=False)
    # print(f"Processed {len(results_df)} EPS entries from {results_df['filename'].nunique()} files")