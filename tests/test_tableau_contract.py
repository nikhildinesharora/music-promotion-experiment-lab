import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _canonical_xml(xml: bytes) -> str:
    # Git normalizes the standalone XML, but not the copy inside the ZIP archive.
    return ET.canonicalize(xml_data=xml.decode("utf-8-sig"))


def test_workbook_comparison_accepts_platform_line_endings():
    xml = b'<?xml version="1.0"?>\n<workbook version="18.1">\n<worksheet />\n</workbook>\n'
    assert _canonical_xml(xml) == _canonical_xml(xml.replace(b"\n", b"\r\n"))


@pytest.mark.parametrize(
    "changed",
    [
        b'<workbook version="26.1"><worksheet /></workbook>',
        b'<workbook version="18.1"><dashboard /></workbook>',
        b'<workbook version="18.1"><worksheet>changed</worksheet></workbook>',
    ],
)
def test_workbook_comparison_detects_content_changes(changed):
    original = b'<workbook version="18.1"><worksheet /></workbook>'
    assert _canonical_xml(original) != _canonical_xml(changed)


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
        assert _canonical_xml(package.read(source.name)) == _canonical_xml(source.read_bytes())
        root = ET.fromstring(package.read(source.name))
        extract = root.find("datasources/datasource/connection").get("dbname")
        assert len(package.read(extract)) > 0
