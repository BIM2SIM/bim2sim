import importlib
import importlib.util
import pandas as pd
from pathlib import Path
import textwrap
from typing import Union

from bim2sim.sim_settings import (BooleanSetting, ChoiceSetting,
                                  NumberSetting, PathSetting,
                                  GuidListSetting, Setting)


def load_module(source: str):
    if source.endswith(".py"):
        spec = importlib.util.spec_from_file_location("temp_module", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    else:
        return importlib.import_module(source)


def simplify_type_name(setting_obj) -> str:
    if isinstance(setting_obj, BooleanSetting):
        return "Boolean"
    if isinstance(setting_obj, NumberSetting):
        return "Number"
    if isinstance(setting_obj, ChoiceSetting):
        return "Choice"
    if isinstance(setting_obj, PathSetting):
        return "Path"
    if isinstance(setting_obj, GuidListSetting):
        return "GuidList"
    if isinstance(setting_obj, Setting):
        return "Base"
    return type(setting_obj).__name__


def fmt_default(val):
    if isinstance(val, str):
        return f"'{val}'"
    return val


def wrap_for_md(text: str, width: int = 120) -> str:
    if text is None:
        return ""
    text = str(text).strip()
    if not text:
        return ""
    # automatic linebreaks
    paragraphs = text.split("\n\n")
    wrapped_paragraphs = []
    for p in paragraphs:
        p_single = " ".join(line.strip() for line in p.splitlines())
        wrapped = textwrap.wrap(p_single, width=width)
        if not wrapped:
            wrapped_paragraphs.append("")
        else:
            wrapped_paragraphs.append("<br>".join(wrapped))
    return "<br><br>".join(wrapped_paragraphs)


def choices_to_string(choices: Union[dict, list, None], wrap_width) -> str:
    s = ""
    if not choices:
        return ""
    if len(choices) > 10 and isinstance(choices, dict):
        choices = list(choices.keys())
    if isinstance(choices, dict):
        entries = [f"'{k}': {v}" if v else f"{k}" for k, v in choices.items()]
        s = "<br>".join(entries)
    elif isinstance(choices, (list, tuple)):
        entries = [str(f"'{e}'") for e in choices]
        s = ", ".join(entries)
        s = wrap_for_md(s, wrap_width)
    return s


def extract_settings_from_class(cls, wrap_width=60):
    rows = []
    for name, value in list(cls.__dict__.items()):
        if name.startswith("_"):
            continue
        if isinstance(value, (BooleanSetting, ChoiceSetting, NumberSetting,
                              PathSetting, GuidListSetting, Setting)):
            stype = simplify_type_name(value)
            default = fmt_default(getattr(value, "default", ""))
            description = getattr(value, "description", "") or ""
            description = wrap_for_md(description, width=wrap_width)
            choices_col = ""
            if isinstance(value, ChoiceSetting):
                choices_col = choices_to_string(getattr(value, "choices",
                                                        None), wrap_width)
            rows.append({"Setting Name": name, "Type": stype, "Default":
                        default, "Description": description, "Choices":
                        choices_col})
    return rows


def settings_to_markdown(source: str, class_name: str,
                         output_md: str = "settings.md", wrap_width: int = 60):
    """
    Generate a markdown table for settings defined in `class_name` found in
    `source`. `source` can be a dotted module name (e.g.
    "bim2sim.sim_settings") or a path to a .py file.
    """
    mod = load_module(source)
    cls = getattr(mod, class_name)
    rows = extract_settings_from_class(cls, wrap_width=wrap_width)
    df = pd.DataFrame(rows)
    df = df[["Setting Name", "Type", "Default", "Description", "Choices"]]
    markdown_str = df.to_markdown(index=False)
    Path(output_md).write_text(markdown_str, encoding="utf-8")
    print(f"Markdown table written to {output_md}")


if __name__ == "__main__":
    save_path = ""  # Add path to save markdown tables
    settings_to_markdown(
        "bim2sim.plugins.PluginComfort.bim2sim_comfort.sim_settings",
        "ComfortSimSettings",
        save_path + "comfort_settings.md")
    # settings_to_markdown("bim2sim.sim_settings",
    #                      "BaseSimSettings",
    #                      save_path + "base_settings.md")
    # settings_to_markdown("bim2sim.sim_settings",
    #                      "BuildingSimSettings",
    #                      save_path + "building_settings.md")
    # settings_to_markdown(
    #     "bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.sim_settings",
    #     "EnergyPlusSimSettings",
    #     save_path + "eplus_settings.md")

