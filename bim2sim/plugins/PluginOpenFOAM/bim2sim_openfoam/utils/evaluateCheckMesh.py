import json
import os
import re
from collections import OrderedDict
from pathlib import Path




def parse_openfoam_log(file_path):
    def set_in_nested_dict(nested, keys, value):
        """Sets a value in a nested OrderedDict based on a list of keys."""
        for key in keys[:-1]:
            nested = nested.setdefault(key, OrderedDict())
        nested[keys[-1]] = value

    def process_key_value(line):
        """Splits a line into key and value."""
        match = re.match(r"(.*?)\s*[:=]\s*(.*)", line)
        if match:
            key, value = match.groups()
            return key.strip(), value.strip()
        return None, None

    def process_table(lines, headers=None):
        """Processes a table into nested dictionaries."""
        rows = [re.split(r"\s{2,}", line) for line in lines]
        header_parts = re.split(r"\s{3,}", headers)
        table_data = OrderedDict()
        if headers and rows and len(header_parts) == len(rows[0]) and len(
                header_parts)> 2:
            header_parts = re.split(r"\s{3,}", headers)
            for row in rows:
                row_key = row[0]
                row_values = OrderedDict((header_parts[i], row[i]) for i in range(1, len(row)))
                table_data[row_key] = row_values
        else:
            if headers and len(header_parts) > 1:
                table_data[header_parts[0]] = header_parts[1]
            for row in rows:
                if len(row) == 2:  # Key-value pair table
                    table_data[row[0]] = int(row[1]) if row[1].isdigit() else row[1]
        return table_data

    def parse_irregular_geometry(lines):
        """Parses irregular 'Checking geometry...' section lines."""
        result = OrderedDict()
        for line in lines:
            match = re.match(r"(.*?)(?:\s*=\s*(.*?))?\s*(OK\.)?$", line)
            if match:
                key, value, status = match.groups()
                key = key.strip()
                subkey_match = re.match(r"(.*)\s+\((.*?)\)", key)
                if subkey_match:
                    main_key, subkey = subkey_match.groups()
                    result.setdefault(main_key.strip(), OrderedDict())[subkey.strip()] = value or status
                elif status:
                    result[key] = {"value": value.strip() if value else None, "status": status}
                elif value:
                    result[key] = float(value) if value.replace('.', '', 1).isdigit() else value
                else:
                    result[key] = None
        return result

    data = OrderedDict()
    current_path = []
    table_buffer = []
    processing_table = False
    in_geometry_section = False
    geometry_lines = []
    last_line = ""
    table_done = False
    keep_key = None

    with open(file_path, "r") as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip()

        if not line or line.startswith(("//", "/*", "\\", "*", "|")):
            if table_buffer:
                table_done = True
            else:
                continue

        # Store the last line before "End" as "Mesh Quality Result"
        if line == "End":
            if last_line:
                set_in_nested_dict(data, ["Mesh Quality Result"], last_line)
            break
        last_line = line

        if "Checking geometry..." in line:
            in_geometry_section = True
            current_path = [line]
            continue

        if in_geometry_section:
            if re.match(r"^\s", line):  # Collect indented lines in geometry section
                geometry_lines.append(line.strip())
                continue
            else:  # End of geometry section
                in_geometry_section = False
                geometry_dict = parse_irregular_geometry(geometry_lines)
                set_in_nested_dict(data, current_path, geometry_dict)
                geometry_lines = []

        # End of a table
        if processing_table and not re.match(r"^\s", line):
            if table_buffer:
                headers = table_buffer.pop(0) if len(table_buffer[0].split()) > 2 else None
                table_dict = process_table(table_buffer, headers)
                if keep_key:
                    set_in_nested_dict(data, current_path + [keep_key], table_dict)
                    keep_key = None
                else:
                    set_in_nested_dict(data, current_path, table_dict)
                table_buffer = []
            processing_table = False

        if not line.startswith(" "):
            key, value = process_key_value(line)
            if not value:
                current_path = [line]
                continue

        key, value = process_key_value(line)
        if key and value:
            set_in_nested_dict(data, current_path + [key], value)
            continue
        elif key:
            keep_key = key
            continue

        if line.startswith(" "):
            processing_table = True
            table_done = False
            table_buffer.append(line.strip())

        if table_buffer and table_done:
            headers = table_buffer.pop(0) if len(table_buffer[0].split()) > 2 else None
            table_dict = process_table(table_buffer, headers)
            set_in_nested_dict(data, current_path, table_dict)
            table_done = False

        if geometry_lines:
            geometry_dict = parse_irregular_geometry(geometry_lines)
            set_in_nested_dict(data, current_path, geometry_dict)

    return data


if __name__ == '__main__':
    directory = Path(r'C:\Users\richter\Documents\CFD-Data\PluginTests')

    for diss_dir in directory.glob(r'grid_conv_1o1p\P1\bm1*'):
        # Check if "OpenFOAM" subdirectory exists within the current directory
        openfoam_dir = diss_dir / 'OpenFOAM'
        if openfoam_dir.is_dir():
            parsed_data = parse_openfoam_log(openfoam_dir /
                                             'logCheckMesh.compress')
            with open(openfoam_dir / 'mesh.json', 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=True, indent=4)
            print(json.dumps(parsed_data, indent=4))

