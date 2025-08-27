import os
import enum
import random
from caproto.server import pvproperty, PVGroup, run
from caproto import ChannelType

# Set the EPICS Channel Access server port
os.environ["EPICS_CA_SERVER_PORT"] = "6000"


class StatusEnum(enum.Enum):
    STOP = 0
    START = 1


class BPMv1(PVGroup):
    x_pv = pvproperty(name=":X_RB", value=0.0, dtype=ChannelType.FLOAT)
    y_pv = pvproperty(name=":Y_VAL", value=0.0, dtype=ChannelType.FLOAT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @x_pv.startup
    async def x_pv(self, instance, async_lib):
        await instance.write(value=random.uniform(-0.2, 0.2))

    @y_pv.startup
    async def y_pv(self, instance, async_lib):
        await instance.write(value=random.uniform(-0.2, 0.2))

    @x_pv.scan(period=0.1)
    async def x_pv(self, instance, async_lib):
        await instance.write(value=random.uniform(-0.2, 0.2))

    @y_pv.scan(period=0.1)
    async def y_pv(self, instance, async_lib):
        await instance.write(value=random.uniform(-0.2, 0.2))


class BPMv2(PVGroup):
    x_pv = pvproperty(name=":X_RBV", value=0.0, dtype=ChannelType.FLOAT)
    y_pv = pvproperty(name=":Y_READBACK", value=0.0, dtype=ChannelType.FLOAT)
    acquisition_status_pv = pvproperty(
        name=":ACQUIRE_RBV", value=StatusEnum.STOP.value, dtype=ChannelType.INT
    )
    set_acquire_pv = pvproperty(
        name=":ACQUIRE",
        value=StatusEnum.STOP.value,
        dtype=ChannelType.ENUM,
        enum_strings=[e.name for e in StatusEnum],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @x_pv.startup
    async def x_pv(self, instance, async_lib):
        await instance.write(value=random.uniform(-0.2, 0.2))

    @y_pv.startup
    async def y_pv(self, instance, async_lib):
        await instance.write(value=random.uniform(-0.2, 0.2))

    @set_acquire_pv.putter
    async def set_acquire_pv(self, instance, value):
        if value in StatusEnum._value2member_map_:
            await self.acquisition_status_pv.write(value)
            print(f"Acquisition set to: {StatusEnum(value).name}")

    @x_pv.scan(period=0.1)
    async def x_pv(self, instance, async_lib):
        if self.set_acquire_pv.value == StatusEnum.START.value:
            await instance.write(value=random.uniform(-0.2, 0.2))

    @y_pv.scan(period=0.1)
    async def y_pv(self, instance, async_lib):
        if self.set_acquire_pv.value == StatusEnum.START.value:
            await instance.write(value=random.uniform(-0.2, 0.2))


def main():
    ioc1 = BPMv1(prefix="VM-BPM-01")
    ioc2 = BPMv2(prefix="VM-BPM-02")

    combined_pvdb = {**ioc1.pvdb, **ioc2.pvdb}
    print("Server started. Press Ctrl+C to stop.")
    run(combined_pvdb)
    print("Server stopped by user.")


if __name__ == "__main__":
    main()
