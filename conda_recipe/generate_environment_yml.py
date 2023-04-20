import jinja2
import argparse
import toml
# Definieren Sie die Variablen, die in der Vorlage verwendet werden sollen
class CreateEnvTemplate():
    def __init__(self, env_name, temp_file, env_file, pip_packages, conda_list, flag: str = "", vision: str = "*"):
        self.env_name = env_name
        self.temp_file = temp_file
        self.env_file = env_file
        self.pip_packages = pip_packages
        self.conda_list = conda_list
        self.flag = flag
        self.vision = vision

    def read_pip_packages(self):
        meine_liste = []
        for packages in self.pip_packages:
            with open(packages, 'r') as f:
                meine_liste.extend([zeile.strip() for zeile in f.readlines() if zeile.strip()])
        return meine_liste

    def read_conda_packages(self):
        meine_liste = []
        for packages in self.conda_list:
            with open(packages, 'r') as f:
                meine_liste.extend([zeile.strip() for zeile in f.readlines() if zeile.strip()])
        self.change_list_entry(meine_liste)
        return meine_liste

    def change_list_entry(self, liste):
        for i, value in enumerate(liste):
            if value.find("bim2sim") > -1:
                liste[i] = f'{value}=={self.vision}{self.flag}'
        return liste

    def create_template(self):
        pip_list = self.read_pip_packages()
        conda_list = self.read_conda_packages()
        template_vars = {
            'environment_name': self.env_name,
            'python_version': '3.9',
            'pip_list': pip_list,
            'conda_list': conda_list}
        # Laden Sie die Vorlagendatei
        with open(self.temp_file) as f:
            template = jinja2.Template(f.read())
        # Füllen Sie die Vorlage aus
        result = template.render(template_vars)
        # Schreiben Sie das Ergebnis in eine Datei
        with open(self.env_file, 'w') as f:
            f.write(result)

if __name__ == '__main__':
    # Einrichten der Argumente
    parser = argparse.ArgumentParser(description='Ein Beispiel-Skript mit Argumenten')
    parser.add_argument('--bim2sim-version', type=str, help='bim2sim version', default="*")
    parser.add_argument('--docker-version', type=str, help='docker version')

    # Parsen der Argumente
    args = parser.parse_args()
    with open('conda_recipe/env-work.toml', 'r') as f:
        config = toml.load(f)
    for conf in config:
        pip_packages = []
        for item in config[conf]:
            pip_req = item['pip_req']
            pip_dep_req = item['pip_dep_req']
            pip_req.extend(pip_dep_req)
            pip_packages = pip_req
            env_name = item['environment_name']
            temp_file = item['temp_file']
            env_file = item['env_file']
            conda_list = item['conda_list']
            CreateEnvTemplate(env_name, temp_file, env_file, pip_packages, conda_list).create_template()

    with open('conda_recipe/env-bim2sim.toml', 'r') as f:
        config = toml.load(f)
    vision = args.bim2sim_version
    for conf in config:
        if conf.find("dev") > -1:
            flag =".dev"
        else:
            flag = ""
        pip_packages = []
        for item in config[conf]:
            pip_req = item['pip_req']
            pip_dep_req = item['pip_dep_req']
            pip_req.extend(pip_dep_req)
            pip_packages = pip_req
            env_name = item['environment_name']
            temp_file = item['temp_file']
            env_file = item['env_file']
            conda_list = item['conda_list']
            CreateEnvTemplate(env_name, temp_file, env_file, pip_packages, conda_list, flag, vision).create_template()

