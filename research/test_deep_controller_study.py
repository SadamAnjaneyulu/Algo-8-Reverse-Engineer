import unittest
import numpy as np

from deep_controller_search import packed, crossing_mask, metrics
from deep_allocation_stops import first_above, crossings, choose


class PackedControllerTests(unittest.TestCase):
    def test_packed_intersections_and_tail_bits_match_boolean_scores(self):
        y=np.array([1,0,1,0,0,1,0,0,1],bool)
        a=np.array([1,1,0,0,0,1,0,1,1],bool)
        b=np.array([1,0,0,1,0,1,1,0,0],bool)
        for expected,mask in ((a&b,packed(a)&packed(b)),(a|b,packed(a)|packed(b))):
            self.assertEqual(mask.bit_count(),int(expected.sum()))
            self.assertEqual((mask&packed(y)).bit_count(),int((expected&y).sum()))

    def test_crossings_follow_contract_not_adjacent_interleaved_row(self):
        states=np.array([1,0,1,1,1,1],bool)
        prior=np.array([np.nan,np.nan,0,1,2,3])
        consecutive=np.array([0,0,1,1,0,1],bool)
        # Row 3 crosses for the second contract; row 4 follows a quote gap.
        np.testing.assert_array_equal(crossing_mask(states,prior,consecutive),[0,0,0,1,0,0])

    def test_empty_signals_do_not_create_precision(self):
        self.assertEqual(metrics(0,0,20)['precision'],0)
        self.assertEqual(metrics(0,0,20)['missed'],20)


class AllocationStopTests(unittest.TestCase):
    def test_first_touch_is_first_crossing_and_unreached_is_infinite(self):
        result=first_above(np.array([9.,12.,10.,15.]),np.array([1.,2.,3.,4.]),[10,14,20])
        np.testing.assert_array_equal(result,[2,4,np.inf])

    def test_intrabar_touch_and_completed_close_are_distinct(self):
        atoms=[dict(family='loss_pct',level=10)]
        high=np.array([12.,13.]);close=np.array([9.,12.]);times=np.array([1.,2.])
        self.assertEqual(crossings(high,close,times,10,atoms,'intrabar_bounds')[0],1)
        self.assertEqual(crossings(high,close,times,10,atoms,'completed_close')[0],2)

    def test_training_subset_selection_ignores_later_targets(self):
        matrix=np.array([[np.inf,np.inf,np.inf],[10.,12.,50.],[20.,22.,60.]])
        cases=[dict(target=10.,fallback=100.),dict(target=12.,fallback=100.),dict(target=60.,fallback=100.)]
        left=np.array([1,2]);right=np.array([0,0])
        (selected,lag),count=choose(matrix,cases,np.array([0,1]),left,right)
        self.assertEqual((selected,lag),(0,0))
        self.assertEqual(count,6)
        cases[2]['target']=999999
        self.assertEqual(choose(matrix,cases,np.array([0,1]),left,right)[0],(selected,lag))


if __name__=='__main__':unittest.main()
