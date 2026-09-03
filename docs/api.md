# Python API

Everything below is importable from the package root: `import jsonplot as jp`.

## Drawing and checking

::: jsonplot.api
    options:
      members: [plot, validate, inspect, build_frame, describe_dataframe, supported, resolve]

## Writing the prompt

::: jsonplot.spec.briefing
    options:
      members: [contract, sections, vocabulary, coverage]

::: jsonplot.spec.schema
    options:
      members: [json_schema, tool_definition, capability_summary]

## The agent surface

::: jsonplot.agent
    options:
      members: [context, columns, repair, RepairResult, errors_as_json]

## Errors

::: jsonplot.binding.errors
    options:
      members: [SpecError, SpecErrorGroup, Code]

## The contract, as types

::: jsonplot.spec.models
    options:
      members: [Spec, Encoding, Channel, DataOps, Filter, Sort, Style, Output]
      show_source: false

## Streamlit

::: jsonplot.streamlit
    options:
      members: [st_plot, png, active_theme, show_errors]
