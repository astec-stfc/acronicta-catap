API Reference
=============

This section provides detailed API documentation for acronicta-catap. For information about the core catapcore classes, see the `catapcore API Reference <https://astec-stfc.github.io/catapcore/api_reference.html>`_.

Generate Hardware Script
------------------------

generate_hardware.py
~~~~~~~~~~~~~~~~~~~~

The main code generation script that creates facility-specific hardware classes from YAML configurations.

.. automodule:: scripts.generate_hardware
   :members:
   :undoc-members:
   :show-inheritance:

Generated Factory Classes
-------------------------

After running ``generate_hardware.py``, you will have factory classes in your output directory. Each factory class manages a collection of hardware objects of a specific type.

Example Generated Factory Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For a hardware type ``BPM`` defined in your YAML files, you would get a factory class like:

.. code-block:: python

    class BPMFactory:
        """Factory for managing BPM hardware instances."""
        
        def __init__(self, is_virtual: bool = False, connect_on_creation: bool = True):
            """Initialize the BPM factory.
            
            Parameters
            ----------
            is_virtual : bool
                If True, use virtual EPICS connections for testing
            connect_on_creation : bool
                If True, connect to PVs on hardware creation
            """
            ...
        
        def create_hardware(self, name: str) -> Hardware:
            """Create a specific hardware instance by name."""
            ...
        
        def get_hardware_by_name(self, name: str) -> Hardware:
            """Get hardware instance by name."""
            ...
        
        def get_hardware_by_area(self, area: str) -> List[Hardware]:
            """Get all hardware instances in a specific machine area."""
            ...
        
        def get_hardware_by_subtype(self, subtype: str) -> List[Hardware]:
            """Get all hardware instances of a specific subtype."""
            ...
        
        @property
        def hardware(self) -> List[Hardware]:
            """Get all managed hardware instances."""
            ...
        
        def create_snapshot(self) -> Snapshot:
            """Create a snapshot of all hardware states."""
            ...
        
        def apply_snapshot(self, snapshot: Snapshot):
            """Restore hardware to a saved snapshot state."""
            ...


Generated Hardware Classes
--------------------------

Each hardware instance is represented by a generated class that inherits from :class:`~catapcore.common.machine.hardware.Hardware`.

Example Generated Hardware Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For a BPM hardware component, you would get a class like:

.. code-block:: python

    class BPM(Hardware):
        """BPM hardware component."""
        
        class Config:
            extra = 'forbid'
        
        @property
        def x(self) -> float:
            """X position readback (mm)."""
            return self.controls_information.pv_record_map.x.get()
        
        @property
        def y(self) -> float:
            """Y position readback (mm)."""
            return self.controls_information.pv_record_map.y.get()
        
        def snapshot(self) -> dict:
            """Create a snapshot of this hardware's state."""
            return self.create_snapshot()


Machine Area Constants
----------------------

Generated constants module provides machine area enumeration:

.. code-block:: python

    # Generated in constants.py
    class MachineAreas(str, Enum):
        """Enumeration of machine areas in the facility."""
        A1 = "A1"
        A2 = "A2"
        B1 = "B1"
        # ... etc


YAML Configuration Reference
-----------------------------

The YAML configuration files follow this structure:

.. code-block:: yaml

    # controls_information - Defines PV mappings
    controls_information:
        pv_record_map:
            PV_NAME:
                type: scalar | binary | state | string | waveform | statistical
                description: "Human-readable description"
                units: "Measurement units"
                pv: "EPICS:PV:NAME"
                protocol: CA | PVA  # optional, defaults to CA
                auto_buffer: true   # for statistical type
                buffer_size: 100    # for statistical type
    
    # properties - Defines hardware metadata
    properties:
        name: "Instance name"
        hardware_type: "Type for grouping"
        subtype: "Optional subtype"
        machine_area: "Location identifier"
        position: 1.5  # Z-position along lattice


YAML Field Definitions
~~~~~~~~~~~~~~~~~~~~~~

**controls_information.pv_record_map[name]**
    The name of the PV mapping in the Python class

    - Type: string
    - Required: yes
    - Example: "x", "y", "gain", "status"

**type**
    The type of the PV value

    - Type: scalar | binary | state | string | waveform | statistical
    - Required: yes
    - Default: None

**description**
    Human-readable description of the PV

    - Type: string
    - Required: yes
    - Used in API documentation

**units**
    Measurement units for the PV

    - Type: string
    - Required: no
    - Example: "mm", "GeV", "A", "%"

**pv**
    The actual EPICS PV name

    - Type: string
    - Required: yes
    - Example: "BPM-01:X", "CAV-01:GAIN"

**protocol**
    EPICS communication protocol

    - Type: CA | PVA
    - Required: no
    - Default: CA

**auto_buffer** (for statistical type)
    Automatically start buffering on connection

    - Type: boolean
    - Required: no
    - Default: false

**buffer_size** (for statistical type)
    Number of values to buffer for statistics

    - Type: integer
    - Required: no
    - Default: 100

**properties.name**
    Unique name of this hardware instance

    - Type: string
    - Required: yes
    - Example: "BPM-01", "CAV-01", "MAG-01"

**properties.hardware_type**
    Type classification for hardware grouping

    - Type: string
    - Required: yes
    - Example: "BPM", "CAVITY", "MAGNET"

**properties.subtype**
    Optional subtype for further categorization

    - Type: string
    - Required: no
    - Example: "STRIPLINE", "CYLINDRICAL", "DIPOLE"

**properties.machine_area**
    Location in the accelerator/facility

    - Type: string
    - Required: yes
    - Example: "A1", "A2", "RF", "BEAM"

**properties.position**
    Z-position along the lattice in meters

    - Type: float
    - Required: yes
    - Used for sorting and sequencing


Catapcore Base Classes
----------------------

The generated classes inherit from catapcore's core classes. For detailed documentation, refer to:

- :class:`~catapcore.common.machine.hardware.Hardware`
- :class:`~catapcore.common.machine.hardware.ControlsInformation`
- :class:`~catapcore.common.machine.hardware.Properties`
- :class:`~catapcore.common.machine.hardware.PVMap`
- :class:`~catapcore.common.machine.factory.Factory`

See the `catapcore documentation <https://astec-stfc.github.io/catapcore/>`_ for complete details on these base classes and their methods.
