#!/usr/bin/python

import sys
import serial
import uu
import argparse

import logging
logging.basicConfig(level=logging.INFO)

sectors = []
for i in range(0, 16):
        base = 0x1000*i
        sectors.append((i, base, base+0xfff))
for i in range(16, 30):
        base = 0x10000 + 0x8000*i
        sectors.append((i, base, base+0x7fff))

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--device', type=str, help='Serial device to which device is connected', default='/dev/ttyUSB0')
parser.add_argument('-f', '--dump-flash', metavar='FILE', type=argparse.FileType('w'), help='Dump FLASH contents to file')
parser.add_argument('-s', '--speed', type=int, help='Crystal frequency in kilohertz', default=12000)
parser.add_argument('-p', '--program', metavar='FILE', type=argparse.FileType('r'), help='Load a program from Intel HEX')
args = parser.parse_args()

s = serial.Serial(args.device, baudrate=115200, xonxoff=True)
s.flush()
s.write('?')
a = s.readline()
if not a.endswith('Synchronized\r\n'):
        raise RuntimeError('Failed to synchronize with device (1)')

s.write('Synchronized\n')
if s.readline() != 'Synchronized\n':
        raise RuntimeError('Failed to synchronize with device (2)')

if s.readline() != 'OK\r\n':
        raise RuntimeError('Failed to synchronize with device (3)')

# Set speed
s.write('%d\r\n' % args.speed)
s.readline() # Discard echo

# Disable echo
s.write('A 0\r\n')
if not s.readline().endswith('0\r\n'):
        raise RuntimeError('Failed to disable echo')

def unlock(code=23130):
        """ Unlock Go and FLASH erase, write commands"""
        s.write('U %d\r\n' % code)
        _check_return_code()

def get_part_id():
        """ Get part ID """
        s.write('J\r\n')
        _check_return_code()
        return int(s.readline())

def get_bl_version():
        """ Get bootloader version """
        s.write('K\r\n')
        _check_return_code()
        minor = int(s.readline())
        major = int(s.readline())
        return (major,minor)

def get_serial():
        """ Get part serial number """
        s.write('N\r\n')
        _check_return_code()
        n = 0
        for i in range(4):
                n += int(s.readline()) * 2**(32*i)
        return n

def _check_return_code():
        return_codes = {
                1: 'Invalid command',
                2: 'Source address error',
                3: 'Destination address error',
                4: 'Source address not mapped',
                5: 'Destination address not mapped',
                6: 'Count error',
                7: 'Invalid sector',
                8: 'Sector not blank',
                9: 'Sector not prepared for write operation',
                10: 'Compare error',
                11: 'Busy',
                12: 'Parameter error',
                13: 'Address error',
                14: 'Address not mapped',
                15: 'Command locked',
                16: 'Invalid code',
                17: 'Invalid baud rate',
                18: 'Invalid stop bit',
                19: 'Code read protection enabled',
        }
        a = s.readline()
        try:
                code = int(a)
        except:
                raise RuntimeError('Invalid return code %s' % a)

        if code == 0:
                return
        elif code in return_codes:
                raise RuntimeError(return_codes[code])
        else:
                raise RuntimeError('Unknown return code %d' % code)

def _compute_checksum(data):
        csum = 0
        for c in data:
                csum += ord(c) & 0xff
        return csum

def read_ram(addr, length):
        s.write('R %u %u\r\n' % (addr, length))
        _check_return_code()

        data = ''
        while True:
                chunk = ''
                nlines = 0
                while (len(chunk)+len(data)) < length and nlines < 20:
                        l = s.readline()
                        encoded = 'begin 666 data\n%s\n`\nend\n' % l.strip()
                        chunk += encoded.decode('uu')
                        nlines += 1
                
                good_csum = int(s.readline())
                if good_csum == _compute_checksum(chunk):
                        s.write('OK\r\n')
                        data += chunk
                else:
                        logging.info('Checksum mismatch during read... retrying')
                        s.write('RESEND\r\n')

                if len(data) == length:
                        return bytearray(data)

def write_ram(addr, data):
        s.write('W %u %d\r\n' % (addr, len(data)))
        _check_return_code()

        i = 0
        while i < len(data):
                chunk = str(data[i:i+20*45])
                lines = chunk.encode('uu').split('\n')[1:-3]
                for l in lines:
                        s.write('%s\r\n' % l)
                
                if i % 20 == 0 or i == len(lines)-1:
                        s.write('%d\r\n' % _compute_checksum(chunk))
                        r = s.readline()
                        if r == 'RESEND\r\n':
                                logging.info('Checksum mismatch during write... retrying')
                                continue
                        elif r != 'OK\r\n':
                                raise RuntimeError('Unknown response during write: %s' % r)

                i += 20*45

def copy_ram_to_flash(ram_addr, flash_addr, length):
        s.write('C %d %d %d\r\n' % (flash_addr, ram_addr, length))
        _check_return_code()

def prepare_sectors(sector_low, sector_high):
        s.write('P %d %d\r\n' % (sector_low, sector_high))
        _check_return_code()

def erase_sectors(sector_low, sector_high):
        s.write('E %d %d\r\n' % (sector_low, sector_high))
        _check_return_code()

def go(address, mode='T'):
        s.write('G %d %s\r\n' % (address, mode))
        _check_return_code()

def rw_test():
        write_ram(0x10000000, b'\x10'*16)
        print read_ram(0x10000000, 16)
        write_ram(0x10000000, b'\x15'*16)
        print read_ram(0x10000000, 16)

logging.info('Found part ID %x' % get_part_id())
logging.info('Found serial number %x' % get_serial())
logging.info('Found bootloader version %s' % str(get_bl_version()))

if args.dump_flash is not None:
        for i in range(0x80):
                sys.stderr.write('Dumping 0x%08x to 0x%08x (%d%%)\r' % (0x1000*i, 0x1000*(i+1)-1, 100*i/0x80))
                sys.stderr.flush()
                args.dump_flash.write(read_ram(0x1000*i, 0x1000))
        sys.stderr.write('\n')

if args.program is not None:
        import ihex
        base = 0x10000200
        max_offset = 0
        for rec in ihex.read_ihex(args.program):
                if rec.__class__ == ihex.DataRec:
                        write_ram(base+rec.addr, rec.data)
                        max_offset = max(max_offset, rec.addr)
                        logging.debug('Wrote %d bytes to %08x' % (len(rec.data), rec.addr))

        if raw_input('Write %08x bytes to FLASH? (y/N)' % max_offset) != 'y':
                sys.exit()

        unlock()
        prepare_sectors(0,0)
        erase_sectors(0,0)
        prepare_sectors(0,0)
        copy_ram_to_flash(base, 0x0000, 4096)

