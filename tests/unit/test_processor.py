from rtve_rag.ingestion.processor import parse_subtitles
def test_parser():
 assert parse_subtitles('00:00:01.000 --> 00:00:02.000\nHola\n')[0].start_ms==1000
