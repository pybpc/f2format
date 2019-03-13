#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Module for registers

The following approach is used for devices with registers:
- Each device class (e.g. hwio.as3722.AS3722 class) has a dictionary of hwio.register.Register class instances
- Each hwio.register.Register class instance has a dictionary of hwio.register.Bitfield class instances
- Subdevice classes may be defined too and device class instance may instantiate them to represent a subdevice (e.g. hwio.as3722.GPIO class)
- Device and subdevice classes may use two approaches to set a bitfield:
    - Using generic variable names and large if-then-else switch (e.g. hwio.as3722.ADC.__init__())
    - Using actual bitfield names iterate over the dictionary of registers (e.g. hwio.as3722.Fuse.__init__()). Obviously in this case all bitfield names must be different
- Bitfields may be split among several registers. See self.slot_select_values in hwio.as3722.AS3722 class for implementation

Name registers and bitfields with underscores instead of whitespaces as it makes it easier to type-ahead such names in other modules
Make bitfields names self-explanatory (e.g. 'pmbus_part1_rev' instead of 'part1_rev')
If it makes sense name registers and bitfields as in datasheet to avoid confusion
To preserve value of reserved bitfields use read-modify-write for the appropriate register

'''


# Standard modules
import logging

# Third-party modules
import bitstring

# Custom modules
import general.logging


#===============================================================================
# exceptions
#===============================================================================
class RegisterError(Exception):
    '''Custom class for recoverable error handling.'''
    pass


class RegisterCritical(Exception):
    '''Custom class for unrecoverable error handling.'''
    pass


#===============================================================================
# classes
#===============================================================================
class Register:
    def __init__(self, description, address, length, bitfields):
        '''Class initializer

        Parameter:
        'description' : (str)       Description
        'address'     : (bitstring) Address. Shall be 'None' is address is not applicable
        'length'      : (int)       Length in bits
        'bitfields'   : (dict)      A dictionary of 'hwio.register.Bitfield' objects

        Return:
        An instance of class

        '''

        self.description = description
        self.address     = address
        self.length      = length

        # Check if bitfields are sequential (i.e. no gaps, no overlaps)
        if bitfields is not None:
            bits = []
            for bitfield in sorted(bitfields.values(), key=lambda bitfield: bitfield.bit_high, reverse=True):
                bits += list(range(bitfield.bit_high, bitfield.bit_low - 1, -1))

            if bits != list(range(self.length - 1, -1, -1)):
                logger.critical(f'Bitfields gap or overlap in \'{self.description}\' register')
                raise RegisterCritical

        self.bitfields = bitfields

    @property
    def value(self):
        '''Get register value

        Parameter:
        None

        Return:
        (bitstring) Combined register bitfields

        '''

        # Convert bitfields to value
        value = bitstring.BitArray(self.length)

        if self.length != 0: # E.g. some PMBus commands don't have data part
            for bitfield in self.bitfields.values():
                value[self.length - bitfield.bit_high - 1 : self.length - bitfield.bit_low] = bitstring.BitArray(f'{bitfield.fmt}:{bitfield.bit_high - bitfield.bit_low + 1}={bitfield.values[bitfield.value] if bitfield.values is not None else bitfield.value}')

        return value

    @value.setter
    def value(self, value):
        '''Set register value

        Parameter:
        'value' : (bitstring) Combined register bitfields

        Return:
        None

        '''

        if value.length != self.length:
            logger.critical(f'Size mismatch between value and \'{self.description}\' register')
            raise RegisterCritical

        # Convert value to bitfields
        if self.length != 0: # E.g. some PMBus commands don't have data part
            for bitfield in self.bitfields.values():
                bitfield.value = value[self.length - bitfield.bit_high - 1 : self.length - bitfield.bit_low].unpack(f'{bitfield.fmt}:{bitfield.bit_high - bitfield.bit_low + 1}')[0]

                # Replace bitfield.value with a key from bitfield.values if any
                if bitfield.values is not None:
                    bitfield.value = next((item[0] for item in bitfield.values.items() if item[1] == bitfield.value), None)

        return None


    def log(self):
        '''Log register bitfields data in human-readable form

        Parameter:
        None

        Return:
        None

        '''

        if self.address is not None:
            logger.debug(f'Register \'{self.description}\', address: 0x{self.address.hex.upper()}, length: {self.length} bits, value: 0b{self.value.bin}')
        else:
            logger.debug(f'Register \'{self.description}\', length: {self.length} bits, value: 0b{self.value.bin}')

        # Create a list of register bitfields sorted in MSb to LSb order
        if self.bitfields is not None:
            bitfields = sorted(self.bitfields.values(), key=lambda bitfield: bitfield.bit_high, reverse=True)

            bits_width = 0
            value_bin_width = 0
            value_hex_width = 0
            value_int_width = 0
            value_str_width = 0

            for bitfield in bitfields:
                bit_value = bitstring.Bits(f'{bitfield.fmt}:{bitfield.bit_high - bitfield.bit_low + 1}={bitfield.values[bitfield.value] if bitfield.values is not None else bitfield.value}')

                if bits_width < len(bitfield.bits):
                    bits_width = len(bitfield.bits)

                if value_bin_width < len(bit_value.bin):
                    value_bin_width = len(bit_value.bin)

                if value_hex_width < len((bitstring.Bits(4 - len(bit_value) % 4) + bit_value).hex if len(bit_value) % 4 != 0 else bit_value.hex):
                    value_hex_width = len((bitstring.Bits(4 - len(bit_value) % 4) + bit_value).hex if len(bit_value) % 4 != 0 else bit_value.hex)

                if bitfield.fmt == 'uint':
                    if value_int_width < len(str(bit_value.uint)):
                        value_int_width = len(str(bit_value.uint))
                elif bitfield.fmt == 'int':
                    if value_int_width < len(str(bit_value.int)):
                        value_int_width = len(str(bit_value.int))

                if bitfield.values is not None:
                    if value_str_width < len(str(bitfield.value)):
                        value_str_width = len(str(bitfield.value))

            for bitfield in bitfields:
                bit_value = bitstring.Bits(f'{bitfield.fmt}:{bitfield.bit_high - bitfield.bit_low + 1}={bitfield.values[bitfield.value] if bitfield.values is not None else bitfield.value}')
                bits = f'{bitfield.bits:{bits_width}}'
                value_bin = f'0b{bit_value.bin:{value_bin_width}}'
                value_hex = f'0x{(bitstring.Bits(4 - len(bit_value) % 4) + bit_value).hex.upper() if len(bit_value) % 4 != 0 else bit_value.hex.upper():{value_hex_width}}'

                if bitfield.fmt == 'uint':
                    value_int = f'{bit_value.uint:{value_int_width}}'
                elif bitfield.fmt == 'int':
                    value_int = f'{bit_value.int:{value_int_width}}'

                if bitfield.values is not None:
                    value_str = f' {bitfield.value:{value_str_width}}'
                else:
                    value_str = ' ' * (value_str_width + 1)

                if value_str == ' ':
                    value_str = ''

                logger.debug(f'{bits} = {value_bin} {value_hex} {value_int}{value_str} {bitfield.description}')

        return None


#===============================================================================
class Bitfield:
    '''Bitfield class

    '''

    def __init__(self, bits, description, fmt, values=None, value=None):
        '''Class initializer

        Parameter:
        'bits'        : (str) Bit range that is occupied by the bitfield within the register (e.g. '[5]', '[2:0]')
        'description' : (str) Description
        'fmt'         : (str) Format for bitstring conversion:
                                'uint' - unsigned integer
                                'int'  - signed integer
        'values'      : (dict) Allowed values for the bitfield
        'value'       : Default value for the bitfield from 'values' (if it's defined). This variable will be used as source for writes to register and as destination for reads from register

        Return:
        An instance of class

        '''

        self.bits = bits

        # Create a tuple with bit numbers
        tmp = self.bits[1:-1].partition(':')
        self.bit_high = int(tmp[0])
        self.bit_low = int(tmp[0]) if tmp[2] == '' else int(tmp[2])

        self.description = description
        self.fmt = fmt
        self.values = values
        self.value = value


#===============================================================================
# main
#===============================================================================
if __name__ != '__main__':
        logger = general.logging.IndentedLogger(logger=logging.getLogger(__name__), extra={})
