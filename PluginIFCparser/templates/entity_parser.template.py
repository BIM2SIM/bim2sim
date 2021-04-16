{% macro getattr(x, n) %}{{ x[n] }}{% endmacro %}
{% macro def_attr(p) %}'{{ p.name }}': self.{{ p.name }}{% endmacro %}
{% set attrs = clauses["DECLARATION"] %}
{% if sschema %}
{% set sschema = sschema %}
{% else %}
{% set sschema = {} %}
{% endif %}
{% set class_name = name %}

class {{ class_name }}({{ parent }}):
    """{{class_name}}"""

    {% if supertype_of != None %}
    ifc_type = {{ supertype_of.strip('ONEOF ').replace(',', '').replace('(', '').replace(')', '').split() + [defname] }}
    {% else %}
    ifc_type = "{{defname}}"
    {% endif %}
    {% if sschema['predefined_type'] %}
    predefined_type = {{sschema['predefined_type']}}
    {% endif %}
    {% if defspec %}
    predefined_types = {{defspec}}
    {% endif %}
    {% if sschema['conditions'] %}

    conditions = [
        {% for condition in sschema['conditions'] %}
        {{condition}}
        {% endfor %}
        ]
    {% endif %}

    pattern_ifc_type = [
        {% if sschema['pattern'] %}
        {% for pattern in sschema['pattern'] %}
        re.compile('{{pattern}}', flags=re.IGNORECASE),
        {% endfor %}
        {% endif %}
    ]

    {% if functions %}
    {% for func in functions%}
{{func}}
    {% endfor %}
    {% endif %}
    {% if sschema['attributes'] %}
    {% for attr in sschema['attributes']%}
    {{attr}} = attribute.Attribute(
    {% for attr_info in sschema['attributes'][attr]%}
        {{attr_info}}
    {% endfor %}
    )
    {% endfor %}

    {% endif %}
{% if sschema['legacy'] %}
{% for sub_element, code in sschema['legacy'].items()%}

class {{sub_element}}({{class_name}}):
    """{{sub_element}}"""
    {{code}}

{% endfor %}
{% endif %}