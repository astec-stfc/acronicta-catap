Examples
=========

This section provides practical examples of using acronicta-catap to generate and work with hardware control systems.

Basic Hardware Definition
-------------------------

Define your hardware in a YAML file:

**yaml/BPM/BPM-01.yaml**

.. code-block:: yaml

    controls_information:
        pv_record_map:
            x:
                type: scalar
                description: "X position readback"
                units: "mm"
                pv: "BPM-01:X"
            y:
                type: scalar
                description: "Y position readback"
                units: "mm"
                pv: "BPM-01:Y"
            intensity:
                type: scalar
                description: "Beam intensity"
                units: "nC"
                pv: "BPM-01:INTENSITY"
    
    properties:
        name: BPM-01
        hardware_type: BPM
        subtype: STRIPLINE
        machine_area: A1
        position: 1.5


Generating Hardware Classes
---------------------------

Run the generation script to create Python classes from your YAML definitions:

.. code-block:: bash

    python ./scripts/generate_hardware.py \
        --yaml_location "./yaml" \
        --output_location "./output" \
        --overwrite_hardware

This will create:
- ``output/hardware/bpm.py`` with ``BPM`` and ``BPMFactory`` classes
- ``output/hardware/__init__.py`` with imports
- ``output/constants.py`` with machine areas


Reading Hardware Values
-----------------------

Once you have generated and installed your hardware classes, you can use them:

.. code-block:: python

    from hardware.bpm import BPMFactory

    # Create factory with real EPICS connections
    bpm_factory = BPMFactory(is_virtual=False, connect_on_creation=True)
    
    # Get a specific BPM
    bpm_01 = bpm_factory.get_hardware_by_name("BPM-01")
    
    # Read PV values
    x_position = bpm_01.x  # Uses catapcore's get() method
    y_position = bpm_01.y
    intensity = bpm_01.intensity
    
    print(f"BPM Position: X={x_position} mm, Y={y_position} mm")
    print(f"Beam Intensity: {intensity} nC")


Batch Operations
----------------

Work with multiple hardware instances efficiently:

.. code-block:: python

    from hardware.bpm import BPMFactory
    
    # Create factory
    factory = BPMFactory(is_virtual=False)
    
    # Get all BPMs
    all_bpms = factory.hardware
    print(f"Found {len(all_bpms)} BPM devices")
    
    # Filter by machine area
    area_a1_bpms = factory.get_hardware_by_area("A1")
    print(f"BPMs in area A1: {len(area_a1_bpms)}")
    
    # Filter by subtype
    stripline_bpms = factory.get_hardware_by_subtype("STRIPLINE")
    
    # Perform operations on all
    for bpm in all_bpms:
        print(f"{bpm.name}: X={bpm.x}, Y={bpm.y}")


Virtual Testing
---------------

Test without a real EPICS system:

.. code-block:: python

    from hardware.bpm import BPMFactory
    
    # Create factory in virtual mode
    # This prepends "TEST:" to all PV names
    factory = BPMFactory(is_virtual=True, connect_on_creation=False)
    
    # Get a BPM
    bpm_01 = factory.get_hardware_by_name("BPM-01")
    
    # In virtual mode, PV names become "TEST:BPM-01:X", etc.
    # This allows testing without affecting the real system


Snapshot Management
-------------------

Save and restore hardware states:

.. code-block:: python

    from hardware.bpm import BPMFactory
    
    factory = BPMFactory(is_virtual=False)
    
    # Take a snapshot of current state
    initial_state = factory.create_snapshot()
    
    # Modify hardware (if writable)
    bpm_01 = factory.get_hardware_by_name("BPM-01")
    # ... make changes ...
    
    # Restore to previous state
    factory.apply_snapshot(initial_state)


Multiple Hardware Types
-----------------------

Organize different hardware types in separate YAML directories:

.. code-block:: text

    yaml/
    ├── BPM/
    │   ├── BPM-01.yaml
    │   ├── BPM-02.yaml
    │   └── BPM-03.yaml
    ├── Cavity/
    │   ├── CAV-01.yaml
    │   ├── CAV-02.yaml
    │   └── CAV-03.yaml
    └── Magnet/
        ├── MAG-01.yaml
        └── MAG-02.yaml


