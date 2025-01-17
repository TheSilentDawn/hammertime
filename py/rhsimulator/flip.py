from collections import namedtuple
import ctypes
import ujson
import sys,os
import time


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dramtrans import *

time_formatter = lambda x:  time.strftime('%H:%M:%S', time.gmtime(x))

class PageBitFlip(namedtuple('PageBitFlip', ['byte_offset', 'mask'])):
    """Represents a byte with one or more flipped bits at a particular offset within a page"""
    

class VictimPage(namedtuple('VictimPage', ['pfn', 'pullups', 'pulldowns'])):
    """Represents the results of one rowhammer attack on one particular physical page"""


class TSPageFlip(namedtuple('TSPageFlip', ['byte_offset', 'mask',  'pullup', 'ts'])):
    """ Page offset indexed bit flip with timestamp too. This is a horrible implementation
        but so far it's the fastest way to bridge with Andrei's implementation
        We need this class only for statistical analysis in the FliptableEstimator.
    """

class Template():
    def __init__(self, flips, ts):
        self.flips      = flips
        self.ts         = ts
    
    def __repr__(s):
        if len(s.flips) > 1:
            flips_str = "[" + "\n\t\t".join([str(x) for x in s.flips]) + "]"
        else:
            flips_str = f"{s.flips}"
        return f"Template(flips: {flips_str}, ts:{s.ts:>12})"

    @classmethod
    def from_json_entry(cls, entry):
        def get_flips(data, bmask, addr, byte_offset, addr_virt):
            flips = []
            
            pup = ~data & bmask & 0xff
            pdn = data  & bmask & 0xff
            bit = 0
            while pup:
                mask = 1 << bit
                if (pup & mask):
                    flips.append(Flip(addr, bit, True, byte_offset, addr_virt))
                    pup &= ~mask
                bit += 1
            bit = 0
            while pdn:
                mask = 1 << bit
                if (pdn & mask):
                    flips.append(Flip(addr, bit, False, byte_offset, addr_virt))
                    pdn &= ~mask
                bit += 1
            return flips

        addr    = DRAMAddr(**entry['dram_addr'])  
        ts      = entry['observed_at']
        flips   = get_flips(entry['data'], entry['bitmask'], addr, entry['page_offset'], entry['addr'])
        return cls(
                flips    = flips,
                ts       = ts)

    def to_physmem(s):
        return type(s) (
                flips   = list(map(lambda x: x.to_physmem(), s.flips)),
                ts      = s.ts)

    #""" this is required for compatibility with Andrei's framework """ 
    #def to_VictimPage(s, pagesize=0x1000):
    #    pfnof = lambda x: x.addr // pagesize
    #    
    #    pfn = pfnof(s.flips[0].to_physmem()) 
    #    ups     = set([x.to_PageBitFlip(pagesize=pagesize) for x in s.flips if x.pullup])
    #    downs   = set([x.to_PageBitFlip(pagesize=pagesize) for x in s.flips if not x.pullup])
    #    return VictimPage( pfn, ups, downs)

    """ this is required for compatibility with Andrei's framework """ 
    def to_VictimPages(s, pagesize=0x1000):
        pfnof = lambda x: x.addr // pagesize
        
        pfn = pfnof(s.flips[0].to_physmem()) 
        # I return single VictimPages so that I can independently
        # count every bit flip instead of counting the templates
        for flip in s.flips:
            if flip.pullup:
                yield VictimPage(pfn, 
                        set([flip.to_PageBitFlip(pagesize=pagesize)]), 
                        set())
            if not flip.pullup:
                yield VictimPage(pfn, 
                        set(), 
                        set([flip.to_PageBitFlip(pagesize=pagesize)])) 

# Note 'addr' is the DRAMAddr and 'addr_virt' the virtual address
class Flip(namedtuple('Flip', ['addr', 'bit', 'pullup', 'byte_offset', 'addr_virt'])):

    def __repr__(s):
        if isinstance(s.addr, DRAMAddr):
            return  f"Flip( addr: bk{s.addr.bank}.r{s.addr.row}, bit: {s.bit} "\
                    f"pullup: {str(s.pullup):>5})"
        else:
            return  f"Flip( addr: {s.addr:>#12x}, bit: {s.bit} "\
                    f"pullup: {str(s.pullup):>5})"
    
    def __eq__(s, o):
        if isinstance(o, Flip):
            return (s.addr, s.bit, s.pullup) == (o.addr, o.bit, o.pullup) 
    
    def to_physmem(self):
        # return type(self)(self.addr.to_addr(), self.bit, self.pullup, self.byte_offset, self.addr_virt)
        return type(self)(int(self.addr_virt, 16), self.bit, self.pullup, self.byte_offset, self.addr_virt)

    """this is required for compatibility with Andrei's framework""" 
    def to_PageBitFlip(s, pagesize=0x1000):
        byte_off = s.addr.to_addr() % pagesize 
        pflip = PageBitFlip(byte_off, 1<<s.bit)
        return pflip 


class Fliptable():

    
    def __init__(self, dimm_id, templates, mem_layout, t_start, t_end,  pattern, mapping):
        self.dimm_id            = dimm_id 
        self.templates          = templates 
        self.mem_layout         = mem_layout
        self.t_start            = t_start 
        self.t_end              = t_end
        self.pattern            = pattern
        self.mapping             = mapping
    
    @property
    def duration(self):
        return self.t_end - self.t_start

    @classmethod
    def from_sweep(cls, data, metadata, layout_ow=False) :
        
        MemLayout.init_layout(metadata['memory_config'], overwrite=layout_ow)
        
        pattern = data['pattern'] 
        mapping = data['mapping'] 
        dimm_id = metadata['dimm_id']
        templates = [Template.from_json_entry(x) for x in data['flips']['details']]

        return cls(
                dimm_id, 
                templates, 
                MemLayout, 
                metadata['start'], 
                metadata['end'],
                pattern, 
                mapping)


    def __repr__(s):
        return  f"Fliptable(dimm: {s.dimm_id}, tot_templates={len(s.templates)},"\
                f" pattern={s.pattern}, dt={s.t_start - s.t_end})"
