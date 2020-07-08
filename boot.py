from network import Bluetooth, LTE
import pycom

pycom.heartbeat(False)

# Disable bluetooth to save power
bluetooth = Bluetooth()
bluetooth.deinit()

# Disable LTE to save power
lte = LTE()
lte.deinit()