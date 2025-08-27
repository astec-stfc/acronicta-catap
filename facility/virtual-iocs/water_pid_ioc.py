import asyncio
import os
import random
import threading
import time
import sys

# Caproto (Channel Access) imports
from caproto.server import pvproperty, PVGroup, run

import numpy as np

# P4P (PVAccess) imports
from p4p.server import Server, ServerOperation
from p4p.server.thread import SharedPV
from p4p.nt import NTScalar
from p4p.client.thread import Context

# ------------------------------------------------------------------------------
# Environment Configuration
# ------------------------------------------------------------------------------

# Set distinct ports for Channel Access and PVAccess servers
os.environ["EPICS_CA_SERVER_PORT"] = "6000"
os.environ["EPICS_PVA_SERVER_PORT"] = "7000"

# ------------------------------------------------------------------------------
# Channel Access IOC (Caproto)
# ------------------------------------------------------------------------------


class CAIOC(PVGroup):
    """
    Channel Access IOC hosting cavity temperature and pressure PVs.
    """

    cavity_temperature = pvproperty(
        name=":CAVITY_TEMP", value=25.0, doc="Cavity temperature in Celsius"
    )

    cavity_pressure = pvproperty(
        name=":CAVITY_PRESSURE", value=1.0, doc="Cavity pressure in Bar"
    )

    @cavity_temperature.scan(period=0.1)
    async def cavity_temperature(self, instance, async_lib):
        loop = asyncio.get_running_loop()
        pva_ctx = Context("pva")
        pva_pvname = "VM-H20-PID-01:PID_READBACK"

        # Run P4P get in a thread to avoid blocking
        def get_pva_value():
            return pva_ctx.get(pva_pvname)

        try:
            pva_value = await loop.run_in_executor(None, get_pva_value)
            await instance.write(pva_value + random.uniform(-0.01, 0.01))
        except Exception as e:
            print(f"Error reading P4P PV: {e}")

    def _calculate_water_vapor_pressure(self, temp_celsius: float) -> float:
        """
        Calculate water vapor pressure in mBar given temperature in Celsius.

        Parameters:
            temp_celsius (float or array-like): Temperature in degrees Celsius.

        Returns:
            float or np.ndarray: Pressure in mBar.
        """
        temp_celsius = np.asarray(temp_celsius)
        pressure_hpa = 6.112 * np.exp((17.62 * temp_celsius) / (243.12 + temp_celsius))
        pressure_mbar = pressure_hpa / 100  # Convert hPa to Bar
        return pressure_mbar

    @cavity_pressure.scan(period=0.1)
    async def cavity_pressure(self, instance, async_lib):
        await instance.write(
            value=self._calculate_water_vapor_pressure(
                self.cavity_temperature.value,
            ),
        )


def run_ca_ioc():
    """
    Starts the Channel Access IOC with prefix 'CA'.
    """
    ioc = CAIOC(prefix="VM-H20-PID-01")
    run(ioc.pvdb)


# ------------------------------------------------------------------------------
# PVAccess IOC (P4P)
# ------------------------------------------------------------------------------


class PVAHandler:
    """
    Handler for PVAccess 'put' operations.
    Posts the new value and marks the operation as complete.
    """

    def put(self, pv, op: ServerOperation):
        pv.post(op.value())
        op.done()


# ------------------------------------------------------------------------------
# Main Execution: Run both IOCs concurrently with graceful shutdown
# ------------------------------------------------------------------------------


def main():
    stop_event = threading.Event()

    # Start Channel Access IOC
    ca_ioc = CAIOC(prefix="VM-H20-PID-01")
    ca_thread = threading.Thread(target=run, args=(ca_ioc.pvdb,), daemon=True)

    # Start PVAccess IOC
    pid_setpoint = SharedPV(nt=NTScalar("d"), initial=24.5, handler=PVAHandler())
    pid_readback = SharedPV(nt=NTScalar("d"), initial=24.7, handler=PVAHandler())
    pva_pvs = {
        "VM-H20-PID-01:PID_SETPOINT": pid_setpoint,
        "VM-H20-PID-01:PID_READBACK": pid_readback,
    }

    def update_loop():
        while not stop_event.is_set():
            timestamp = time.time()
            # Simulate dynamic values
            readback = pid_setpoint.current().real + 0.2 * (0.5 - (time.time() % 1))
            pid_readback.post(readback, timestamp=timestamp)
            time.sleep(1.0)

    updater_thread = threading.Thread(target=update_loop, daemon=True)
    updater_thread.start()

    def pva_runner():
        with Server(providers=[pva_pvs]):
            while not stop_event.is_set():
                time.sleep(0.5)

    pva_thread = threading.Thread(target=pva_runner, daemon=True)

    # Start threads
    ca_thread.start()
    pva_thread.start()

    print("Both Channel Access and PVAccess IOCs are running. Press Ctrl+C to exit.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down IOCs...")
        stop_event.set()
        ca_thread.join(timeout=2)
        pva_thread.join(timeout=2)
        print("IOCs stopped successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
