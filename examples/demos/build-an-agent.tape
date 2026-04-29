# Locus — three tools, idempotent write, real ReAct loop, on screen.
#
# Compile:  vhs build-an-agent.tape  →  build-an-agent.gif
#
# Pre-reqs to recompile:
#   pip install locus[oci]
#   ~/.oci/config with at least one GenAI-enabled profile
#   export OCI_PROFILE=<your-profile>
#   brew install bat   # syntax-highlighted code reveal

Output build-an-agent.gif
Set FontSize 14
Set Width 1300
Set Height 1000
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 8ms
Set Shell "bash"

# --- setup (hidden) ----------------------------------------------------------
Hide
Type "cd /tmp/locus-gifs/editor-demo" Enter
Type "export PATH=/Users/federico.kamelhar/Projects/locus/.venv/bin:$PATH" Enter
Type "export OCI_PROFILE=LUIGI_FRA_API" Enter
Type "clear" Enter
Sleep 300ms
Show

# --- 1) reveal the program ---------------------------------------------------
# bat shows the file syntax-highlighted in one shot — no character-by-char
# typing. The viewer sees the whole module at once.
Type "bat --paging=never --style=numbers,header --color=always agent.py"
Enter
Sleep 7500ms

# --- 2) run it ---------------------------------------------------------------
Type "python agent.py"
Enter
Sleep 11000ms

Sleep 2500ms
