import unittest
from bike_data import load_stations
from geo import distance_m, stations_within
from map_view import build_map_html

class BikeTests(unittest.TestCase):
    def test_official_header_invalid_and_duplicate_rows(self):
        text = "기준일,2026-10-22\n대여소 번호,보관소(대여소)명,위도,경도\n1,시청,37.5665,126.978\n1,시청,37.5665,126.978\n2,오류,nan,127\n"
        result = load_stations(text.encode("utf-8-sig"), "official.csv")
        self.assertEqual(len(result["stations"]),1)
        self.assertEqual(result["skipped"],2)

    def test_cp949_and_radius(self):
        text = "대여소명,위도,경도\n시청,37.5665,126.978\n멀리,37.7,127.1"
        result = load_stations(text.encode("cp949"),"stations.csv")
        nearby = stations_within(result["stations"],37.5665,126.978,1)
        self.assertEqual([x["name"] for x in nearby],["시청"])
        self.assertAlmostEqual(distance_m(0,0,0,1),111195,delta=10)

    def test_xlsx(self):
        from openpyxl import Workbook
        from io import BytesIO
        book=Workbook(); sheet=book.active
        sheet.append(["대여소명","위도","경도"])
        sheet.append(["시청",37.5665,126.978])
        stream=BytesIO(); book.save(stream)
        self.assertEqual(len(load_stations(stream.getvalue(),"stations.xlsx")["stations"]),1)

    def test_reject_unrecognized_and_non_seoul(self):
        for text in ["name,price\na,1", "대여소명,위도,경도\n오류,0,0"]:
            with self.assertRaises(ValueError):
                load_stations(text.encode(),"bad.csv")

    def test_uploaded_label_cannot_escape_script(self):
        html=build_map_html("key",stations=[{"name":"</script><script>alert(1)</script>"}])
        self.assertNotIn("</script><script>alert",html)

if __name__ == "__main__":
    unittest.main()
