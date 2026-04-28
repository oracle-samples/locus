# Locus — three agents collaborate on a Tokyo trip plan (real services)
#
# The Playwright-rendered intro + scenes (logo + problem + architecture)
# are concatenated separately. This tape captures only the terminal:
#   1. nvim — the program first.
#   2. python — the live run with streaming + human consent.

Output trip_team_run.gif
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

# --- Code reveal in nvim --------------------------------------------------
Type `nvim -R -c "set hlsearch" -c "let @/='@tool\|idempotent\|input(\|Agent(\|search_food\|search_culture\|book_restaurant\|email_itinerary'" /Users/federico.kamelhar/Projects/locus/examples/demos/trip_team/trip_team.py`
Enter
Sleep 3500ms
PageDown
Sleep 7000ms
PageDown
Sleep 7000ms
PageDown
Sleep 7000ms
Type ":q"
Enter
Sleep 400ms
Type "clear"
Enter
Sleep 200ms

# --- Live run -------------------------------------------------------------
Type "python /Users/federico.kamelhar/Projects/locus/examples/demos/trip_team/trip_team.py"
Enter
Sleep 70000ms

# Approval prompt — type y.
Type "y"
Enter

Sleep 24000ms
