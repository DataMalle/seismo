{#- Miljöseparation: prod ger seismo_<lager>, andra miljöer seismo_<miljö>_<lager>. Samma regel som pipeline/seismo_lib.py. -#}
{% macro schema_prefix() -%}
    {%- set env = var('env', target.name) -%}
    {{- 'seismo' if env == 'prod' else 'seismo_' ~ env -}}
{%- endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set layer = (custom_schema_name | trim) if custom_schema_name is not none else 'silver' -%}
    {{- schema_prefix() }}_{{ layer -}}
{%- endmacro %}
