package com.filesextract.mobile;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.io.ByteArrayInputStream;
import java.util.ArrayList;
import java.util.List;
import javax.xml.parsers.DocumentBuilderFactory;

final class XmlUtil {
    private XmlUtil() {}

    static Document parse(byte[] xml) throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setNamespaceAware(true);
        trySet(f, "http://apache.org/xml/features/disallow-doctype-decl", true);
        trySet(f, "http://xml.org/sax/features/external-general-entities", false);
        trySet(f, "http://xml.org/sax/features/external-parameter-entities", false);
        trySet(f, "http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        f.setExpandEntityReferences(false);
        return f.newDocumentBuilder().parse(new ByteArrayInputStream(xml));
    }

    private static void trySet(DocumentBuilderFactory f, String feature, boolean value) {
        try { f.setFeature(feature, value); } catch (Exception ignored) {}
    }

    static String local(Node n) {
        String v = n.getLocalName();
        if (v != null) return v;
        String name = n.getNodeName();
        int colon = name.indexOf(':');
        return colon >= 0 ? name.substring(colon + 1) : name;
    }

    static String attr(Element e, String localName) {
        if (e.hasAttribute(localName)) return e.getAttribute(localName);
        for (int i = 0; i < e.getAttributes().getLength(); i++) {
            Node a = e.getAttributes().item(i);
            if (localName.equals(local(a))) return a.getNodeValue();
        }
        return "";
    }

    static List<Element> children(Element parent, String localName) {
        List<Element> out = new ArrayList<>();
        NodeList nodes = parent.getChildNodes();
        for (int i = 0; i < nodes.getLength(); i++) {
            Node n = nodes.item(i);
            if (n instanceof Element && localName.equals(local(n))) out.add((Element) n);
        }
        return out;
    }

    static List<Element> descendants(Element parent, String localName) {
        List<Element> out = new ArrayList<>();
        walk(parent, localName, out);
        return out;
    }

    private static void walk(Node node, String localName, List<Element> out) {
        NodeList nodes = node.getChildNodes();
        for (int i = 0; i < nodes.getLength(); i++) {
            Node n = nodes.item(i);
            if (n instanceof Element) {
                if (localName.equals(local(n))) out.add((Element) n);
                walk(n, localName, out);
            }
        }
    }

    static String descendantText(Element parent, String localName) {
        StringBuilder sb = new StringBuilder();
        for (Element e : descendants(parent, localName)) {
            if (sb.length() > 0) sb.append(' ');
            sb.append(e.getTextContent());
        }
        return sb.toString().trim();
    }

    static Element firstChild(Element parent, String localName) {
        for (Element e : children(parent, localName)) return e;
        return null;
    }
}
