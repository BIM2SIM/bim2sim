import re
from pathlib import Path
import subprocess
import bim2sim

def count_functions_with_correct_docstrings(directory):
    """Check how many functions have no docstrings and structure the output in a dict."""
    result = subprocess.run(['pydocstyle', directory], capture_output=True, text=True)
    output = result.stdout

    output_list = output.splitlines()

    functions_without_docstrings = 0
    last_function_index = 0
    structured_messages = {}
    pattern = r'D\d{3}:'
    for i, line in enumerate(output_list):

        # error indicators are always starting with "DXXX:"
        matches = [match[:-1] for match in re.findall(pattern, line)]
        if matches:
            error_msg = line
            file_msg = str(output_list[last_function_index:i])
            last_function_index = i+1
            # ignore aixlib submodule
            if r"\\plugins\\AixLib\\" in file_msg:
                continue
            functions_without_docstrings += 1
            structured_messages[file_msg] = error_msg


    return functions_without_docstrings, structured_messages


def generate_markdown_table(data):
    max_line_length = 100
    table = "| done | Function                  | Error |\n|------|---------------------------|-------|\n"

    for key, value in data.items():
        key = key.replace("|", "\\|")  # Ersetze "|" durch "\|"

        # Entferne den angegebenen Teilstring, falls vorhanden
        key = key.split('bim2sim', 1)[-1].strip()

        # Füge Zeilenumbrüche in die erste Spalte ein, wenn nötig
        key_lines = [key[i:i + max_line_length] for i in range(0, len(key), max_line_length)]
        key = " \n".join(key_lines).replace('\n', ' ')

        value = value.replace("|", "\\|")  # Ersetze "|" durch "\|"
        table += f"| [ ] | {key.ljust(26)} | {value} |\n"

    return table


# run the function against current bim2sim repository
functions_with_docstrings, structured_messages = count_functions_with_correct_docstrings(Path(bim2sim.__file__).parent)
markdown_table = generate_markdown_table(structured_messages)
print(f'Number of cuntions with Docstrings: {functions_with_docstrings}')

print(markdown_table)
