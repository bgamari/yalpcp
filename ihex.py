#!/usr/bin/python

from collections import namedtuple

DataRec = namedtuple('DataRec', 'addr data')
StartAddrRec = namedtuple('StartAddrRec', 'cs ip')
StartLinearAddrRec = namedtuple('StartLinearAddrRec', 'ip')

def read_ihex(f):
        upper = 0
        for l in f.readlines():
                l = l.strip()
                if not l.startswith(':'):
                        raise RuntimeError('Invalid ihex start code')
                count = int(l[1:3], 16)
                addr = int(l[3:7], 16)
                rectype = int(l[7:9], 16)
                data = bytearray(int(l[9+2*i : 9+2*i+2], 16) for i in range(count))
                csum = int(l[-2:], 16)

                tmp = count + (0xff&addr) + (0xff&(addr>>8)) + rectype + sum(data) + csum
                tmp &= 0xff
                if tmp != 0x00:
                        raise RuntimeError('Invalid checksum')

                if rectype == 0x00:             # data
                        yield DataRec(upper | addr, data)
                elif rectype == 0x01:           # EOF
                        return
                elif rectype == 0x02:           # Extended address
                        if count != 2:
                                raise RuntimeError('Invalid Extended Address record')
                        upper = addr<<4
                elif rectype == 0x03:           # Start address
                        if count != 4 or addr != 0:
                                raise RuntimeError('Invalid Start Address record')
                        cs = data[0] | (data[1]<<8)
                        ip = data[2] | (data[3]<<8)
                        yield StartAddrRec(cs, ip)
                elif rectype == 0x04:           # Extended linear address
                        if count != 2 or addr != 0:
                                raise RuntimeError('Invalid Extended Linear Address record')
                        upper = (data[0] | (data[1]<<8)) << 16
                elif rectype == 0x05:           # Start linear address
                        if count != 4 or addr != 0:
                                raise RuntimeError('Invalid Start Linear Address record')
                        upper = (data[0] | (data[1]<<8)) << 16
                        ip = data[0] | (data[1]<<8) | (data[2])<<16 | (data[3]<<24)
                        yield StartLinearAddrRec(ip)
                else:
                        raise RuntimeError('Unsupported record type 0x%02x' % rectype)

def write_ihex(f, recs):
        def emit_record(addr, rtype, data=[]):
                f.write(':%02X%04X%02X' % (len(data), addr, rtype))
                for d in data: f.write('%02X' % d)
                csum = len(data) + (0xff&addr) + (0xff&(addr>>8)) + rtype + sum(data)
                csum = 0xff & (0x100 - csum)
                f.write('%02X\n' % csum)
                
        upper = 0x0
        for rec in recs:
                addr = 0x0
                rtype = None
                data = []
                if rec.__class__ is DataRec:
                        if rec.addr & 0xffff0000 != upper:
                                # Emit extended linear address record
                                upper = addr & 0xffff0000
                                emit_record(0, 0x04, [upper & 0xff, (upper>>8) & 0xff])
                        addr = rec.addr - upper
                        data = rec.data
                        rtype = 0x00
                elif rec.__class__ is StartAddrRec:
                        rtype = 0x03
                        data = [ rec.cs & 0xff, (rec.cs>>8) & 0xff,
                                 rec.ip & 0xff, (rec.ip>>8) & 0xff ]
                elif rec.__class__ is StartLinearAddrRec:
                        rtype = 0x05
                        data = [ rec.eip & 0xff, (rec.eip>>8) & 0xff,
                                 (rec.eip>>16) & 0xff, (rec.eip>>24) & 0xff ]
                else:
                        raise RuntimeError("Unknown IHEX record type")
                
                emit_record(addr, rtype, data)
		
	emit_record(0x0, 0x1)

if __name__ == '__main__':
        write_ihex(open('test.out', 'w'), read_ihex(open('test.hex')))
        f = open('test.hex')
        for r in read_ihex(f):
                print r

