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
                data = bytearray(int(l[9+2*i:2*i+11], 16) for i in range(count))
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

if __name__ == '__main__':
        f = open('test.hex')
        for r in read_ihex(f):
                print r

