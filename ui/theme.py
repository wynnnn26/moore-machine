"""Theme constants (fonts, button colours, help text) and light/dark behaviour."""

import customtkinter as ctk
from tkinter import ttk



ctk.set_appearance_mode("light")  # the diagram canvas and tables are light, so keep the whole window light
ctk.set_default_color_theme("blue")

# font hierarchy - every label picks from these five, so headings and captions stay consistent
F_H1 = ("Arial", 17, "bold")   # dialog titles
F_H2 = ("Arial", 15, "bold")   # panel / section titles
F_H3 = ("Arial", 12, "bold")   # field labels, buttons, emphasised values
F_BODY = ("Arial", 12)         # running text
F_CAP = ("Arial", 11)          # captions, hints, column headers

FONT_B = ("Arial", 12, "bold")


STYLES = {  # button colours: (normal, hover)
    "go": ("#2e7d32", "#1b5e20"), "warn": ("#ef6c00", "#e65100"),
    "danger": ("#c62828", "#8e0000"), "plain": ("#607d8b", "#455a64"),
}
HELP_WHAT = ("WHAT IS A MOORE MACHINE?\n"
             "A small machine that sits in one state at a time. Whatever state it is sitting in is\n"
             "what it prints. The input NEVER picks the output - the input only decides which state\n"
             "you move to next.\n"
             "\n"
             "        [ state: prints 0 ] --(input 1)--> [ state: prints 1 ]\n"
             "\n"
             "Like a lift: where you are decides what you see, the button only moves you.\n"
             "\n")

HELP_STEPS = ("HOW TO USE IT - 7 steps\n"
              "Create -> Connect -> Visualize -> Enter Input -> Step/Run -> Understand Output\n"
              "\n"
              "1. CREATE STATES. Type a name (q0) and an output (0 or 1), then press Add State.\n"
              "2. EVERY STATE NEEDS AN OUTPUT. In a Moore machine the output belongs to the state itself.\n"
              "3. SET THE INITIAL STATE. Click a state in the list, then press Set as Initial State (green arrow).\n"
              "4. CONNECT THEM. Pick From, type ONE input symbol, pick To, then press Add Transition.\n"
              "5. ENTER AN INPUT STRING such as 10110 in the Input string box.\n"
              "6. PRESS STEP for exactly one symbol, or RUN to play the whole string (PAUSE stops, RESET "
              "restarts only the simulation). The machine starts in the start state and shows its output "
              "before reading anything.\n"
              "7. WATCH THE OUTPUT. Follow the highlighted state in the diagram, the Simulation Results, and the "
              "table, which fills in by itself.\n"
              "\n"
              "THE MOORE RULE: read a symbol -> follow the arrow -> land in a new state -> show THAT state's output. "
              "The output always comes from the state you arrive in, never from the input.\n"
              "\n"
              "CHECK YOUR WORK. Type what you expect into 'Expected output' and run the machine - the line under it "
              "says whether it matches, and if not, where the first difference is.\n"
              "\n"
              "TIPS\n"
              "- Press Enter in the Name, Output or Input string box to act quickly.\n"
              "- Click any row in a list to load it into the boxes for editing.\n"
              "- Drag a state in the diagram to move it. Use Zoom In / Zoom Out / Fit Diagram to resize.\n"
              "- Auto Build (top of the Machine Editor) works out the states, their outputs and every\n"
              "  transition from an input string and the output it should print. Press Build, then\n"
              "  rename the states if you like.\n"
              "- Reset Simulation keeps your machine. Clear Machine deletes it (and always asks first).")


class ThemeMixin:
    """light / dark, and repainting for it."""

    # ----- light / dark -----
    def dark(self):
        return ctk.get_appearance_mode() == "Dark"

    def toggle_theme(self, *_):
        ctk.set_appearance_mode("light" if self.dark() else "dark")
        self.apply_theme()

    def apply_theme(self):
        dk = self.dark()
        self.cv.configure(highlightbackground="#3a3a3a" if dk else "#cfd8dc")
        sty = ttk.Style()
        sty.configure("Treeview", background="#2b2b2b" if dk else "white",
                      fieldbackground="#2b2b2b" if dk else "white",
                      foreground="#e0e0e0" if dk else "black")
        sty.configure("Treeview.Heading", background="#3a3a3a" if dk else "#e8eef4",
                      foreground="#e0e0e0" if dk else "black")
        sty.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])
        self.table.tag_configure("latest", background="#6d4c00" if dk else "#ffe082")
        self.draw()

    # ----- diagram view: zoom + drag -----

