"""Regression tests for the final 1.10 review: recovery, feedback and scenes."""
import io
import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw
from brain.storage import Memory
from brain.vision import analyze_direction, compose_learned_scene, feedback_signature, _pixels


class ReviewTests(unittest.TestCase):
    def test_conflicting_orientation_examples_are_indeterminate(self):
        reference=Image.new('RGB',(160,160),'white')
        ImageDraw.Draw(reference).polygon([(65,30),(95,30),(95,80),(118,80),(80,125),(42,80),(65,80)],fill='black')
        result=analyze_direction(reference,[reference,reference.rotate(180)])
        self.assertEqual(result['rotation'],'indeterminada')

    def test_restore_point_and_failed_import_preserve_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory=Memory(Path(tmp)/'laura.db')
            memory.remember('Nicolas','cidade','Campinas')
            memory.save_restore_point()
            bad=memory.export_data('Nicolas')
            bad['facts']=[{'key':'cidade','value':'Outra cidade'}]
            bad['generation_feedback']=[{'signature':'[]','rating':'good'}]
            with self.assertRaises(ValueError): memory.import_data('Nicolas',bad)
            self.assertEqual(memory.recall('Nicolas','cidade'),'Campinas')
            memory.remember('Nicolas','cidade','Valinhos')
            previous=Memory(memory.restore_point_path)
            self.assertEqual(previous.recall('Nicolas','cidade'),'Campinas')
            previous.close();memory.close()

    def test_undo_rating_preserves_other_users_and_survives_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory=Memory(Path(tmp)/'laura.db')
            signature=feedback_signature(Image.new('RGB',(24,24),'red'))
            for user in ('Nicolas','Outro'):
                memory.rate_generation(user,'same-id','learned:bola','good',signature)
            self.assertTrue(memory.remove_generation_rating('Nicolas','same-id'))
            self.assertFalse(memory.remove_generation_rating('Nicolas','same-id'))
            self.assertEqual(memory.feedback_counts('Outro','learned:bola')['good'],1)
            self.assertEqual(memory.export_data('Nicolas')['generation_feedback'],[])
            memory.close()

    def test_scene_position_and_upside_down_follow_description(self):
        reference=Image.new('RGB',(160,160),'white')
        ImageDraw.Draw(reference).polygon([(65,25),(95,25),(95,85),(125,85),(80,135),(35,85),(65,85)],fill=(220,20,20))
        def red_bounds(image):
            mask=Image.new('L',image.size)
            mask.putdata([255 if r>140 and r>g*2 and r>b*2 else 0 for r,g,b in _pixels(image)])
            return mask.getbbox(),mask
        with patch('brain.vision.generate',side_effect=lambda prompt,w,h,seed:Image.new('RGB',(w,h),(20,100,20))):
            upper=compose_learned_scene('seta na floresta em cima à esquerda',[],[reference]*3,384,384,'same',quality='rapida')
            lower=compose_learned_scene('seta na floresta embaixo à direita de ponta-cabeça',[],[reference]*3,384,384,'same',quality='rapida')
        box1,m1=red_bounds(upper);box2,m2=red_bounds(lower)
        self.assertLess(box1[0],30);self.assertLess(box1[1],30)
        self.assertGreater(box2[2],350);self.assertGreater(box2[3],350)
        shape1=m1.crop(box1).resize((32,32));shape2=m2.crop(box2).resize((32,32))
        def diff(a,b):return sum(abs(x-y) for x,y in zip(_pixels(a),_pixels(b)))
        self.assertLess(diff(shape1.rotate(180),shape2),diff(shape1,shape2))


class WebReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('review_web',Path(__file__).parents[1]/'app_web.py')
        cls.web=importlib.util.module_from_spec(spec)
        with patch('brain.LauraEngine'):
            spec.loader.exec_module(cls.web)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=HTTPServer(('127.0.0.1',0),self.web.LauraHandler)
        self.ready=threading.Event()
        def serve():
            memory=Memory(Path(self.tmp.name)/'laura.db')
            memory.remember('Nicolas','original','preservar')
            self.web.laura=SimpleNamespace(memory=memory,retrain_classifier=lambda user:None)
            self.ready.set()
            self.server.serve_forever()
            memory.close()
        self.thread=threading.Thread(target=serve,daemon=True);self.thread.start();self.ready.wait()

    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close();self.tmp.cleanup()

    def call(self,path,payload=None,method=None):
        data=None if payload is None else json.dumps(payload).encode()
        request=urllib.request.Request('http://127.0.0.1:'+str(self.server.server_port)+path,data,
                                       {'Content-Type':'application/json'},method=method)
        try:response=urllib.request.urlopen(request,timeout=15)
        except urllib.error.HTTPError as error:response=error
        with response:return response.status,json.load(response)

    def test_import_creates_downloadable_previous_backup(self):
        status,backup=self.call('/api/export')
        backup['facts']=[{'key':'novo','value':'importado'}]
        status,result=self.call('/api/import',backup)
        self.assertEqual(status,200)
        status,previous=self.call('/api/export-previous-backup')
        self.assertEqual(status,200)
        self.assertEqual(previous['facts'][0]['key'],'original')
        status,current=self.call('/api/export')
        self.assertEqual(current['facts'][0]['key'],'novo')

    def test_invalid_json_shape_and_conflicting_subject_return_errors(self):
        self.assertEqual(self.call('/api/import',[])[0],400)
        status,result=self.call('/api/vision/generate',{'prompt':'cavalo na floresta','learned_label':'banana'})
        self.assertEqual(status,400)
        self.assertIn('não corresponde',result['error'])
        status,result=self.call('/api/vision/generate',{'prompt':'cavalo e gato na floresta'})
        self.assertEqual(status,400)

if __name__=='__main__':unittest.main()
