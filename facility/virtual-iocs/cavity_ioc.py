import os
import time
import numpy as np
from p4p.server import Server, ServerOperation
from p4p.server.thread import SharedPV
from p4p.nt import NTScalar, NTEnum
import random
import threading
import difflib

os.environ["EPICS_PVAS_SERVER_PORT"] = "7000"
os.environ["EPICS_PVAS_BROADCAST_PORT"] = "7000"

# Configuration dictionary for PVs
PV_CONFIG = {
    "CAV-01": {
        "PHASE_SETPOINT": {"virtual_pv": "SIM:CAV:01:PHASE_SETPOINT", "type": "scalar"},
        "AMPLITUDE_SETPOINT": {"pv": "CAV:01:AMPLITUDE_SETPOINT", "type": "scalar"},
        "PHASE_READBACK": {"pv": "CAV:01:PHASE_READBACK", "type": "scalar"},
        "AMPLITUDE_READBACK": {"pv": "CAV:01:AMPLITUDE_READBACK"},
        "CAVITY_STATUS": {
            "pv": "CAV:01:STATUS",
            "type": "state",
            "states": {"OK": 0, "FAULT": 1, "OFF": 2},
        },
        "PROBE_TRACE": {"virtual_pv": "SIM:CAV:01:PROBE_TRACE", "type": "waveform"},
    },
    "CAV-02": {
        "PHASE_SETPOINT": {"virtual_pv": "VIRT:CAV2:PHASE_SETPOINT", "type": "scalar"},
        "AMPLITUDE_SETPOINT": {"pv": "MOD:CAV2:AMPLITUDE_SETPOINT", "type": "scalar"},
        "PHASE_READBACK": {"pv": "MOD:CAV2:PHASE_READBACK", "type": "scalar"},
        "AMPLITUDE_READBACK": {"pv": "MOD:CAV2:AMPLITUDE_READBACK", "type": "scalar"},
        "CAVITY_STATUS": {
            "pv": "MOD:CAV2:STATUS",
            "type": "state",
            "states": {"OK": 0, "FAULT": 1, "OFF": 2},
        },
        "PROBE_TRACE": {"virtual_pv": "VIRT:CAV2:PROBE_TRACE", "type": "waveform"},
    },
    "CAV-03": {
        "PHASE_SETPOINT": {
            "virtual_pv": "SIMSYS:CAV3:PHASE_SETPOINT",
            "type": "scalar",
        },
        "AMPLITUDE_SETPOINT": {"pv": "SYS:CAV3:AMPLITUDE_SETPOINT", "type": "scalar"},
        "PHASE_READBACK": {"pv": "SYS:CAV3:PHASE_READBACK", "type": "scalar"},
        "AMPLITUDE_READBACK": {"pv": "SYS:CAV3:AMPLITUDE_READBACK", "type": "scalar"},
        "CAVITY_STATUS": {
            "pv": "SYS:CAV3:STATUS",
            "type": "state",
            "states": {"OK": 0, "FAULT": 1, "OFF": 2},
        },
        "PROBE_TRACE": {"virtual_pv": "SIMSYS:CAV3:PROBE_TRACE", "type": "waveform"},
    },
    "CAV-04": {
        "PHASE_SETPOINT": {"virtual_pv": "VCTRL:CAV4:PHASE_SETPOINT", "type": "scalar"},
        "AMPLITUDE_SETPOINT": {"pv": "CTRL:CAV4:AMPLITUDE_SETPOINT", "type": "scalar"},
        "PHASE_READBACK": {"pv": "CTRL:CAV4:PHASE_READBACK", "type": "scalar"},
        "AMPLITUDE_READBACK": {"pv": "CTRL:CAV4:AMPLITUDE_READBACK", "type": "scalar"},
        "CAVITY_STATUS": {
            "pv": "CTRL:CAV4:STATUS",
            "type": "state",
            "states": {"OK": 0, "FAULT": 1, "OFF": 2},
        },
        "PROBE_TRACE": {"virtual_pv": "VCTRL:CAV4:PROBE_TRACE", "type": "waveform"},
    },
}


class Handler:
    """
    Handler class for processing 'put' operations on PVs.
    """

    def put(self, pv: SharedPV, op: ServerOperation):
        """
        Handles 'put' operations by posting the new value to the PV.
        Adds a timestamp if one is not already present.

        Args:
            pv (SharedPV): The process variable to update.
            op (ServerOperation): The operation containing the new value.
        """
        if not op.value().raw.changed("timeStamp"):
            timestamp = time.time()
            pv.post(op.value(), timestamp=timestamp)
        else:
            pv.post(op.value())
        op.done()


class EnumHandler(Handler):

    def put(self, pv, op):
        if not op.value().changed("timeStamp"):
            seconds, nanoseconds = time_in_seconds_and_nanoseconds(time.time())
            op.value()["timeStamp"] = {
                "secondsPastEpoch": seconds,
                "nanoseconds": nanoseconds,
                "userTag": 0,
            }
        pv.post(op.value())
        op.done()


def _find_closest_pv(pv: str, search_term: str) -> str:
    prefix = pv.split(f":{pv}")[0]
    cavity_name = difflib.get_close_matches(
        prefix,
        PV_CONFIG.keys(),
        n=1,
        cutoff=0.1,
    )[0]
    pv_config = PV_CONFIG.get(cavity_name, {}).get(
        search_term,
        {},
    )
    if "virtual_pv" in pv_config:
        result_pv = pv_config.get("virtual_pv")
    else:
        result_pv = f"VM-{pv_config.get('pv', '')}"
    return result_pv


