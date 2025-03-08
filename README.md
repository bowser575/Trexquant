# Trexquant
# EPS Extractor

A Python tool for extracting Earnings Per Share (EPS) values from financial HTML filings.

## Overview

This project extracts EPS (Earnings Per Share) values from financial reports in HTML format. It uses a sophisticated pattern-matching and scoring system to identify and select the most appropriate EPS value from each filing, with proper handling of:

- Basic vs. diluted EPS
- GAAP vs. non-GAAP values
- Various formats of negative numbers
- Footnote references
- Multi-row and multi-column tables

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/eps-extractor.git
   cd eps-extractor
   ```

2. Install the required dependencies:
   ```
   pip install pandas beautifulsoup4
   ```

## Usage

### Command Line

```bash
python eps_extractor.py --input_dir path/to/filings --output_file results.csv --verbose
```

Arguments:
- `--input_dir`: Directory containing HTML filings (default: 'Training_Filings')
- `--output_file`: Path for the output CSV file (default: 'eps_results.csv')
- `--verbose`: Enable detailed logging (optional)

### As a Module

```python
from eps_extractor import process_directory

# Process a directory of filings
results_df = process_directory('path/to/filings', verbose=False)

# Save results
results_df.to_csv('results.csv', index=False)
```

## How It Works

1. **Parsing**: Uses BeautifulSoup to parse HTML tables from financial filings
2. **Pattern Detection**: Identifies text patterns indicating EPS information
3. **Value Extraction**: Extracts numeric values with handling for negative numbers
4. **Classification**: Determines if values are basic/diluted and GAAP/non-GAAP
5. **Prioritization**: Scores each potential EPS value based on a rule system
6. **Selection**: Selects the most appropriate value based on priority rules

## Example Output

The tool generates a CSV file with two columns:
- `filename`: The HTML filing filename
- `eps`: The extracted EPS value

Example:
```
filename,eps
0000066740-20-000010.html,0.74
0000066932-20-000029.html,-0.53
0000067347-20-000005.html,1.22
```

