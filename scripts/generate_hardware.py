import os
import subprocess
import yaml
from typing import Dict, List, Set, Any
from jinja2 import Environment, FileSystemLoader
import argparse
import shutil
from warnings import warn

EXCLUDE_FOLDERS = ["FEBELaser", "PILaser"]
LATTICE_LOCATION = os.path.abspath("../isis/output/yaml")
OUTPUT_DIR = "../isis/output/"
MODEL_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "models")
HARDWARE_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "hardware")
TEMPLATE_DIR = os.path.abspath("./templates/classes")


def ensure_directories():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(HARDWARE_OUTPUT_DIR, exist_ok=True)
    os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(LATTICE_LOCATION):
        raise FileNotFoundError(f"Could not find yaml directory: {LATTICE_LOCATION} ")


def get_example_files(lattice_location: str, exclude_folders: List[str]) -> List[str]:
    filelist = []
    for (root, direc, files) in os.walk(lattice_location):
        if direc not in exclude_folders and root.split(os.path.sep)[-1] not in exclude_folders:
            if len(direc) == 0:
                # *_schema.yaml is a shared controls template, not an element:
                # it is pulled in by the elements that name it, not generated
                # from (see resolve_controls_schema).
                filelist += [
                    f"{root}/{f}"
                    for f in files
                    if f.endswith(".yaml") and not f.endswith("_schema.yaml")
                ]
    return filelist


def extract_differing_keys(file_pv_maps: Dict[str, Set[str]]) -> Set[str]:
    if not file_pv_maps:
        return set()
    all_keys = set.union(*file_pv_maps.values())
    common_keys = set.intersection(*file_pv_maps.values())
    return all_keys - common_keys


def construct_pv_map_info(pv_map: Dict[str, Dict[str, Any]]) -> (Dict, Dict, Dict):
    pvs = {}
    read_only = {}
    pv_descriptions = {}
    for pv_name, pv_info in pv_map.items():
        pv_type = pv_info.get("type", "").lower()
        # get pv type, default ScalarPV
        pvs[pv_name] = {
            "binary": "BinaryPV",
            "state": "StatePV",
            "scalar": "ScalarPV",
            "statistical": "StatisticalPV",
            "waveform": "WaveformPV",
            "string": "StringPV",
        }.get(pv_type, "ScalarPV")
        read_only[pv_name] = pv_info.get("read_only", True)
        pv_descriptions[pv_name] = pv_info.get("description", "Missing description")
    return pvs, read_only, pv_descriptions


def load_yaml_file(file_path: str) -> Dict:
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


INHERIT_KEYS = ("inherits_from", "inherit")
NON_INHERITED_KEYS: Dict[str, Any] = {
    "name": None,
    "alias": None,
    "virtual_name": None,
    "subelement": None,
    "upstream": None,
    "downstream": None,
    "physical": frozenset(
        {
            "middle",
            "s",
            "s_point",
            "datum",
            "reference_placement",
            "rotation",
            "global_rotation",
            "survey",
            "error",
            "physical_angle",
        }
    ),
}

CONTROLS_RESOLUTION_KEYS = ("schema", "schema_", "identifier_pattern")

_SCHEMA_VARIABLE_CACHE: Dict[str, Dict] = {}


def build_element_namespace(lattice_location: str) -> Dict[str, Dict]:
    """
    Index every named element in the tree by name, for inheritance lookups.
    This walks the whole tree. Excluded folders are indexed
    too: a child we do generate from may inherit from one we don't.

    Parameters
    ----------
    lattice_location: str
        Directory containing lattice files

    Returns
    -------
    dict[str, dict]
        Namespace dictionary containing loaded lattice files
    """
    namespace: Dict[str, Dict] = {}
    for (root, _, files) in os.walk(lattice_location):
        for f in files:
            if not f.endswith(".yaml") or f.endswith("_schema.yaml"):
                continue
            data = load_yaml_file(os.path.join(root, f))
            if isinstance(data, dict) and data.get("name"):
                namespace[data["name"]] = data
    return namespace


def _merge_inherited(parent: Dict, child: Dict) -> Dict:
    """
    Recursive merge of ``child`` onto ``parent``; the child wins.

    Parameters
    ----------
    parent: dict
        Dictionary 1
    child: dict
        Dictionary 2

    Returns
    -------
    dict
        Merged dict
    """
    merged = dict(parent)
    for key, value in child.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_inherited(merged[key], value)
        else:
            merged[key] = value
    return merged


def _strip_non_inherited(parent: Dict) -> Dict:
    """Drop the keys of ``parent`` that a child must never inherit;
    see ``NON_INHERITED_KEYS."""
    stripped = {}
    for key, value in parent.items():
        if key in NON_INHERITED_KEYS:
            excluded = NON_INHERITED_KEYS[key]
            if excluded is None:
                continue
            if isinstance(value, dict):
                value = {k: v for k, v in value.items() if k not in excluded}
                if not value:
                    continue
        stripped[key] = value
    return stripped


