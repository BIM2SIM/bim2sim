from pathlib import Path

from livereload import Server, shell

if __name__ == '__main__':
    root = Path(__file__).parent.parent
    rebuild_cmd = f'{root}\\make.bat html'.replace('\\', '/')

    server = Server()
    server.watch('*.rst', shell(rebuild_cmd), delay=1)
    server.watch('*.md', shell(rebuild_cmd), delay=1)
    server.watch('*.py', shell(rebuild_cmd), delay=1)
    server.watch('../../bim2sim/*.py', shell(rebuild_cmd), delay=1)
    server.watch('_static/*', shell(rebuild_cmd), delay=1)
    server.watch('_templates/*', shell(rebuild_cmd), delay=1)
    server.serve(root='../build/html')
