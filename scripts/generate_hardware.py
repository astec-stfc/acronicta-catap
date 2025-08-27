import os
import subprocess
import yaml
from typing import Dict, List, Set, Any
from jinja2 import Environment, FileSystemLoader
import argparse
import shutil

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
    files = []
    for folder in os.listdir(lattice_location):
        if folder not in exclude_folders:
            folder_path = os.path.join(lattice_location, folder)
            if os.path.isdir(folder_path):
                files += [
                    os.path.join(folder_path, f)
                    for f in os.listdir(folder_path)
                    if f.endswith(".yaml")
                ]
    return files


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
        pvs[pv_name] = {
            "binary": "BinaryPV",
            "state": "StatePV",
            "scalar": "ScalarPV",
            "statistical": "StatisticalPV",
            "waveform": "WaveformPV",
            "string": "StringPV",
        }.get(pv_type, None)
        read_only[pv_name] = pv_info.get("read_only", True)
        pv_descriptions[pv_name] = pv_info.get("description", "Missing description")
    return pvs, read_only, pv_descriptions


def load_yaml_file(file_path: str) -> Dict:
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def collect_class_data(example_files: List[str]):
    file_pv_keys = {}
    file_pv_info = {}
    file_controls_keys = {}
    file_controls_info = {}
    file_property_keys = {}
    file_property_info = {}
    machine_areas = []
    hardware_and_subtypes = {}

    for file in example_files:
        data = load_yaml_file(file)
        properties = data.get("properties", {})
        hardware_type = properties.get("hardware_type")
        if hardware_type is None:
            raise ValueError(f"hardware_type is not defined in the YAML file: {file}")
        class_name = hardware_type

        controls_info = data.get("controls_information", {})
        pv_map = controls_info.pop("pv_record_map", None)
        if pv_map is None:
            raise ValueError(f"pv_record_map missing in controls_information: {file}")

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
    (
        file_pv_keys,
        file_pv_info,
        file_controls_keys,
        file_controls_info,
        file_property_keys,
        file_property_info,
        machine_areas,
        hardware_and_subtypes,
    ) = collect_class_data(example_files)

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
