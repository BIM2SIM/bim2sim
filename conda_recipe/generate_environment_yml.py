import jinja2
import argparse
# Definieren Sie die Variablen, die in der Vorlage verwendet werden sollen
class CreateEnvTemplate():
    def __init__(self, env_name, temp_file, env_file, pip_packages):
        self.env_name = env_name
        self.temp_file = temp_file
        self.env_file = env_file
        self.pip_packages = pip_packages

    def read_pip_packages(self):
        meine_liste =  []
        for packages in self.pip_packages:
            with open(packages, 'r') as f:
                # Lesen Sie alle Zeilen in eine Liste ein
                meine_liste.extend([zeile.strip() for zeile in f.readlines()])

        return meine_liste
        # Geben Si

    def create_template(self):
        pip_list = self.read_pip_packages()
        template_vars = {
            'environment_name': self.env_name,
            'python_version': '3.9',
            'pip_list': pip_list}
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
    parser.add_argument('--name', type=str, help='Ihr Name')
    parser.add_argument('--age', type=int, help='Ihr Alter')

    # Parsen der Argumente
    args = parser.parse_args()
    # basic
        # dev
        # main
        # work_env
    # plugins
        # dev
        # main
        # work_env
    # total
        # dev
        # main
        # work_env
    env_name = "bim2sim_env"
    temp_file = "conda_recipe/total/environment.yml.j2"
    env_file = "conda_recipe/total/environmentt.yml"
    pip_packages = ["bim2sim/plugins/PluginTeaser/requirements.txt", "bim2sim/plugins/PluginTeaser/dependency_requirements.txt"]
    CreateEnvTemplate(env_name, temp_file, env_file, pip_packages).create_template()
