#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Module for FTDI devices in MPSSE mode

FT232H:  Port A has 1 kB RX FIFO buffer and 1 kB TX FIFO buffer
FT2232H: Ports A and B have 4 kB RX FIFO buffer and 4 kB TX FIFO buffer each
FT4232H: Ports A and B have 2 kB RX FIFO buffer and 2 kB TX FIFO buffer each

USB control transfers are used for configuration and status
USB bulk transfers (512 bytes packets in High Speed mode) are used for actual data exchange
On USB bulk reads two modem status bytes are always returned in the beginning of each 512 bytes packet
MPSSE COMMANDS will not be accepted if RX buffer it full (with RESPONSES from previous COMMANDS)
For JTAG and SPI interfaces both bit and byte shift MPSSE COMMANDS may be used
For I2C interface only bit shift MPSSE COMMANDS may be used as every byte on I2C bus needs to be acknowledged
Only SPI mode 0 (CPOL = 0, CPHA = 0) is implemented
Only one SPI SS# is implemented

Ports

Port A (Interface 0, endpoint OUT: 0x02, endpoint IN: 0x81)
Port B (Interface 1, endpoint OUT: 0x04, endpoint IN: 0x83)

Pinouts

Pin        JTAG SPI  I2C
D0, output TCK  SCK  SCL
D1, output TDI  MOSI SDAO
D2, input  TDO  MISO SDAI
D3, output TMS  SS#  no connection

D[7:4], GPIOL[3:0], no connection
C[7:0], GPIOH[7:0], no connection

