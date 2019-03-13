#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Module for Xilinx FPGAs JTAG communication'''


# Standard modules
import logging
import time

# Third-party modules
import bitstring

# Custom modules
import general.logging
import hwio.register
import hwio.jtag


#===============================================================================
# variables
#===============================================================================
axi_responses = {0b00 : 'OKAY',   # Normal access success. Indicates that a normal access has been successful. Can also indicate an exclusive access has failed
                 0b01 : 'EXOKAY', # Exclusive access okay. Indicates that either the read or write portion of an exclusive access has been successful
                 0b10 : 'SLVERR', # Slave error. Used when the access has reached the slave successfully, but the slave wishes to return an error condition to the originating master
                 0b11 : 'DECERR'} # Decode error. Generated, typically by an interconnect component, to indicate that there is no slave at the transaction address


#===============================================================================
# exceptions
#===============================================================================
class XilinxError(Exception):
    '''Custom class for recoverable error handling'''
    pass


class XilinxCritical(Exception):
    '''Custom class for unrecoverable error handling'''
    pass


#===============================================================================
# classes
#===============================================================================
class XC6SLX(hwio.jtag.JTAGDevice):
    def __init__(self, **kwargs):
        '''Class initializer

        Parameter:
        Inherited from the parent class

        Return:
        An instance of class

        '''

        super().__init__(owner=kwargs['owner'], description=kwargs['description'])

        self.ir_length = 6

        self.dr_lengths = {'bypass'         : 1,
                           'boundary_scan'  : None, # Replace with actual length depending on FPGA package
                           'identification' : 32,
                           'configuration'  : 16,
                           'dna'            : 57}

        self.instructions = {'bypass'            : bitstring.Bits('0b111111'),

                             'sample'            : bitstring.Bits('0b000001'),
                             'preload'           : bitstring.Bits('0b000001'), # Same as SAMPLE instruction
                             'extest'            : bitstring.Bits('0b001111'),
                             'intest'            : bitstring.Bits('0b000111'),
                             'highz'             : bitstring.Bits('0b001010'),

                             'idcode'            : bitstring.Bits('0b001001'),
                             'usercode'          : bitstring.Bits('0b001000'),

                             'cfg_in'            : bitstring.Bits('0b000101'), # Access the configuration bus for configuration. Not available during configuration with another mode
                             'cfg_out'           : bitstring.Bits('0b000100'), # Access the configuration bus for readback. Not available during configuration with another mode

                             'user1'             : bitstring.Bits('0b000010'), # Access user-defined TAP data register 1. Not available until after configuration
                             'user2'             : bitstring.Bits('0b000011'), # Access user-defined TAP data register 2. Not available until after configuration
                             'user3'             : bitstring.Bits('0b011010'), # Access user-defined TAP data register 3. Not available until after configuration
                             'user4'             : bitstring.Bits('0b011011'), # Access user-defined TAP data register 4. Not available until after configuration

                             'jprogram'          : bitstring.Bits('0b001011'), # Equivalent to and has the same effect as toggling the dedicated PROGRAM# pin. Not available during configuration with another mode
                             'jstart'            : bitstring.Bits('0b001100'), # Clocks the startup sequence. Not available during configuration with another mode
                             'jshutdown'         : bitstring.Bits('0b001101'), # Clocks the shutdown sequence. Not available during configuration with another mode

                             'isc_enable'        : bitstring.Bits('0b010000'), # Marks the beginning of ISC configuration. Full shutdown is executed
                             'isc_program'       : bitstring.Bits('0b010001'), # Enables in-system programming
                             'isc_program_key'   : bitstring.Bits('0b010010'), # Program key
                             'isc_address_shift' : bitstring.Bits('0b010011'),
                             'isc_noop'          : bitstring.Bits('0b010100'), # In-system programming 'No Operation' command
                             'isc_read'          : bitstring.Bits('0b010101'), # Used to read back battery-backed RAM
                             'isc_disable'       : bitstring.Bits('0b010110'), # Completes ISC configuration. Startup sequence is executed
                             'isc_dna'           : bitstring.Bits('0b110000'), # Selects the DNA eFUSE registers. Must be preceded by ISC_ENABLE and followed by ISC_DISABLE
                             'isc_fuse_write'    : bitstring.Bits('0b110001'),
                             'isc_ioimisr'       : bitstring.Bits('0b110010'),

                             'fuse_key'          : bitstring.Bits('0b111011'), # Selects the 256-bit FUSE_KEY register
                             'fuse_option'       : bitstring.Bits('0b111100'), # Selects the 16-bit FUSE_OPTION register for data and commands for interfacing with eFUSE
                             'fuse_update'       : bitstring.Bits('0b111010'), # Updates the FPGA with the values from the AES and CNTL eFUSEs
                             'fuse_cntl'         : bitstring.Bits('0b111101')} # Selects the 32-bit FUSE_CNTL register. Dictionary value is from BSDL file. Configuration user guide shows it as 0b110100

        # Signals captured into Instruction Register in Capture-IR TAP state
        self.status_register = hwio.register.Register(description = 'Status',
                                                      address     = None,
                                                      length      = 6,
                                                      bitfields   = {'done'        : hwio.register.Bitfield(bits='[5]',
                                                                                                            description='DONE state',
                                                                                                            fmt='uint',
                                                                                                            values={'no'  : 0,
                                                                                                                    'yes' : 1}), # 1 when DONE is released as a part of startup sequence
                                                                     'init'        : hwio.register.Bitfield(bits='[4]',
                                                                                                            description='INIT complete state',
                                                                                                            fmt='uint',
                                                                                                            values={'no'  : 0,
                                                                                                                    'yes' : 1}), # 1 if initialization is complete (e.g. FPGAs configuration memory is cleared)
                                                                     'isc_enabled' : hwio.register.Bitfield(bits='[3]',
                                                                                                            description='ISC_ENABLED state',
                                                                                                            fmt='uint',
                                                                                                            values={'no'  : 0,
                                                                                                                    'yes' : 1}),
                                                                     'isc_done'    : hwio.register.Bitfield(bits='[2]',
                                                                                                            description='ISC_DONE state',
                                                                                                            fmt='uint',
                                                                                                            values={'no'  : 0,
                                                                                                                    'yes' : 1}),
                                                                     'reserved'    : hwio.register.Bitfield(bits='[1:0]',
                                                                                                            description='reserved',
                                                                                                            fmt='uint',
                                                                                                            value=0b01)})

        self.spi_buffer_size = self.owner.jtag_buffer_size

        # Placeholders
        self.idcode = None # (int)
        # self.write_register = None # (object) Instance of hwio.register.Register to get write data from
        # self.read_register  = None # (object) Instance of hwio.register.Register to set read data to

        self.axi_address_width = None # (int)
        self.axi_data_width    = None # (int)


    def status(self):
        '''Read FPGA configuration status from Instruction Register

        Parameter:
        None

        Return:
        (bitstring) Status bits

        '''

        logger.debug(f'{self.description}, status')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write BYPASS instruction and advance TAP to Exit1-IR state
        data = self.ir_before + self.instructions['bypass'] + self.ir_after
        length = self.ir_before.length + self.ir_length + self.ir_after.length
        data_r = self.owner.jtag_shift(data=data, length=length, tms=bitstring.Bits('0b1'))
        value = data_r[self.ir_before.length:self.ir_before.length + self.ir_length]

        self.status_register.value = value
        self.status_register.log()

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        logger.debug('OK')

        return None


    def identify(self):
        '''Retrieve identification register value

        Parameter:
        None

        Return:
        (bitstring) IDCODE value

        '''

        logger.debug(f'{self.description}, identify')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write IDCODE instruction and advance TAP to Exit1-IR state
        data = self.ir_before + self.instructions['idcode'] + self.ir_after
        self.owner.jtag_shift(data=data, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Read IDCODE Data Register and advance TAP to Shift-DR state
        length = self.dr_before.length + self.dr_lengths['identification'] + self.dr_after.length
        data_r = self.owner.jtag_shift(data=None, length=length, tms=bitstring.Bits('0b1'))

        self.idcode = data_r[self.dr_before.length:self.dr_before.length + self.dr_lengths['identification']].uint

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        logger.debug(f'OK, IDCODE: 0x{self.idcode:08X}')

        return None


    def configure(self, bitstream):
        '''Configure FPGA with selected bitstream

        Parameter:
        'bitstream' : (bitstring) FPGA configuration bitstream

        Return:
        None

        '''

        logger.debug(f'{self.description}, configure')

        start_time = time.time()

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write JPROGRAM instruction and advance TAP to Exit1-IR state
        logger.debug('| Reset')
        data = self.ir_before + self.instructions['jprogram'] + self.ir_after
        self.owner.jtag_shift(data=data, length=None, tms=bitstring.Bits('0b1'))

        # Poll INIT bit in the status register to determine if initialization is complete
        for attempt in range(10000):
            # Advance TAP to Shift-IR state
            self.owner.jtag_advance(tms=bitstring.Bits('0b00111'))

            # JPROGRAM instruction must be followed by CFG_IN instruction in order for JTAG to preserve control over the configuration process
            # Write CFG_IN instruction and advance TAP to Exit1-IR state
            data = self.ir_before + self.instructions['cfg_in'] + self.ir_after
            length = self.ir_before.length + self.ir_length + self.ir_after.length
            data_r = self.owner.jtag_shift(data=data, length=length, tms=bitstring.Bits('0b1'))
            value = data_r[self.ir_before.length:self.ir_before.length + self.ir_length]

            self.status_register.value = value
            # logger.debug(f'| Status register: 0b{value.bin}')

            # Strict status check:
            # DONE, ISC_ENABLED, ISC_DONE bits are expected to be 0b0
            # INIT bit is expected to be either 0b0 or 0b1
            # Reserved bits are expected to be 0b01
            if self.status_register.value not in [bitstring.Bits('0b000001'), bitstring.Bits('0b010001')]:
                logger.error(f'| FAIL: Wrong status register value: expected: 0b000001 or 0b010001, actual: 0b{self.status_register.value.bin}')
                self.status_register.log()
                raise XilinxError

            # # DONE bit is expected be 0 here
            # if self.status_register.bitfields['done'].value != 'no':
            #     logger.error(f'| FAIL: Unexpected DONE state: {self.status_register.bitfields["done"].value}')
            #     raise XilinxError

            if self.status_register.bitfields['init'].value == 'yes':
                break
        else:
            logger.error('| FAIL: Timeout occurred during INIT polling')
            raise XilinxError

        # Advance TAP to Shift-DR state (this works if there is only one device in chain)
        # self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Advance TAP to Shift-DR state through Run-Test/Idle state. According to Xilinx documentation it's needed if there is more than one device in chain
        self.owner.jtag_advance(tms=bitstring.Bits('0b00101'))

        # Write FPGA configuration bitstream and advance TAP to Exit1-DR state in the end
        bitstream_tmp = self.dr_before + bitstream + self.dr_after
        logger.debug('| Send bitstream')
        # chunk_size = self.owner.jtag_buffer_size * 8
        chunk_size = 1023 # Length in bits. It seems Xilinx Spartan-6 configuration logic has troubles handling very long vectors. This value was found experimentally while configuring several FPGAs in a chain
        for pos_end in range(bitstream_tmp.length, 0, -chunk_size): # Split bitstream into vectors starting from the end of the bitstring as bits shall be shifted out LSb first
            pos_start = max(pos_end - chunk_size, 0)
            # logger.debug(f'| Chunk: {pos_start}...{pos_end} bits')
            self.owner.jtag_shift(data=bitstream_tmp[pos_start:pos_end], length=None, tms=bitstring.Bits('0b0' if pos_start != 0 else '0b1'))

        # Advance TAP to Shift-IR state through Run-Test/Idle state
        self.owner.jtag_advance(tms=bitstring.Bits('0b001101'))

        # Write JSTART instruction and advance TAP to Exit1-IR state
        logger.debug('| Startup sequence')
        data = self.ir_before + self.instructions['jstart'] + self.ir_after
        self.owner.jtag_shift(data=data, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Run-Test/Idle state and stay there for 16 TCK clocks (startup sequence)
        # Startup sequence lasts a minimum of eight CCLK cycles. DONE pin goes high during startup sequence. Additional CCLKs can be required to complete the startup sequence
        self.owner.jtag_advance(tms=bitstring.Bits('16*0b0, 0b01'))

        # Advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Check if configuration is done

        # Write BYPASS instruction, read status register and advance TAP to Exit1-IR state
        data = self.ir_before + self.instructions['bypass'] + self.ir_after
        length = self.ir_before.length + self.ir_length + self.ir_after.length
        data_r = self.owner.jtag_shift(data=data, length=length, tms=bitstring.Bits('0b1'))
        value = data_r[self.ir_before.length:self.ir_before.length + self.ir_length]

        self.status_register.value = value
        # logger.debug(f'| Status register: 0b{value.bin}')

        # Strict status check:
        # DONE, INIT, ISC_DONE bits are expected to be 0b1
        # ISC_ENABLED bit is expected to be 0b0
        # Reserved bits are expected to be 0b01
        if self.status_register.value != bitstring.Bits('0b110101'):
            logger.error(f'| FAIL: Wrong status register value: expected: 0b110101, actual: 0b{self.status_register.value.bin}')
            self.status_register.log()
            raise XilinxError

        # # INIT bit is expected be 1 here
        # if self.status_register.bitfields['init'].value != 'yes':
        #     logger.error(f'| FAIL: Unexpected INIT state: {self.status_register.bitfields["init"].value}')
        #     raise XilinxError

        # # DONE bit is expected be 1 here
        # if self.status_register.bitfields['done'].value != 'yes':
        #     logger.error(f'| FAIL: Unexpected DONE state: {self.status_register.bitfields["done"].value}')
        #     raise XilinxError

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        end_time = time.time()

        logger.debug(f'OK, {end_time - start_time:.1f} s')

        return None


    def reset(self):
        '''Reset FPGA

        This is equivalent to toggling PROGRAM# pin
        JPROGRAM instruction is sent followed by INIT and DONE bits polling in the status register using BYPASS instruction

        This method is used when we need to reconfigure FPGA from the attached SPI flash

        Parameter:
        None

        Return:
        None

        '''

        logger.debug(f'{self.description}, reset')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write JPROGRAM instruction and advance TAP to Exit1-IR state
        data = self.ir_before + self.instructions['jprogram'] + self.ir_after
        self.owner.jtag_shift(data=data, length=None, tms=bitstring.Bits('0b1'))

        # Poll INIT and DONE bits in the status register to determine if configuration is complete
        for attempt in range(1000000): # 10000, Sometimes DONE bit takes longer to get set (dependency on SPI width and PLL lock?)
            # Advance TAP to Shift-IR state
            self.owner.jtag_advance(tms=bitstring.Bits('0b00111'))

            # Write BYPASS instruction and advance TAP to Exit1-IR state
            data = self.ir_before + self.instructions['bypass'] + self.ir_after
            length = self.ir_before.length + self.ir_length + self.ir_after.length
            data_r = self.owner.jtag_shift(data=data, length=length, tms=bitstring.Bits('0b1'))
            value = data_r[self.ir_before.length:self.ir_before.length + self.ir_length]

            self.status_register.value = value
            # self.status_register.log()

            if self.status_register.bitfields['init'].value == 'yes' and self.status_register.bitfields['done'].value == 'yes':
                break
        else:
            logger.error('| FAIL: Timeout occurred during INIT and DONE polling')
            raise XilinxError

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        logger.debug('OK')

        return None


    def spi_write(self, data):
        '''Write data to SPI device

        FPGA shall be configured with an appropriate bitstream that implements JTAG-to-SPI bridge using Xilinx BSCAN_SPARTAN6 primitive
        Xilinx USER1 instruction is used to activate this bridge
        Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

        Parameter:
        'data' : (list) Bytes to write

        Return:
        None

        '''

        # logger.debug(f'SPI write, {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write USER1 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user1'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Prepare data
        data_w = bitstring.BitArray(bytes=bytes(data))
        data_w.reverse() # SPI flash expects MSb first
        data_w.append('0b1') # Fist bit to be shifted out shall be one. This is needed to activate SPI SS# in JTAG-to-SPI bridge as there might be zeros before it that get loaded into bypass registers of other TAPs
        data_w.prepend('0b0') # Last bit to be shifted out (dummy bit) is needed in order to shift in the last bit from TDO as BSCAN_SPARTAN6 updates TDO on falling edge (see JTAG-to-SPI bridge FPGA design for details)
        data_w.prepend(self.dr_before)

        # Shift data through JTAG-to-SPI bridge and advance TAP to Exit-DR state
        self.owner.jtag_shift(data=data_w, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        # logger.debug('OK')

        return None


    def spi_read(self, length):
        '''Read data from SPI device

        FPGA shall be configured with an appropriate bitstream that implements JTAG-to-SPI bridge using Xilinx BSCAN_SPARTAN6 primitive
        Xilinx USER1 instruction is used to activate this bridge
        Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

        Parameter:
        'length' : (int) Number of bytes to read

        Return:
        (list) Read bytes

        '''

        # logger.debug(f'SPI read, {length:d} bytes')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write USER1 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user1'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Prepare data
        data_w = bitstring.BitArray(length * 8) # Dummy zero bits for data read
        data_w.append('0b1') # Fist bit to be shifted out shall be one. This is needed to activate SPI SS# in JTAG-to-SPI bridge as there might be zeros before it that get loaded into bypass registers of other TAPs
        data_w.prepend('0b0') # Last bit to be shifted out (dummy bit) is needed in order to shift in the last bit from TDO as BSCAN_SPARTAN6 updates TDO on falling edge (see JTAG-to-SPI bridge FPGA design for details)
        data_w.prepend(self.dr_before)
        data_w.prepend(self.dr_after)

        # Shift data through JTAG-to-SPI bridge and advance TAP to Exit-DR state
        data_r = self.owner.jtag_shift(data=data_w, length=data_w.length, tms=bitstring.Bits('0b1'))

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        data_r = data_r[:length * 8]

        data_r.reverse()

        data_r = list(data_r.bytes)

        # logger.debug(f'OK, {len(data_r):d} bytes: [{", ".join([f"0x{item:02X}" for item in data_r])}]')

        return data_r


    def spi_write_read(self, data, length):
        '''Write data to SPI device then read data from SPI device

        FPGA shall be configured with an appropriate bitstream that implements JTAG-to-SPI bridge using Xilinx BSCAN_SPARTAN6 primitive
        Xilinx USER1 instruction is used to activate this bridge
        Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

        Parameter:
        'data'    : (list) Bytes to write
        'length'  : (int)  Number of bytes to read

        Return:
        (list) Read bytes

        '''

        # logger.debug(f'SPI write then read, {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write USER1 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user1'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Prepare data
        data_w = bitstring.BitArray(bytes=bytes(data))
        data_w.reverse() # SPI flash expects MSb first
        data_w.prepend(bitstring.BitArray(length * 8)) # Dummy zero bits for data read
        data_w.append('0b1') # Fist bit to be shifted out shall be one. This is needed to activate SPI SS# in JTAG-to-SPI bridge as there might be zeros before it that get loaded into bypass registers of other TAPs
        data_w.prepend('0b0') # Last bit to be shifted out (dummy bit) is needed in order to shift in the last bit from TDO as BSCAN_SPARTAN6 updates TDO on falling edge (see JTAG-to-SPI bridge FPGA design for details)
        data_w.prepend(self.dr_before)
        data_w.prepend(self.dr_after)

        # Shift data through JTAG-to-SPI bridge and advance TAP to Exit-DR state
        data_r = self.owner.jtag_shift(data=data_w, length=data_w.length, tms=bitstring.Bits('0b1'))
        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        data_r = data_r[:length * 8]

        data_r.reverse()

        data_r = list(data_r.bytes)

        # logger.debug(f'OK, {len(data_r):d} bytes: [{", ".join([f"0x{item:02X}" for item in data_r])}]')

        return data_r


    # def spi_exchange(self, data):
    #     '''Shifts data through SPI

    #     FPGA shall be configured with an appropriate bitstream that implements JTAG-to-SPI bridge using Xilinx BSCAN_SPARTAN6 primitive
    #     Xilinx USER1 instruction is used to activate this bridge
    #     Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

    #     Parameter:
    #     data : (list) Bytes to shift out, MSb first

    #     Return:
    #     (list) Bytes shifted in

    #     '''

    #     logger.debug(f'{self.description}, SPI exchange, {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

    #     # Reset TAP and advance TAP to Shift-IR state
    #     self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

    #     # Write USER1 instruction and advance TAP to Exit1-IR state
    #     self.owner.jtag_shift(data=self.ir_before + self.instructions['user1'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

    #     # Advance TAP to Shift-DR state
    #     self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

    #     # Prepare data
    #     data_w = bitstring.BitArray(bytes=bytes(data))
    #     data_w.reverse() # SPI flash expects MSb first
    #     length = data_w.length
    #     data_w.append('0b1') # Fist bit to be shifted out shall be one. This is needed to activate SPI SS# in JTAG-to-SPI bridge as there might be zeros before it that get loaded into bypass registers of other TAPs
    #     data_w.prepend('0b0') # Last bit to be shifted out (dummy bit) is needed in order to shift in the last bit from TDO as BSCAN_SPARTAN6 updates TDO on falling edge (see JTAG-to-SPI bridge FPGA design for details)

    #     # TODO: check this
    #     # Shift data through JTAG-to-SPI bridge and advance TAP to Exit-DR state
    #     # data_r = self.owner.jtag_shift(data=self.dr_before + data_w + self.dr_after, length=self.dr_before.length + data_w.length + self.dr_after.length, tms=bitstring.Bits('0b1'))
    #     # data_r = self.owner.jtag_shift(data=self.dr_after + data_w + self.dr_before, length=self.dr_after.length + data_w.length  + self.dr_before.length, tms=bitstring.Bits('0b1'))
    #     data_r = self.owner.jtag_shift(data=self.dr_before + data_w, length=self.dr_before.length + data_w.length, tms=bitstring.Bits('0b1'))
    #     # data_r = self.owner.jtag_shift(data=data_w, length=data_w.length, tms=bitstring.Bits('0b1'))

    #     # Advance TAP to Test-Logic-Reset state
    #     self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

    #     # data_r = data_r[self.dr_before.length : self.dr_before.length + data_w.length - 1 - 1] # Remove appended and prepend bits
    #     # data_r = data_r[self.dr_before.length: -self.dr_after.length*2-2] # Remove appended and prepend bits
    #     # data_r = data_r[self.dr_before.length : -self.dr_after.length-2]
    #     data_r = data_r[0 : length]

    #     data_r.reverse()

    #     data_r = list(data_r.bytes)

    #     logger.debug(f'OK, {len(data_r):d} bytes: [{", ".join([f"0x{item:02X}" for item in data_r])}]')

    #     return data_r

    # TODO: Extend axi_write() and axi_read() to handle for more than (axi_address_width // 8) bytes

    def axi_write(self, address, data):
        '''Write data to AXI slave

        FPGA shall be configured with an appropriate bitstream that implements JTAG-to-AXI bridge using Xilinx BSCAN_SPARTAN6 primitives
        Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

        Xilinx USER2 JTAG instruction is used for AXI address
        Xilinx USER3 JTAG instruction is used for AXI write data

        AXI BRESP and BVALID signals readback is implemented in order to make sure transaction has successfully finished

        Parameter:
        'address' : (int)  AXI slave address
        'data'    : (list) Bytes to write

        Return:
        None

        '''

        logger.debug(f'AXI write, address: 0x{address:0{self.axi_address_width // 4 + (1 if self.axi_address_width % 4 != 0 else 0)}X}, {len(data):d} bytes: [{", ".join([f"0x{item:02X}" for item in data])}]')

        if len(data) % (self.axi_data_width // 8) != 0:
            logger.critical(f'FAIL: AXI write data length ({len(data):d} bytes) is not multiple of AXI data bus width ({self.axi_data_width:d} bits)')
            raise XilinxCritical

        #--------------------------------------------------
        # Address register (Xilinx USER2 JTAG instruction)

        # Advance TAP to Test-Logic-Reset state and then to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write USER2 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user2'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Write USER2 data and advance TAP to Exit1-DR state
        self.owner.jtag_shift(data=self.dr_before + bitstring.Bits(uint=address, length=self.axi_address_width) + self.dr_after, length=None, tms=bitstring.Bits('0b1'))

        #--------------------------------------------------
        # Write data register (Xilinx USER3 JTAG instruction)

        # Advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00111'))

        # Write USER3 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user3'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Write USER3 data and advance TAP to Exit1-DR state
        self.owner.jtag_shift(data=self.dr_before + bitstring.Bits(bytes=bytes(list(reversed(data)))) + self.dr_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state through Run-Test/Idle state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00101')) # When TAP is in Run-Test/Idle state AXI write transaction is initiated

        # Read out status with timeout
        for attempt in range(100):
            # Read AXI transaction status and advance TAP to Exit-DR state
            data_r = self.owner.jtag_shift(data=None, length=self.dr_before.length + 3 + self.dr_after.length, tms=bitstring.Bits('0b1'))

            axi_bresp  = data_r[self.dr_before.length : self.dr_before.length + 2]
            axi_bvalid = data_r[self.dr_before.length + 2 : self.dr_before.length + 2 + 1]

            # logger.debug(f'| Status: BRESP[1:0] = 0b{axi_bresp.bin} (\'{axi_responses[axi_bresp.uint]}\'), BVALID = 0b{axi_bvalid.bin}')

            if axi_bvalid == bitstring.Bits('0b1'): # AXI BVALID = 1
                # Advance TAP to Test-Logic-Reset state
                self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))
                break

            # Advance TAP to Shift-DR state
            self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        else:
            # Advance TAP to Test-Logic-Reset state
            self.owner.jtag_advance(tms=bitstring.Bits('0b11111'))

            logger.error(f'FAIL: AXI write transaction timeout: BVALID = 0b{axi_bvalid.bin}')
            raise XilinxError

        if axi_responses[axi_bresp.uint] != 'OKAY': # AXI BRESP[1:0] = OKAY
            logger.error(f'FAIL: AXI write transaction error: BRESP[1:0] = 0b{axi_bresp.bin} (\'{axi_responses[axi_bresp.uint]}\')')
            raise XilinxError

        logger.debug('OK')

        return None


    def axi_read(self, address, length):
        '''Read data from AXI slave

        FPGA shall be configured with an appropriate bitstream that implements JTAG-to-AXI bridge using Xilinx BSCAN_SPARTAN6 primitives
        Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

        Xilinx USER2 JTAG instruction is used for AXI address
        Xilinx USER4 JTAG instruction is used for AXI read data

        AXI RRESP and RVALID signals readback is implemented in order to make sure transaction has successfully finished

        Parameter:
        'address' : (int) AXI slave address
        'length'  : (int) Number of bytes to read

        Return:
        (list) Read bytes

        '''

        logger.debug(f'AXI read, address: 0x{address:0{self.axi_address_width // 4 + (1 if self.axi_address_width % 4 != 0 else 0)}X}, {length:d} bytes')

        if length % (self.axi_data_width // 8) != 0:
            logger.critical(f'FAIL: AXI read data length ({length:d} bytes) is not multiple of AXI data bus width ({self.axi_data_width:d} bits)')
            raise XilinxCritical

        #--------------------------------------------------
        # Address register (Xilinx USER2 JTAG instruction)

        # Advance TAP to Test-Logic-Reset state and then to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write USER2 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user2'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Write USER2 data and advance TAP to Exit1-DR state
        self.owner.jtag_shift(data=self.dr_before + bitstring.Bits(uint=address, length=self.axi_address_width) + self.dr_after, length=None, tms=bitstring.Bits('0b1'))

        #--------------------------------------------------
        # Read data register (Xilinx USER4 JTAG instruction)

        # Advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00111'))

        # Write USER4 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user4'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state through Run-Test/Idle state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00101')) # When TAP is in Run-Test/Idle state AXI read transaction is initiated

        # Read out data status with timeout
        for attempt in range(100):
            # Read AXI transaction data and status and advance TAP to Exit-DR state
            data_r = self.owner.jtag_shift(data=None, length=self.dr_before.length + self.axi_data_width + 3 + self.dr_after.length, tms=bitstring.Bits('0b1'))

            data   = list(reversed(list(data_r[self.dr_before.length : self.dr_before.length + self.axi_data_width].bytes)))

            axi_rresp  = data_r[self.dr_before.length + self.axi_data_width : self.dr_before.length + self.axi_data_width + 2]
            axi_rvalid = data_r[self.dr_before.length + self.axi_data_width + 2 : self.dr_before.length + self.axi_data_width + 2 + 1]

            # logger.debug(f'| Status: RRESP[1:0] = 0b{axi_rresp.bin} (\'{axi_responses[axi_rresp.uint]}\'), RVALID = 0b{axi_rvalid.bin}')

            if axi_rvalid == bitstring.Bits('0b1'): # AXI RVALID = 1
                # Advance TAP to Test-Logic-Reset state
                self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))
                break

            # Advance TAP to Shift-DR state
            self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        else:
            # Advance TAP to Test-Logic-Reset state
            self.owner.jtag_advance(tms=bitstring.Bits('0b11111'))

            logger.error(f'FAIL: AXI read transaction timeout: RVALID = 0b{axi_rvalid.bin}')
            raise XilinxError

        if axi_responses[axi_rresp.uint] != 'OKAY': # AXI RRESP[1:0] = OKAY
            logger.error(f'FAIL: AXI read transaction error: RRESP[1:0] = 0b{axi_rresp.bin} (\'{axi_responses[axi_rresp.uint]}\')')
            raise XilinxError

        logger.debug(f'OK: [{", ".join([f"0x{item:02X}" for item in data])}]')

        return data


    # def exchange(self):
    #     '''Write data to user write register and read data from user read register

    #     FPGA shall be configured with an appropriate bitstream that implements 'jtag_register_exchange' module using Xilinx BSCAN_SPARTAN6 primitive
    #     Xilinx USER2 instruction is used

    #     Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

    #     Parameter:
    #     None

    #     Return:
    #     None

    #     '''

    #     # logger.debug('{description}, register exchange')

    #     # Reset TAP and advance TAP to Shift-IR state
    #     self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

    #     # Write USER2 instruction and advance TAP to Exit1-IR state
    #     self.owner.jtag_shift(data=self.ir_before + self.instructions['user2'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

    #     # Advance TAP to Shift-DR state
    #     self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

    #     # Shift data through and advance TAP to Exit-DR state
    #     data_r = self.owner.jtag_shift(data=self.dr_before + self.exchange_register.value + self.dr_after, length=self.dr_before.length + self.exchange_register.length + self.dr_after.length, tms=bitstring.Bits('0b1'))

    #     # Advance TAP to Test-Logic-Reset state
    #     self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

    #     data_r = data_r[self.dr_before.length : self.dr_before.length + self.exchange_register.length]

    #     self.exchange_register.value = data_r

    #     # logger.debug('OK')

    #     return None


    def write(self):
        '''Write data to user write register

        FPGA shall be configured with an appropriate bitstream that implements 'jtag_register_write' module using Xilinx BSCAN_SPARTAN6 primitive
        Xilinx USER3 instruction is used

        Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

        Parameter:
        None

        Return:
        None

        '''

        # logger.debug('{description}, register write')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write USER3 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user3'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Shift data through and advance TAP to Exit-DR state
        self.owner.jtag_shift(data=self.dr_before + self.write_register.value + self.dr_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        # logger.debug('OK')

        return None


    def read(self):
        '''Read data from user read register

        FPGA shall be configured with an appropriate bitstream that implements 'jtag_register_read' module using Xilinx BSCAN_SPARTAN6 primitive
        Xilinx USER4 instruction is used

        Other TAPs in JTAG chain are put in bypass and their bypass registers are loaded with zeros

        Parameter:
        None

        Return:
        None

        '''

        # logger.debug('{description}, register read')

        # Reset TAP and advance TAP to Shift-IR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b00110, 0b11111'))

        # Write USER4 instruction and advance TAP to Exit1-IR state
        self.owner.jtag_shift(data=self.ir_before + self.instructions['user4'] + self.ir_after, length=None, tms=bitstring.Bits('0b1'))

        # Advance TAP to Shift-DR state
        self.owner.jtag_advance(tms=bitstring.Bits('0b0011'))

        # Shift data through and advance TAP to Exit-DR state
        data_r = self.owner.jtag_shift(data=None, length=self.dr_before.length + self.read_register.length + self.dr_after.length, tms=bitstring.Bits('0b1'))

        # Advance TAP to Test-Logic-Reset state
        self.owner.jtag_advance(tms=bitstring.Bits('0b1111'))

        self.read_register.value = data_r[self.dr_before.length : self.dr_before.length + self.read_register.length]

        # logger.debug('OK')

        return None


#===============================================================================
# functions
#===============================================================================
def parse_bit_file(path):
    '''Parse Xilinx BIT file

    Parameter:
    'path' : (str) Path to BIT file

    Return:
    (bitstring) FPGA configuration bitstream


    Xilinx BIT file format

    Length, bytes Name        Value         Comment
    2             length      0x0009        big endian
    9                                       some sort of header
    2             length      0x0001        Length of key 'a' (?)
    These 13 bytes are: 0x00, 0x09, 0x0F, 0xF0, 0x0F, 0xF0, 0x0F, 0xF0, 0x0F, 0xF0, 0x00, 0x00, 0x01

    1             key         0x61          Letter 'a'
    2             length      0x000A        Value depends on file name length
    10            design name 'xform.ncd'   Including a trailing 0x00

    1             key         0x62          Letter 'b'
    2             length      0x000C        Value depends on part name length
    12            part name   'v1000efg860' Including a trailing 0x00

    1             key         0x63          Letter 'c'
    2             length      0x000B
    11            date        '2001/08/10'  Including a trailing 0x00

    1             key         0x64          Letter 'd'
    2             length      0x0009
    9             time        '06:55:04'    Including a trailing 0x00

    1             key         0x65          Letter 'e'
    4             length      0x000C9090    Value depends on device type and maybe design details
    823440        bitstream                 Starts with 0xffffffff aa995566 sync word

    '''

    logger.debug(f'Parse Xilinx BIT file: \'{path}\'')

    data = bitstring.BitStream(filename=path)
    # print(data)

    data.bytepos += 13 # Skip header

    a_key    = data.read(8).bytes.decode('utf-8')
    a_length = data.read(8*2).uint
    a_value  = data.read(8*a_length).bytes[:-1].decode('utf-8') # Skip trailing 0x00
    # print(a_key, a_length, a_value)
    bitstream_design = a_value

    b_key    = data.read(8).bytes.decode('utf-8')
    b_length = data.read(8*2).uint
    b_value  = data.read(8*b_length).bytes[:-1].decode('utf-8') # Skip trailing 0x00
    # print(b_key, b_length, b_value)
    bitstream_part = b_value

    c_key    = data.read(8).bytes.decode('utf-8')
    c_length = data.read(8*2).uint
    c_value  = data.read(8*c_length).bytes[:-1].decode('utf-8') # Skip trailing 0x00
    # print(c_key, c_length, c_value)
    bitstream_date = c_value

    d_key    = data.read(8).bytes.decode('utf-8')
    d_length = data.read(8*2).uint
    d_value  = data.read(8*d_length).bytes[:-1].decode('utf-8') # Skip trailing 0x00
    # print(d_key, d_length, d_value)
    bitstream_time = d_value

    e_key    = data.read(8).bytes.decode('utf-8')
    e_length = data.read(8*4).uint
    e_value  = data.read(8*e_length)
    # print(e_key, e_length, e_value.hex)
    bitstream = e_value
    bitstream.reverse() # Need to reverse bit vector as FPGA configuration register is MSb first, which is different from other registers that are LSb first

    logger.debug(f'OK, name: \'{bitstream_design}\', part: \'{bitstream_part}\', date: \'{bitstream_date}\', time: \'{bitstream_time}\', length: {len(bitstream)} bits')

    return bitstream


#===============================================================================
# main
#===============================================================================
if __name__ != '__main__':
        logger = general.logging.IndentedLogger(logger=logging.getLogger(__name__), extra={})
