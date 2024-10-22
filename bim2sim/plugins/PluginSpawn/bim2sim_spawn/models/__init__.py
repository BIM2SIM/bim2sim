from pathlib import Path


def to_modelica_spawn(parameter):
    """converts parameter to modelica readable string"""
    if parameter is None:
        return parameter
    if isinstance(parameter, bool):
        return 'true' if parameter else 'false'
    if isinstance(parameter, (int, float)):
        return str(parameter)
    if isinstance(parameter, str):
        return '"%s"' % parameter
    if isinstance(parameter, (list, tuple, set)):
        return "{%s}" % (
            ",".join(
                (to_modelica_spawn(par) for par
                 in parameter)))
    if isinstance(parameter, Path):
        return \
            f"Modelica.Utilities.Files.loadResource(\"" \
            f"{str(parameter)}\")" \
                .replace("\\", "\\\\")
    return str(parameter)