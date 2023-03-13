from pathlib import Path
import os

def copy_non_code_file(non_code_dir, not_include):
    path_file_dict = {}
    _dir = non_code_dir.replace(".", os.sep)
    for subdir, dirs, files in os.walk(_dir):
        file_list = []
        for file in files:
            filepath = Path(subdir, file)
            file_name = Path(filepath.name)
            file_list.append(str(file_name))
            for end in not_include:
                if file_name.suffix == end:
                    file_list.remove(str(file_name))
        if len(file_list) > 0:
            path_file_dict[str(filepath.parent).replace(os.sep, ".")] = file_list
        continue
    return path_file_dict


if __name__ == '__main__':

    files = copy_non_code_file(non_code_dir=f'bim2sim',
                               not_include=[".py", ".Dockerfile", ".pyc"])
    print(files)