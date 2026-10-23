import unittest
from unittest.mock import patch
from io import BytesIO
from openpyxl import Workbook
from streamlit.testing.v1 import AppTest
from bike_data import load_stations,bundled_stations

class MapAutoloadTests(unittest.TestCase):
    def test_merged_official_header(self):
        book=Workbook();sheet=book.active
        sheet.append(['대여소\n번호','보관소(대여소)명','소재지'])
        sheet.append([None,None,'자치구','상세주소','위도','경도'])
        sheet.append([1,'테스트대여소','중구','주소',37.56,127.0])
        buffer=BytesIO();book.save(buffer)
        self.assertEqual(load_stations(buffer.getvalue(),'official.xlsx')['stations'][0]['name'],'테스트대여소')

    def test_real_default_bikes_are_available(self):
        data=bundled_stations()
        self.assertEqual(len(data['stations']),2789)
        self.assertIn('2026-06',data['origin'])

    def test_population_autoload_without_rent_selection(self):
        point={'latitude':37.56,'longitude':127.,'legal_code':'1114016200','name':'신당동'}
        resident={'code':'1114016200','month':'202609','total':100,'ages':{20:20,30:30,60:10}}
        source='from map_data_view import map_region\np,m=map_region()'
        with patch('map_data_view.locate',return_value=point),patch('map_data_view.population_snapshot',return_value={}),patch('map_data_view.population',return_value=resident) as pop:
            app=AppTest.from_string(source,default_timeout=20).run()
            self.assertEqual(len(app.exception),0)
            pop.assert_called_once()
            self.assertTrue(any('20대 20.0%' in c.value for c in app.caption))
            app.run();self.assertEqual(pop.call_count,1)
