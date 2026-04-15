tell application "Safari"
    set output to ""
    set windowCount to count of windows
    
    repeat with w from 1 to windowCount
        set windowTitle to name of window w
        set output to output & "=== " & windowTitle & " ===" & linefeed
        
        set windowTabs to tabs of window w
        set tabIndex to 1
        
        repeat with t in windowTabs
            set tabName to name of t
            set tabURL to URL of t
            set output to output & "  Tab " & tabIndex & ": " & tabName & linefeed
            set output to output & "         " & tabURL & linefeed & linefeed
            set tabIndex to tabIndex + 1
        end repeat
        
        set output to output & linefeed
    end repeat
    
    return output
end tell
