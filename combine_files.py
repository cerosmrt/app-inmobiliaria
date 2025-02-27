# Save this as combine_files.py in Z:\programming\Dad\
import os

root_folder = '.'  # Current directory (Z:\programming\Dad)
output_file = 'all_code.txt'

# Extensions to include (adjust as needed)
valid_extensions = ('.py', '.html', '.css', '.js')

def combine_files(directory, output):
    with open(output, 'w', encoding='utf-8') as outfile:
        for root, dirs, files in os.walk(directory):
            # Skip unwanted folders
            if any(exclude in root for exclude in ('venv', '__pycache__', 'instance', 'migrations')):
                continue
            for file in files:
                if file.endswith(valid_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            outfile.write(f'\n--- File: {file_path} ---\n')
                            outfile.write(infile.read())
                            outfile.write('\n')
                        print(f"Added: {file_path}")
                    except Exception as e:
                        print(f"Skipped {file_path}: {str(e)}")

combine_files(root_folder, output_file)
print(f"All files combined into {output_file}")