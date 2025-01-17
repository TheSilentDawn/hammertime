#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright (c) 2016 Andrei Tatar
# Copyright (c) 2017-2018 Vrije Universiteit Amsterdam
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import math
import itertools
import functools
from collections import namedtuple, Counter, OrderedDict
import ujson
import sys, os
import pprint as pp
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flip import *

class ExploitModel:
   
    def check_page(self, vpage):
        raise NotImplementedError()
    
    """ WARNING!! 
        `check_temapltes` return a list of TSPageFlip objects
        every TSPageFlip represents a unique exploitable bit flip with timestamp. 
        While the TSPageFlip class is redundant it made implementation of the
        statistical analysis simpler. So we roll with this for now (and probably forever). 
    """
    def check_templates(self, templates):
        for tmpl in templates:
            for vpage in tmpl.to_VictimPages():
                if self.check_page(vpage):
                    pullup = False
                    if vpage.pullups:
                        assert len(vpage.pullups) == 1
                        (flip,) = vpage.pullups # horrible syntax for 1 element set unpacking
                        pullup = True
                    if vpage.pulldowns:
                        assert len(vpage.pulldowns) == 1
                        (flip,) = vpage.pulldowns# horrible syntax for 1 element set unpacking
                    yield TSPageFlip(*flip, pullup=pullup, ts=tmpl.ts) 



"""
    This function returns a list of tuples (x,y) where
    x = time
    y = cumulative number of exploitable flips
"""
def _exploitable_flips_over_time(results, t_start):
    ts_counter = Counter(sorted([flp.ts-t_start for flp in results])) 
    flips_vs_time = []
    flip_cnt = 0
    for ts in ts_counter.keys():
        curr_flips = ts_counter[ts]
        flips_vs_time.append((ts,flip_cnt+curr_flips))
        flip_cnt += curr_flips 
    return flips_vs_time

