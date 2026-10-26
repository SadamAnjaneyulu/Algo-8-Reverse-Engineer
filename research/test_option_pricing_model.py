"""Verify pricing parity, inversion, sensitivities and exact attribution accounting."""
import unittest
import option_pricing_model as m


class PricingModelChecks(unittest.TestCase):
    def test_put_call_parity_with_discount(self):
        import math
        c=m.price(24050,24000,.01,.2,'CE',.06)
        p=m.price(24050,24000,.01,.2,'PE',.06)
        self.assertAlmostEqual(c-p,math.exp(-.06*.01)*50,places=8)

    def test_iv_roundtrip_and_invalid_intrinsic_price(self):
        for right in ('CE','PE'):
            p=m.price(24050,24000,.01,.23,right,.06)
            self.assertAlmostEqual(m.implied_vol(p,24050,24000,.01,right,.06),.23,places=8)
        self.assertIsNone(m.implied_vol(10,24100,24000,.01,'CE'))
        self.assertIsNone(m.implied_vol(.01,24000,24000,.01,'CE'))

    def test_symmetric_attribution_reconciles_and_isolates_iv_only_change(self):
        a=m.attribute(24000,.01,.2,24200,.005,.25,24000,'CE')
        self.assertAlmostEqual(sum(a[k] for k in ('movement','time','iv')),a['total'],places=8)
        b=m.attribute(24000,.01,.2,24000,.01,.25,24000,'CE')
        self.assertAlmostEqual(b['movement'],0,places=8)
        self.assertAlmostEqual(b['time'],0,places=8)
        self.assertAlmostEqual(b['iv'],b['total'],places=8)

    def test_sharp_move_can_lose_despite_unchanged_iv_and_positive_decay(self):
        total={k:0. for k in ('movement','time','iv','total')}
        for strike,right,q in [(24000,'CE',-1),(24000,'PE',-1),(26000,'CE',1),(22000,'PE',1)]:
            a=m.attribute(24000,1/365,.2,24240,.25/365,.2,strike,right)
            for k in total:
                total[k]+=q*a[k]
        self.assertLess(total['total'],0)
        self.assertGreater(total['time'],0)
        self.assertAlmostEqual(total['iv'],0,places=8)

    def test_vega_and_gamma_match_small_price_perturbations(self):
        f,k,t,s=24000,24000,.01,.2
        g=m.greeks(f,k,t,s,'CE')
        numeric_vega=(m.price(f,k,t,s+.00001,'CE')-m.price(f,k,t,s-.00001,'CE'))/.00002*.01
        numeric_gamma=m.price(f+1,k,t,s,'CE')-2*m.price(f,k,t,s,'CE')+m.price(f-1,k,t,s,'CE')
        self.assertAlmostEqual(g['vega_one_point'],numeric_vega,places=5)
        self.assertAlmostEqual(g['gamma'],numeric_gamma,places=7)


if __name__=='__main__':
    unittest.main()
