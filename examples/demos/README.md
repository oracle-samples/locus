# Demos

Short visual walkthroughs of locus.

## `build-an-agent.gif`

![Build an agent in your editor, then run it.](build-an-agent.gif)

What the recording shows, end-to-end:

1. `bat` reveals a 50-line program — three tools (one of them
   `@tool(idempotent=True)`) and an `Agent` against `oci:openai.gpt-5.5`.
2. `python agent.py` runs the program against OCI GenAI's V1 transport.
3. The output prints the model's reply, every tool that fired, and the
   iteration count — that's the typed `RunResult` exposed by `run_sync`.

The actual program is committed alongside as
[`agent_quickstart.py`](agent_quickstart.py).

### Regenerating the GIF

The recording was made with [VHS](https://github.com/charmbracelet/vhs)
and uses [`bat`](https://github.com/sharkdp/bat) for the syntax-highlighted
reveal:

```bash
brew install vhs bat
cd examples/demos
export OCI_PROFILE=<your-oci-config-profile>
vhs build-an-agent.tape
```

`build-an-agent.tape` is the source script — feel free to fork it for your own
walkthrough.
