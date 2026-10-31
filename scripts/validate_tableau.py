"""Optional structural check against Tableau's published 2026.1 workbook schema."""

import argparse
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
XS = "{http://www.w3.org/2001/XMLSchema}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args()
    workbook = etree.parse(str(ROOT / "tableau/Music-Promotion-Experiment-Lab.twb"))
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
    for imported in document.findall(XS + "import"):
        suffix = "user.xsd" if "tableau" in imported.get("namespace", "") else "xml.xsd"
        imported.set("schemaLocation", suffix)
    schema = etree.XMLSchema(document)
    if not schema.validate(workbook):
        raise ValueError("\n".join(str(error) for error in schema.error_log))
    print("PASS: Tableau core workbook schema. Native rendering remains a separate check.")


if __name__ == "__main__":
    main()
