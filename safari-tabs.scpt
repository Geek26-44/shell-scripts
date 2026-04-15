tell application "Safari"
    set tabInfo to {}
    set windowCount to count of windows
    
    repeat with w from 1 to windowCount
        set windowTabs to tabs of window w
        repeat with t in windowTabs
            set end of tabInfo to "Window " & w & " | " & (name of t) & " | " & (URL of t)
        end repeat
    end repeat
    
    set AppleScript's text item delimiters to linefeed
    set output to tabInfo as text
    set AppleScript's text item delimiters to ""
    
    return output
end tell
