import os
import time
from hardware.bpm import BPMFactory

# Set EPICS CA server port for communication with control system
os.environ["EPICS_CA_SERVER_PORT"] = "6000"


def print_bpm_readbacks(bpms: BPMFactory):
    """
    Prints the current X and Y position readbacks for all BPMs.

    Args:
        bpms (BPMFactory): The BPM factory instance.
    """
    x_readings = bpms.x()
    y_readings = bpms.y()

    for name in bpms.names:
        print(f"{name} X: {x_readings.get(name, 'N/A')}")
        print(f"{name} Y: {y_readings.get(name, 'N/A')}")


def wait_for_buffer_fill(statistics, bpm_name: str, delay: float = 0.1):
    """
    Waits until the statistics buffer is full.

    Args:
        statistics: The statistics object to monitor.
        bpm_name (str): Name of the BPM (for logging).
        delay (float): Time to wait between checks (in seconds).
    """
    while not statistics.is_buffer_full:
        print(
            f"Waiting for {bpm_name} X buffer to fill "
            f"({len(statistics.buffer)}/{statistics.buffer_size})",
            end="\r",
        )
        time.sleep(delay)


def clear_and_refill_buffer(statistics, bpm_name: str, new_size: int = 100):
    """
    Clears the buffer and waits for it to refill with new data.

    Args:
        statistics: The statistics object to clear and monitor.
        bpm_name (str): Name of the BPM (for logging).
        new_size (int): New buffer size to set.
    """
    statistics.buffer_size = new_size
    statistics.clear_buffer()
    print(f"Buffer cleared: ({len(statistics.buffer)}/{statistics.buffer_size})")
    wait_for_buffer_fill(statistics, bpm_name)


def print_statistics(statistics, bpm_name: str):
    """
    Prints statistical data for the BPM's X position.

    Args:
        statistics: The statistics object containing data.
        bpm_name (str): Name of the BPM.
    """
    print(
        f"\nFilled buffer for {bpm_name} X ({len(statistics.buffer)}/{statistics.buffer_size})"
    )
    print("X Mean:", statistics.mean)
    print("X Standard Deviation:", statistics.stdev)
    print("X Min:", statistics.min)
    print("X Max:", statistics.max)


def main():
    """
    Main function to demonstrate BPM data acquisition and statistics.
    """
    # Instantiate the BPM factory
    bpms = BPMFactory()

    # Print current X and Y readbacks for all BPMs
    print_bpm_readbacks(bpms)

    # Access a specific BPM and its X statistics
    bpm = bpms.get_bpm("BPM-01")
    x_stats = bpm.get_statistics("X")

    print("Full Buffer?:", x_stats.is_buffer_full)

    # If buffer is full, clear it and refill with new data
    if x_stats.is_buffer_full:
        clear_and_refill_buffer(x_stats, bpm.name)

    # Wait until buffer is full
    wait_for_buffer_fill(x_stats, bpm.name)

    # Print statistical summary
    print_statistics(x_stats, bpm.name)


if __name__ == "__main__":
    main()
