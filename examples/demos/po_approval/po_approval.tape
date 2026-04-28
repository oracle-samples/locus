# Locus — three agents collaborate on a vendor PO approval (real services)
#
# The Playwright-rendered intro + scenes (logo, problem, workflow) are
# concatenated separately. This tape captures only the live run.

Output po_approval_run.gif
Set FontSize 14
Set Width 1500
Set Height 800
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 16ms
Set Shell "bash"

Hide
Type "cd $(mktemp -d) && clear" Enter
Sleep 200ms
Show

# Live run only — no nvim, no code walkthrough.
Type "python /Users/federico.kamelhar/Projects/locus/examples/demos/po_approval/po_approval.py"
Enter
Sleep 70000ms

# Approval prompt — type y.
Type "y"
Enter

Sleep 24000ms
