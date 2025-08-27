from typing import Dict
from hardware.cooling import CoolingFactory, Cooling
from catapcore.config import TYPES
from catapcore.common.machine.pv_utils import StatisticalPV
import yaml
import os

# Set EPICS CA server port for communication with control system
os.environ["EPICS_CA_SERVER_PORT"] = "6000"

# Set EPICS PVA for local communication
os.environ["EPICS_PVA_NAME_SERVERS"] = "localhost:7000"


def set_and_wait(
    cavity_pid: Cooling,
    temp_stats: StatisticalPV,
    setpoint: float,
    tolerance: float = 0.01,
    step: int = 0,
    total_steps: int = 1,
):
    """
    Sets the PID setpoint and waits until the temperature stabilizes within the given tolerance.

    Args:
        cavity_pid (Cooling): The cooling PID controller.
        temp_stats (StatisticalPV): Statistical temperature data.
        setpoint (float): Desired temperature setpoint.
        tolerance (float): Acceptable deviation from the setpoint.
        step (int): Current step index (for logging).
        total_steps (int): Total number of steps (for logging).
    """
    cavity_pid.setpoint = setpoint
    while not temp_stats.is_buffer_full and abs(cavity_pid.setpoint - temp_stats.mean) > tolerance:
        print(
            f"Step {step + 1}/{total_steps} | Cavity temp: {round(temp_stats.mean, 3)} {temp_stats.units}",
            end="\r",
        )


def write(filename: str = "pid_setpoint_dataset.yaml", dataset: Dict = {}):
    """
    Writes the dataset to a YAML file.

    Args:
        filename (str): Output filename.
        dataset (Dict): Data to write.
    """
    with open(filename, "w") as file:
        yaml.dump(dataset, file)


def flush_buffer(statistics: StatisticalPV):
    """
    Clears the statistics buffer and waits until new data is available.

    Args:
        statistics (StatisticalPV): The statistics object to flush.
    """
    statistics.clear_buffer()
    while statistics.mean is None:
        pass  # Wait until buffer is filled with valid data


def main():
    """
    Main execution function to scan through PID setpoints and record snapshots.
    """
    # Initialize cooling hardware
    pids = CoolingFactory()
    cavity_pid: Cooling = pids.get_hardware_by_subtype(
        subtypes=TYPES.COOLING.CAVITY_WATER_PID,
        with_subtypes=False,
    )["H20-PID-01"]

    # Define scan parameters
    setpoints = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    tolerance = 0.1
    temp_stats = cavity_pid.get_statistics()["TEMPERATURE"]

    # Wait until buffer is full before starting
    while not cavity_pid.is_buffer_full("TEMPERATURE"):
        print("Filling buffer before starting scan.", end="\r")

    output_data = {}

    # Iterate through each setpoint
    for step, value in enumerate(setpoints):
        flush_buffer(temp_stats)
        set_and_wait(
            cavity_pid=cavity_pid,
            temp_stats=temp_stats,
            setpoint=value,
            tolerance=tolerance,
            step=step,
            total_steps=len(setpoints),
        )
        output_data[f"step_{step + 1}"] = cavity_pid.create_snapshot()

    # Save results to file
    write(dataset=output_data)


if __name__ == "__main__":
    main()