def _generate_waveform(amplitude=1.0, num_points=1024):
    """
    Generate a probe-like waveform which is scaled by the amplitude with 1024 point

    Args:
    amplitude (float): Amount to scale the waveform by.
    num_points (int): Length of the output waveform.

    Returns:
        np.ndarray: waveform
    """
    # Generate x values in the range (0.001, 4] (us)
    x = np.linspace(0.001, 4, num_points)

    # Compute the waveform
    waveform = x**0.3 * (1 - np.log(x))
    waveform /= np.max(waveform)
    waveform *= amplitude

    return waveform


def update_pvs_periodically(pv_objects, update_interval=0.1):
    """
    Periodically updates selected PVs with random values or state changes.

    Args:
        pv_objects (dict): Dictionary of PV name to SharedPV objects.
        update_interval (float): Time between updates in seconds.
    """

    def updater():
        while True:
            timestamp = time.time()
            for name, pv in pv_objects.items():
                status_pv = _find_closest_pv(
                    name,
                    search_term="CAVITY_STATUS",
                )
                setpoint_pv = None
                value = random.uniform(-0.2, 0.2)
                # Update scalar readbacks
                if "PHASE_READBACK" in name:
                    setpoint_pv = _find_closest_pv(
                        name,
                        search_term="PHASE_SETPOINT",
                    )
                if "AMPLITUDE_READBACK" in name:
                    setpoint_pv = _find_closest_pv(
                        name,
                        search_term="AMPLITUDE_SETPOINT",
                    )
                if setpoint_pv:
                    if pv_objects[status_pv].current().value.index == 0:
                        value = pv_objects[setpoint_pv].current().real + random.uniform(
                            -0.2, 0.2
                        )
                    pv.post(
                        value,
                        timestamp=timestamp,
                    )
                # Update waveform readbacks based on amplitude
                if "TRACE" in name:
                    amplitude_pv = _find_closest_pv(
                        name,
                        search_term="AMPLITUDE_READBACK",
                    )
                    waveform = _generate_waveform(
                        amplitude=pv_objects[amplitude_pv].current().real
                    )
                    pv.post(
                        waveform.tolist(),
                        timestamp=timestamp,
                    )

            time.sleep(update_interval)

    thread = threading.Thread(target=updater, daemon=True)
    thread.start()


def time_in_seconds_and_nanoseconds(timestamp: float):
    """
    Converts a floating-point timestamp into seconds and nanoseconds.

    Args:
        timestamp (float): The timestamp to convert.

    Returns:
        tuple: (seconds, nanoseconds)
    """
    seconds = int(timestamp)
    nanoseconds = int((timestamp % 1) * 1e9)
    return seconds, nanoseconds


def get_server_conf():
    """
    Retrieves EPICS server configuration from environment variables.

    Returns:
        dict: Configuration dictionary for the EPICS server.
    """
    return {
        "EPICS_PVAS_BROADCAST_PORT": str(os.getenv("EPICS_PVAS_BROADCAST_PORT", 6090)),
        "EPICS_PVAS_SERVER_PORT": str(os.getenv("EPICS_PVAS_SERVER_PORT", 6090)),
        "EPICS_PVA_ADDR_LIST": str(os.getenv("EPICS_PVA_ADDR_LIST", "")),
        "EPICS_PVA_AUTO_ADDR_LIST": str(os.getenv("EPICS_PVA_AUTO_ADDR_LIST", "YES")),
        "EPICS_PVA_SERVER_PORT": str(os.getenv("EPICS_PVA_SERVER_PORT", 6090)),
        "EPICS_PVA_INTF_ADDR_LIST": str(os.getenv("EPICS_PVA_INTF_ADDR_LIST", "")),
    }


def create_pv(cfg: dict):
    """
    Creates a SharedPV object based on the configuration.

    Args:
        name (str): The name of the PV.
        cfg (dict): Configuration dictionary for the PV.

    Returns:
        SharedPV: The created process variable.
    """
    pv_type = cfg.get("type", "scalar")
    seconds, nanoseconds = time_in_seconds_and_nanoseconds(time.time())

    if pv_type == "scalar":
        nt = NTScalar("d")
        initial = 0.0
        return SharedPV(nt=nt, initial=initial, handler=Handler())

    elif pv_type == "waveform":
        nt = NTScalar("ad", display=True)
        initial = []
        return SharedPV(nt=nt, initial=initial, handler=Handler())

    elif pv_type == "state":
        initial = NTEnum.buildType()()
        initial.value.index = 0
        initial.value.choices = list(cfg["states"].keys())
        initial.timeStamp = {
            "secondsPastEpoch": seconds,
            "nanoseconds": nanoseconds,
            "userTag": 0,
        }

        return SharedPV(handler=EnumHandler(), initial=initial)

    return None


def main():
    # Create PV objects
    pv_objects = {}
    for _, entry in PV_CONFIG.items():
        for _, cfg in entry.items():
            name = (
                cfg.get("virtual_pv")
                if "virtual_pv" in cfg
                else f"VM-{cfg.get('pv', '')}"
            )
            if name is None:
                continue
            pv = create_pv(cfg)
            if pv:
                pv_objects[name] = pv

    # Start periodic updates (default: 10Hz)
    update_pvs_periodically(pv_objects, update_interval=0.1)

    # Start the EPICS server
    conf = get_server_conf()
    print(f"Starting server with configuration: {conf}")
    with Server(providers=[pv_objects], conf=conf) as server:
        try:
            print("Server started. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Server stopped by user.")
            server.stop()


if __name__ == "__main__":
    main()
