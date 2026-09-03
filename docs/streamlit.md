# In Streamlit

```python
import jsonplot.streamlit as jps

jps.st_plot(spec, df)          # draws it, or shows the errors
png = jps.png(spec, df)        # bytes, for st.download_button or a cache
```

`st_plot` returns `[]` when it drew, and the list of `SpecError` when it could
not. In an app, a contract the data does not support should show what is wrong,
not take the page down.

```python
jps.st_plot(spec, df, target=col2, theme="dark", errors="raise")
```

## Why the adapter exists

The host has three constraints the library's defaults get wrong, and all three
live at the boundary:

| Constraint | What the adapter does |
| --- | --- |
| the script reruns on every interaction | closes the figure; `png()` returns bytes, which `st.cache_data` can memoize |
| the app has its own appearance | resolves `theme="auto"` from `st.context.theme`, unless the contract chose a theme |
| a traceback kills the page | catches `SpecErrorGroup` and renders the errors as an element, returning them to the caller |

It renders PNG bytes and hands them to `st.image` rather than calling
`st.pyplot`, which fixes its own dpi and deprecates `savefig` arguments — the
contract's `dpi` and a transparent surface would both be lost.

Neither the CLI nor this adapter is imported by the core, so `import jsonplot`
never imports Streamlit and the dependency stays optional.

## The example app

```bash
uv run streamlit run examples/streamlit_app.py
```

A live contract editor: presets on the left, the chart or the errors on the
right, and an expander showing the contract exactly as a model receives it.
