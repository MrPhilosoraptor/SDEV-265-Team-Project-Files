StudyQuest CHANGELOG | Current Version: 3.1

============================================================================

Version 3.1
macOS bug fixes

The save file was moved to the following directory:
    C -> Users -> <your-username> -> .studyquest -> studyquest_save.txt (Windows)
    /Users/<your-username>/.studyquest/studyquest_save.txt (macOS)

Fixed the macOS bug where the save file is never written
    due to macOS's security restrictions (Errno 30 read-only file system)
    
============================================================================

Version 3.0
Delete Profile button, macOS bug fix, another security feature and small cosmetic changes

Delete Profile Button added.

New file the program works with:
    studyquest_save.txt.bak - a save file created in case profile deletion fails
    the program will restore the progress from that file in such case
  
"Tasks (pending, completed and total goals)" cosmetic change:
    It now look as follows: Pending: x | Completed: y | Total Goals: z
    
Search label was moved next to the search bar

Fixed the macOS bug where the main program always launched in behind (testing in progress)

============================================================================

Version 2.0
UI Redesign Update



**Added**

  Unified header layout combining app name and player info
  
  Dedicated header styles for stronger hierarchy
  
  Card-style stat panels for Level, XP, and Tasks
  
  Difficulty bar column in goal list
  
  Color-coded difficulty indicators
  
  XP progress strip with centered progress bar
  
  Styled action button theme for consistent rendering
  
  Filter styling aligned with panel background
  
  Improved details panel layout and spacing

**Changed**

  Increased app title size and weight
  
  Updated profile display format to: Player {name} | Level {level}
  
  Simplified status text in goal list
  
  Moved detailed task and habit information to the Details panel
  
  Adjusted column widths for improved readability
  
  Refined padding and spacing across all panels
  
  Standardized fonts and color palette
  
  Removed horizontal scrollbar in goal list
  
  Improved alignment of search and filter controls

**Fixed**

  Button text not visible on Windows themes
  
  Inconsistent background rendering in header
  
  Misaligned filter row spacing
  
  Extra borders causing boxed header appearance
  
  Visual clutter in list view
  
  UI System Improvements
  
  Centralized color theme
  
  Consistent panel borders
  
  Improved contrast for readability
  
  Cleaner layout separation between major sections
  
  Fixed window dimensions for layout stability
**
No Backend Changes**

**The following systems remain unchanged:**
  
  Player logic
  
  XP calculation and leveling
  
  Task completion logic
  
  Habit streak logic
  
  Save and load system
  
  GoalManager behavior
