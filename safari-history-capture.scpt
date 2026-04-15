tell application "Safari"
    activate
end tell

delay 0.5

tell application "System Events"
    keystroke "y" using command down
end tell

delay 1

tell application "System Events"
    tell process "Safari"
        set frontWindow to front window
        set windowBounds to bounds of frontWindow
        set {x, y, x2, y2} to windowBounds
        set windowWidth to x2 - x
        set windowHeight to y2 - y
    end tell
end tell

return (x & "," & y & "," & windowWidth & "," & windowHeight)
