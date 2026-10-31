import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_workbook_declares_the_grammar_it_uses():
    source = ROOT / "tableau/Music-Promotion-Experiment-Lab.twb"
    root = ET.parse(source).getroot()
    assert root.get("version") == root.get("original-version") == "18.1"
    manifest = root.find("document-format-change-manifest")
    assert manifest.find("ManifestByVersion") is None
    assert manifest.find("SheetIdentifierTracking") is not None
    assert manifest.find("SortTagCleanup") is not None
    assert root.find("explain-data") is None
    assert len(root.findall("worksheets/worksheet")) == 4
    assert root.find("dashboards/dashboard").get("name") == "Promotion Quality Review"
    for layouts in root.findall("dashboards/dashboard/devicelayouts"):
        assert layouts.find("devicelayout") is not None


def test_tableau_package_contains_current_xml_and_its_referenced_extract():
    source = ROOT / "tableau/Music-Promotion-Experiment-Lab.twb"
    with ZipFile(source.with_suffix(".twbx")) as package:
        assert package.testzip() is None
        assert package.read(source.name) == source.read_bytes()
        root = ET.fromstring(package.read(source.name))
        extract = root.find("datasources/datasource/connection").get("dbname")
        assert len(package.read(extract)) > 0