def resolve_inheritance(
    elem: Dict,
    namespace: Dict[str, Dict],
    memo: Dict[str, Dict] = None,
    chain: tuple = (),
) -> Dict:
    """
    Merge ``elem`` on top of the element named by its ``inherits_from``.

    Parameters
    ----------
    elem: dict
        Dictionary containing element information
    namespace: dict[str, dict]
        Dictionary containing names elements, no schemas
    memo: dict[str, dict], optional
        Additional information
    chain: tuple, optional
        Inheritance chain
    """
    parent_name = next(
        (elem[key] for key in INHERIT_KEYS if elem.get(key) is not None), None
    )
    if not parent_name:
        return elem

    name = elem.get("name", "<unknown>")
    if memo is not None and name in memo:
        return memo[name]

    if parent_name in chain + (name,):
        warn(
            f"inheritance cycle: {' -> '.join(chain + (name, parent_name))}, "
            f"leaving {name} unresolved."
        )
        return elem

    parent_raw = namespace.get(parent_name)
    if parent_raw is None:
        warn(
            f"{name} inherits from '{parent_name}', which is not defined "
            "anywhere in the lattice, leaving it unresolved."
        )
        return elem

    parent = resolve_inheritance(parent_raw, namespace, memo, chain + (name,))
    merged = _merge_inherited(_strip_non_inherited(parent), elem)
    if memo is not None:
        memo[name] = merged
    return merged


def _resolve_schema_path(schema_ref: str, base_dir: str) -> str:
    """
    Figure out where the ``controls.schema`` path points to, check if
    absolute or relative path.

    Parameters
    ----------
    schema_ref: str
        Path given for the schema file
    base_dir: str
        Base directory for the lattice

    Returns
    -------
    str
        Absolute path to the schema file
    """
    if os.path.isabs(schema_ref) or os.path.exists(schema_ref):
        return os.path.abspath(schema_ref)
    return os.path.abspath(os.path.join(base_dir, schema_ref))


def load_schema_variables(schema_ref: str, base_dir: str) -> Dict:
    """
    The raw, still ``{name}``-templated ``variables`` of a controls schema,
    cached by path.

    Parameters
    ----------
    schema_ref: str
        Path to the schema file
    base_dir: str
        Base directory for the lattice

    Returns
    -------
    dict
        Variables declared in the schema
    """
    path = _resolve_schema_path(schema_ref, base_dir)
    if path not in _SCHEMA_VARIABLE_CACHE:
        if not os.path.exists(path):
            warn(
                f"controls schema '{schema_ref}' not found (looked in "
                f"{base_dir}), so its variables are missing."
            )
            _SCHEMA_VARIABLE_CACHE[path] = {}
        else:
            data = load_yaml_file(path) or {}
            _SCHEMA_VARIABLE_CACHE[path] = (
                data.get("variables", {}) if isinstance(data, dict) else {}
            )
    return _SCHEMA_VARIABLE_CACHE[path]


def _substitute_schema_placeholders(value: Any, name: str):
    """
    Replace the ``{name}`` placeholder with the owning element's name,
    recursively through nested dicts and lists (it appears in `identifier`).

    Parameters
    ----------
    value: Any
        Value to return
    name: str
        Element name

    Returns
    -------
    Any
        ``value`` with ``"{name}"`` replaced with element name
    """
    if isinstance(value, str):
        return value.replace("{name}", name)
    if isinstance(value, dict):
        return {k: _substitute_schema_placeholders(v, name) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_schema_placeholders(v, name) for v in value]
    return value


