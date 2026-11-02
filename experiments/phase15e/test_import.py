import unittest,tempfile
from pathlib import Path
from import_boundary import import_boundary,clip
class BoundaryImportTests(unittest.TestCase):
 def test_open_oneway_with_ramp_survives_without_an_scc_and_keeps_lanes(self):
  xml='''<osm><node id="1" lat="0" lon="-2"/><node id="2" lat="0" lon="0"/><node id="3" lat="0" lon="2"/><node id="4" lat="0.5" lon="0.5"/><way id="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="motorway"/><tag k="ref" v="US 101"/><tag k="lanes" v="5"/></way><way id="2"><nd ref="2"/><nd ref="4"/><tag k="highway" v="motorway_link"/><tag k="oneway" v="yes"/><tag k="lanes" v="2"/></way></osm>'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'map.osm';p.write_text(xml);m,meta=import_boundary(p,(-1,-1,1,1))
  main=[e for e in m['edges'] if e['class']=='motorway'];ramps=[e for e in m['edges'] if e['class']=='ramp'];self.assertEqual(len(main),2);self.assertEqual([e['lanes'] for e in main],[5,5]);self.assertEqual(ramps[0]['lanes'],2)
  self.assertEqual(main[0]['to'],ramps[0]['from']);self.assertEqual(main[1]['from'],ramps[0]['from'])
  self.assertEqual(m['nodes'][main[0]['from']]['lon'],-1);self.assertGreater(m['nodes'][main[0]['from']]['demand_per_s'],0)
  self.assertEqual(m['nodes'][main[1]['to']]['lon'],1);self.assertGreater(m['nodes'][main[1]['to']]['sink_weight'],0)
 def test_clip_does_not_keep_roads_outside_box(self):
  self.assertIsNone(clip((-2,2),(2,2),(-1,-1,1,1)))
  self.assertEqual(clip((-2,0),(2,0),(-1,-1,1,1)),(.25,.75))
if __name__=='__main__':unittest.main()
