# MCU
MCU = cortex-m0plus
ARMV = 6
USE_FPU = no
MCU_FAMILY = HT32
MCU_SERIES = HT32F523xx
MCU_LDSCRIPT = HT32F52352_ANNEPro2D_REV1
MCU_STARTUP = ht32f523xx

BOARD = ANNEPro2D_REV1

# The board has no ChibiOS/QMK serial bootloader; it is flashed over the
# vendor "DISCOVERY IAP" HID bootloader using tools/hexcore_iap.py.
BOOTLOADER = custom