def resolve_controls_schema(controls: Dict, element_name: str, base_dir: str) -> Dict:
    """Expand a ``controls.schema`` reference into a full ``variables`` dict.

    The schema holds one templated ``variables`` mapping shared by every
    element of a type; ``{name}`` in it is replaced by the element's
    ``identifier_pattern``, or by its name when it has no pattern. Any
    ``variables`` stated inline are then layered on top one field at a time, so
    an element can override a single entry without restating the map.

    Parameters
    ----------
    controls: dict
        Dictionary containing controls variables
    element_name: str
        Name of the element to be included over the schema placeholder
    base_dir: str
        Directory containing element files

    Returns
    -------
    dict
        Resolved ``controls.schema``
    """
    schema_ref = controls.get("schema") or controls.get("schema_")
    if not schema_ref:
        return controls

    schema_variables = load_schema_variables(schema_ref, base_dir)
    substitution_name = controls.get("identifier_pattern") or element_name
    merged = {
        key: _substitute_schema_placeholders(var_def, substitution_name)
        for key, var_def in schema_variables.items()
    }
    for key, override in (controls.get("variables") or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(override, dict):
            merged[key] = {**merged[key], **override}
        else:
            merged[key] = override

    resolved = {
        k: v
        for k, v in controls.items()
        if k != "variables" and k not in CONTROLS_RESOLUTION_KEYS
    }
    resolved["variables"] = merged
    return resolved


def collect_class_data(example_files: List[str], namespace: Dict[str, Dict] = None):
    file_pv_keys = {}
    file_pv_info = {}
    file_controls_keys = {}
    file_controls_info = {}
    file_property_keys = {}
    file_property_info = {}
    machine_areas = []
    hardware_and_subtypes = {}
    inheritance_memo = {}

    for file in example_files:
        data = load_yaml_file(file)
        data = resolve_inheritance(data, namespace or {}, inheritance_memo)
        properties = data.get("properties", {})
        hardware_type = properties.get("hardware_type") or data.get("hardware_type")
        if hardware_type is None:
            warn(f"hardware_type is not defined in the YAML file: {file}, skipping this file.")
            continue
        class_name = hardware_type

        controls_info = (
                data.get("controls_information")
                or data.get("controls")
                or {}
        )
        controls_info = resolve_controls_schema(
            controls_info, data.get("name", ""), os.path.dirname(file)
        )
        pv_map = None
        for key in ("pv_record_map", "variables"):
            if key in controls_info:
                pv_map = controls_info[key]
                controls_info = {k: v for k, v in controls_info.items() if k != key}
                break
        if pv_map is None:
            warn(f"pv_record_map/variables missing in controls_information.controls: {file}, skipping PV info for this file.")
            continue

        # Initialize dicts for each class_name
        for d in [
            file_pv_keys,
            file_pv_info,
            file_controls_info,
            file_controls_keys,
            file_property_keys,
            file_property_info,
        ]:
            if class_name not in d:
                d[class_name] = {}

        file_pv_keys[class_name][file] = set(pv_map.keys())
        file_pv_info[class_name].update(pv_map)
        file_controls_keys[class_name][file] = set(controls_info.keys())
        file_controls_info[class_name].update(controls_info)
        file_property_keys[class_name][file] = set(properties.keys())
        file_property_info[class_name].update(properties)

        _area = properties.get("machine_area")
        if _area and _area not in machine_areas:
            machine_areas.append(_area)
        _subtype = properties.get("subtype")
        if _subtype:
            ht_upper = hardware_type.upper()
            if ht_upper not in hardware_and_subtypes:
                hardware_and_subtypes[ht_upper] = []
            if _subtype.upper() not in hardware_and_subtypes[ht_upper]:
                hardware_and_subtypes[ht_upper].append(_subtype.upper())

    return (
        file_pv_keys,
        file_pv_info,
        file_controls_keys,
        file_controls_info,
        file_property_keys,
        file_property_info,
        machine_areas,
        hardware_and_subtypes,
    )


def render_templates(
    env: Environment,
    class_name: str,
    hardware_type: str,
    pvs: Dict,
    read_only: Dict,
    pv_descriptions: Dict,
    filtered_properties: Dict,
    current_optional_properties: Set[str],
    current_optional_pvs: Set[str],
    current_controls_information: Dict,
    current_optional_controls_parameters: Set[str],
    machine_areas: List[str],
    hardware_and_subtypes: Dict,
    lattice_location: str,
):
    output_filename = f"{class_name.lower()}.py"
    template = env.get_template("component_model_template.j2")
    hardware_template = env.get_template("hardware_model_template.j2")
    init_template = env.get_template("init_template.j2")

    hardware_output = hardware_template.render(
        class_name=class_name,
        hardware_type=hardware_type.lower(),
    )
    init_output = init_template.render(
        lattice_folder=lattice_location,
        areas=machine_areas,
        hardware_types=hardware_and_subtypes if hardware_and_subtypes else None,
    )
    model_output = template.render(
        class_name=class_name,
        pvs=pvs,
        read_only=read_only,
        hardware_type=hardware_type,
        properties=filtered_properties,
        optional_properties=current_optional_properties,
        pv_descriptions=pv_descriptions,
        optional_pvs=current_optional_pvs,
        controls_information=current_controls_information,
        optional_controls_parameters=current_optional_controls_parameters,
    )
    return output_filename, model_output, hardware_output, init_output


def write_output_files(
    model_output_dir: str,
    hardware_output_dir: str,
    output_filename: str,
    model_output: str,
    hardware_output: str,
    init_output: str,
    overwrite_hardware: bool,
):
    with open(os.path.join(model_output_dir, output_filename), "w") as f:
        f.write(model_output)
    if overwrite_hardware:
        with open(os.path.join(hardware_output_dir, output_filename), "w") as f:
            f.write(hardware_output)
        with open(os.path.join(hardware_output_dir, "__init__.py"), "w") as f:
            f.write(init_output)
    with open(os.path.join(model_output_dir, "__init__.py"), "w") as f:
        f.write(init_output)
    open(os.path.join(OUTPUT_DIR, "__init__.py"), "w").close()


def main(overwrite_hardware: bool = False):
    ensure_directories()
    example_files = get_example_files(LATTICE_LOCATION, EXCLUDE_FOLDERS)
    namespace = build_element_namespace(LATTICE_LOCATION)
    (
        file_pv_keys,
        file_pv_info,
        file_controls_keys,
        file_controls_info,
        file_property_keys,
        file_property_info,
        machine_areas,
        hardware_and_subtypes,
    ) = collect_class_data(example_files, namespace)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    created_classes = set()
    init_output = None

    for hardware_type in file_pv_keys:
        class_name = hardware_type
        current_optional_pvs = extract_differing_keys(file_pv_keys[hardware_type])
        current_pv_map = file_pv_info.get(hardware_type, {})
        if not current_pv_map:
            raise ValueError(f"No PV map found for {hardware_type}")
        pvs, read_only, pv_descriptions = construct_pv_map_info(current_pv_map)
        current_optional_controls_parameters = extract_differing_keys(
            file_controls_keys[hardware_type]
        )
        current_controls_information = file_controls_info.get(hardware_type, {})
        current_optional_properties = extract_differing_keys(
            file_property_keys[hardware_type]
        )
        current_properties = file_property_info.get(hardware_type, {})

        excluded_keys = {
            "hardware_type",
            "name",
            "name_alias",
            "machine_area",
            "position",
            "subtype",
        }
        filtered_properties = {
            k: v for k, v in current_properties.items() if k not in excluded_keys
        }

        if class_name not in created_classes:
            output_filename, model_output, hardware_output, init_output = (
                render_templates(
                    env,
                    class_name,
                    hardware_type,
                    pvs,
                    read_only,
                    pv_descriptions,
                    filtered_properties,
                    current_optional_properties,
                    current_optional_pvs,
                    current_controls_information,
                    current_optional_controls_parameters,
                    machine_areas,
                    hardware_and_subtypes,
                    LATTICE_LOCATION,
                )
            )
            write_output_files(
                MODEL_OUTPUT_DIR,
                HARDWARE_OUTPUT_DIR,
                output_filename,
                model_output,
                hardware_output,
                init_output,
                overwrite_hardware,
            )
            created_classes.add(class_name)
            print(
                f"Generated {output_filename} and {class_name.lower()}.py for {hardware_type}"
            )
    # Format all generated Python files with black
    # We have to add an exclude here to avoid using .gitignore
    # I chose to exclude *.pyc files because they allow
    # us to include files in the .gitingore
    subprocess.run(["black", "--exclude", '"*.pyc"', OUTPUT_DIR], check=True)
    print("Formatted generated files with black.")
    if not os.path.exists(os.path.join(OUTPUT_DIR, "catapcore")):
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir_above = os.path.dirname(parent_dir)
        _new_path = shutil.copytree(
            os.path.join(parent_dir_above, "catapcore"),
            os.path.join(OUTPUT_DIR, "catapcore"),
            dirs_exist_ok=False,
        )
        print(f"Copied catapcore to output folder {_new_path}")
    print(f"Generated __init__.py for {MODEL_OUTPUT_DIR}")
    print(f"Generated __init__.py for {HARDWARE_OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--yaml_location",
        help="The directory where the facilty YAML folders are located",
        type=str,
    )
    parser.add_argument(
        "--output_location",
        help="The location where you want to Model and Hardware classes to be built",
        type=str,
    )
    parser.add_argument(
        "--overwrite_hardware",
        help="Specify whether to overwrite the Hardware classes",
        action="store_true",
    )
    parser.add_argument(
        "--exclude_folders",
        help="YAML folders to exclude from generation i.e. Folder_A, Folder_B, ..., Folder_N",
        default="",
        type=str,
    )
    args = parser.parse_args()

    LATTICE_LOCATION = os.path.abspath(args.yaml_location)
    OUTPUT_DIR = os.path.abspath(args.output_location)
    HARDWARE_OUTPUT_DIR = os.path.join(args.output_location, "hardware")
    MODEL_OUTPUT_DIR = os.path.join(args.output_location, "models")
    EXCLUDE_FOLDERS = args.exclude_folders.strip().split(",")
    overwrite_hardware = bool(args.overwrite_hardware)
    main(overwrite_hardware=overwrite_hardware)
