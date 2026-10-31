"""Check the feature contract; optionally validate a version-based workbook's XSD."""

import argparse
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
XS = "{http://www.w3.org/2001/XMLSchema}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path)
    args = parser.parse_args()
    workbook = etree.parse(str(ROOT / "tableau/Music-Promotion-Experiment-Lab.twb"))
    root = workbook.getroot()
    if root.get("version") == root.get("original-version") == "18.1":
        manifest = root.find("document-format-change-manifest")
        required = {"SheetIdentifierTracking", "SortTagCleanup", "WindowsPersistSimpleIdentifiers"}
        if manifest is None or not required.issubset({node.tag for node in manifest}):
            raise ValueError("Missing explicit compatibility feature declarations.")
        if manifest.find("ManifestByVersion") is not None or root.find("explain-data") is not None:
            raise ValueError("Mixed explicit-feature and version-based workbook grammars.")
        print(
            "PASS: explicit-feature compatibility contract. "
            "The 2026 XSD is not its runtime grammar; native Tableau loading is required."
        )
        return
    if args.schema is None:
        parser.error("--schema is required for a version-based workbook.")
    # The published XSD omits locations for these two foreign imports. Our workbook
    # uses neither namespace, so supply declarations only to compile its core XSD.
    for node in workbook.iter():
        if any(key.startswith("{") for key in node.attrib):
            raise ValueError(
                "Foreign-attribute schema stubs cannot validate namespaced attributes."
            )

    class Imports(etree.Resolver):
        def resolve(self, url, public_id, context):
            if url.endswith("user.xsd"):
                return self.resolve_string(
                    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                    'targetNamespace="http://www.tableausoftware.com/xml/user">'
                    '<xs:attributeGroup name="UserAttributes-AG"/></xs:schema>',
                    context,
                )
            if url.endswith("xml.xsd"):
                return self.resolve_string(
                    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                    'targetNamespace="http://www.w3.org/XML/1998/namespace">'
                    '<xs:attribute name="base" type="xs:anyURI"/></xs:schema>',
                    context,
                )
            return None

    xml_parser = etree.XMLParser(no_network=True)
    xml_parser.resolvers.add(Imports())
    document = etree.parse(str(args.schema), xml_parser)
    release = document.getroot().get("version", "").split(".")[:2]
    expected = ".".join([release[0][-2:], release[1]])
    root = workbook.getroot()
    if root.get("version") != expected or root.get("original-version") != expected:
        raise ValueError(f"Workbook versions must be {expected} for this schema.")
    if root.find("document-format-change-manifest/ManifestByVersion") is None:
        raise ValueError("The version-based workbook manifest is required.")
    for imported in document.findall(XS + "import"):
        suffix = "user.xsd" if "tableau" in imported.get("namespace", "") else "xml.xsd"
        imported.set("schemaLocation", suffix)
    schema = etree.XMLSchema(document)
    if not schema.validate(workbook):
        raise ValueError("\n".join(str(error) for error in schema.error_log))
    print("PASS: Tableau core workbook schema. Native rendering remains a separate check.")


if __name__ == "__main__":
    main()