Generate all hardware types:

.. code-block:: bash

    python ./scripts/generate_hardware.py \
        --yaml_location "./yaml" \
        --output_location "./output" \
        --overwrite_hardware


Use all hardware types together:

.. code-block:: python

    from hardware.bpm import BPMFactory
    from hardware.cavity import CavityFactory
    from hardware.magnet import MagnetFactory
    
    # Create factories for each hardware type
    bpms = BPMFactory(is_virtual=False)
    cavities = CavityFactory(is_virtual=False)
    magnets = MagnetFactory(is_virtual=False)
    
    # Use them together
    print(f"BPMs: {len(bpms.hardware)}")
    print(f"Cavities: {len(cavities.hardware)}")
    print(f"Magnets: {len(magnets.hardware)}")
    
    # Get diagnostics
    for bpm in bpms.hardware:
        x = bpm.x
        y = bpm.y
        print(f"{bpm.name}: ({x}, {y})")


Integrated System Example
-------------------------

A complete example managing multiple hardware types:

.. code-block:: python

    from hardware.bpm import BPMFactory
    from hardware.cavity import CavityFactory
    
    class BeamlineControl:
        """High-level control of the beamline."""
        
        def __init__(self, is_virtual=False):
            self.bpms = BPMFactory(is_virtual=is_virtual)
            self.cavities = CavityFactory(is_virtual=is_virtual)
        
        def diagnostics(self):
            """Read all beam diagnostics."""
            results = {}
            
            # BPM measurements
            for bpm in self.bpms.hardware:
                results[bpm.name] = {
                    'x': bpm.x,
                    'y': bpm.y,
                    'intensity': bpm.intensity
                }
            
            # Cavity diagnostics
            for cavity in self.cavities.hardware:
                results[cavity.name] = {
                    'voltage': cavity.voltage,
                    'phase': cavity.phase
                }
            
            return results
        
        def get_status(self):
            """Generate system status report."""
            diagnostics = self.diagnostics()
            
            print("=== Beamline Status ===")
            for name, data in diagnostics.items():
                print(f"{name}:")
                for key, value in data.items():
                    print(f"  {key}: {value}")
        
        def take_snapshot(self):
            """Take snapshot of entire beamline state."""
            return {
                'bpms': self.bpms.create_snapshot(),
                'cavities': self.cavities.create_snapshot(),
                'timestamp': __import__('time').time()
            }
    
    # Usage
    if __name__ == "__main__":
        beamline = BeamlineControl(is_virtual=False)
        beamline.get_status()
        
        # Save state
        state = beamline.take_snapshot()
        
        # Make changes...
        
        # Restore state
        beamline.bpms.apply_snapshot(state['bpms'])
        beamline.cavities.apply_snapshot(state['cavities'])


Common Patterns
---------------

**Filtering by Machine Area**

.. code-block:: python

    factory = BPMFactory()
    area_a1 = factory.get_hardware_by_area("A1")

**Getting All Hardware**

.. code-block:: python

    factory = BPMFactory()
    all_hardware = factory.hardware

**Accessing PV Information**

.. code-block:: python

    bpm = factory.get_hardware_by_name("BPM-01")
    # Access the PVMap directly for advanced operations
    pv_map = bpm.controls_information.pv_record_map
    x_pv = pv_map.x  # Get the PVSignal object

**Statistical PVs**

.. code-block:: python

    # If you have statistical PVs configured
    bpm = factory.get_hardware_by_name("BPM-01")
    
    # Start buffering
    bpm.start_buffering()
    
    # ... collect data ...
    
    # Check if buffer is full
    if bpm.is_buffer_full():
        stats = bpm.statistics
    
    # Stop buffering
    bpm.stop_buffering()

For more information on catapcore's features, refer to the `catapcore documentation <https://astec-stfc.github.io/catapcore/>`_.
