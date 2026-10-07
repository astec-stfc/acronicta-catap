import importlib.util
import os
import shutil
import tempfile
import unittest
import warnings

import yaml

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "generate_hardware.py",
)
_spec = importlib.util.spec_from_file_location("generate_hardware", _SCRIPT)
gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gh)


# A parent as LAURA writes one: the shared physics, at the root of the tree.
PARENT = {
    "name": "Quadrupole_L0p263",
    "hardware_class": "Magnet",
    "hardware_type": "Quadrupole",
    "magnetic": {"length": 0.263, "multipoles": {"K1L": {"order": 1}}},
    "physical": {"length": 0.263, "middle": {"z": 1.0}},
    "subelement": "SOL1",
}

# A child as LAURA writes one: only what differs, and a schema reference
# instead of a PV map.
CHILD = {
    "name": "QDOG7",
    "inherits_from": "Quadrupole_L0p263",
    "machine_area": "COL0",
    "controls": {
        "identifier_pattern": "QUAD:DOG:215",
        "schema": "Quadrupole_schema.yaml",
    },
    "magnetic": {"multipoles": {"K1L": {"normal": 0.148}}},
    "physical": {"middle": {"z": 1033.4}, "s": 1033.4},
}

SCHEMA = {
    "variables": {
        "bact": {
            "dtype": "float",
            "identifier": "{name}:BACT",
            "protocol": "CA",
            "type": "scalar",
        },
        "bctrl": {
            "dtype": "float",
            "identifier": "{name}:BCTRL",
            "protocol": "CA",
            "type": "scalar",
        },
    }
}

# A facility with neither indirection (JFEL, ISIS, CLARA all look like this).
INLINE = {
    "name": "JFEL-S08-MAG-QUAD-01",
    "hardware_class": "Magnet",
    "hardware_type": "Quadrupole",
    "machine_area": "S08",
    "controls": {
        "variables": {
            "SETI": {
                "identifier": "JFEL-S08-MAG-QUAD-01:SETI",
                "type": "scalar",
                "read_only": False,
            }
        }
    },
}


def write_yaml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f)


class LatticeTreeTestCase(unittest.TestCase):
    """Builds the directory shape a LAURA lattice actually has: parents at the
    root, elements and their schema in a leaf directory below it."""

    def setUp(self):
        gh._SCHEMA_VARIABLE_CACHE.clear()
        self.root = tempfile.mkdtemp()
        self.leaf = os.path.join(self.root, "Magnet", "Quadrupole")
        write_yaml(os.path.join(self.root, "_Quadrupole_L0p263.yaml"), PARENT)
        write_yaml(os.path.join(self.leaf, "QDOG7.yaml"), CHILD)
        write_yaml(os.path.join(self.leaf, "Quadrupole_schema.yaml"), SCHEMA)
        write_yaml(os.path.join(self.leaf, "JFEL-S08-MAG-QUAD-01.yaml"), INLINE)

    def tearDown(self):
        shutil.rmtree(self.root)


class TestGetExampleFiles(LatticeTreeTestCase):
    def test_schema_files_are_not_elements(self):
        files = gh.get_example_files(self.root, [])
        self.assertNotIn("Quadrupole_schema.yaml", [os.path.basename(f) for f in files])

    def test_leaf_elements_are_collected(self):
        files = [os.path.basename(f) for f in gh.get_example_files(self.root, [])]
        self.assertCountEqual(files, ["QDOG7.yaml", "JFEL-S08-MAG-QUAD-01.yaml"])


class TestBuildElementNamespace(LatticeTreeTestCase):
    def test_indexes_root_level_parents(self):
        # the parent is the point of the namespace: get_example_files never
        # returns it, because the root of the tree is not a leaf directory.
        namespace = gh.build_element_namespace(self.root)
        self.assertIn("Quadrupole_L0p263", namespace)
        self.assertEqual(namespace["Quadrupole_L0p263"]["hardware_type"], "Quadrupole")

    def test_skips_schema_files(self):
        namespace = gh.build_element_namespace(self.root)
        self.assertEqual(
            sorted(namespace),
            ["JFEL-S08-MAG-QUAD-01", "QDOG7", "Quadrupole_L0p263"],
        )