class BaseEstimator:
    def __init__(self):
        self.clear()

    def run_exploit(self, model):
        self.results = list(model.check_templates(self.ftbl.templates))

    def clear(self):
        self.results = []

    def print_stats(self):
        if not self.results:
            print(f"No vulnerable template in: {time_formatter(self.ftbl.duration)}")
            return
        
        tot_templates       = len(self.ftbl.templates)
        tot_expl_flips      = len(self.results) 
        tot_expl_tmpl       = len(set(self.results)) # results contain  
        tot_flips           = sum(len(x.flips) for x in self.ftbl.templates)
        str_tot_expl_flip   = f"{tot_expl_flips}/{tot_flips} ({tot_expl_flips/tot_flips:.3f})"

        expl_flips_vs_time = _exploitable_flips_over_time(self.results, self.ftbl.t_start)
        ttf = expl_flips_vs_time[0][0] # tuple(ts, sum_flips)[0] == tuple.ts
        # computing mean time to exploitable flip
        # adding a zero as first ts and `duration` as last in order to take into account also time to last
        # exploitable bit flip (this is not super accurate but since the `duration`) does not
        # represent the last exploitable flip bu I don't know how to compute it otherwise
        padded_ts = [0] + [x[0] for x in expl_flips_vs_time] + [self.ftbl.duration] 
        ttf_dists = [abs(v-padded_ts[i-1]) for i,v in enumerate(padded_ts) if i > 0]
        mean_ttf = sum(ttf_dists)/len(ttf_dists)
  
        print(f"{'Total time:':<40} {time_formatter(self.ftbl.duration):>20}")
        print(f"{'Total templates:':<40} {tot_templates:>20}")
        print(f"{'Total flips:':<40} {tot_flips:>20}")
        print(f"{'Total exploitable flips:':<40} {str_tot_expl_flip:>20}")
        print(f"{'Time to first expl flip:':<40} {time_formatter(ttf):>20}")
        print(f"{'Avg time to flip:':<40} {time_formatter(mean_ttf):>20}")


    def get_csv_stats(self, expl_name):
        
        def compute_ttf():
            expl_flips_vs_time = _exploitable_flips_over_time(self.results, self.ftbl.t_start)
            first_ttf = expl_flips_vs_time[0][0] # tuple(ts, sum_flips)[0] == tuple.ts
            # computing mean time to exploitable flip
            # adding a zero as first ts and `duration` as last in order to take into account also time to last
            # exploitable bit flip (this is not super accurate but since the `duration`) does not
            # represent the last exploitable flip bu I don't know how to compute it otherwise
            padded_ts = [0] + [x[0] for x in expl_flips_vs_time] 
            ttf_dists = [abs(v-padded_ts[i-1]) for i,v in enumerate(padded_ts) if i > 0]
            mean_ttf = sum(ttf_dists)/len(ttf_dists)
            return first_ttf, mean_ttf

        #--------------------------------
        # get_csv_stats() body
        
        if not self.results:
            stats_dict = OrderedDict({
                "expl_name":            expl_name,
                "dimm_id":              self.ftbl.dimm_id,
                "duration":             self.ftbl.duration,
                "pattern":              self.ftbl.pattern,
                "mapping":              self.ftbl.mapping,
                "tot_templates":        0, 
                "tot_flips":            0, 
                "tot_expl_flips":       0, 
                "tot_expl_flip_str":    "N/A", 
                "first_ttf":            "N/A", 
                "mean_ttf":             "N/A", 
                "latex_export":         "{:>5} & {:>10} ".format("--", "--"),
                })
            return stats_dict

        first_ttf, mean_ttf = compute_ttf()

        tot_flips =  sum(len(x.flips) for x in self.ftbl.templates)
        tot_expl_flips = len(self.results)
        latex_export_str = "{:>5} & {:>10,d}\,s".format(
                tot_expl_flips, int(mean_ttf)
                ) 
        latex_export_str += "*" if tot_expl_flips == 1 else " "

        stats_dict = OrderedDict({
                "expl_name":            expl_name,
                "dimm_id":              self.ftbl.dimm_id,
                "duration":             self.ftbl.duration,
                "pattern":              self.ftbl.pattern,
                "mapping":              self.ftbl.mapping,
                "tot_templates":        len(self.ftbl.templates), 
                "tot_flips":            tot_flips,
                "tot_expl_flips":       tot_expl_flips,
                "tot_expl_flip_str":    f"{tot_expl_flips}/{tot_flips} ({tot_expl_flips/tot_flips:.3f})",
                "first_ttf":            first_ttf,
                "mean_ttf":             mean_ttf,
                "latex_export":         latex_export_str 
                })
        
        return stats_dict


#    def print_stats(self):
#        if self.results:
#            succ = sum(1 for x in self.results if x)
#            npages = sum(len(x) for x in self.results if x)
#            prop = succ / len(self.results)
#            print('{} total attacks (over {} KiB), of which {} successful ({:5.1f} %)'.format(
#                len(self.results), len(self.results) * 8, succ, 100.0 * prop
#            ))
#            print('{} exploitable pages found'.format(npages))
#            if prop != 0:
#                mna = 1 / prop
#                print('Minimum (contiguous) memory required: {} KiB'.format(math.ceil(mna) * 8))
#                print('Mean number of attacks until successful: {:.1f}'.format(mna))
#                print('Mean time to successful attack: {:.1f} seconds (assuming {:.1f}ms/attack)'.format(mna * self.atk_time * 10**-3, self.atk_time))
#


class FliptableEstimator(BaseEstimator):
    
    def __init__(self, ftbl):
        self.ftbl       = ftbl
        self.results    = []

    @classmethod
    def main(cls, ftbl, model):
        """Set up an estimator, run an exploit and print out statistics"""
        est = cls(ftbl)
        est.run_exploit(model)
        est.print_stats()
        return est
