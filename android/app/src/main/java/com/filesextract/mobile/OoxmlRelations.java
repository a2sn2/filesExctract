package com.filesextract.mobile;

import org.w3c.dom.Document;
import org.w3c.dom.Element;

import java.util.LinkedHashMap;
import java.util.Map;

final class OoxmlRelations {
    static final class Rel {
        String id;
        String type;
        String target;
        String targetMode;
    }

    private OoxmlRelations() {}

    static Map<String, Rel> parse(byte[] xml) throws Exception {
        Map<String, Rel> out = new LinkedHashMap<>();
        if (xml == null) return out;
        Document doc = XmlUtil.parse(xml);
        for (Element e : XmlUtil.descendants(doc.getDocumentElement(), "Relationship")) {
            Rel r = new Rel();
            r.id = XmlUtil.attr(e, "Id");
            r.type = XmlUtil.attr(e, "Type");
            r.target = XmlUtil.attr(e, "Target");
            r.targetMode = XmlUtil.attr(e, "TargetMode");
            out.put(r.id, r);
        }
        return out;
    }
}
