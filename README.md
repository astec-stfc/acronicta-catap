# Acronicta CATAP

A python library that combines Pydantic and Jinja2 templating to produce a facility-specific middle layer for EPICS-based control systems.

acronicta-catap leverages [catapcore](https://github.com/astec-stfc/catapcore) as its foundation, providing an object-oriented interface for EPICS PV interactions through auto-generated hardware classes from YAML configurations.

## Documentation

For comprehensive documentation, including getting started guides, architecture details, and API references, please visit the [API Documentation](https://astec-stfc.github.io/acronicta-catap/).

## How to generate your middle layer

### Prerequisites

Ensure you have installed the required dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

- Provide a set of folders with YAML files that describe your hardware components:
```bash
- yaml/
  - BPM/
    - DEVICE-01.yaml
    - DEVICE-02.yaml
    - ...
  - Cavity/
    - CAVITY-01.yaml
    - CAVITY-02.yaml
    - ...
  - ...
```
- Each component file must provide the following information at least:
  - `controls_information`
    - `pv_record_map` : A set of PVs (see example below)
  - `properties`
    - `name`: Full name of the component
    - `hardware_type`: Type of component (this links with the Model/Hardware class generation)
    - `subtype`: Subtype (i.e. QUADRUPOLE, DIPOLE, etc.)
    - `machine_area`: Used in generation to setup `MACHINE_AREAS` constants
    - `position`: Used to sort components
```yaml
# example file in ./yaml/BPM/DEVICE-01.yaml

controls_information:
    pv_record_map:
        X:
            type: scalar
            description: "X position readback for the BPM"
            units: "mm"
            pv: "BPM-DEVICE-01:X"
        Y:
            type: statistical
            auto_buffer: true
            buffer_size: 100
            description: "X position readback for the BPM"
            units: "mm"
            pv: "BPM-DEVICE-01:Y"
properties:
    name: DEVICE-01
    hardware_type: BPM
    subtype: STRIPLINE
    machine_area: A1
    position: 1.0
```

### Running the generation script

From the top level directory, you should be able to do:

``` bash
python ./scripts/generate_hardware.py --yaml_location "<yaml-directory>" --output_location "<output-directory>" --overwrite_hardware
```

For the first time you run the generation, you will need to supply the `--overwrite_hardware` argument to generate the `hardware/` folder with component definitions in.

After the first time, you may not want to overwrite the hardware classes due to them having facility-specific logic in there. If this is the case, do not supply the `--overwrite_hardware` option.

### Testing your generated middle layer

- Go into the output location
- Open a python interpreter and you should be able to do something like:

```python
# import your factory
from hardware.magnet import MagnetFactory

# create your factory
magnets = MagnetFactory(is_virtual=False)

# get a parameter for all components in the factory.
magnets.current()
```

## Related Projects

- **[catapcore](https://github.com/astec-stfc/catapcore)**: The underlying framework that provides the core PV interaction functionality
