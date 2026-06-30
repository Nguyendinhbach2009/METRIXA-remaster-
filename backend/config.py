"""
Configuration file for data paths and file ranges
"""

# Full base paths with {xxxx} placeholder for the number
BASE_PATH_JSON = '/home/dtth/proj_paper/duy/extracted_combined/{xxxx}/non_empty_aff_{xxxx}.json'
BASE_PATH_CSV = '/home/dtth/proj_paper/duck/output_shard/{xxxx}/result_many_prompts_deleted_empty.csv'

# File range configuration
FILE_START = 0  # Start number (e.g., 0001)
FILE_END = 508    # End number (e.g., 0002)

# Number formatting (4 digits with leading zeros)
FILE_NUMBER_FORMAT = "{:04d}"  # e.g., 0001, 0002, etc.

def get_json_file_path(file_number):
    """Get the full path for a JSON file by number"""
    number_str = FILE_NUMBER_FORMAT.format(file_number)
    return BASE_PATH_JSON.replace('{xxxx}', number_str)

def get_csv_file_path(file_number):
    """Get the full path for a CSV file by number"""
    number_str = FILE_NUMBER_FORMAT.format(file_number)
    return BASE_PATH_CSV.replace('{xxxx}', number_str)

def get_all_json_files():
    """Get all JSON file paths in the configured range"""
    return [get_json_file_path(i) for i in range(FILE_START, FILE_END + 1)]

def get_merge_json_file_path():
    """Get the path to the single merge.json file"""
    return '/home/dtth/proj_paper/duy/extracted_combined_merged/merge.json'

def get_all_csv_files():
    """Get all CSV file paths in the configured range"""
    return [get_csv_file_path(i) for i in range(FILE_START, FILE_END + 1)]