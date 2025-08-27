import os
import time
from hardware.cavity import CavityFactory

# Set EPICS PVA for local communication
os.environ["EPICS_PVA_NAME_SERVERS"] = "localhost:7000"


def print_cavity_readbacks(cavities: CavityFactory):
    """
    Prints amplitude and phase readbacks for all cavities.

    Args:
        cavities (CavityFactory): The cavity factory instance.
    """
    amplitudes = cavities.amplitude_readback()
    phases = cavities.phase_readback()

    for name in cavities.names:
        print(f"{name} Amplitude: {amplitudes.get(name, None)}")
        print(f"{name} Phase: {phases.get(name, None)}")


def wait_for_full_buffer(statistics, cavity_name: str):
    """
    Waits until the statistics buffer is full.

    Args:
        statistics: The statistics object with buffer info.
        cavity_name (str): Name of the cavity (for logging).
    """
    while not statistics.is_buffer_full:
        print(
            f"Waiting for {cavity_name} amplitude buffer to fill "
            f"({len(statistics.buffer)}/{statistics.buffer_size})",
            end="\r",
        )
        time.sleep(1.0)


def clear_and_refill_buffer(statistics, cavity_name: str, new_size: int = 25):
    """
    Clears the buffer and waits for it to refill.

    Args:
        statistics: The statistics object to clear and monitor.
        cavity_name (str): Name of the cavity (for logging).
        new_size (int): New buffer size to set.
    """
    statistics.buffer_size = new_size
    statistics.clear_buffer()
    print(f"Buffer cleared: ({len(statistics.buffer)}/{statistics.buffer_size})")
    wait_for_full_buffer(statistics, cavity_name)


def print_statistics(statistics, cavity_name: str):
    """
    Prints statistical data for the cavity.

    Args:
        statistics: The statistics object containing data.
        cavity_name (str): Name of the cavity.
    """
    print(f"\nFilled buffer for {cavity_name} AMPLITUDE ({len(statistics.buffer)}/{statistics.buffer_size})")
    print("Amplitude Mean:", statistics.mean)
    print("Amplitude Std Dev:", statistics.stdev)
    print("Amplitude Min:", statistics.min)
    print("Amplitude Max:", statistics.max)


def main():
    """
    Main function to read cavity data, manage buffers, and print statistics.
    """
    cavities = CavityFactory()

    # Print amplitude and phase readbacks
    print_cavity_readbacks(cavities)

    # Access a specific cavity and its amplitude statistics
    cavity = cavities.get_cavity("CAV-01")
    amp_stats = cavity.get_statistics("AMPLITUDE_READBACK")

    # Ensure cavity status is OK
    if cavity.status != "OK":
        cavity.status = "OK"

    print("Full Buffer?:", amp_stats.is_buffer_full)

    # Wait for initial buffer fill
    wait_for_full_buffer(amp_stats, cavity.name)

    # Clear and refill buffer with new size
    clear_and_refill_buffer(amp_stats, cavity.name)

    # Print final statistics
    print_statistics(amp_stats, cavity.name)


if __name__ == "__main__":
    main()
