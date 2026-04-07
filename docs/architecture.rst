Architecture
=============

Overview
--------

acronicta-catap is built on a layered architecture that extends :external:doc:`catapcore <architecture>` with automatic code generation capabilities. The system bridges the gap between YAML hardware configurations and Python class definitions.

Core Components
---------------

YAML Configuration Layer
~~~~~~~~~~~~~~~~~~~~~~~~

The YAML configuration files define:

- **Hardware metadata** (name, type, position, machine area)
- **PV mappings** (EPICS process variable definitions and types)
- **Hardware relationships** (grouping by type and area)

Template Layer
~~~~~~~~~~~~~~

Jinja2 templates are used to generate Python classes from YAML definitions:

- ``hardware_model_template.j2`` - Generates hardware model classes
- ``component_model_template.j2`` - Generates component classes
- ``init_template.j2`` - Generates factory initialization code

Code Generation Engine
~~~~~~~~~~~~~~~~~~~~~~

The ``generate_hardware.py`` script orchestrates the generation process:

1. Reads YAML configuration files
2. Groups hardware by type
3. Applies Jinja2 templates to generate Python code
4. Generates factory classes for hardware management
5. Creates machine area constants

Generated Architecture
~~~~~~~~~~~~~~~~~~~~~~

After code generation, the output structure provides:

**Factory Classes**
    Each hardware type gets a Factory class (e.g., ``BPMFactory``, ``CavityFactory``) that:
    
    - Creates hardware instances from YAML data
    - Manages collections of hardware objects
    - Provides filtering and querying methods
    - Handles snapshot creation and restoration

**Hardware Classes**
    Generated hardware classes inherit from catapcore's base classes:
    
    - Combine ``PVMap``, ``ControlsInformation``, and ``Properties``
    - Provide type-safe access to hardware PVs
    - Support virtual and physical connection modes

**Constant Definitions**
    Generated constants module provides:
    
    - Machine area enumeration
    - Hardware type mappings
    - Position-based sorting information

Integration with catapcore
--------------------------

acronicta-catap leverages catapcore's core architecture:

**PVMap** (from catapcore)
    Manages EPICS PV connections at the lowest level

**ControlsInformation** (from catapcore)
    Provides controlled interface for reading/writing PVs

**Properties** (from catapcore)
    Manages hardware metadata

**Hardware** (from catapcore)
    Combines the above three for a unified hardware interface

**Factory** (from catapcore)
    Base class for facility-specific factory implementations

Design Patterns
---------------

Template-Based Code Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rather than writing individual hardware classes by hand, acronicta-catap uses Jinja2 templates to generate them from YAML specifications. This approach provides:

- **Consistency** - All generated code follows the same patterns
- **Maintainability** - Update templates once, regenerate all code
- **Type Safety** - Generated classes use catapcore's Pydantic models
- **Flexibility** - Easy to customize via template modifications

Configuration-Driven Development
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The YAML-first approach means:

- Hardware definitions are version-controlled
- Easy to see all hardware configurations at a glance
- PV mappings are centralized and documented
- Minimal Python boilerplate code

Factory Pattern for Hardware Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The generated Factory classes provide:

- **Lazy initialization** - Hardware objects created on demand
- **Centralized configuration** - All YAML data loaded by factory
- **Querying capabilities** - Filter by area, name, type, or subtype
- **Batch operations** - Apply operations to multiple hardware objects

Code Generation Workflow
------------------------

1. **Configuration Phase**
   - User creates YAML files with hardware definitions
   - Each file describes one hardware instance

2. **Parsing Phase**
   - ``generate_hardware.py`` reads all YAML files
   - Validates configuration against Pydantic models
   - Groups hardware by type and area

3. **Template Phase**
   - Jinja2 renders templates with parsed data
   - Generates Python module structure
   - Creates factory and hardware classes

4. **Output Phase**
   - Generated code written to output directory
   - Machine area constants generated
   - Factory initialization code created

5. **Integration Phase**
   - User imports generated factories
   - Creates factory instances
   - Uses hardware objects normally

PV Type Mapping
---------------

YAML configuration types map to catapcore PV types:

- ``scalar`` → :class:`~catapcore.common.machine.pv_utils.ScalarPV`
- ``binary`` → :class:`~catapcore.common.machine.pv_utils.BinaryPV`
- ``state`` → :class:`~catapcore.common.machine.pv_utils.StatePV`
- ``string`` → :class:`~catapcore.common.machine.pv_utils.StringPV`
- ``waveform`` → :class:`~catapcore.common.machine.pv_utils.WaveformPV`
- ``statistical`` → :class:`~catapcore.common.machine.pv_utils.StatisticalPV`

Virtual vs Physical Control Systems
------------------------------------

Generated hardware supports both modes:

**Virtual Mode**
    - PV names are prefixed (e.g., "TEST:BPM-01:X") globally or use `virtual_pv` specific to YAML PV defintion
    - Useful for testing and development
    - Read/Write Access allowed for all PVs
    - Set via ``is_virtual=True`` in factory creation

**Physical Mode**
    - Direct connection to EPICS PVs
    - Requires running EPICS IOCs
    - Ability to force `read_only` mode at PV level
    - PV names used as specified in YAML
    - Set via ``is_virtual=False`` in factory creation

Snapshot Management
-------------------

Generated factories support snapshot creation and restoration:

.. code-block:: python

    factory = BPMFactory(is_virtual=False)
    
    # Create a snapshot of all hardware states
    snapshot = factory.create_snapshot()
    
    # Modify hardware
    bpm = factory.get_hardware_by_name("BPM-01")
    bpm.gain = 5.0
    
    # Restore to previous state
    factory.apply_snapshot(snapshot)