'''


# Standard modules
import ctypes
import logging

# Third-party modules
import bitstring
import usb.backend.libusb1
import usb.core
import usb.util

# Custom modules
import general.logging
import hwio.register
import hwio.i2c # Used for raising I2CError. TODO: Implement the same for JTAG, SPI, AXI


#===============================================================================
# variables
#===============================================================================
VENDOR_ID = 0x0403 # FTDI

PRODUCT_IDS = {0x6014 : 'FT232H',
               0x6010 : 'FT2232H',
               0x6011 : 'FT4232H'}

USB_PACKET_SIZE = 512

# FTDI device endpoints
ENDPOINTS_OUT = {'A' : 0x02,
                 'B' : 0x04}

ENDPOINTS_IN  = {'A' : 0x81,
                 'B' : 0x83}

# Vendor-specific USB control requests
CONTROL_REQUESTS = {'reset_buffer'      : 0x00, # Reset UART BUFFERS
                    'set_modem_control' : 0x01, # Set modem control
                    'set_flow_control'  : 0x02, # Set flow control
                    'set_baud_rate'     : 0x03, # Set baud rate
                    'set_data_format'   : 0x04, # Set data format
                    'get_modem_status'  : 0x05, # Get modem status
                    'set_event_char'    : 0x06, # Set event character
                    'set_error_char'    : 0x07, # Set error character
                    'set_latency_timer' : 0x09, # Set receive buffer latency timer
                    'get_latency_timer' : 0x0A, # Get receive buffer latency timer
                    'set_bit_mode'      : 0x0B, # Set bit mode
                    'get_pin_values'    : 0x0C, # Get pin values
                    'eeprom_read'       : 0x90, # Read 16-bit word from EEPROM
                    'eeprom_write'      : 0x91, # Write 16-bit word to EEPROM
                    'eeprom_erase'      : 0x92} # Erase whole EEPROM

# Vendor-specific USB control request values
BUFFERS = {'rx_tx' : 0x0000, # Reset UART RX and TX BUFFERS
           'rx'    : 0x0001, # Reset UART RX buffer
           'tx'    : 0x0002} # Reset UART TX buffer

BIT_MODES = {'disable'       : 0x0000, # Disable bit mode (i.e. enable UART mode)
             'async_bitbang' : 0x0100, # Asynchronous bitbang
             'mpsse'         : 0x0200, # Multi-Protocol Synchronous Serial Engine (MPSSE)
             'sync_bitbang'  : 0x0400, # Synchronous bitbang
             'cpu'           : 0x0800, # CPU bus emulation
             'fast_serial'   : 0x1000, # Fast serial
             'cbus_bitbang'  : 0x2000, # CBUS bitbang
             'sync_fifo'     : 0x4000} # Synchronous FIFO

MODEM_STATUS_LENGTH = 2

# MPSSE
COMMANDS = {'lsb_tdi_out_f_byte'          : 0x19, # 8b<length[7:0]>, 8b<length[15:8]>, 8b<byte 0>, ... 8b<byte 65535>
                                                  # Shift bytes out to TDI pin on clock falling edge, LSb first
                                                  # 16b<length>: 0x0000 - shift 1 byte, ..., 0xFFFF - shift 65536 bytes

            'lsb_tdo_in_r_byte'           : 0x28, # 8b<length[7:0]>, 8b<length[15:8]>
                                                  # Shift bytes in from TDO pin on clock rising edge, LSb first
                                                  # 16b<length>: 0x0000 - shift 1 byte, ..., 0xFFFF - shift 65536 bytes
                                                  # return: 8b<byte 0>, ... 8b<byte 65535>: bytes shifted in from TDO pin

            'lsb_tdi_out_f_tdo_in_r_byte' : 0x39, # 8b<length[7:0]>, 8b<length[15:8]>, 8b<byte 0>, ... 8b<byte 65535>
                                                  # Shift bytes out to TDI pin on clock falling edge and shift bytes in from TDO pin on clock rising edge, LSb first
                                                  # 16b<length>: 0x0000 - shift 1 byte, ..., 0xFFFF - shift 65536 bytes
                                                  # return: 8b<byte 0>, ... 8b<byte 65535>: bytes shifted in from TDO pin

            'msb_tdi_out_f_byte'          : 0x11, # 8b<length[7:0]>, 8b<length[15:8]>, 8b<byte 0>, ... 8b<byte 65535>
                                                  # Shift bytes out to TDI pin on clock falling edge, MSb first
                                                  # 16b<length>: 0x0000 - shift 1 byte, ..., 0xFFFF - shift 65536 bytes

            'msb_tdo_in_r_byte'           : 0x20, # 8b<length[7:0]>, 8b<length[15:8]>
                                                  # Shift bytes in from TDO pin on clock rising edge, MSb first
                                                  # 16b<length>: 0x0000 - shift 1 byte, ..., 0xFFFF - shift 65536 bytes
                                                  # return: 8b<byte 0>, ... 8b<byte 65535>: bytes shifted in from TDO pin

            'msb_tdi_out_f_tdo_in_r_byte' : 0x31, # 8b<length[7:0]>, 8b<length[15:8]>, 8b<byte 0>, ... 8b<byte 65535>
                                                  # Shift bytes out to TDI pin on clock falling edge and shift bytes in from TDO pin on clock rising edge, MSb first
                                                  # 16b<length>: 0x0000 - shift 1 byte, ..., 0xFFFF - shift 65536 bytes
                                                  # return: 8b<byte 0>, ... 8b<byte 65535>: bytes shifted in from TDO pin

            #--------------------------------------------------

            'lsb_tdi_out_f_bit'           : 0x1B, # 8b<length>, 8b<value>
                                                  # Shift bits out to TDI pin on clock falling edge, LSb first
                                                  # 8b<length>: 0 - shift 1 bit, ..., 7 - shift 8 bits

            'lsb_tdo_in_r_bit'            : 0x2A, # 8b<length>
                                                  # Shift bits in from TDO pin on clock rising edge, LSb first
                                                  # 8b<length>: 0 - shift 1 bit, ..., 7 - shift 8 bits
                                                  # return: 8b<value>: bits shifted in from TDO pin
                                                  # Bits from previous shift COMMANDS are preserved and returned so if less than 8 bits are shifted in old bits shall be masked

            'lsb_tdi_out_f_tdo_in_r_bit'  : 0x3B, # 8b<length>, 8b<value>
                                                  # Shift bits out to TDI pin on clock falling edge and shift bits in from TDO pin on clock rising edge, LSb first
                                                  # 8b<length>: 0 - shift 1 bit, ..., 7 - shift 8 bits
                                                  # 8b<value>: value to be shifted
                                                  # return: 8b<value>: bits shifted in from TDO pin
                                                  # Bits from previous shift COMMANDS are preserved and returned so if less than 8 bits are shifted in old bits shall be masked

            #--------------------------------------------------

            'msb_tdi_out_f_bit'           : 0x13, # 8b<length>, 8b<value>
                                                  # Shift bits out to TDI pin on clock falling edge, MSb first
                                                  # 8b<length>: 0 - shift 1 bit, ..., 7 - shift 8 bits

            'msb_tdo_in_r_bit'            : 0x22, # 8b<length>
                                                  # Shift bits in from TDO pin on clock rising edge, MSb first
                                                  # 8b<length>: 0 - shift 1 bit, ..., 7 - shift 8 bits
                                                  # return: 8b<value>: bits shifted in from TDO pin
                                                  # Bits from previous shift COMMANDS are preserved and returned so if less than 8 bits are shifted in old bits shall be masked

            #--------------------------------------------------

            'lsb_tms_out_f'               : 0x4B, # 8b<length>, 8b<value>
                                                  # Shift bits out to TMS pin on clock falling edge, LSb first
                                                  # 8b<length>: 0 - shift 1 bit, ..., 6 - shift 7 bits
                                                  # 8b<value>: bits [6:0] - bits to be shifted out to TMS pin, bit [7] - bit to be put on TDI pin during transaction
                                                  # Actually all 8 bits (bits [7:0]) may be shifted out to TMS pin (i.e. length = 7) but highest TMS bit (bit[7]) will define TDI pin state during transaction

            'lsb_tms_out_f_tdo_in_r'      : 0x6B, # 8b<length>, 8b<value>
                                                  # Shift bits out to TMS pin on clock falling edge and shift bits in from TDO pin on clock rising edge, LSb first
                                                  # 8b<length>: 0 - shift 1 bit, ..., 6 - shift 7 bits
                                                  # 8b<value>: bits [6:0] - bits to be shifted out to TMS pin, bit [7] - bit to be put on TDI pin during transaction
                                                  # return: 8b<value>: value shifted in from TDO pin
                                                  # Bits from previous shift COMMANDS are preserved and returned so if less than 8 bits are shifted in old bits shall be masked
                                                  # Actually all 8 bits (bits [7:0]) may be shifted out to TMS pin and shifted in from TDO pin (i.e. length = 7) but highest TMS bit (bit[7]) will define TDI pin state during transaction

            #--------------------------------------------------

            'set_pins_d'                  : 0x80, # 8b<value>, 8b<direction>
                                                  # Set direction and value of D[7:0] pins
                                                  # 8b<value>: 0 - low level, 1 - high level
                                                  # 8b<direction>: 0 - input, 1 - output
                                                  # Selected direction stays until explicitly changed
                                                  # It seems that the value gets written to the pin first and only then it's direction gets written
                                                  # Therefore attention needs to be paid when changing both port value from 1 to 0 and it's direction from output to input as it might produce a narrow runt pulse as there are 75 kOhm internal pull-up on every I/O pin

            'get_pins_d'                  : 0x81, # Get value of D[7:0] pins

            'set_pins_c'                  : 0x82, # Set direction and value of C[7:0] pins

            'get_pins_c'                  : 0x83, # Get value of C[7:0] pins

            #--------------------------------------------------

            'enable_loopback'             : 0x84, # Enable internal TDI->TDO loopback

            'disable_loopback'            : 0x85, # Disable internal TDI->TDO loopback

            'set_clock_divider'           : 0x86, # Set master clock divider to obtain required TCK/SCK/SCL frequency

            'send_immediate'              : 0x87, # Send RESPONSES back to host immediately not waiting for the read latency timer

            'wait_pin_high'               : 0x88, # Wait until GPIOL1 is high. Following MPSSE instructions are kept in TX buffer and not processed during this wait

            'wait_pin_low'                : 0x89, # Wait until GPIOL1 is low. Following MPSSE instructions are kept in TX buffer and not processed during this wait

            'disable_x5_clock_divider'    : 0x8A, # Disable master clock x5 divider

            'enable_3_phase_clocking'     : 0x8C, # Enable 3-phase clocking (required for I2C): data setup for 1/2 clock period -> pulse clock for 1/2 clock period -> data hold for 1/2 clock period

            'disable_3_phase_clocking'    : 0x8D, # Disable 3-phase clocking: data setup for 1/2 clock period -> pulse clock for 1/2 clock period

            'clock_pulse_bit'             : 0x8E, # 8b<length>
                                                  # Pulse clock with no data transfer
                                                  # 8b<length>: 0 - generate 1 pulse, ..., 7 - generate 8 pulses

            'clock_pulse_byte'            : 0x8F, # 8b<length[7:0]>, 8b<length[15:8]>
                                                  # Pulse clock with no data transfer
                                                  # 16b<length>: 0x0000 - generate 8 pulses, ..., 0xFFFF - generate 524288 pulses

            'invalid_command_0'           : 0xAA, # First invalid command for checking if MPSSE is operational

            'invalid_command_1'           : 0xAB} # Second invalid command for checking if MPSSE is operational

RESPONSES = {'invalid_command' : 0xFA} # Response to invalid command which is followed by echoing the invalid command

# Master clock is 60 MHz after /5 clock divider is disabled
# required_clock = master_clock / ((1 + divider) * 2)
# divider = master_clock / required_clock / 2 - 1
FREQUENCIES = {'1 kHz'     : 29999,
               '10 kHz'    : 2999,
               '100 kHz'   : 299,   # I2C Standard-mode
               '400 kHz'   : 74,    # I2C Fast-mode
               '1 MHz'     : 29,    # I2C Fast-mode Plus
               '1.11 MHz'  : 26,
               '1.2 MHz'   : 24,
               '1.25 MHz'  : 23,
               '1.5 MHz'   : 19,
               '1.67 MHz'  : 17,
               '1.875 MHz' : 15,
               '2 MHz'     : 14,
               '2.5 MHz'   : 11,
               '3 MHz'     : 9,
               '3.33 MHz'  : 8,
               '3.75 MHz'  : 7,
               '5 MHz'     : 5,
               '6 MHz'     : 4,
               '7.5 MHz'   : 3,
               '10 MHz'    : 2,
               '15 MHz'    : 1,
               '30 MHz'    : 0}

# These delays are created using high-speed USB microframe time (125 us) and are equal to half of the selected clock period
# Minimum achievable delay is 250 us (based on actual measurements)
DELAYS = {'1 kHz'   : 2000, # 2000 * 250 ns = 500 us
          '10 kHz'  : 200,  #  200 * 250 ns = 50 us
          '100 kHz' : 20,   #   20 * 250 ns = 5 us
          '400 kHz' : 5,    #    5 * 250 ns = 1.25 us
          '1 MHz'   : 2,    #    2 * 250 ns = 0.5 us
          '2 MHz'   : 1,    #    1 * 250 ns = 0.25 us
          '3 MHz'   : 1,    #    1 * 250 ns = 0.25 us, minimum achievable delay
          '5 MHz'   : 1,    #    1 * 250 ns = 0.25 us, minimum achievable delay
          '6 MHz'   : 1,    #    1 * 250 ns = 0.25 us, minimum achievable delay
          '7.5 MHz' : 1,    #    1 * 250 ns = 0.25 us, minimum achievable delay
          '10 MHz'  : 1,    #    1 * 250 ns = 0.25 us, minimum achievable delay
          '15 MHz'  : 1,    #    1 * 250 ns = 0.25 us, minimum achievable delay
          '30 MHz'  : 1}    #    1 * 250 ns = 0.25 us, minimum achievable delay


#===============================================================================
# exceptions
#===============================================================================
class FTDIError(Exception):
    '''Custom class for recoverable error handling'''
    pass

class FTDICritical(Exception):
    '''Custom class for unrecoverable error handling'''
    pass


#===============================================================================
# classes
#===============================================================================
class FTDI:
    def __init__(self, device):

        self.device = device

        self.port_jtag = None
        self.port_spi  = None
        self.port_i2c  = None

        if PRODUCT_IDS[self.device.idProduct] == 'FT232H':
            self.ports = {'A' : 0x0001}

            self.jtag_buffer_size = 1000
            self.spi_buffer_size  = 1000
            self.i2c_buffer_size  = 1000

        elif PRODUCT_IDS[self.device.idProduct] == 'FT2232H':
            # FTDI device port indexes
            self.ports = {'A' : 0x0001,
                          'B' : 0x0002}

            # FTDI device uses FIFO for data transfer so there is no fixed-size buffer per se
            self.jtag_buffer_size = 8000 # This value was determined experimentally by shifting 65465 bits through TDI->TDO when in internal loopback mode at TCK = 100 kHz, 1 MHz, 10 MHz, 30 MHz
            self.spi_buffer_size  = 8000 # This value was determined experimentally by shifting 65465 bits through MOSI->MISO when in internal loopback mode at SCK = 100 kHz, 1 MHz, 10 MHz, 30 MHz
            self.i2c_buffer_size  = 4000 # This value was determined experimentally by writing and reading full array of the Microchip 24LC512 EEPROM (64 kbyte) at SCL = 100 kHz, 400 kHz, 1 MHz

        elif PRODUCT_IDS[self.device.idProduct] == 'FT4232H':
            self.ports = {'A' : 0x0001,
                          'B' : 0x0002}

            self.jtag_buffer_size = 4000
            self.spi_buffer_size  = 4000
            self.i2c_buffer_size  = 2000

        else:
            logger.critical(f'FAIL: Wrong USB idProduct: 0x{self.device.idProduct:04X}')
            raise FTDICritical


    def __enter__(self):
        logger.debug('Initialize FTDI device')

        # Set default timeout (ms)
        self.device.default_timeout = 1000 # 1 s timeout

        # logger.debug(f'| FTDI device found on bus {self.device.bus:03d}, address {self.device.address:03d}\n{self.device}')

        # Detach from kernel driver
        for configuration in self.device: # Iterate over device configurations
            for interface in configuration: # Iterate over configuration interfaces
                if self.device.is_kernel_driver_active(interface = interface.bInterfaceNumber) is True:
                    logger.debug(f'| OS: Detach kernel driver from configuration {configuration.bConfigurationValue}, interface {interface.bInterfaceNumber}')
                    self.device.detach_kernel_driver(interface = interface.bInterfaceNumber)

        # Set configuration
        configuration = self.device.get_active_configuration()
        logger.debug(f'| USB: Active configuration: {"none" if configuration is None else configuration.bConfigurationValue}')

        if configuration is None or configuration.bConfigurationValue != 1:
            logger.debug('| USB: Set active configuration: 1')
            self.device.set_configuration(configuration = 1)

        # Claim interfaces
        for configuration in self.device: # Iterate over device configurations
            for interface in configuration: # Iterate over configuration interfaces
                logger.debug(f'| USB: Claim configuration {configuration.bConfigurationValue}, interface {interface.bInterfaceNumber}')
                usb.util.claim_interface(device = self.device, interface = interface.bInterfaceNumber)

        # Check if active configuration is still the same as other software might have activated another one
        configuration = self.device.get_active_configuration()
        if configuration is None or configuration.bConfigurationValue != 1:
            logger.error(f'FAIL: Wrong current active configuration: {"none" if configuration is None else configuration.bConfigurationValue}')
            raise FTDIError

        # Reset the USB port device is connected to (generic USB command)
        logger.debug('| USB: Reset port device is connected to')
        self.device.reset()

        for port in self.ports.keys():
            # Reset UART BUFFERS (vendor-specific command)
            logger.debug(f'| FTDI device, port {port}: Reset UART BUFFERS')
            self.device.ctrl_transfer(bmRequestType = usb.util.build_request_type(direction = usb.util.CTRL_OUT, type = usb.util.CTRL_TYPE_VENDOR, recipient = usb.util.CTRL_RECIPIENT_DEVICE),
                                      bRequest = CONTROL_REQUESTS['reset_buffer'],
                                      wValue = BUFFERS['rx_tx'],
                                      wIndex = self.ports[port])

            # Set receive buffer latency timer (vendor-specific command)
            # Latency Timer is used as a timeout to flush short packets of data back to the host
            # The default is 16 ms, but it can be altered between 0 ms and 255 ms
            # At 0 ms latency packet transfer is done on every high speed microframe (every 125 us)
            # For MPSSE it's recommended to set it to the default 16 ms and use "send_immediate" command to send bytes back to host when required
            # This approach seems to be working fine for FT2232H but with FT232H there seems to be a latency delay present on the first small packet transfer therefore latency is set to 1
            # This was observed while programming SPI flash and checking its status register value
            logger.debug(f'| FTDI device, port {port}: Set read latency timer')
            self.device.ctrl_transfer(bmRequestType = usb.util.build_request_type(direction = usb.util.CTRL_OUT, type = usb.util.CTRL_TYPE_VENDOR, recipient = usb.util.CTRL_RECIPIENT_DEVICE),
                                      bRequest = CONTROL_REQUESTS['set_latency_timer'],
                                      wValue = 1,
                                      wIndex = self.ports[port])

            # TODO(?): To ensure that the device driver will not issue IN requests if the buffer is unable to accept data, add a call to FT_SetFlowControl prior to entering MPSSE mode

            # Set MPSSE bit mode (vendor-specific command)
            logger.debug(f'| FTDI device, port {port}: Set MPSSE bit mode')
            self.device.ctrl_transfer(bmRequestType = usb.util.build_request_type(direction = usb.util.CTRL_OUT, type = usb.util.CTRL_TYPE_VENDOR, recipient = usb.util.CTRL_RECIPIENT_DEVICE),
                                      bRequest = CONTROL_REQUESTS['set_bit_mode'],
                                      wValue = BIT_MODES['mpsse'],
                                      wIndex = self.ports[port])

            # Check MPSSE synchronization
            # Send invalid COMMANDS 0xAA and 0xAB to the MPSSE to check if it responds correctly
            logger.debug(f'| FTDI device, port {port}: Check MPSSE synchronization')
            for command in [COMMANDS['invalid_command_0'], COMMANDS['invalid_command_1']]:
                self.write(port = port, data = [command])
                data_r = self.read(port = port, length = 2)

                if data_r != [RESPONSES['invalid_command'], command]:
                    logger.error(f'FAIL: Wrong response to an invalid command 0x{command:02X} from FTDI device, port {port}: [{", ".join([f"0x{item:02X}" for item in data_r])}]')
                    raise FTDIError

            # Disable master clock x5 divider
            logger.debug(f'| FTDI device, port {port}: Disable master clock x5 divider')
            self.write(port = port, data = [COMMANDS['disable_x5_clock_divider']])
            # self.read(port = port, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

            # Configure pins as inputs
            # Every I/O pin (AD[7:0], AC[7:0], BD[7:0], BC[7:0]) has an internal 75 kOhm pull-up to VCCIO
            # Just in case, wright 1 to all I/O pins output latches to match the default pin state when it's configured as input (pulled-up internally to VCCIO)
            # Configure all I/O pins as inputs
            logger.debug(f'| FTDI device, port {port}: Configure I/O pins as inputs')
            self.write(port = port, data = [COMMANDS['set_pins_d'], 0b11111111, 0b00000000, COMMANDS['set_pins_c'], 0b11111111, 0b00000000])
            # self.read(port = port, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

            # TEST: Read pins
            # logger.debug(f'| FTDI device, port {port}: Read pins')
            # value = self.write(port = port, data = [COMMANDS['get_pins_d'], COMMANDS['get_pins_c'], COMMANDS['send_immediate']])
            # self.read(port = port, length = 2)

        logger.debug('OK')

        return self


    def __exit__(self, exc_type, exc_value, traceback):
        logger.debug('Finalize FTDI device')

        # If some strings (e.g. iManufacturer, iProduct) in FTDI configuration EEPROM have changed it invalidates the USB device descriptor (self.device) as it essentially disconnects the USB device
        # OS shall free the device resources (including claiming) when this happens
        # This might be fixed in future PyUSB release (github.com/pyusb/pyusb/issues/64) but for now the usb.core.USBError exception shall be caught here
        try:
            # Reset the USB port device is connected to (generic USB command)
            logger.debug('| USB: Reset port device is connected to')
            self.device.reset()

        except usb.core.USBError as exception:
            if exception.args == (2, 'Entity not found'):
                pass
            else:
                raise

        else:
            # Release interfaces
            for configuration in self.device: # Iterate over device configurations
                for interface in configuration: # Iterate over configuration interfaces
                    logger.debug(f'| USB: Release configuration {configuration.bConfigurationValue}, interface {interface.bInterfaceNumber}')
                    usb.util.release_interface(device = self.device, interface = interface.bInterfaceNumber)

            # Reattach kernel driver
            for configuration in self.device: # iterate over device configurations
                for interface in configuration: # iterate over configuration interfaces
                    logger.debug(f'| OS: Attach kernel driver to configuration {configuration.bConfigurationValue}, interface {interface.bInterfaceNumber}')
                    self.device.attach_kernel_driver(interface = interface.bInterfaceNumber)

        finally:
            # Free all resources allocated by the device object
            logger.debug('| Dispose resources')
            usb.util.dispose_resources(device = self.device)

        logger.debug('OK')

        return False

    #---------------------------------------------------------------------------
    # EEPROM
    def eeprom_write(self, address, data):
        '''Write external uWire configuration EEPROM

        Parameter:
        'address' : (int)  Start word address
        'data'    : (list) Words to write

        Return:
        None

        '''

        logger.debug(f'FTDI device, EEPROM, write, address: 0x{address:02X}, length: {len(data):d} words')
        logger.debug(f'[{", ".join([f"0x{item:04X}" for item in data])}]')

        if data == []:
            logger.critical(f'FAIL: zero words were requested to be written to EEPROM')
            raise FTDICritical

        for current_address in range(address, len(data)):
            # This command writes a 16-bit word at a time
            self.device.ctrl_transfer(bmRequestType = usb.util.build_request_type(direction = usb.util.CTRL_OUT, type = usb.util.CTRL_TYPE_VENDOR, recipient = usb.util.CTRL_RECIPIENT_DEVICE),
                                      bRequest = CONTROL_REQUESTS['eeprom_write'],
                                      wValue = data[current_address],
                                      wIndex = current_address)

        logger.debug('OK')

        return None


    def eeprom_read(self, address, length):
        '''Read external uWire configuration EEPROM

        Parameter:
        'address' : (int) Start word address
        'length'  : (int) Number of words to read

        Return:
        (list) Read words

        '''

        logger.debug(f'FTDI device, EEPROM, read, address: 0x{address:02X}, length: {length:d} words')

        data = []

        for current_address in range(address, length):
            # This command reads a 16-bit word at a time
            data_r = self.device.ctrl_transfer(bmRequestType = usb.util.build_request_type(direction = usb.util.CTRL_IN, type = usb.util.CTRL_TYPE_VENDOR, recipient = usb.util.CTRL_RECIPIENT_DEVICE),
                                               bRequest = CONTROL_REQUESTS['eeprom_read'],
                                               wValue = 0,
                                               wIndex = current_address,
                                               data_or_wLength = 2)
            data += [data_r[1] * 256 + data_r[0]]

        logger.debug('OK')
        logger.debug(f'[{", ".join([f"0x{item:04X}" for item in data])}]')

        return data


    def eeprom_erase(self):
        '''Erase external uWire configuration EEPROM

        Parameter:
        None

        Return:
        None

        '''

        logger.debug('FTDI device, EEPROM, erase')

        self.device.ctrl_transfer(bmRequestType = usb.util.build_request_type(direction = usb.util.CTRL_OUT, type = usb.util.CTRL_TYPE_VENDOR, recipient = usb.util.CTRL_RECIPIENT_DEVICE),
                                  bRequest = CONTROL_REQUESTS['eeprom_erase'],
                                  wValue = 0,
                                  wIndex = 0)

        logger.debug('OK')

        return None


    def eeprom_program(self, address, data):
        '''Program external uWire configuration EEPROM

        Parameter:
        'address' : (int)  Start word address
        'data'    : (list) Words to write

        Return:
        None

        '''

        logger.debug('FTDI device, EEPROM, program')

        self.eeprom_write(address = address, data = data)

        data_r = self.eeprom_read(address = address, length = len(data))

        if data != data_r:
            logger.error('FAIL: write and read data are different')
            raise FTDIError

        logger.debug('OK')

        return None


    #---------------------------------------------------------------------------
    # USB
    def write(self, port, data):
        '''Write to FTDI device over USB

        Parameter:
        'port' : (str) Port name ('A', 'B')
        'data' : (list) list of bytes to write

        Return:
        None

        '''

        # Any amount of data may be sent to OUT endpoint as USB subsystem handles this automatically: device sends NAK on the OUT endpoint when its buffer gets full and the host computer reschedules the data delivery
        # Therefore there is no need to split write data in chunks here

        # logger.debug(f'Write {len(data)} byte(s) to FTDI device, port {port}: [{", ".join([f"0x{item:02X}" for item in data])}]')

        if data == []:
            logger.critical(f'FAIL: zero bytes were requested to be written')
            raise FTDICritical

        length = self.device.write(endpoint = ENDPOINTS_OUT[port], data = data)

        if length != len(data):
            logger.error(f'FAIL: {len(data)} bytes were requested to be written, {length} bytes were actually written')
            raise FTDIError

        # length = 0

        # for attempt in range(10):
        #     length += self.device.write(endpoint = ENDPOINTS_OUT[port], data = data[length:])

        #     logger.debug(f| 'Attempt {attempt}: {length} out of {len(data)} bytes(s)')

        #     if length == len(data):
        #         break
        # else:
        #     logger.error(f'FAIL: {len(data)} bytes were requested to be written, {length} bytes were actually written')
        #     raise FTDIError

        # logger.debug(f| 'Write {len(data)} byte(s) in chunks to FTDI device, port {port}')
        # Split long data list into chunks of maximum TX buffer
        # for offset in range(0, len(data), self.tx_buffer_size):
        #     chunk = data[offset : offset + min(self.tx_buffer_size, len(data) - offset)]

        #     logger.debug(f'| Write {len(chunk)} byte(s) to FTDI device, port {port}: [{", ".join([f"0x{item:02X}" for item in chunk])}]')

        #     length = self.device.write(endpoint = ENDPOINTS_OUT[port], data = chunk)

        #     if length != len(chunk):
        #         logger.error(f'FAIL: {len(chunk)} bytes were requested to be written, {length} bytes were actually written')
        #         raise FTDIError

        # logger.debug('OK')

        return None


    def read(self, port, length):
        '''Read from FTDI device over USB

        Parameter:
        'port'   : (str) Port name ('A', 'B')
        'length' : (int) number of bytes to read

        Return:
        (list) list of read bytes

        '''

        # Host computer BUFFERS data from the IN endpoint until either its size reaches the requested limit or a timeout occurs

        # logger.debug(f'Read {length} byte(s) from FTDI device, port {port}')

        data = []

        # Read out data with timeout
        for attempt in range(100):
            length_r = length - len(data)
            length_r += MODEM_STATUS_LENGTH * (length_r // (USB_PACKET_SIZE - MODEM_STATUS_LENGTH) + 1) # Reserve space for modem status bytes in each USB packet
            data_r = list(self.device.read(endpoint = ENDPOINTS_IN[port], size_or_buffer = length_r))

            for packet, offset in enumerate(range(0, len(data_r), USB_PACKET_SIZE)):
                chunk = data_r[offset : offset + min(USB_PACKET_SIZE, len(data_r) - offset)]

                modem_status = chunk[0:2]

                data += chunk[2:] # Skip modem status bytes that FTDI device returns on each USB read

                # logger.debug(f'| Attempt {attempt}, packet {packet}: modem status [{", ".join([f"0x{item:02X}" for item in modem_status])}], {len(data)} out of {length} bytes(s)\n| [{", ".join([f"0x{item:02X}" for item in chunk[2:]])}]')

            if len(data) == length:
                break
        else:
            logger.error(f'FAIL: {length} bytes were requested to be read, {len(data)} byte(s) were actually read: [{", ".join([f"0x{item:02X}" for item in data])}]')
            raise FTDIError

        # logger.debug(f'OK, {len(data)} byte(s): [{", ".join([f"0x{item:02X}" for item in data])}]')

        return data


    #---------------------------------------------------------------------------
    # MPSSE
    def mpsse_test_buffer(self, port, length):
        '''Test FTDI device BUFFERS

        Parameter:
        'port'   : (str) Port name ('A', 'B')
        'length' : (int) Number of invalid COMMANDS to send

        Return:
        None

        '''

        logger.debug('Test FTDI device TX buffer')

        data_w = []
        # data_w += [COMMANDS['wait_pin_low']] # As GPIOL1 pin is not connected externally and has an internal pull-up MPSSE engine will stuck at this command indefinitely and will not process any further COMMANDS
        # data_w += [COMMANDS['disable_loopback']]*4095 # Fill TX buffer up to 4096 bytes (full buffer). USB write will pass
        # data_w += [COMMANDS['disable_loopback']]*4096 # Fill TX buffer up to 4097 bytes (one byte too many). USB write will fail. This proves TX buffer size is 4096 bytes

        # data_w += [COMMANDS['disable_loopback']]*1000000 # Transfer a lot of COMMANDS that don't return any data

        # First 2048 invalid command bytes from TX buffer will be processed and 4096 invalid command response bytes will be put into RX buffer
        # That would allow for another 2048 bytes to be put in TX buffer so the maximum TX size is 6144 bytes
        data_w += [COMMANDS['invalid_command_0']] * length

        self.write(port = port, data = data_w)

        data_r = self.read(port = port, length = len(data_w) * MODEM_STATUS_LENGTH) # Invalid command response is 2 bytes each

        if data_r != [RESPONSES['invalid_command'], COMMANDS['invalid_command_0']] * len(data_w):
            logger.error('FAIL: returned bytes are different than expected')
            raise FTDIError

        logger.debug('OK')

        return None


    def mpsse_loopback(self, port, state):
        '''Control FTDI device internal loopback

        Parameter:
        'port'  : (str) Port name ('A', 'B')
        'state' : (str) TDI->TDO internal loopback state ('off', 'on')

        Return:
        None

        '''

        logger.debug(f'Control FTDI device TDI->TDO internal loopback: {state}')

        if state == 'off':
            data_w = [COMMANDS['disable_loopback']]
        elif state == 'on':
            data_w = [COMMANDS['enable_loopback']]
        else:
            logger.critical(f'Wrong state: {state}')
            raise FTDICritical

        self.write(port = port, data = data_w)

        logger.debug('OK')

        return None


    #---------------------------------------------------------------------------
    # JTAG
    def jtag_initialize(self, port, frequency):
        '''Initialize JTAG interface

        Parameter:
        'port'      : (str) Port name ('A', 'B')
        'frequency' : (str) JTAG TCK frequency from FREQUENCIES dictionary

        Return:
        None

        '''

        logger.debug('Initialize JTAG')

        self.port_jtag = port

        # Set master clock divider
        logger.debug(f'| FTDI device, port {self.port_jtag}: Set master clock divider for \'{frequency}\' frequency')
        if frequency not in FREQUENCIES.keys():
            logger.critical(f'Wrong TCK frequency: \'{frequency}\'')
            raise FTDICritical

        data_w = [COMMANDS['set_clock_divider'], FREQUENCIES[frequency] & 0xFF, (FREQUENCIES[frequency] >> 8) & 0xFF]
        self.write(port = self.port_jtag, data = data_w)

        self.jtag_frequency = frequency

        # Set idle states for I/O pins
        # JTAG signals have external pull-ups. Other I/O pins don't matter as they are not connected
        logger.debug(f'| FTDI device, port {self.port_jtag}: Configure I/O pins idle states')
        data_w = [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.jtag_frequency] # TMS = H, TDO = Z, TDI = H, TCK = L
        self.write(port = self.port_jtag, data = data_w)

        logger.debug('OK')

        return None


    def jtag_finalize(self):
        '''Perform clean-up actions on JTAG interface

        Parameter:
        None

        Return:
        None

        '''

        logger.debug('Finalize JTAG')

        data_w = []

        data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.jtag_frequency] # TMS = H, TDO = Z, TDI = H, TCK = L
        data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00001011] * DELAYS[self.jtag_frequency] # TMS = H, TDO = Z, TDI = H, TCK = H
        data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00000000] * DELAYS[self.jtag_frequency] # TMS = Z, TDO = Z, TDI = Z, TCK = Z

        self.write(port = self.port_jtag, data = data_w)

        logger.debug('OK')

        return None


    def jtag_set_frequency(self, frequency):
        '''Set TCK frequency

        Parameter:
        'frequency' : (str) JTAG TCK frequency from FREQUENCIES dictionary

        Return:
        None

        '''

        logger.debug('Set TCK frequency')

        # Set master clock divider
        logger.debug(f'| FTDI device, port {self.port_jtag}: Set master clock divider for \'{frequency}\' frequency')
        if frequency not in FREQUENCIES.keys():
            logger.critical(f'Wrong TCK frequency: \'{frequency}\'')
            raise FTDICritical

        data_w = [COMMANDS['set_clock_divider'], FREQUENCIES[frequency] & 0xFF, (FREQUENCIES[frequency] >> 8) & 0xFF]
        self.write(port = self.port_jtag, data = data_w)

        self.jtag_frequency = frequency

        logger.debug('OK')

        return None


    def jtag_pulse(self, pulses):
        '''Generate pulses on TCK

        This might be required by some FPGAs in order to start up after having been configured over JTAG

        Parameter:
        'pulses' : (int) Number of pulses (1..8)

        Return:
        None

        '''

        logger.debug('Pulse TCK')

        data_w = []
        data_w += [COMMANDS['clock_pulse_bit'], pulses - 1] # Generate clock pulses, no data transfer

        self.write(port = self.port_jtag, data = data_w)

        logger.debug('OK')

        return None


    def jtag_advance(self, tms):
        '''Advance JTAG TAP state machine

        Parameter:
        tms : (bitstring) Sequence of TMS states, '0' or '1', LSb first

        Return:
        None

        '''

        logger.debug(f'Advance JTAG TAP state machine, TMS: 0b{tms.bin}')

        data_w = []

        for pos in range(tms.length, 0, -8): # FTDI device can shift 8 bits max
            value = tms[max(pos - 8, 0):pos]
            data_w += [COMMANDS['lsb_tms_out_f'], value.length - 1, value.uint]

        self.write(port = self.port_jtag, data = data_w)

        logger.debug('OK')

        return None


    def jtag_shift(self, data, length, tms):
        '''Shift data through JTAG register

        Parameter:
        data   : (bitstring) Bits to shift out, LSb first, may be None if no data needs to be shifted out
        length : (int)       Number of bits to shift in, may be None if no data needs to be shifted in
        tms    : (bitstring) TMS state on the last shifted bit, 0b0 or 0b1. This define whether TAP stays in Shift-IR/Shift-DR state or advances to Exit-IR/Exit-DR state

        Return:
        (bitstring) Read bits or None

        '''

        if tms.length != 1:
            logger.critical('TMS vector is longer than 1 bit')
            raise FTDICritical

        if data is not None and length is not None:
            logger.debug(f'Shift {data.length} bits out to TDI and {length} bits in from TDO: 0b{data.bin}')

            if data.length != length:
                logger.critical('TDI and TDO lengths are different')
                raise FTDICritical

            bits = [] # List of meaningful bits for each read byte
            data_w = []

            # Split bitstring into 8-bit vectors starting from the end of the bitstring as bits shall be shifted out LSb first
            byte_length, bit_length = divmod(data[1:].length, 8)

            # Use byte shifts for all bytes except the last one
            # TODO: Replace this with a loop to take care of byte length > 65536
            if byte_length != 0: # This will be true if data is longer than 9 bits
                length_h, length_l = divmod(byte_length - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
                data_w += [COMMANDS['lsb_tdi_out_f_tdo_in_r_byte'], length_l, length_h] + list(reversed(list(data[1:][-byte_length * 8:].bytes)))
                bits += [8] * byte_length

            # Use bit shifts for last byte
            if bit_length != 0: # This will be true if data is longer than 1 bit
                data_w += [COMMANDS['lsb_tdi_out_f_tdo_in_r_bit'], bit_length - 1, data[1:bit_length + 1].uint] # Need to subtract 1 as data length for MPSSE command starts with 0
                bits += [bit_length]

            # Use TMS shifts for last bit
            # Shift out last bit (MSb) and advance JTAG TAP to Exit-IR/Exit-DR state
            # data_w += [COMMANDS['lsb_tms_out_f_tdo_in_r'], 1-1, (data[0:1].uint << 7) | 0b00000001] # TDI = MSb, TMS = 1
            data_w += [COMMANDS['lsb_tms_out_f_tdo_in_r'], 1 - 1, (data[0:1].uint << 7) | tms.uint] # TDI = MSb, TMS = TMS
            bits += [1]

            # Ask for MPSSE response to be sent immediately
            data_w += [COMMANDS['send_immediate']]

            self.write(port = self.port_jtag, data = data_w)
            data_r = self.read(port = self.port_jtag, length = len(bits))

            # Reverse data as bytes were shifted in LSb first
            # Mask data as the last byte contains only one useful bit and the one before may contain less than 8 useful bits
            value = bitstring.BitArray()

            # Convert all bytes except the last one
            if len(data_r) > 2:
                value.append(bitstring.BitArray(bytes = bytes(data_r[:-2])))
                value.byteswap() # Reverse all bytes

            # Convert last byte
            if len(data_r) > 1:
                value.prepend(bitstring.BitArray(uint = data_r[-2] >> (8 - bits[-2]), length = bits[-2]))

            # Convert last bit
            value.prepend(bitstring.BitArray(uint = data_r[-1] >> (8 - bits[-1]), length = bits[-1]))

            logger.debug(f'OK, {value.length} bits: 0b{value.bin}')

        elif data is not None:
            logger.debug(f'Shift {data.length} bits out to TDI: 0b{data.bin}')

            bits = [] # List of meaningful bits for each read byte
            data_w = []

            # Split bitstring into 8-bit vectors starting from the end of the bitstring as bits shall be shifted out LSb first
            byte_length, bit_length = divmod(data[1:].length, 8)

            # Use byte shifts for all bytes except the last one
            if byte_length != 0: # This will be true if data is longer than 9 bits
                length_h, length_l = divmod(byte_length - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
                data_w += [COMMANDS['lsb_tdi_out_f_byte'], length_l, length_h] + list(reversed(list(data[1:][-byte_length * 8:].bytes)))
                bits += [8] * byte_length

            # Use bit shifts for last byte
            if bit_length != 0: # This will be true if data is longer than 1 bit
                data_w += [COMMANDS['lsb_tdi_out_f_bit'], bit_length - 1, data[1:bit_length + 1].uint] # Need to subtract 1 as data length for MPSSE command starts with 0
                bits += [bit_length]

            # Use TMS shifts for last bit
            # Shift out last bit (MSb) and advance JTAG TAP to Exit-IR/Exit-DR state
            # data_w += [COMMANDS['lsb_tms_out_f'], 1-1, (data[0:1].uint << 7) | 0b00000001] # TDI = MSb, TMS = 1
            data_w += [COMMANDS['lsb_tms_out_f'], 1 - 1, (data[0:1].uint << 7) | tms.uint] # TDI = MSb, TMS = TMS
            bits += [1]

            # Ask for MPSSE response to be sent immediately
            data_w += [COMMANDS['send_immediate']]

            self.write(port = self.port_jtag, data = data_w)

            value = None

            logger.debug('OK')

        elif length is not None:
            logger.debug(f'Shift {length} bits in from TDO')

            bits = [] # List of meaningful bits for each read byte
            data_w = []

            # Split bitstring into 8-bit vectors starting from the end of the bitstring as bits shall be shifted out LSb first
            byte_length, bit_length = divmod(bitstring.BitArray(length)[1:].length, 8) # Use dummy bitstring to define number of bytes

            # Use byte shifts for all bytes except the last one
            if byte_length != 0: # This will be true if data is longer than 9 bits
                length_h, length_l = divmod(byte_length - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
                data_w += [COMMANDS['lsb_tdo_in_r_byte'], length_l, length_h]
                bits += [8] * byte_length

            # Use bit shifts for last byte
            if bit_length != 0: # This will be true if data is longer than 1 bit
                data_w += [COMMANDS['lsb_tdo_in_r_bit'], bit_length - 1] # Need to subtract 1 as data length for MPSSE command starts with 0
                bits += [bit_length]

            # Use TMS shifts for last bit
            # Shift out last bit (MSb) and advance JTAG TAP to Exit-IR/Exit-DR state
            # data_w += [COMMANDS['lsb_tms_out_f_tdo_in_r'], 1-1, 0b00000001] # TDI = L, TMS = 1
            data_w += [COMMANDS['lsb_tms_out_f_tdo_in_r'], 1 - 1, tms.uint] # TDI = L, TMS = TMS
            bits += [1]

            # Ask for MPSSE response to be sent immediately
            data_w += [COMMANDS['send_immediate']]

            self.write(port = self.port_jtag, data = data_w)
            data_r = self.read(port = self.port_jtag, length = len(bits))

            # Reverse data as bytes were shifted in LSb first
            # Mask data as the last byte contains only one useful bit and the one before may contain less than 8 useful bits
            value = bitstring.BitArray()

            # Convert all bytes except the last one
            if len(data_r) > 2:
                value.append(bitstring.BitArray(bytes = bytes(data_r[:-2])))
                value.byteswap() # Reverse all bytes

            # Convert last byte
            if len(data_r) > 1:
                value.prepend(bitstring.BitArray(uint = data_r[-2] >> (8 - bits[-2]), length = bits[-2]))

            # Convert last bit
            value.prepend(bitstring.BitArray(uint = data_r[-1] >> (8 - bits[-1]), length = bits[-1]))

            logger.debug(f'OK, {value.length} bits: 0b{value.bin}')

        return value


    #---------------------------------------------------------------------------
    # SPI
    def spi_initialize(self, port, frequency):
        '''Initialize SPI interface

        Parameter:
        'port'      : (str) Port name ('A', 'B')
        'frequency' : (str) SPI SCK frequency from FREQUENCIES dictionary

        Return:
        None

        '''

        logger.debug('Initialize SPI')

        self.port_spi = port

        # Set master clock divider
        logger.debug(f'| FTDI device, port {self.port_spi}: Set master clock divider for \'{frequency}\' frequency')
        if frequency not in FREQUENCIES.keys():
            logger.critical(f'| Wrong SCK frequency: \'{frequency}\'')
            raise FTDICritical

        data_w = [COMMANDS['set_clock_divider'], FREQUENCIES[frequency] & 0xFF, (FREQUENCIES[frequency] >> 8) & 0xFF]
        self.write(port = self.port_spi, data = data_w)

        self.spi_frequency = frequency

        # Set idle states for I/O pins
        # SPI signals have external pull-ups. Other I/O pins don't matter as they are not connected
        logger.debug(f'| FTDI device, port {self.port_spi}: Configure I/O pins idle states')
        data_w = [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = H, MISO = Z, MOSI = H, SCK = L
        self.write(port = self.port_spi, data = data_w)

        logger.debug('OK')

        return None


    def spi_finalize(self):
        '''Perform clean-up actions on SPI interface

        Parameter:
        None

        Return:
        None

        '''

        logger.debug('Finalize SPI')

        logger.debug(f'| FTDI device, port {self.port_spi}: Configure I/O pins as inputs')

        data_w = []

        data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = H, MISO = Z, MOSI = H, SCK = L
        data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00001011] * DELAYS[self.spi_frequency] # SS# = H, MISO = Z, MOSI = H, SCK = H
        data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00000000] * DELAYS[self.spi_frequency] # SS# = Z, MISO = Z, MOSI = Z, SCK = Z

        self.write(port = self.port_spi, data = data_w)

        logger.debug('OK')

        return None


    def spi_write(self, data):
        '''Write data to SPI device

        Parameter:
        'data' : (list) Bytes to write

        Return:
        None

        '''

        logger.debug(f'SPI write, {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        data_w = []

        # Activate SS#
        data_w += [COMMANDS['set_pins_d'], 0b11110110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = L, MISO = Z, MOSI = H, SCK = L

        # Shift data out
        # TODO: Replace this with a loop to take care of length > 65536
        length_h, length_l = divmod(len(data) - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
        data_w += [COMMANDS['msb_tdi_out_f_byte'], length_l, length_h] + data

        # Deactivate SS#
        data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = H, MISO = Z, MOSI = H, SCK = L

        # Ask for MPSSE response to be sent immediately
        data_w += [COMMANDS['send_immediate']]

        self.write(port = self.port_spi, data = data_w)

        logger.debug('OK')

        return None


    def spi_read(self, length):
        '''Read data from SPI device

        Parameter:
        'length' : (int) Number of bytes to read

        Return:
        (list) Read bytes

        '''

        logger.debug(f'SPI read, {length:d} bytes')

        data_w = []

        # Activate SS#
        data_w += [COMMANDS['set_pins_d'], 0b11110110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = L, MISO = Z, MOSI = H, SCK = L

        # Shift data in
        # TODO: Replace this with a loop to take care of length > 65536
        length_h, length_l = divmod(length - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
        data_w += [COMMANDS['msb_tdo_in_r_byte'], length_l, length_h]

        # Deactivate SS#
        data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = H, MISO = Z, MOSI = H, SCK = L

        # Ask for MPSSE response to be sent immediately
        data_w += [COMMANDS['send_immediate']]

        self.write(port = self.port_spi, data = data_w)
        data_r = self.read(port = self.port_spi, length = length)

        logger.debug(f'OK, {len(data_r):d} bytes: [{", ".join([f"0x{item:02X}" for item in data_r])}]')

        return data_r


    def spi_write_read(self, data, length):
        '''Write data to SPI device then read data from SPI device

        Parameter:
        'data'    : (list) Bytes to write
        'length'  : (int)  Number of bytes to read

        Return:
        (list) Read bytes

        '''

        logger.debug(f'SPI write then read, {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        data_w = []

        # Activate SS#
        data_w += [COMMANDS['set_pins_d'], 0b11110110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = L, MISO = Z, MOSI = H, SCK = L

        # Shift data out
        # TODO: Replace this with a loop to take care of length > 65536
        length_h, length_l = divmod(len(data) - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
        data_w += [COMMANDS['msb_tdi_out_f_byte'], length_l, length_h] + data

        # Shift data in
        # TODO: Replace this with a loop to take care of length > 65536
        length_h, length_l = divmod(length - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
        data_w += [COMMANDS['msb_tdo_in_r_byte'], length_l, length_h]

        # Deactivate SS#
        data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = H, MISO = Z, MOSI = H, SCK = L

        # Ask for MPSSE response to be sent immediately
        data_w += [COMMANDS['send_immediate']]

        self.write(port = self.port_spi, data = data_w)
        data_r = self.read(port = self.port_spi, length = length)

        logger.debug(f'OK, {len(data_r):d} bytes: [{", ".join([f"0x{item:02X}" for item in data_r])}]')

        return data_r



    # def spi_exchange(self, data):
    #     '''Shifts data through SPI

    #     Parameter:
    #     data : (list) Bytes to shift out

    #     Return:
    #     (list) Bytes shifted in

    #     '''

    #     logger.debug(f'SPI exchange, {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

    #     data_w = []

    #     # Activate SS#
    #     data_w += [COMMANDS['set_pins_d'], 0b11110110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = L, MISO = Z, MOSI = H, SCK = L

    #     # Shift data
    #     # TODO: Replace this with a loop to take care of length > 65536
    #     length_h, length_l = divmod(len(data) - 1, 256) # Need to subtract 1 as data length for MPSSE command starts with 0
    #     data_w += [COMMANDS['msb_tdi_out_f_tdo_in_r_byte'], length_l, length_h] + data

    #     # Deactivate SS#
    #     data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00001011] * DELAYS[self.spi_frequency] # SS# = H, MISO = Z, MOSI = H, SCK = L

    #     # Ask for MPSSE response to be sent immediately
    #     data_w += [COMMANDS['send_immediate']]

    #     self.write(port = self.port_spi, data = data_w)
    #     data_r = self.read(port = self.port_spi, length = len(data))

    #     logger.debug(f'OK, {len(data_r):d} bytes: [{", ".join([f"0x{item:02X}" for item in data_r])}]')

    #     return data_r


    #---------------------------------------------------------------------------
    # I2C
    def i2c_initialize(self, port, frequency):
        '''Initialize I2C interface

        Parameter:
        'port'      : (str) Port name ('A', 'B')
        'frequency' : (str) I2C SCL frequency from FREQUENCIES dictionary

        Return:
        None

        '''

        logger.debug('Initialize I2C')

        self.port_i2c = port

        # Enable 3-phase clocking
        logger.debug(f'| FTDI device, port {self.port_i2c}: Enable 3-phase clocking')
        self.write(port = self.port_i2c, data = [COMMANDS['enable_3_phase_clocking']])
        # self.read(port = self.port_i2c, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

        # Set master clock divider
        logger.debug(f'| FTDI device, port {self.port_i2c}: Set master clock divider for \'{frequency}\' frequency')
        if frequency not in FREQUENCIES.keys():
            logger.critical(f'Wrong I2C frequency: \'{frequency}\'')
            raise FTDICritical

        self.write(port = self.port_i2c, data = [COMMANDS['set_clock_divider'], FREQUENCIES[frequency] & 0xFF, (FREQUENCIES[frequency] >> 8) & 0xFF])
        # self.read(port = self.port_i2c, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

        self.i2c_frequency = frequency

        # Set idle states for I/O pins when they are configured as outputs and configure all I/O pins as inputs (tri-state)
        # I2C signals are kept high by external pull-ups in idle state (start and end of I2C bus transaction), other I/O pins don't matter as they are not connected
        logger.debug(f'| FTDI device, port {self.port_i2c}: Configure I/O pins idle states')
        self.write(port = self.port_i2c, data = [COMMANDS['set_pins_d'], 0b00000000, 0b00000000] * DELAYS[self.i2c_frequency]) # SDAO = Z, SCL = Z. TODO: change value to 0b11111100
        # self.read(port = self.port_i2c, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

        # TEST: Generate several pulses on SCL using 'clock_pulse_bit' command
        # self.write(port = self.port_i2c, data = [COMMANDS['set_pins_d'], 0b11111111, 0b00000001, # Enable SCL output buffer
        #                                 COMMANDS['clock_pulse_bit'], 7, # Generate 8 clock pulses, no data transfer
        #                                 COMMANDS['set_pins_d'], 0b11111111, 0b00000000]) # Disable SCL output buffer
        # self.read(port = self.port_i2c, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

        # TEST: Generate a pulse on SCL using back-to-back 'set_pins_d' COMMANDS
        # One such command seems to create a 250 ns delay on a high-speed USB bus
        # data_w = []
        # data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00000000]*1  # Disable SCL output buffer
        # data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00000001]*1  # Enable SCL output buffer, drive SCL high
        # data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00000001]*10 # Enable SCL output buffer, drive SCL low. This keeps SCL low for 2.5 us
        # data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00000001]*10 # Enable SCL output buffer, drive SCL high. This keeps SCL high for 2.5 us
        # data_w += [COMMANDS['set_pins_d'], 0b11111110, 0b00000001]*10 # Enable SCL output buffer, drive SCL low. This keeps SCL low for 2.5 us
        # data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00000001]*1  # Enable SCL output buffer, drive SCL high
        # data_w += [COMMANDS['set_pins_d'], 0b11111111, 0b00000000]*1  # Disable SCL output buffer
        # self.write(port = self.port_i2c, data = data_w)
        # self.read(port = self.port_i2c, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

        logger.debug('OK')

        return None


    def i2c_finalize(self):
        '''Perform clean-up actions on I2C interface

        Parameter:
        None

        Return:
        None

        '''

        logger.debug('Finalize I2C')
        logger.debug('OK')

        return None


    def i2c_pulse(self, pulses):
        '''Generate pulses on SCL

        This might be used to reset an I2C slave that locks SDA

        Parameter:
        'pulses' : (int) Number of pulses (1..8)

        Return:
        None

        '''

        logger.debug('Pulse SCL')

        data_w = []
        data_w += [COMMANDS['set_pins_d'], 0b00000000, 0b00000001] # SCL = L
        data_w += [COMMANDS['clock_pulse_bit'], pulses - 1] # Generate clock pulses, no data transfer
        data_w += [COMMANDS['set_pins_d'], 0b00000000, 0b00000000] # SCL = Z

        # data_w = []
        # data_w += [COMMANDS['set_pins_d'], 0b00000000, 0b00000001] * 10 # SCL = L
        # data_w += [COMMANDS['set_pins_d'], 0b00000001, 0b00000001] * 10 # SCL = H
        # data_w += [COMMANDS['set_pins_d'], 0b00000000, 0b00000001] * 10 # SCL = L
        # data_w += [COMMANDS['set_pins_d'], 0b00000001, 0b00000001] * 10 # SCL = H
        # data_w += [COMMANDS['set_pins_d'], 0b00000000, 0b00000001] * 10 # SCL = L
        # data_w += [COMMANDS['set_pins_d'], 0b00000001, 0b00000001] * 10 # SCL = H
        # data_w += [COMMANDS['set_pins_d'], 0b00000001, 0b00000000] # SCL = Z


        self.write(port = self.port_i2c, data = data_w)
        # self.read(port = self.port_i2c, length = 0) # This read is used to indirectly check that command was accepted by MPSEE as it should return just two modem status bytes and nothing else

        logger.debug('OK')

        return None


    def i2c_start(self, repeated):
        '''Create a sequence of MPSSE COMMANDS requited to generate I2C start condition

        Parameter:
        'repeated' : (bool) False - I2C start condition, True - I2C repeated start condition


        Return:
        (list) list of bytes that represent MPSSE COMMANDS

        '''

        data = []

        if repeated is True:
            # Previous state: I2C acknowledge bit (SDAO = L, SCL = L)
            data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000001] * DELAYS[self.i2c_frequency] # SDAO = Z, SCL = L
            data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000000] * DELAYS[self.i2c_frequency] # I2C tSU;STA. SDAO = Z, SCL = Z

        # Previous state: idle (SDAO = Z, SCL = Z)
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000010] * DELAYS[self.i2c_frequency] # I2C tHD;STA. SDAO = L, SCL = Z
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000011] * DELAYS[self.i2c_frequency] # SDAO = L, SCL = L

        return data


    def i2c_address(self, address, operation):
        '''Create a sequence of MPSSE COMMANDS requited to shift out I2C device address and R/W# bit

        Parameter:
        'address'  : (int) I2C device address, 7-bit, right-justified
        'operation': (str) State of I2C R/W# bit
                           'write' - R/W# bit = 0
                           'read'  - R/W# bit = 1

        Return:
        (list) list of bytes that represent MPSSE COMMANDS

        '''

        if operation == 'write':
            data = [COMMANDS['msb_tdi_out_f_bit'], 7, (address << 1) & 0b11111110] # Shift out 8 bits
        elif operation == 'read':
            data = [COMMANDS['msb_tdi_out_f_bit'], 7, (address << 1) | 0b00000001] # Shift out 8 bits
        else:
            logger.critical(f'Wrong operation: {operation}')
            raise FTDICritical

        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000011] * DELAYS[self.i2c_frequency] # SDAO = L, SCL = L

        return data


    def i2c_byte_out(self, byte):
        '''Create a sequence of MPSSE COMMANDS requited to shift out a byte

        Parameter:
        'byte' : (int) A byte of data to be shifted out

        Return:
        (list) list of bytes that represent MPSSE COMMANDS

        '''

        # Previous state: I2C acknowledge bit (SDAO = L, SCL = L)
        data = []
        data += [COMMANDS['msb_tdi_out_f_bit'], 7, byte] # Shift out 8 bits
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000011] * DELAYS[self.i2c_frequency] # SDAO = L, SCL = L

        return data


    def i2c_byte_in(self):
        '''Create a sequence of MPSSE COMMANDS requited to shift in a byte

        Parameter:
        None

        Return:
        (list) list of bytes that represent MPSSE COMMANDS

        '''

        # Previous state: I2C acknowledge bit (SDAO = L, SCL = L)
        data = []
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000001] # SDAO = Z, SCL = L
        data += [COMMANDS['msb_tdo_in_r_bit'], 7]               # Shift in 8 bits
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000011] * DELAYS[self.i2c_frequency] # SDAO = L, SCL = L

        return data


    def i2c_get_ack(self):
        '''Create a sequence of MPSSE COMMANDS requited to receive I2C acknowledge bit

        Parameter:
        None

        Return:
        (list) list of bytes that represent MPSSE COMMANDS

        '''

        # Previous state: I2C address or byte out (SDAO = L, SCL = L)
        data = []
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000001] # SDAO = Z, SCL = L
        data += [COMMANDS['msb_tdo_in_r_bit'], 0]               # Shift in acknowledge bit
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000011] * DELAYS[self.i2c_frequency] # SDAO = L, SCL = L

        return data


    def i2c_set_ack(self, acknowledge):
        '''Create a sequence of MPSSE COMMANDS requited to send I2C acknowledge bit

        Parameter:
        'acknowledge' : (bool) False - set acknowledge bit to 1, True - set acknowledge bit to 0

        Return:
        (list) list of bytes that represent MPSSE COMMANDS

        '''

        ack_bit = 0b00000000 if acknowledge is True else 0b11111111

        # Previous state: byte in (SDAO = L, SCL = L)
        data = []
        data += [COMMANDS['msb_tdi_out_f_bit'], 0, ack_bit] # Shift out acknowledge bit
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000011] * DELAYS[self.i2c_frequency] # SDAO = L, SCL = L

        return data


    def i2c_stop(self):
        '''Create a sequence of MPSSE COMMANDS requited to generate I2C stop condition

        Parameter:
        None

        Return:
        (list) list of bytes that represent MPSSE COMMANDS

        '''

        # Previous state: I2C acknowledge bit (SDAO = L, SCL = L)
        data = []
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000010] * DELAYS[self.i2c_frequency] # I2C tSU;STO. SDAO = L, SCL = Z
        data += [COMMANDS['set_pins_d'], 0b00000000, 0b00000000] * DELAYS[self.i2c_frequency] # I2C tBUF. SDAO = Z, SCL = Z

        return data


    def i2c_write(self, address, data):
        '''Write data to I2C device

        Parameter:
        'address' : (int)  I2C device address, 7-bit, right-justified
        'data'    : (list) Bytes to write

        Return:
        None

        '''

        logger.debug(f'I2C write, address: 0x{address:02X}, length: {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        data_w = []
        data_w += self.i2c_start(repeated = False) # I2C start condition

        data_w += self.i2c_address(address = address, operation = 'write') # I2C address and R/W# bit = 0
        data_w += self.i2c_get_ack() # I2C get acknowledge bit

        for byte in data:
            data_w += self.i2c_byte_out(byte = byte) # Send data byte
            data_w += self.i2c_get_ack() # I2C get acknowledge bit

        data_w += self.i2c_stop() # I2C stop condition

        data_w += [COMMANDS['send_immediate']] # Ask for MPSSE response to be sent immediately

        self.write(port = self.port_i2c, data = data_w)

        data_r = self.read(port = self.port_i2c, length = 1 + len(data)) # Address acknowledge status byte, data acknowledge status bytes

        if (data_r[0] & 0x01) != 0x00: # Check I2C address acknowledge bit
            logger.error('FAIL: Address was not acknowledged')
            raise hwio.i2c.I2CError('Address was not acknowledged')

        for number, status in enumerate(data_r[1:]):
            if (status & 0x01) != 0x00: # Check I2C data byte acknowledge bit
                logger.warning(f'FAIL: Data byte {number} was not acknowledged') # Log level is WARNING because some I2C devices don't acknowledge data under certain conditions (e.g. writing to a locked ID page of EEPROMs that have it). This allows avoiding false-positive errors being logged at higher-level scope
                raise hwio.i2c.I2CError(f'Data byte {number} was not acknowledged')

        logger.debug('OK')

        return None


    def i2c_read(self, address, length):
        '''Read data from I2C device

        Parameter:
        'address' : (int) I2C device address, 7-bit, right-justified
        'length'  : (int) Number of bytes to read

        Return:
        (list) Read bytes

        '''

        logger.debug(f'I2C read, address: 0x{address:02X}, length: {length:d} bytes')

        data_w = []
        data_w += self.i2c_start(repeated = False) # I2C start condition

        data_w += self.i2c_address(address = address, operation = 'read') # I2C address and R/W# bit = 1
        data_w += self.i2c_get_ack() # I2C get acknowledge bit

        # Mater must acknowledge all received bytes except the last one
        # Absence of acknowledgment from master tells slave to release SDA line so master could generate an I2C stop condition
        for number in range(length - 1):
            data_w += self.i2c_byte_in() # Receive data byte
            data_w += self.i2c_set_ack(acknowledge = True) # I2C get acknowledge bit

        data_w += self.i2c_byte_in() # Receive data byte
        data_w += self.i2c_set_ack(acknowledge = False) # I2C get acknowledge bit

        data_w += self.i2c_stop() # I2C stop condition

        data_w += [COMMANDS['send_immediate']] # Ask for MPSSE response to be sent immediately

        self.write(port = self.port_i2c, data = data_w)

        data_r = self.read(port = self.port_i2c, length = 1 + length) # Address acknowledge byte, data bytes

        if (data_r[0] & 0x01) != 0x00: # Check I2C address acknowledge bit
            logger.error('FAIL: Address was not acknowledged')
            raise hwio.i2c.I2CError('Address was not acknowledged')

        data = data_r[1:]

        logger.debug(f'OK, length: {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        return data


    def i2c_write_read(self, address, data, length):
        '''Write data to I2C device, generate repeated start (Sr) and then read data from I2C device

        Parameter:
        'address' : (int)  I2C device address, 7-bit, right-justified
        'data'    : (list) Bytes to write
        'length'  : (int)  Number of bytes to read

        Return:
        (list) Read bytes

        '''

        logger.debug(f'I2C write then read, address: 0x{address:02X}, length: {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        data_w = []
        data_w += self.i2c_start(repeated = False) # I2C start condition

        data_w += self.i2c_address(address = address, operation = 'write') # I2C address and R/W# bit = 0
        data_w += self.i2c_get_ack() # I2C get acknowledge bit

        for byte in data:
            data_w += self.i2c_byte_out(byte = byte) # Send data byte
            data_w += self.i2c_get_ack() # I2C get acknowledge bit

        data_w += self.i2c_start(repeated = True) # I2C repeated start condition

        data_w += self.i2c_address(address = address, operation = 'read') # I2C address and R/W# bit = 1
        data_w += self.i2c_get_ack() # I2C get acknowledge bit

        # Mater must acknowledge all received bytes except the last one
        # Absence of acknowledgment from master tells slave to release SDA line so master could generate an I2C stop condition
        for number in range(length - 1):
            data_w += self.i2c_byte_in() # Receive data byte
            data_w += self.i2c_set_ack(acknowledge = True) # I2C get acknowledge bit

        data_w += self.i2c_byte_in() # Receive data byte
        data_w += self.i2c_set_ack(acknowledge = False) # I2C get acknowledge bit

        data_w += self.i2c_stop() # I2C stop condition

        data_w += [COMMANDS['send_immediate']] # Ask for MPSSE response to be sent immediately

        self.write(port = self.port_i2c, data = data_w)

        data_r = self.read(port = self.port_i2c, length = 1 + len(data) + 1 + length) # Address acknowledge status byte (write), write data acknowledge status bytes, address acknowledge byte (read), multiple read bytes

        write_address_ack = data_r[0]
        write_data_acks = data_r[1:1 + len(data)]
        read_address_ack = data_r[1 + len(data)]
        read_data = data_r[1 + len(data) + 1:1 + len(data) + 1 + length]

        if (write_address_ack & 0x01) != 0x00: # Check I2C write address acknowledge bit
            logger.error('FAIL: Address was not acknowledged on write operation')
            raise hwio.i2c.I2CError('Address was not acknowledged on write operation')

        for number, status in enumerate(write_data_acks):
            if (status & 0x01) != 0x00: # Check I2C write data byte acknowledge bit
                logger.error(f'FAIL: Data byte {number} was not acknowledged on write operation')
                raise hwio.i2c.I2CError(f'Data byte {number} was not acknowledged on write operation')

        if (read_address_ack & 0x01) != 0x00: # Check I2C read address acknowledge bit
            logger.error('FAIL: Address was not acknowledged on read operation')
            raise hwio.i2c.I2CError('Address was not acknowledged on read operation')

        logger.debug(f'OK, length: {len(read_data):d} bytes: [{", ".join([f"0x{item:02X}" for item in read_data])}]')

        return read_data


    def i2c_poke(self, address, operation):
        '''Check if an I2C device with given address responds to it

        Apart from checking if an I2C device with given address exists on the bus this function is used to check if I2C EEPROM write cycle is complete (acknowledge polling)
        In that case 'operation' shall be set to 'write'

        Parameter:
        'address'   : (int) I2C device address, 7-bit, right-justified
        'operation' : (str) 'write'          - Use I2C write operation (R/W# bit = 0) to discover slave
                            'read'           - Use I2C read operation (R/W# bit = 1) to discover slave
                            'write_and_read' - First use I2C write operation to discover slave. Then if slave didn't reply use read operations to discover slave

        Return:
        'True' if I2C device responds
        'False' if I2C device doesn't respond

        '''

        logger.debug(f'I2C poke, address 0x{address:02X}')

        slave_exists = False

        if operation in ['write', 'write_and_read']:
            # Poke I2C address with write request
            logger.debug('| Poke with write request (R/W#=0)')

            data_w = []
            data_w += self.i2c_start(repeated = False) # I2C start condition

            data_w += self.i2c_address(address = address, operation = 'write') # I2C address and R/W# bit = 0
            data_w += self.i2c_get_ack() # I2C acknowledge bit

            data_w += self.i2c_stop() # I2C stop condition

            data_w += [COMMANDS['send_immediate']] # Ask for MPSSE response to be sent immediately

            self.write(port = self.port_i2c, data = data_w) # Write data

            data_r = self.read(port = self.port_i2c, length = 1) # Read data

            if (data_r[0] & 0x01) == 0x00: # Skip modem status bytes and mask previously shifted in bits
                logger.debug('| Slave exists')
                slave_exists = True

            elif (data_r[0] & 0x01) == 0x01: # Skip modem status bytes and mask previously shifted in bits
                logger.debug('| Slave does not exist')

        if operation in ['read', 'write_and_read'] and slave_exists is False:
            # Poke I2C address with read request
            logger.debug('| Poke with read request (R/W#=1)')

            data_w = []
            data_w += self.i2c_start(repeated = False) # I2C start condition

            data_w += self.i2c_address(address = address, operation = 'read') # I2C address and R/W# bit = 1
            data_w += self.i2c_get_ack() # I2C acknowledge bit

            data_w += self.i2c_stop() # I2C stop condition

            data_w += [COMMANDS['send_immediate']] # Ask for MPSSE response to be sent immediately

            self.write(port = self.port_i2c, data = data_w) # Write data

            data_r = self.read(port = self.port_i2c, length = 1) # Read data

            if (data_r[0] & 0x01) == 0x00: # Skip modem status bytes and mask previously shifted in bits
                logger.debug('| Slave exists')
                slave_exists = True

            elif (data_r[0] & 0x01) == 0x01: # Skip modem status bytes and mask previously shifted in bits
                logger.debug('| Slave does not exist')

        logger.debug('OK')

        return slave_exists


# External uWire configuration EEPROM
class FTDIEEPROM:
    def __init__(self, owner, description, eeprom_type, manufacturer, product, serial_number, drive, slew, hysteresis):
        '''Class initializer

        Parameter:
        'owner'         : (object)      Instance of the FTDI class for the device this EEPROM is connected to
        'description'   : (str)         Device description
        'eeprom_type'   : (str)         EEPROM type: 'x56', 'x66'
        'manufacturer'  : (str or None) USB iManufacturer
        'product'       : (str or None) USB iProduct
        'serial_number' : (str or None) USB iSerialNumber
        'drive'         : (str)         Output drive current: '4 mA', '8 mA', '12 mA', '16 mA'
        'slew'          : (str)         Output slew rate: 'fast', 'slow'
        'hysteresis'    : (str)         Input hysteresis: 'no', 'yes'

        Return:
        An instance of class

        '''

        self.owner       = owner
        self.description = description

        if PRODUCT_IDS[self.owner.device.idProduct] not in ['FT232H', 'FT2232H', 'FT4232H']:
            logger.critical(f'FAIL: Wrong USB idProduct: 0x{self.owner.device.idProduct:04X}')
            raise FTDICritical

        # EEPROM size in 16-bit words
        if eeprom_type == 'x56':
            self.eeprom_size = 0x80
        elif eeprom_type == 'x66':
            self.eeprom_size = 0x100
        else:
            logger.critical(f'FAIL: Wrong EEPROM type: {eeprom_type}')
            raise FTDICritical


        #-----------------------------------------------------------------------
        self.registers = {}

        # EEPROM register addresses are in words
        # USB string addresses and lengths are in bytes

        # USB string descriptors
        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H']:
            offset = 0x50 * 2 # Offset in bytes. It seems there are problems if this offset is less than 0x50 (in words) (0xA0 in bytes) (e.g. lsusb doesn't decode strings properly etc). FT_Prog also uses offset 0x50 (in words)
        elif PRODUCT_IDS[self.owner.device.idProduct] in ['FT2232H', 'FT4232H']:
            offset = 0x0D * 2 # Offset in bytes. TODO: Check what offset does FT_Prog use

        if manufacturer is not None:
            mfg_str_addr  = offset # Address in bytes
            mfg_str_value = manufacturer.encode('utf-16be') # UTF-16BE encoding creates proper byte string for EEPROM 16-bit words (e.g. b'\x00F\x00T\x00D\x00I')
            mfg_str_len   = 1 + 1 + len(mfg_str_value) # Length in bytes. Reserve space for bDescriptorType, bLength
            mfg_str_value = b'\x03' + bytes([mfg_str_len]) + mfg_str_value # Add bDescriptorType, bLength

            self.registers['usb_mfg_desc'] = hwio.register.Register(description = 'USB manufacturer string descriptor (iManufacturer)',
                                                                    address     = bitstring.Bits(uint = mfg_str_addr // 2, length = 8), # Address in words
                                                                    length      = mfg_str_len * 8,
                                                                    bitfields   = {'mfg_str' : hwio.register.Bitfield(bits        = f'[{mfg_str_len * 8 - 1}:0]',
                                                                                                                      description = 'Manufacturer string descriptor (iManufacturer)',
                                                                                                                      fmt         = 'uint',
                                                                                                                      value       = bitstring.Bits(bytes = mfg_str_value).uint)})
        else:
            mfg_str_addr  = 0x00
            mfg_str_len   = 0x00

        if product is not None:
            prod_str_addr  = offset + mfg_str_len
            prod_str_value = product.encode('utf-16be')
            prod_str_len   = 1 + 1 + len(prod_str_value)
            prod_str_value = b'\x03' + bytes([prod_str_len]) + prod_str_value

            self.registers['usb_prod_desc'] = hwio.register.Register(description = 'USB product string descriptor (iProduct)',
                                                                     address     = bitstring.Bits(uint = prod_str_addr // 2, length = 8), # Address in words
                                                                     length      = prod_str_len * 8,
                                                                     bitfields   = {'prod_str' : hwio.register.Bitfield(bits        = f'[{prod_str_len * 8 - 1}:0]',
                                                                                                                        description = 'Product string descriptor (iProduct)',
                                                                                                                        fmt         = 'uint',
                                                                                                                        value       = bitstring.Bits(bytes = prod_str_value).uint)})
        else:
            prod_str_addr  = 0x00
            prod_str_len   = 0x00

        if serial_number is not None:
            ser_no_str_addr  = offset + mfg_str_len + prod_str_len
            ser_no_str_value = serial_number.encode('utf-16be')
            ser_no_str_len   = 1 + 1 + len(ser_no_str_value)
            ser_no_str_value = b'\x03' + bytes([ser_no_str_len]) + ser_no_str_value

            self.registers['usb_ser_no_desc'] = hwio.register.Register(description = 'USB serial number string descriptor (iSerialNumber)',
                                                                       address     = bitstring.Bits(uint = ser_no_str_addr // 2, length = 8), # Address in words
                                                                       length      = ser_no_str_len * 8,
                                                                       bitfields   = {'ser_no_str' : hwio.register.Bitfield(bits        = f'[{ser_no_str_len * 8 - 1}:0]',
                                                                                                                            description = 'Serial number string descriptor (iSerialNumber)',
                                                                                                                            fmt         = 'uint',
                                                                                                                            value       = bitstring.Bits(bytes = ser_no_str_value).uint)})
        else:
            ser_no_str_addr  = 0x00
            ser_no_str_len   = 0x00

        # Registers
        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H']:
            self.registers['port_cfg'] = hwio.register.Register(description = 'Port configuration',
                                                                address     = bitstring.Bits('0x00'),
                                                                length      = 16,
                                                                bitfields   = {'suspend_ac7'           : hwio.register.Bitfield(bits        = '[15]',
                                                                                                                                description = 'Suspend when AC7 pin is low',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'no'  : 0b0,
                                                                                                                                               'yes' : 0b1},
                                                                                                                                value       = 'no'),

                                                                               'reserved_1'            : hwio.register.Bitfield(bits        = '[14:11]',
                                                                                                                                description = 'reserved',
                                                                                                                                fmt         = 'uint',
                                                                                                                                value       = 0b0000),

                                                                               'ft1248_flow_control'   : hwio.register.Bitfield(bits        = '[10]',
                                                                                                                                description = 'FT1248 flow control',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'yes' : 0b0,
                                                                                                                                               'no'  : 0b1},
                                                                                                                                value       = 'yes'),

                                                                               'ft1248_bit_order'      : hwio.register.Bitfield(bits        = '[9]',
                                                                                                                                description = 'FT1248 bit order',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'msb' : 0b0,
                                                                                                                                               'lsb' : 0b1},
                                                                                                                                value       = 'msb'),

                                                                               'ft1248_clock_polarity' : hwio.register.Bitfield(bits        = '[8]',
                                                                                                                                description = 'FT1248 clock polarity',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'low'  : 0b0,
                                                                                                                                               'high' : 0b1},
                                                                                                                                value       = 'low'),

                                                                               'reserved_0'            : hwio.register.Bitfield(bits        = '[7:5]',
                                                                                                                                description = 'reserved',
                                                                                                                                fmt         = 'uint',
                                                                                                                                value       = 0b000),

                                                                               'port_driver'           : hwio.register.Bitfield(bits        = '[4]',
                                                                                                                                description = 'Port driver',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'d2xx' : 0b0,
                                                                                                                                               'vcp'  : 0b1},
                                                                                                                                value       = 'vcp'),

                                                                               'port_type'             : hwio.register.Bitfield(bits        = '[3:0]',
                                                                                                                                description = 'Port type',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'uart'        : 0b0000,
                                                                                                                                               'fifo_245'    : 0b0001,
                                                                                                                                               'fifo_cpu'    : 0b0010,
                                                                                                                                               'fast_serial' : 0b0100,
                                                                                                                                               'ft1248'      : 0b1000},
                                                                                                                                value       = 'uart')})

        elif PRODUCT_IDS[self.owner.device.idProduct] in ['FT2232H']:
            self.registers['port_cfg'] = hwio.register.Register(description = 'Port configuration',
                                                                address     = bitstring.Bits('0x00'),
                                                                length      = 16,
                                                                bitfields   = {'suspend_bc7'           : hwio.register.Bitfield(bits        = '[15]',
                                                                                                                                description = 'Suspend when BC7 pin is low',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'no'  : 0b0,
                                                                                                                                               'yes' : 0b1},
                                                                                                                                value       = 'no'),

                                                                               'reserved_1'            : hwio.register.Bitfield(bits        = '[14:12]',
                                                                                                                                description = 'reserved',
                                                                                                                                fmt         = 'uint',
                                                                                                                                value       = 0b000),


                                                                               'port_b_driver'         : hwio.register.Bitfield(bits        = '[11]',
                                                                                                                                description = 'Port B driver',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'d2xx' : 0b0,
                                                                                                                                               'vcp'  : 0b1},
                                                                                                                                value       = 'vcp'),

                                                                               'port_b_type'           : hwio.register.Bitfield(bits        = '[10:8]',
                                                                                                                                description = 'Port B type',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'uart'        : 0b000,
                                                                                                                                               'fifo_245'    : 0b001,
                                                                                                                                               'fifo_cpu'    : 0b010,
                                                                                                                                               'fast_serial' : 0b100},
                                                                                                                                value       = 'uart'),

                                                                               'reserved_0'            : hwio.register.Bitfield(bits        = '[7:4]',
                                                                                                                                description = 'reserved',
                                                                                                                                fmt         = 'uint',
                                                                                                                                value       = 0b0000),

                                                                               'port_a_driver'         : hwio.register.Bitfield(bits        = '[3]',
                                                                                                                                description = 'Port A driver',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'d2xx' : 0b0,
                                                                                                                                               'vcp'  : 0b1},
                                                                                                                                value       = 'vcp'),

                                                                               'port_a_type'           : hwio.register.Bitfield(bits        = '[2:0]',
                                                                                                                                description = 'Port A type',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'uart'        : 0b000,
                                                                                                                                               'fifo_245'    : 0b001,
                                                                                                                                               'fifo_cpu'    : 0b010,
                                                                                                                                               'fast_serial' : 0b100},
                                                                                                                                value       = 'uart')})

        elif PRODUCT_IDS[self.owner.device.idProduct] in ['FT4232H']:
            self.registers['port_cfg'] = hwio.register.Register(description = 'Port configuration',
                                                                address     = bitstring.Bits('0x00'),
                                                                length      = 16,
                                                                bitfields   = {'port_d_driver'         : hwio.register.Bitfield(bits        = '[15]',
                                                                                                                                description = 'Port D driver',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'d2xx' : 0b0,
                                                                                                                                               'vcp'  : 0b1},
                                                                                                                                value       = 'vcp'),

                                                                               'port_d_type'           : hwio.register.Bitfield(bits        = '[14:12]',
                                                                                                                                description = 'Port D type',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'uart' : 0b000},
                                                                                                                                value       = 'uart'),

                                                                               'port_b_driver'         : hwio.register.Bitfield(bits        = '[11]',
                                                                                                                                description = 'Port B driver',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'d2xx' : 0b0,
                                                                                                                                               'vcp'  : 0b1},
                                                                                                                                value       = 'vcp'),

                                                                               'port_b_type'           : hwio.register.Bitfield(bits        = '[10:8]',
                                                                                                                                description = 'Port B type',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'uart' : 0b000},
                                                                                                                                value       = 'uart'),

                                                                               'port_c_driver'         : hwio.register.Bitfield(bits        = '[7]',
                                                                                                                                description = 'Port C driver',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'d2xx' : 0b0,
                                                                                                                                               'vcp'  : 0b1},
                                                                                                                                value       = 'vcp'),

                                                                               'port_c_type'           : hwio.register.Bitfield(bits        = '[6:4]',
                                                                                                                                description = 'Port C type',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'uart' : 0b000},
                                                                                                                                value       = 'uart'),

                                                                               'port_a_driver'         : hwio.register.Bitfield(bits        = '[3]',
                                                                                                                                description = 'Port A driver',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'d2xx' : 0b0,
                                                                                                                                               'vcp'  : 0b1},
                                                                                                                                value       = 'vcp'),

                                                                               'port_a_type'           : hwio.register.Bitfield(bits        = '[2:0]',
                                                                                                                                description = 'Port A type',
                                                                                                                                fmt         = 'uint',
                                                                                                                                values      = {'uart' : 0b000},
                                                                                                                                value       = 'uart')})


        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H', 'FT2232H', 'FT4232H']:
            self.registers['usb_vid'] = hwio.register.Register(description = 'USB vendor ID (idVendor)',
                                                               address = bitstring.Bits('0x01'),
                                                               length = 16,
                                                               bitfields = {'usb_vid' : hwio.register.Bitfield(bits        = '[15:0]',
                                                                                                               description = 'USB vendor ID (idVendor)',
                                                                                                               fmt         = 'uint',
                                                                                                               values      = {'FTDI' : 0x0403},
                                                                                                               value       = 'FTDI')})

            self.registers['usb_pid'] = hwio.register.Register(description = 'USB product ID (idProduct)',
                                                               address = bitstring.Bits('0x02'),
                                                               length = 16,
                                                               bitfields = {'usb_pid' : hwio.register.Bitfield(bits        = '[15:0]',
                                                                                                               description = 'USB product ID (idProduct)',
                                                                                                               fmt         = 'uint',
                                                                                                               values      = {'FT232H'  : 0x6014,
                                                                                                                              'FT2232H' : 0x6010,
                                                                                                                              'FT4232H' : 0x6011},
                                                                                                               value       = PRODUCT_IDS[self.owner.device.idProduct])})

            self.registers['usb_dev_rel_no'] = hwio.register.Register(description = 'USB device release number (bcdDevice)',
                                                                      address = bitstring.Bits('0x03'),
                                                                      length = 16,
                                                                      bitfields = {'usb_dev_rel_no' : hwio.register.Bitfield(bits        = '[15:0]',
                                                                                                                             description = 'USB device release number (bcdDevice)',
                                                                                                                             fmt         = 'uint',
                                                                                                                             values      = {'FT232H'  : 0x0900,
                                                                                                                                            'FT2232H' : 0x0700,
                                                                                                                                            'FT4232H' : 0x0800},
                                                                                                                             value       = PRODUCT_IDS[self.owner.device.idProduct])})

            self.registers['usb_cfg_desc'] = hwio.register.Register(description = 'USB configuration descriptor (bmAttributes, bMaxPower)',
                                                                    address     = bitstring.Bits('0x04'),
                                                                    length      = 16,
                                                                    bitfields   = {'max_power' : hwio.register.Bitfield(bits        = '[15:8]',
                                                                                                                        description = 'Maximum current consumption in 2 mA steps (bMaxPower)',
                                                                                                                        fmt         = 'uint',
                                                                                                                        value       = 50), # 50 * 2 mA = 100 mA

                                                                                   'reserved_1'                  : hwio.register.Bitfield(bits        = '[7]',
                                                                                                                                          description = 'reserved (bmAttributes)',
                                                                                                                                          fmt         = 'uint',
                                                                                                                                          value       = 0b1),

                                                                                   'power_source'                : hwio.register.Bitfield(bits        = '[6]',
                                                                                                                                          description = 'Power source (bmAttributes)',
                                                                                                                                          fmt         = 'uint',
                                                                                                                                          values      = {'bus'  : 0b0,
                                                                                                                                                         'self' : 0b1},
                                                                                                                                          value       = 'bus'),

                                                                                   'remote_wakeup'               : hwio.register.Bitfield(bits        = '[5]',
                                                                                                                                          description = 'Remote wakeup (bmAttributes)',
                                                                                                                                          fmt         = 'uint',
                                                                                                                                          values      = {'no'  : 0b0,
                                                                                                                                                         'yes' : 0b1},
                                                                                                                                          value       = 'no'),

                                                                                   'reserved_0'                  : hwio.register.Bitfield(bits        = '[4:0]',
                                                                                                                                          description = 'reserved (bmAttributes)',
                                                                                                                                          fmt         = 'uint',
                                                                                                                                          value       = 0b00000)})

        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H', 'FT2232H']:
            self.registers['chip_cfg'] = hwio.register.Register(description = 'Chip configuration',
                                                                address     = bitstring.Bits('0x05'),
                                                                length      = 16,
                                                                bitfields   = {'reserved_1'                  : hwio.register.Bitfield(bits        = '[15:4]',
                                                                                                                                      description = 'reserved',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      value       = 0b000000000000),

                                                                               'use_ser_no'                  : hwio.register.Bitfield(bits        = '[3]',
                                                                                                                                      description = 'Use serial number',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'no'  : 0b0,
                                                                                                                                                     'yes' : 0b1},
                                                                                                                                      value       = 'no' if serial_number is None else 'yes'),

                                                                               'suspend_pd'                  : hwio.register.Bitfield(bits        = '[2]',
                                                                                                                                      description = 'Enable internal pull-downs on pins in suspend mode',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'no'  : 0b0,
                                                                                                                                                     'yes' : 0b1},
                                                                                                                                      value       = 'no'),

                                                                               'reserved_0'                  : hwio.register.Bitfield(bits        = '[1:0]',
                                                                                                                                      description = 'reserved',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      value       = 0b00)})

        elif PRODUCT_IDS[self.owner.device.idProduct] in ['FT4232H']:
            self.registers['chip_cfg'] = hwio.register.Register(description = 'Chip configuration',
                                                                address     = bitstring.Bits('0x05'),
                                                                length      = 16,
                                                                bitfields   = {'dd7_cfg'                     : hwio.register.Bitfield(bits        = '[15]',
                                                                                                                                      description = 'Pin DD7 configuration',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'ri#'   : 0b0,
                                                                                                                                                     'txden' : 0b1},
                                                                                                                                      value       = 'ri#'),

                                                                               'cd7_cfg'                     : hwio.register.Bitfield(bits        = '[14]',
                                                                                                                                      description = 'Pin CD7 configuration',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'ri#'   : 0b0,
                                                                                                                                                     'txden' : 0b1},
                                                                                                                                      value       = 'ri#'),

                                                                               'bd7_cfg'                     : hwio.register.Bitfield(bits        = '[13]',
                                                                                                                                      description = 'Pin BD7 configuration',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'ri#'   : 0b0,
                                                                                                                                                     'txden' : 0b1},
                                                                                                                                      value       = 'ri#'),

                                                                               'ad7_cfg'                     : hwio.register.Bitfield(bits        = '[12]',
                                                                                                                                      description = 'Pin AD7 configuration',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'ri#'   : 0b0,
                                                                                                                                                     'txden' : 0b1},
                                                                                                                                      value       = 'ri#'),

                                                                               'reserved_1'                  : hwio.register.Bitfield(bits        = '[11:4]',
                                                                                                                                      description = 'reserved',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      value       = 0b00000000),

                                                                               'use_ser_no'                  : hwio.register.Bitfield(bits        = '[3]',
                                                                                                                                      description = 'Use serial number',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'no'  : 0b0,
                                                                                                                                                     'yes' : 0b1},
                                                                                                                                      value       = 'no' if serial_number is None else 'yes'),

                                                                               'suspend_pd'                  : hwio.register.Bitfield(bits        = '[2]',
                                                                                                                                      description = 'Enable internal pull-downs on pins in suspend mode',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'no'  : 0b0,
                                                                                                                                                     'yes' : 0b1},
                                                                                                                                      value       = 'no'),

                                                                               'reserved_0'                  : hwio.register.Bitfield(bits        = '[1:0]',
                                                                                                                                      description = 'reserved',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      value       = 0b00)})

        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H']:
            self.registers['pin_cfg'] = hwio.register.Register(description = 'Pin configuration',
                                                               address     = bitstring.Bits('0x06'),
                                                               length      = 16,
                                                               bitfields   = {'reserved'                      : hwio.register.Bitfield(bits        = '[15:8]',
                                                                                                                                       description = 'reserved',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       value       = 0b00000000),

                                                                              'port_ac_hyst'                  : hwio.register.Bitfield(bits        = '[7]',
                                                                                                                                       description = 'Port AC input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_ac_slew'                  : hwio.register.Bitfield(bits        = '[6]',
                                                                                                                                       description = 'Port AC output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_ac_drive'               : hwio.register.Bitfield(bits        = '[5:4]',
                                                                                                                                     description = 'Port AC output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive),

                                                                              'port_ad_hyst'                  : hwio.register.Bitfield(bits        = '[3]',
                                                                                                                                       description = 'Port AD input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_ad_slew'                  : hwio.register.Bitfield(bits        = '[2]',
                                                                                                                                       description = 'Port AD output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_ad_drive'               : hwio.register.Bitfield(bits        = '[1:0]',
                                                                                                                                     description = 'Port AD output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive)})

        elif PRODUCT_IDS[self.owner.device.idProduct] in ['FT2232H']:
            self.registers['pin_cfg'] = hwio.register.Register(description = 'Pin configuration',
                                                               address     = bitstring.Bits('0x06'),
                                                               length      = 16,
                                                               bitfields   = {'port_bc_hyst'                  : hwio.register.Bitfield(bits        = '[15]',
                                                                                                                                       description = 'Port BC input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_bc_slew'                  : hwio.register.Bitfield(bits        = '[14]',
                                                                                                                                       description = 'Port BC output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_bc_drive'               : hwio.register.Bitfield(bits        = '[13:12]',
                                                                                                                                     description = 'Port BC output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive),

                                                                              'port_bd_hyst'                  : hwio.register.Bitfield(bits        = '[11]',
                                                                                                                                       description = 'Port BD input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_bd_slew'                  : hwio.register.Bitfield(bits        = '[10]',
                                                                                                                                       description = 'Port BD output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_bd_drive'               : hwio.register.Bitfield(bits        = '[9:8]',
                                                                                                                                     description = 'Port BD output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive),

                                                                              'port_ac_hyst'                  : hwio.register.Bitfield(bits        = '[7]',
                                                                                                                                       description = 'Port AC input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_ac_slew'                  : hwio.register.Bitfield(bits        = '[6]',
                                                                                                                                       description = 'Port AC output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_ac_drive'               : hwio.register.Bitfield(bits        = '[5:4]',
                                                                                                                                     description = 'Port AC output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive),

                                                                              'port_ad_hyst'                  : hwio.register.Bitfield(bits        = '[3]',
                                                                                                                                       description = 'Port AD input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_ad_slew'                  : hwio.register.Bitfield(bits        = '[2]',
                                                                                                                                       description = 'Port AD output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_ad_drive'               : hwio.register.Bitfield(bits        = '[1:0]',
                                                                                                                                     description = 'Port AD output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive)})

        elif PRODUCT_IDS[self.owner.device.idProduct] in ['FT4232H']:
            self.registers['pin_cfg'] = hwio.register.Register(description = 'Pin configuration',
                                                               address     = bitstring.Bits('0x06'),
                                                               length      = 16,
                                                               bitfields   = {'port_dd_hyst'                  : hwio.register.Bitfield(bits        = '[15]',
                                                                                                                                       description = 'Port DD input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_dd_slew'                  : hwio.register.Bitfield(bits        = '[14]',
                                                                                                                                       description = 'Port DD output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_dd_drive'               : hwio.register.Bitfield(bits        = '[13:12]',
                                                                                                                                     description = 'Port DD output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive),

                                                                              'port_cd_hyst'                  : hwio.register.Bitfield(bits        = '[11]',
                                                                                                                                       description = 'Port CD input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_cd_slew'                  : hwio.register.Bitfield(bits        = '[10]',
                                                                                                                                       description = 'Port CD output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_cd_drive'               : hwio.register.Bitfield(bits        = '[9:8]',
                                                                                                                                     description = 'Port CD output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive),

                                                                              'port_bd_hyst'                  : hwio.register.Bitfield(bits        = '[7]',
                                                                                                                                       description = 'Port BD input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value       = hysteresis),

                                                                              'port_bd_slew'                  : hwio.register.Bitfield(bits        = '[6]',
                                                                                                                                       description = 'Port BD output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_bd_drive'               : hwio.register.Bitfield(bits        = '[5:4]',
                                                                                                                                     description = 'Port BD output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive),

                                                                              'port_ad_hyst'                  : hwio.register.Bitfield(bits        = '[3]',
                                                                                                                                       description = 'Port AD input hysteresis',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'no'  : 0b0,
                                                                                                                                                      'yes' : 0b1},
                                                                                                                                       value  = hysteresis),

                                                                              'port_ad_slew'                  : hwio.register.Bitfield(bits        = '[2]',
                                                                                                                                       description = 'Port AD output slew',
                                                                                                                                       fmt         = 'uint',
                                                                                                                                       values      = {'fast' : 0b0,
                                                                                                                                                      'slow' : 0b1},
                                                                                                                                       value       = slew),

                                                                              'port_ad_drive'               : hwio.register.Bitfield(bits        = '[1:0]',
                                                                                                                                     description = 'Port AD output drive',
                                                                                                                                     fmt         = 'uint',
                                                                                                                                     values      = {'4 mA'  : 0b00,
                                                                                                                                                    '8 mA'  : 0b01,
                                                                                                                                                    '12 mA' : 0b10,
                                                                                                                                                    '16 mA' : 0b11},
                                                                                                                                     value       = drive)})

        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H', 'FT2232H', 'FT4232H']:
            self.registers['usb_mfg_cfg'] = hwio.register.Register(description = 'USB manufacturer string configuration',
                                                                   address     = bitstring.Bits('0x07'),
                                                                   length      = 16,
                                                                   bitfields   = {'mfg_str_len' : hwio.register.Bitfield(bits        = '[15:8]',
                                                                                                                         description = 'Manufacturer string length (iManufacturer)',
                                                                                                                         fmt         = 'uint',
                                                                                                                         value       = mfg_str_len), # Length in bytes

                                                                                  'mfg_str_addr' : hwio.register.Bitfield(bits        = '[7:0]',
                                                                                                                          description = 'Manufacturer string address (iManufacturer)',
                                                                                                                          fmt         = 'uint',
                                                                                                                          value       = mfg_str_addr)}) # Address in bytes

            self.registers['usb_prod_cfg'] = hwio.register.Register(description = 'USB product string configuration',
                                                                    address     = bitstring.Bits('0x08'),
                                                                    length      = 16,
                                                                    bitfields   = {'prod_str_len' : hwio.register.Bitfield(bits        = '[15:8]',
                                                                                                                           description = 'Product string length (iProduct)',
                                                                                                                           fmt         = 'uint',
                                                                                                                           value       = prod_str_len), # Length in bytes

                                                                                   'prod_str_addr' : hwio.register.Bitfield(bits        = '[7:0]',
                                                                                                                            description = 'Product string address (iProduct)',
                                                                                                                            fmt         = 'uint',
                                                                                                                            value       = prod_str_addr)}) # Address in bytes

            self.registers['usb_ser_no_cfg'] = hwio.register.Register(description = 'USB Serial Number string configuration',
                                                                      address     = bitstring.Bits('0x09'),
                                                                      length      = 16,
                                                                      bitfields   = {'ser_no_str_len' : hwio.register.Bitfield(bits        = '[15:8]',
                                                                                                                               description = 'Serial Number string length (iSerialNumber)',
                                                                                                                               fmt         = 'uint',
                                                                                                                               value       = ser_no_str_len), # Length in bytes

                                                                                     'ser_no_str_addr' : hwio.register.Bitfield(bits        = '[7:0]',
                                                                                                                                description = 'Serial Number string address (iSerialNumber)',
                                                                                                                                fmt         = 'uint',
                                                                                                                                value       = ser_no_str_addr)}) # Address in bytes

        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H']:
            self.registers['pin_ac_3_0_cfg'] = hwio.register.Register(description = 'Pin AC[3:0] configuration',
                                                                      address     = bitstring.Bits('0x0C'),
                                                                      length      = 16,
                                                                      bitfields   = {'ac3' : hwio.register.Bitfield(bits        = '[15:12]',
                                                                                                                    description = 'Pin AC3 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'txd_en'      : 0b1001},
                                                                                                                    value        = 'tristate_pu'),

                                                                                     'ac2' : hwio.register.Bitfield(bits        = '[11:8]',
                                                                                                                    description = 'Pin AC2 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'txd_en'      : 0b1001},
                                                                                                                    value        = 'tristate_pu'),

                                                                                     'ac1' : hwio.register.Bitfield(bits        = '[7:4]',
                                                                                                                    description = 'Pin AC1 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'txd_en'      : 0b1001},
                                                                                                                    value        = 'tristate_pu'),

                                                                                     'ac0' : hwio.register.Bitfield(bits        = '[3:0]',
                                                                                                                    description = 'Pin AC0 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'drive_high'  : 0b0111,
                                                                                                                                   'txd_en'      : 0b1001,
                                                                                                                                   'clk_30mhz'   : 0b1010,
                                                                                                                                   'clk_15mhz'   : 0b1011,
                                                                                                                                   'clk_7_5mhz'  : 0b1100},
                                                                                                                    value        = 'tristate_pu')})

            self.registers['pin_ac_7_4_cfg'] = hwio.register.Register(description = 'Pin AC[7:4] configuration',
                                                                      address     = bitstring.Bits('0x0D'),
                                                                      length      = 16,
                                                                      bitfields   = {'ac7' : hwio.register.Bitfield(bits        = '[15:12]',
                                                                                                                    description = 'Pin AC7 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000},
                                                                                                                    value        = 'tristate_pu'),

                                                                                     'ac6' : hwio.register.Bitfield(bits        = '[11:8]',
                                                                                                                    description = 'Pin AC6 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'drive_high'  : 0b0111,
                                                                                                                                   'io_mode'     : 0b1000,
                                                                                                                                   'txd_en'      : 0b1001,
                                                                                                                                   'clk_30mhz'   : 0b1010,
                                                                                                                                   'clk_15mhz'   : 0b1011,
                                                                                                                                   'clk_7_5mhz'  : 0b1100},
                                                                                                                    value        = 'tristate_pu'),

                                                                                     'ac5' : hwio.register.Bitfield(bits        = '[7:4]',
                                                                                                                    description = 'Pin AC5 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'drive_high'  : 0b0111,
                                                                                                                                   'io_mode'     : 0b1000,
                                                                                                                                   'txd_en'      : 0b1001,
                                                                                                                                   'clk_30mhz'   : 0b1010,
                                                                                                                                   'clk_15mhz'   : 0b1011,
                                                                                                                                   'clk_7_5mhz'  : 0b1100},
                                                                                                                    value        = 'tristate_pu'),

                                                                                     'ac4' : hwio.register.Bitfield(bits        = '[3:0]',
                                                                                                                    description = 'Pin AC4 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'txd_en'      : 0b1001},
                                                                                                                    value        = 'tristate_pu')})

            self.registers['pin_ac_9_8_cfg'] = hwio.register.Register(description = 'Pin AC[9:8] configuration',
                                                                      address     = bitstring.Bits('0x0E'),
                                                                      length      = 16,
                                                                      bitfields   = {'reserved' : hwio.register.Bitfield(bits        = '[15:8]',
                                                                                                                         description = 'reserved',
                                                                                                                         fmt         = 'uint',
                                                                                                                         value       = 0b00000000),

                                                                                     'ac9' : hwio.register.Bitfield(bits        = '[7:4]',
                                                                                                                    description = 'Pin AC9 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'drive_high'  : 0b0111,
                                                                                                                                   'io_mode'     : 0b1000,
                                                                                                                                   'txd_en'      : 0b1001,
                                                                                                                                   'clk_30mhz'   : 0b1010,
                                                                                                                                   'clk_15mhz'   : 0b1011,
                                                                                                                                   'clk_7_5mhz'  : 0b1100},
                                                                                                                    value        = 'tristate_pu'),

                                                                                     'ac8' : hwio.register.Bitfield(bits        = '[3:0]',
                                                                                                                    description = 'Pin AC8 configuration',
                                                                                                                    fmt         = 'uint',
                                                                                                                    values      = {'tristate_pu' : 0b0000,
                                                                                                                                   'tx_led#'     : 0b0001,
                                                                                                                                   'rx_led#'     : 0b0010,
                                                                                                                                   'txrx_led#'   : 0b0011,
                                                                                                                                   'ready#'      : 0b0100,
                                                                                                                                   'suspend#'    : 0b0101,
                                                                                                                                   'drive_low'   : 0b0110,
                                                                                                                                   'drive_high'  : 0b0111,
                                                                                                                                   'io_mode'     : 0b1000,
                                                                                                                                   'txd_en'      : 0b1001,
                                                                                                                                   'clk_30mhz'   : 0b1010,
                                                                                                                                   'clk_15mhz'   : 0b1011,
                                                                                                                                   'clk_7_5mhz'  : 0b1100},
                                                                                                                    value        = 'tristate_pu')})
        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H']:
            self.registers['eeprom_type'] = hwio.register.Register(description = 'EEPROM type',
                                                                   address = bitstring.Bits('0x0F'),
                                                                   length = 16,
                                                                   bitfields = {'eeprom_type' : hwio.register.Bitfield(bits        = '[15:0]',
                                                                                                                       description = 'EEPROM type',
                                                                                                                       fmt         = 'uint',
                                                                                                                       values      = {'x56' : 0x0056,
                                                                                                                                      'x66' : 0x0066},
                                                                                                                       value       = eeprom_type)})

        elif PRODUCT_IDS[self.owner.device.idProduct] in ['FT2232H', 'FT4232H']:
            self.registers['eeprom_type'] = hwio.register.Register(description = 'EEPROM type',
                                                                   address = bitstring.Bits('0x0C'),
                                                                   length = 16,
                                                                   bitfields = {'eeprom_type' : hwio.register.Bitfield(bits        = '[15:0]',
                                                                                                                       description = 'EEPROM type',
                                                                                                                       fmt         = 'uint',
                                                                                                                       values      = {'x56' : 0x0056,
                                                                                                                                      'x66' : 0x0066},
                                                                                                                       value       = eeprom_type)})
        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H']:
            self.registers['vreg_cfg'] = hwio.register.Register(description = 'Chip configuration',
                                                                address     = bitstring.Bits('0x45'),
                                                                length      = 16,
                                                                bitfields   = {'reserved_1'                  : hwio.register.Bitfield(bits        = '[15:7]',
                                                                                                                                      description = 'reserved',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      value       = 0b000000000),

                                                                               'vreg_adjust'                 : hwio.register.Bitfield(bits        = '[6:4]',
                                                                                                                                      description = 'Voltage regulator adjustment',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      values      = {'default' : 0b100},
                                                                                                                                      value       = 'default'),

                                                                               'reserved_0'                  : hwio.register.Bitfield(bits        = '[3:0]',
                                                                                                                                      description = 'reserved',
                                                                                                                                      fmt         = 'uint',
                                                                                                                                      value       = 0b1000)})
        if PRODUCT_IDS[self.owner.device.idProduct] in ['FT232H', 'FT2232H', 'FT4232H']:
            self.registers['eeprom_checksum'] = hwio.register.Register(description = 'EEPROM checksum',
                                                                       address = bitstring.Bits('0x7F'),
                                                                       length = 16,
                                                                       bitfields = {'eeprom_checksum' : hwio.register.Bitfield(bits        = '[15:0]',
                                                                                                                               description = 'EEPROM checksum',
                                                                                                                               fmt         = 'uint',
                                                                                                                               value       = 0x0000)}) # Placeholder value, will be replaced with actual checksum


    def program(self):
        '''Program

        Parameter:
        None

        Return:
        None

        '''

        logger.debug(f'{self.description}, program')

        # Fill EEPROM with 0x0000 (instead of 0xFFFF) as required by FTDI documentation
        data = [0x0000] * self.eeprom_size

        # Convert register values to EEPROM
        for register in self.registers.values():
            for offset, word in enumerate(register.value.cut(16)): # Split long registers into words
                data[register.address.uint + offset] = word.uint

        # Calculate checksum
        checksum = bitstring.BitArray(uint = 0xAAAA, length = 16)

        # for word in data[:-1]: # Skip last word as it's used for checksum
        #     checksum ^= bitstring.BitArray(uint = word, length = 16)
        #     checksum.rol(bits = 1)

        for address in range(0x7F): # Checksum is calculated over the 0x00..0x7E words and is stored in the 0x7F word
            checksum ^= bitstring.BitArray(uint = data[address], length = 16)
            checksum.rol(bits = 1)

        self.registers['eeprom_checksum'].bitfields['eeprom_checksum'].value = checksum.uint

        data[self.registers['eeprom_checksum'].address.uint] = self.registers['eeprom_checksum'].bitfields['eeprom_checksum'].value

        self.owner.eeprom_program(address = 0, data = data)

        logger.debug('OK')

        return None



class LibusbVersion(ctypes.Structure):
    _fields_ = [('major',    ctypes.c_uint16),
                ('minor',    ctypes.c_uint16),
                ('micro',    ctypes.c_uint16),
                ('nano',     ctypes.c_uint16),
                ('rc',       ctypes.c_char_p),
                ('describe', ctypes.c_char_p)]


#===============================================================================
# functions
#===============================================================================
def find_devices():
    '''Find FTDI devices that support MPSSE

    Parameter:
    None

    Return:
    (list) Found devices

    '''

    logger.debug('Find FTDI devices')

    # pyusb version
    logger.debug(f'| pyusb version: {usb.__version__:s}')

    # Use libusb1 as backend
    backend = usb.backend.libusb1.get_backend()

    # libusb version
    backend.lib.libusb_get_version.restype = ctypes.POINTER(LibusbVersion)
    version = backend.lib.libusb_get_version().contents
    logger.debug(f'| libusb version: {version.major:d}.{version.minor:d}.{version.micro:d}')

    # Find relevant FTDI devices that support MPSSE
    devices = [device for device in usb.core.find(find_all = True, backend = backend, idVendor = VENDOR_ID) if device.idProduct in PRODUCT_IDS.keys()]

    logger.debug('OK')

    return devices


#===============================================================================
# main
#===============================================================================
if __name__ != '__main__':
        logger = general.logging.IndentedLogger(logger = logging.getLogger(__name__), extra = {})
