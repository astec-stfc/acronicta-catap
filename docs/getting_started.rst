Getting Started
===============

Installation
------------

To install acronicta-catap, ensure you have the required dependencies and then install the library:

.. code-block:: bash

    pip install -r requirements.txt
    pip install -e .

Or if you prefer to install in development mode from the repository:

.. code-block:: bash

    cd acronicta-catap
    pip install -r requirements.txt
    pip install -e .

Basic Concepts
--------------

acronicta-catap is built on top of :external:doc:`catapcore <index>`, a comprehensive Python framework for interacting with EPICS PVs through an object-oriented interface. acronicta-catap extends this by providing:

1. **YAML-based Hardware Configuration** - Define your hardware components in YAML files
2. **Automatic Code Generation** - Generate facility-specific hardware classes from YAML templates
3. **Factory Pattern** - Create and manage multiple hardware objects efficiently
4. **Hardware Models** - Auto-generated Python classes for your specific hardware types

Quick Start
-----------

Here's a minimal example to get you started:

1. **Create a YAML configuration file** for your hardware component:

.. code-block:: yaml

    # bpm.yaml
    controls_information:
        pv_record_map:
            X:
                type: scalar
                description: "X position readback"
                units: "mm"
                pv: "BPM-01:X"
            Y:
                type: scalar
                description: "Y position readback"
                units: "mm"
                pv: "BPM-01:Y"
    
    properties:
        name: BPM-01
        hardware_type: BPM
        subtype: STRIPLINE
        machine_area: A1
        position: 1.5

2. **Generate hardware classes**:

.. code-block:: bash

    python ./scripts/generate_hardware.py \
        --yaml_location "./yaml" \
        --output_location "./output" \
        --overwrite_hardware

3. **Use your generated hardware**:

.. code-block:: python

    from output.hardware.bpm import BPMFactory

    # Create a factory for BPM hardware
    bpm_factory = BPMFactory(is_virtual=False)

    # Get all BPM objects
    all_bpms = bpm_factory.hardware

    # Access specific hardware
    bpm_01 = bpm_factory.get_hardware_by_name("BPM-01")

    # Read PV values
    x_position = bpm_01.x
    y_position = bpm_01.y

Virtual Mode
------------

For testing and development, acronicta-catap supports a virtual mode where PV names are automatically prefixed:

.. code-block:: python

    # This will use "TEST:BPM-01:X" instead of "BPM-01:X"
    bpm_factory = BPMFactory(is_virtual=True)
    bpm_01 = bpm_factory.get_hardware_by_name("BPM-01")

Physical Mode
-------------

To connect to real EPICS PVs:

.. code-block:: python

    # Connect to actual EPICS control system
    bpm_factory = BPMFactory(is_virtual=False)
    bpm_01 = bpm_factory.get_hardware_by_name("BPM-01")

Directory Structure
-------------------

After generation, your output directory will have this structure:

.. code-block:: text

    output/
    ├── hardware/
    │   ├── __init__.py
    │   ├── bpm.py           # BPM hardware factory and classes
    │   ├── cavity.py        # Cavity hardware factory and classes
    │   └── ...
    └── constants.py         # Machine area and other constants

YAML File Format
----------------

Each YAML file should contain two main sections:

**controls_information**
    Defines the PVs (Process Variables) for this hardware:

    - ``pv_record_map``: Dictionary of PV names to configurations
    
        - ``type``: PV type (scalar, binary, statistical, string, waveform)
        - ``description``: Human-readable description
        - ``units``: Measurement units (if applicable)
        - ``pv``: The EPICS PV name
        - ``protocol``: EPICS protocol (CA or PVA, defaults to CA)

**properties**
    Defines hardware metadata:

    - ``name``: Unique name of this hardware instance
    - ``hardware_type``: Type of hardware (used for grouping and factory generation)
    - ``subtype``: Hardware subtype for further categorization
    - ``machine_area``: Location in the accelerator/facility
    - ``position``: Z-position along the lattice (meters)

Next Steps
----------

- Check the :doc:`architecture` for an in-depth explanation of the framework design
- See :doc:`api_reference` for detailed class and method documentation
- View :doc:`examples` for more advanced usage patterns
- Refer to :external:doc:`catapcore documentation <getting_started>` for core framework concepts
