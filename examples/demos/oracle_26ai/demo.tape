# Locus — Oracle 26ai end-to-end demo (real services, narrated)
#
# Three scenes:
#   1. View the skill in nvim (key terms highlighted).
#   2. Walk the agent program in nvim (key terms highlighted, slow pages).
#   3. Run it. Watch the chain of thought, the live Oracle 26ai rows,
#      Reflexion, the idempotent email, and the final reply.

Output demo.gif
Set FontSize 18
Set Width 1500
Set Height 1280
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 18ms
Set Shell "bash"

Hide
Type "cd $(mktemp -d) && clear" Enter
Sleep 200ms
Show

# --- Scene 1: skill in nvim with keyword highlighting ----------------------
Type `nvim -R -c "set hlsearch" -c "let @/='search_corpus\|email_report\|idempotent\|Skill\|Loop'" /Users/federico.kamelhar/Projects/locus/examples/demos/oracle_26ai/skills/researcher/SKILL.md`
Enter
Sleep 14000ms
Type ":q"
Enter
Sleep 400ms

# --- Scene 2: agent program in nvim with keyword highlighting --------------
Type `nvim -R -c "set hlsearch" -c "let @/='@tool\|idempotent\|reflexion\|skills\|search_corpus\|Agent\|OracleVectorStore\|OCIBucketBackend\|ThinkEvent'" /Users/federico.kamelhar/Projects/locus/examples/demos/oracle_26ai/demo.py`
Enter
Sleep 3000ms
PageDown
Sleep 9000ms
PageDown
Sleep 9000ms
PageDown
Sleep 9000ms
Type ":q"
Enter
Sleep 400ms

# --- Scene 3: live run -----------------------------------------------------
Type "python /Users/federico.kamelhar/Projects/locus/examples/demos/oracle_26ai/demo.py"
Enter
Sleep 28000ms

Sleep 6000ms