class TestResolveInheritance(unittest.TestCase):
    def setUp(self):
        self.namespace = {PARENT["name"]: PARENT}

    def test_child_gains_parent_hardware_type(self):
        resolved = gh.resolve_inheritance(CHILD, self.namespace)
        self.assertEqual(resolved["hardware_type"], "Quadrupole")
        self.assertEqual(resolved["hardware_class"], "Magnet")

    def test_child_keeps_its_own_identity(self):
        resolved = gh.resolve_inheritance(CHILD, self.namespace)
        self.assertEqual(resolved["name"], "QDOG7")
        self.assertNotIn("subelement", resolved)

    def test_child_overrides_win_and_merge_key_by_key(self):
        resolved = gh.resolve_inheritance(CHILD, self.namespace)
        self.assertEqual(
            resolved["magnetic"]["multipoles"]["K1L"], {"order": 1, "normal": 0.148}
        )
        self.assertEqual(resolved["magnetic"]["length"], 0.263)

    def test_position_is_never_inherited(self):
        resolved = gh.resolve_inheritance(CHILD, self.namespace)
        self.assertEqual(resolved["physical"]["middle"], {"z": 1033.4})
        self.assertEqual(resolved["physical"]["length"], 0.263)

    def test_element_without_inherits_from_is_untouched(self):
        self.assertIs(gh.resolve_inheritance(INLINE, self.namespace), INLINE)

    def test_chain_is_followed_to_the_root(self):
        middle = {"name": "Mid", "inherits_from": "Quadrupole_L0p263", "order": 1}
        leaf = {"name": "Leaf", "inherits_from": "Mid"}
        namespace = dict(self.namespace, Mid=middle)
        resolved = gh.resolve_inheritance(leaf, namespace)
        self.assertEqual(resolved["hardware_type"], "Quadrupole")
        self.assertEqual(resolved["order"], 1)
        self.assertEqual(resolved["name"], "Leaf")

    def test_missing_parent_warns_and_leaves_element_unresolved(self):
        orphan = {"name": "Orphan", "inherits_from": "NoSuchElement"}
        with self.assertWarnsRegex(UserWarning, "NoSuchElement"):
            resolved = gh.resolve_inheritance(orphan, self.namespace)
        self.assertIs(resolved, orphan)

    def test_cycle_warns_rather_than_recursing_forever(self):
        a = {"name": "A", "inherits_from": "B"}
        b = {"name": "B", "inherits_from": "A"}
        with self.assertWarnsRegex(UserWarning, "inheritance cycle"):
            gh.resolve_inheritance(a, {"A": a, "B": b})

    def test_parent_is_not_mutated_by_resolving_a_child(self):
        parent = {k: v for k, v in PARENT.items()}
        gh.resolve_inheritance(CHILD, {PARENT["name"]: parent})
        self.assertEqual(parent["magnetic"]["multipoles"]["K1L"], {"order": 1})


class TestResolveControlsSchema(LatticeTreeTestCase):
    def test_name_placeholder_uses_the_identifier_pattern(self):
        resolved = gh.resolve_controls_schema(CHILD["controls"], "QDOG7", self.leaf)
        self.assertEqual(
            resolved["variables"]["bact"]["identifier"], "QUAD:DOG:215:BACT"
        )

    def test_name_placeholder_falls_back_to_the_element_name(self):
        controls = {"schema": "Quadrupole_schema.yaml"}
        resolved = gh.resolve_controls_schema(controls, "QDOG7", self.leaf)
        self.assertEqual(resolved["variables"]["bctrl"]["identifier"], "QDOG7:BCTRL")

    def test_inline_variables_are_layered_on_field_by_field(self):
        controls = {
            "identifier_pattern": "QUAD:DOG:215",
            "schema": "Quadrupole_schema.yaml",
            "variables": {
                "bctrl": {"read_only": False},
                "extra": {"identifier": "QUAD:DOG:215:EXTRA"},
            },
        }
        resolved = gh.resolve_controls_schema(controls, "QDOG7", self.leaf)
        bctrl = resolved["variables"]["bctrl"]
        self.assertFalse(bctrl["read_only"])
        self.assertEqual(bctrl["identifier"], "QUAD:DOG:215:BCTRL")
        self.assertIn("extra", resolved["variables"])

    def test_resolution_keys_are_dropped(self):
        resolved = gh.resolve_controls_schema(CHILD["controls"], "QDOG7", self.leaf)
        self.assertNotIn("schema", resolved)
        self.assertNotIn("identifier_pattern", resolved)

    def test_controls_without_a_schema_are_untouched(self):
        controls = INLINE["controls"]
        self.assertIs(
            gh.resolve_controls_schema(controls, INLINE["name"], ""), controls
        )

    def test_missing_schema_warns_rather_than_failing_the_build(self):
        controls = {"schema": "NotThere_schema.yaml"}
        with self.assertWarnsRegex(UserWarning, "NotThere_schema.yaml"):
            resolved = gh.resolve_controls_schema(controls, "QDOG7", self.leaf)
        self.assertEqual(resolved["variables"], {})


class TestCollectClassData(LatticeTreeTestCase):
    def collect(self):
        files = gh.get_example_files(self.root, [])
        namespace = gh.build_element_namespace(self.root)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return gh.collect_class_data(files, namespace)

    def test_inheriting_schema_using_element_produces_a_class(self):
        file_pv_keys, file_pv_info = self.collect()[:2]
        self.assertIn("Quadrupole", file_pv_keys)
        self.assertEqual(set(file_pv_info["Quadrupole"]), {"bact", "bctrl", "SETI"})

    def test_resolution_keys_do_not_become_controls_parameters(self):
        # ControlsInformation renders one model field per remaining controls
        # key, and pydantic refuses a field named 'schema'.
        file_controls_info = self.collect()[3]
        self.assertEqual(file_controls_info["Quadrupole"], {})

    def test_without_a_namespace_inherited_elements_are_still_skipped(self):
        # the pre-existing behaviour, kept as the no-namespace default
        files = [os.path.join(self.leaf, "QDOG7.yaml")]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            file_pv_keys = gh.collect_class_data(files)[0]
        self.assertEqual(file_pv_keys, {})


if __name__ == "__main__":
    unittest.main()
